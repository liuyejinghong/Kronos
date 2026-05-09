"""Binance testnet paper-trading control plane."""
# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol
from urllib.parse import urlencode

import httpx

from kronos.agent.secrets import LocalSecretStore, SecretMaskedStatus

BINANCE_TESTNET_PROVIDER = "binance-testnet"
BINANCE_USDM_TESTNET_BASE_URL = "https://testnet.binancefuture.com"
BINANCE_MAINNET_BASE_URL = "https://fapi.binance.com"
DEFAULT_PAPER_REPORTS_PATH = Path("reports/paper")


class PaperTradingError(ValueError):
    """Raised when paper trading cannot safely continue."""


@dataclass(frozen=True)
class BinanceTestnetCredentials:
    api_key: str
    api_secret: str


@dataclass(frozen=True)
class PaperPreflightResult:
    ok: bool
    status: str
    message: str
    environment: str
    plan_path: Path | None
    report_path: Path
    masked_api_key: str | None = None
    blockers: tuple[str, ...] = ()

    def summary_lines(self) -> list[str]:
        lines = [
            "--- Paper Trading Preflight ---",
            f"状态: {self.status}",
            f"环境: {self.environment}",
            f"结论: {self.message}",
            f"report: {self.report_path}",
        ]
        if self.plan_path is not None:
            lines.append(f"plan: {self.plan_path}")
        if self.masked_api_key is not None:
            lines.append(f"api_key: {self.masked_api_key}")
        return lines


@dataclass(frozen=True)
class TestnetOrder:
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    status: str
    environment: str = "testnet"


@dataclass(frozen=True)
class TestnetFill:
    order_id: str
    trade_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    commission: float
    commission_asset: str
    fill_time: str
    environment: str = "testnet"


@dataclass(frozen=True)
class PaperRunResult:
    run_id: str
    status: str
    run_dir: Path
    order: TestnetOrder | None
    fill: TestnetFill | None
    report_path: Path
    status_path: Path

    def summary_lines(self) -> list[str]:
        lines = [
            "--- Testnet Paper Run ---",
            f"run_id: {self.run_id}",
            f"状态: {self.status}",
            "环境: testnet",
            f"report: {self.report_path}",
            f"status: {self.status_path}",
        ]
        if self.order is not None:
            lines.append(f"testnet_order_id: {self.order.order_id}")
            lines.append(f"order_status: {self.order.status}")
        return lines


class TestnetClient(Protocol):
    """Small client contract used by the paper runner."""

    def ping_account(self) -> dict[str, Any]:
        """Validate credentials and return a user-data response."""

    def ticker_price(self, symbol: str) -> float:
        """Return the latest testnet ticker price."""

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ) -> TestnetOrder:
        """Submit a Binance testnet market order."""

    def query_fill(self, *, symbol: str, order_id: str) -> TestnetFill | None:
        """Return fill evidence for a testnet order when available."""


class BinanceUSDMMockTestnetClient:
    """Deterministic testnet adapter for local verification and CI."""

    def __init__(self) -> None:
        self._orders: dict[str, TestnetOrder] = {}

    def ping_account(self) -> dict[str, Any]:
        return {"environment": "testnet", "canTrade": True}

    def ticker_price(self, symbol: str) -> float:
        return 50_000.0 if symbol.upper() == "BTCUSDT" else 1_000.0

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ) -> TestnetOrder:
        order = TestnetOrder(
            order_id="mock-testnet-order-1",
            client_order_id=client_order_id,
            symbol=symbol.upper(),
            side=side.upper(),
            order_type="MARKET",
            quantity=quantity,
            status="FILLED",
        )
        self._orders[order.order_id] = order
        return order

    def query_fill(self, *, symbol: str, order_id: str) -> TestnetFill | None:
        order = self._orders.get(order_id)
        quantity = order.quantity if order is not None else 0.001
        side = order.side if order is not None else "BUY"
        return TestnetFill(
            order_id=order_id,
            trade_id="mock-testnet-trade-1",
            symbol=symbol.upper(),
            side=side,
            price=50_000.0,
            quantity=quantity,
            commission=0.0,
            commission_asset="USDT",
            fill_time=datetime.now(UTC).isoformat(),
        )


class BinanceUSDMTestnetClient:
    """Minimal Binance USD-M Futures testnet REST client."""

    def __init__(
        self,
        credentials: BinanceTestnetCredentials,
        *,
        base_url: str = BINANCE_USDM_TESTNET_BASE_URL,
        timeout_seconds: float = 10.0,
    ) -> None:
        if base_url.rstrip("/") != BINANCE_USDM_TESTNET_BASE_URL:
            raise PaperTradingError("paper mode only supports Binance USD-M Futures testnet.")
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def ping_account(self) -> dict[str, Any]:
        return self._signed_request("GET", "/fapi/v2/account")

    def ticker_price(self, symbol: str) -> float:
        response = httpx.get(
            f"{self.base_url}/fapi/v1/ticker/price",
            params={"symbol": symbol.upper()},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        price = payload.get("price")
        if not isinstance(price, str):
            raise PaperTradingError("Binance testnet ticker response did not include a price.")
        return float(price)

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ) -> TestnetOrder:
        payload = self._signed_request(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol.upper(),
                "side": side.upper(),
                "type": "MARKET",
                "quantity": _format_quantity(quantity),
                "newClientOrderId": client_order_id,
                "newOrderRespType": "RESULT",
            },
        )
        return TestnetOrder(
            order_id=str(payload.get("orderId", "")),
            client_order_id=str(payload.get("clientOrderId") or client_order_id),
            symbol=str(payload.get("symbol") or symbol.upper()),
            side=str(payload.get("side") or side.upper()),
            order_type=str(payload.get("type") or "MARKET"),
            quantity=quantity,
            status=str(payload.get("status") or "UNKNOWN"),
        )

    def query_fill(self, *, symbol: str, order_id: str) -> TestnetFill | None:
        payload = self._signed_request_payload(
            "GET",
            "/fapi/v1/userTrades",
            {"symbol": symbol.upper(), "orderId": order_id, "limit": 20},
        )
        if not isinstance(payload, list):
            raise PaperTradingError("Binance testnet trade response was not a list.")
        trades = [item for item in payload if isinstance(item, dict)]
        if not trades:
            return None
        quantities = [abs(float(item.get("qty") or 0.0)) for item in trades]
        total_quantity = sum(quantities)
        notional = sum(
            abs(float(item.get("price") or 0.0)) * quantity
            for item, quantity in zip(trades, quantities, strict=True)
        )
        if total_quantity <= 0 or notional <= 0:
            return None
        commissions = [float(item.get("commission") or 0.0) for item in trades]
        commission_assets = sorted({
            str(item.get("commissionAsset") or "UNKNOWN") for item in trades
        })
        latest_time_ms = max(int(item.get("time") or 0) for item in trades)
        first_trade = trades[0]
        return TestnetFill(
            order_id=order_id,
            trade_id=str(first_trade.get("id") or ""),
            symbol=str(first_trade.get("symbol") or symbol.upper()),
            side="BUY" if bool(first_trade.get("buyer")) else "SELL",
            price=notional / total_quantity,
            quantity=total_quantity,
            commission=sum(commissions),
            commission_asset=commission_assets[0] if len(commission_assets) == 1 else "MIXED",
            fill_time=datetime.fromtimestamp(latest_time_ms / 1000, UTC).isoformat(),
        )

    def _signed_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, str | int | float] | None = None,
    ) -> dict[str, Any]:
        payload = self._signed_request_payload(method, endpoint, params)
        if not isinstance(payload, dict):
            raise PaperTradingError("Binance testnet response was not an object.")
        return payload

    def _signed_request_payload(
        self,
        method: str,
        endpoint: str,
        params: dict[str, str | int | float] | None = None,
    ) -> Any:
        query: dict[str, str | int | float] = dict(params or {})
        query["timestamp"] = int(time.time() * 1000)
        query["recvWindow"] = 5000
        encoded = urlencode(query)
        signature = hmac.new(
            self.credentials.api_secret.encode("utf-8"),
            encoded.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signed_query = f"{encoded}&signature={signature}"
        response = httpx.request(
            method,
            f"{self.base_url}{endpoint}?{signed_query}",
            headers={"X-MBX-APIKEY": self.credentials.api_key},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def set_testnet_credentials(
    *,
    api_key: str,
    api_secret: str,
    secret_store: LocalSecretStore | None = None,
) -> SecretMaskedStatus:
    store = secret_store or LocalSecretStore()
    return store.set_secret(
        provider=BINANCE_TESTNET_PROVIDER,
        api_key=api_key,
        api_secret=api_secret,
    )


def delete_testnet_credentials(secret_store: LocalSecretStore | None = None) -> SecretMaskedStatus:
    store = secret_store or LocalSecretStore()
    return store.delete_secret(BINANCE_TESTNET_PROVIDER)


def get_testnet_credential_status(secret_store: LocalSecretStore | None = None) -> SecretMaskedStatus:
    store = secret_store or LocalSecretStore()
    return store.get_status(BINANCE_TESTNET_PROVIDER)


def load_testnet_credentials(secret_store: LocalSecretStore | None = None) -> BinanceTestnetCredentials | None:
    store = secret_store or LocalSecretStore()
    pair = store.get_secret_pair(BINANCE_TESTNET_PROVIDER)
    if pair is None:
        return None
    return BinanceTestnetCredentials(api_key=pair[0], api_secret=pair[1])


def find_latest_observation_plan(reports_path: str | Path = "reports/research") -> Path | None:
    base = Path(reports_path) / "experiments"
    if not base.exists():
        return None
    candidates = [path for path in base.glob("*/paper_observation_plan.md") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def run_paper_preflight(
    *,
    plan_path: str | Path | None = None,
    reports_path: str | Path = "reports/research",
    output_base_path: str | Path = DEFAULT_PAPER_REPORTS_PATH,
    secret_store: LocalSecretStore | None = None,
    client: TestnetClient | None = None,
    run_id: str | None = None,
) -> PaperPreflightResult:
    resolved_plan = Path(plan_path) if plan_path is not None else find_latest_observation_plan(reports_path)
    run_dir = Path(output_base_path) / (run_id or _new_run_id("preflight"))
    report_path = run_dir / "paper_preflight_report.md"
    run_dir.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    if resolved_plan is None or not resolved_plan.is_file():
        blockers.append("没有找到只读观察计划。先运行 `kronos report observation-plan`。")
    elif not _plan_is_observation_candidate(resolved_plan):
        blockers.append("观察计划还不是只读观察候选，不能启动测试网模拟盘。")

    status = get_testnet_credential_status(secret_store)
    credentials = load_testnet_credentials(secret_store)
    if credentials is None:
        blockers.append("Binance 测试网 API Key / Secret 尚未配置。")

    if not blockers:
        try:
            selected_client = client
            if selected_client is None and credentials is not None:
                selected_client = _build_real_client(credentials)
            if selected_client is not None:
                selected_client.ping_account()
        except Exception as exc:  # pragma: no cover - real client boundary
            blockers.append(f"Binance 测试网连接失败: {exc}")

    ok = not blockers
    result = PaperPreflightResult(
        ok=ok,
        status="通过" if ok else "未通过",
        message="可以启动 Binance 测试网模拟盘。" if ok else "启动前还有阻塞项。",
        environment="testnet",
        plan_path=resolved_plan if resolved_plan is not None else None,
        report_path=report_path,
        masked_api_key=status.masked_value,
        blockers=tuple(blockers),
    )
    _write_preflight_report(result)
    return result


def start_paper_run(
    *,
    plan_path: str | Path | None = None,
    reports_path: str | Path = "reports/research",
    output_base_path: str | Path = DEFAULT_PAPER_REPORTS_PATH,
    secret_store: LocalSecretStore | None = None,
    client: TestnetClient | None = None,
    run_id: str | None = None,
    symbol: str = "BTCUSDT",
    side: str = "BUY",
    quantity: float = 0.001,
    max_notional_usdt: float = 100.0,
    reset_stopped: bool = False,
) -> PaperRunResult:
    resolved_run_id = run_id or _new_run_id("paper")
    run_dir = Path(output_base_path) / resolved_run_id
    status_path = Path(output_base_path) / "current_status.json"
    report_path = run_dir / "paper_report.md"
    normalized_side = side.upper()

    def fail(reason: str, *, stopped_guard: bool = False) -> NoReturn:
        _write_failed_run(
            run_dir=run_dir,
            status_path=status_path,
            report_path=report_path,
            run_id=resolved_run_id,
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            max_notional_usdt=max_notional_usdt,
            reason=reason,
            stopped_guard=stopped_guard,
        )
        raise PaperTradingError(reason)

    if quantity <= 0:
        fail("quantity must be positive.")
    if max_notional_usdt <= 0:
        fail("max_notional_usdt must be positive.")
    if normalized_side not in {"BUY", "SELL"}:
        fail("side must be BUY or SELL.")
    if _is_stopped(output_base_path) and not reset_stopped:
        fail("测试网模拟盘已停止。若要重新启动，请显式传入 --reset-stopped。", stopped_guard=True)

    credentials = load_testnet_credentials(secret_store)
    preflight = run_paper_preflight(
        plan_path=plan_path,
        reports_path=reports_path,
        output_base_path=output_base_path,
        secret_store=secret_store,
        client=client,
        run_id=f"{resolved_run_id}-preflight",
    )
    if not preflight.ok:
        fail("; ".join(preflight.blockers) or "paper preflight failed.")

    selected_client = client or _build_real_client(credentials)
    try:
        price = selected_client.ticker_price(symbol)
    except Exception as exc:
        _write_failed_run(
            run_dir=run_dir,
            status_path=status_path,
            report_path=report_path,
            run_id=resolved_run_id,
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            max_notional_usdt=max_notional_usdt,
            reason=f"Binance 测试网行情读取失败: {exc}",
        )
        raise PaperTradingError(f"Binance 测试网行情读取失败: {exc}") from exc
    notional = price * quantity
    if notional > max_notional_usdt:
        reason = f"order notional {notional:.2f} USDT exceeds max {max_notional_usdt:.2f} USDT."
        _write_failed_run(
            run_dir=run_dir,
            status_path=status_path,
            report_path=report_path,
            run_id=resolved_run_id,
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            max_notional_usdt=max_notional_usdt,
            reason=reason,
        )
        raise PaperTradingError(reason)

    run_dir.mkdir(parents=True, exist_ok=True)
    client_order_id = f"kronos-{resolved_run_id}"[:36]
    try:
        order = selected_client.place_market_order(
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            client_order_id=client_order_id,
        )
        fill = selected_client.query_fill(symbol=symbol, order_id=order.order_id)
    except Exception as exc:
        _write_failed_run(
            run_dir=run_dir,
            status_path=status_path,
            report_path=report_path,
            run_id=resolved_run_id,
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            max_notional_usdt=max_notional_usdt,
            reason=f"Binance 测试网下单或成交查询失败: {exc}",
        )
        raise PaperTradingError(f"Binance 测试网下单或成交查询失败: {exc}") from exc

    _append_jsonl(run_dir / "paper_orders.jsonl", asdict(order))
    if fill is not None:
        _append_jsonl(run_dir / "paper_fills.jsonl", asdict(fill))

    run_payload = {
        "run_id": resolved_run_id,
        "status": "completed",
        "environment": "testnet",
        "run_dir": str(run_dir),
        "report_path": str(report_path),
        "symbol": symbol.upper(),
        "side": normalized_side,
        "quantity": quantity,
        "max_notional_usdt": max_notional_usdt,
        "order": asdict(order),
        "fill": asdict(fill) if fill is not None else None,
        "testnet_only": True,
    }
    _write_json(run_dir / "paper_run.json", run_payload)
    _write_json(status_path, run_payload)
    _write_run_report(report_path, run_payload)
    return PaperRunResult(
        run_id=resolved_run_id,
        status="completed",
        run_dir=run_dir,
        order=order,
        fill=fill,
        report_path=report_path,
        status_path=status_path,
    )


def read_paper_status(
    output_base_path: str | Path = DEFAULT_PAPER_REPORTS_PATH,
) -> dict[str, Any] | None:
    status_path = Path(output_base_path) / "current_status.json"
    if not status_path.exists():
        return None
    raw = json.loads(status_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def stop_paper_run(
    output_base_path: str | Path = DEFAULT_PAPER_REPORTS_PATH,
) -> Path:
    status_path = Path(output_base_path) / "current_status.json"
    status = read_paper_status(output_base_path) or {}
    status["status"] = "stopped"
    status["environment"] = "testnet"
    status["stopped_at"] = datetime.now(UTC).isoformat()
    status["message"] = "已停止测试网模拟盘，本地循环不会再提交新订单。"
    _write_json(status_path, status)
    return status_path


def _build_real_client(credentials: BinanceTestnetCredentials | None) -> BinanceUSDMTestnetClient:
    if credentials is None:
        raise PaperTradingError("Binance 测试网 API Key / Secret 尚未配置。")
    return BinanceUSDMTestnetClient(credentials)


def _plan_is_observation_candidate(path: Path) -> bool:
    metadata_path = path.with_suffix(".json")
    if not metadata_path.exists():
        return False
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("artifact_type") != "kronos.paper_observation_plan":
        return False
    if payload.get("eligible_for_testnet_paper") is not True:
        return False
    if payload.get("status") != "只读观察候选":
        return False
    if payload.get("data_kind") == "synthetic":
        return False
    if float(payload.get("span_days") or 0.0) < 90:
        return False
    if int(payload.get("promoted") or 0) <= 0:
        return False
    return _metadata_hashes_match(payload, metadata_path)


def _metadata_hashes_match(payload: dict[str, Any], metadata_path: Path) -> bool:
    source_report_value = payload.get("source_report")
    source_hash = payload.get("source_report_sha256")
    if not isinstance(source_report_value, str) or not isinstance(source_hash, str):
        return False
    source_report = _resolve_metadata_path(source_report_value, metadata_path)
    if not source_report.is_file() or _sha256_file(source_report) != source_hash:
        return False

    summary_value = payload.get("summary_path")
    summary_hash = payload.get("summary_sha256")
    if not isinstance(summary_value, str) or not isinstance(summary_hash, str):
        return False
    summary_path = _resolve_metadata_path(summary_value, metadata_path)
    return summary_path.is_file() and _sha256_file(summary_path) == summary_hash


def _resolve_metadata_path(value: str, metadata_path: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate.resolve()
    return (metadata_path.parent / candidate).resolve()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_preflight_report(result: PaperPreflightResult) -> None:
    lines = [
        "# Binance 测试网模拟盘 Preflight",
        "",
        f"- 状态：{result.status}",
        f"- 环境：{result.environment}",
        f"- 结论：{result.message}",
        "- 边界：这里只允许 Binance testnet，不会连接 mainnet/live。",
        "- 资金：测试网资金与真实资金隔离。",
    ]
    if result.plan_path is not None:
        lines.append(f"- 观察计划：{result.plan_path}")
    if result.masked_api_key is not None:
        lines.append(f"- API Key：{result.masked_api_key}")
    if result.blockers:
        lines.extend(["", "## 阻塞项"])
        lines.extend(f"- {blocker}" for blocker in result.blockers)
    result.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_run_report(path: Path, payload: dict[str, Any]) -> None:
    order = payload.get("order")
    fill = payload.get("fill")
    lines = [
        "# Binance 测试网模拟盘报告",
        "",
        f"- run_id：{payload['run_id']}",
        "- 环境：Binance testnet",
        "- 资金：测试资金，不影响真实账户。",
        "- 实盘边界：这不是实盘收益证明，不能自动升级实盘。",
        f"- 品种：{payload['symbol']}",
        f"- 方向：{payload['side']}",
        f"- 数量：{payload['quantity']}",
    ]
    if payload.get("status") == "failed":
        lines.append(f"- 失败原因：{payload.get('failure_reason', '未知')}")
    elif isinstance(order, dict):
        lines.extend([
            f"- 测试网订单 ID：{order['order_id']}",
            f"- 订单状态：{order['status']}",
        ])
    if fill is not None:
        lines.extend([
            f"- 成交价格：{fill['price']}",
            f"- 成交数量：{fill['quantity']}",
            f"- 手续费：{fill['commission']} {fill['commission_asset']}",
            f"- 成交时间：{fill['fill_time']}",
        ])
    elif payload.get("status") == "completed":
        lines.append("- 成交明细：未查询到完整 testnet trade 记录，只保留订单状态。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_failed_run(
    *,
    run_dir: Path,
    status_path: Path,
    report_path: Path,
    run_id: str,
    symbol: str,
    side: str,
    quantity: float,
    max_notional_usdt: float,
    reason: str,
    stopped_guard: bool = False,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "status": "failed",
        "environment": "testnet",
        "run_dir": str(run_dir),
        "report_path": str(report_path),
        "symbol": symbol.upper(),
        "side": side,
        "quantity": quantity,
        "max_notional_usdt": max_notional_usdt,
        "order": None,
        "fill": None,
        "failure_reason": reason,
        "testnet_only": True,
        "stopped_guard": stopped_guard,
    }
    _append_jsonl(run_dir / "paper_errors.jsonl", {
        "run_id": run_id,
        "environment": "testnet",
        "reason": reason,
        "created_at": datetime.now(UTC).isoformat(),
    })
    _write_json(run_dir / "paper_run.json", payload)
    _write_json(status_path, payload)
    _write_run_report(report_path, payload)


def _is_stopped(output_base_path: str | Path) -> bool:
    status = read_paper_status(output_base_path)
    return isinstance(status, dict) and (
        status.get("status") == "stopped" or status.get("stopped_guard") is True
    )


def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _new_run_id(suffix: str) -> str:
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{suffix}"


def _format_quantity(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")
