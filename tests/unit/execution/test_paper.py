from __future__ import annotations

# ruff: noqa: RUF001
import json
from typing import TYPE_CHECKING

import pytest

from kronos.agent.secrets import LocalSecretStore
from kronos.execution.paper import (
    BINANCE_MAINNET_BASE_URL,
    BinanceTestnetCredentials,
    BinanceUSDMMockTestnetClient,
    BinanceUSDMTestnetClient,
    PaperTradingError,
    delete_testnet_credentials,
    get_testnet_credential_status,
    run_paper_preflight,
    set_testnet_credentials,
    start_paper_run,
    stop_paper_run,
)
from kronos.reporting.observation_plan import generate_observation_plan

if TYPE_CHECKING:
    from pathlib import Path

    from kronos.execution.paper import TestnetOrder


def _secret_store(tmp_path: Path) -> LocalSecretStore:
    return LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json")


def _write_auto_report(tmp_path: Path, *, promoted: int = 1, span_days: float = 120.0) -> Path:
    run_dir = tmp_path / "reports" / "research" / "experiments" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    report = run_dir / "auto_run_report.md"
    report.write_text("# Kronos 自动研究日报\n", encoding="utf-8")
    (run_dir / "auto_run_summary.json").write_text(
        json.dumps({
            "summary": {
                "evaluated": 1,
                "promoted": promoted,
                "not_promoted": max(1 - promoted, 0),
                "skipped": 0,
            },
            "run_id": "run-1",
            "symbols": ["BTCUSDT"],
            "timeframe": "15m",
            "data_coverage": [{
                "symbol": "BTCUSDT",
                "dataset": "klines_15m",
                "span_days": span_days,
            }],
            "config_snapshot": {"data_kind": "local"},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _write_candidate_plan(tmp_path: Path) -> Path:
    return generate_observation_plan(_write_auto_report(tmp_path)).path


def _write_ineligible_plan(tmp_path: Path) -> Path:
    return generate_observation_plan(_write_auto_report(tmp_path, promoted=0)).path


def _write_forged_candidate_plan(tmp_path: Path) -> Path:
    plan = tmp_path / "reports" / "research" / "experiments" / "forged" / "paper_observation_plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("- 状态：只读观察候选\n", encoding="utf-8")
    return plan


def test_testnet_credentials_are_masked_and_retrievable(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    key = "testnet-api-key-123456"
    secret = "testnet-secret-abcdef"

    status = set_testnet_credentials(api_key=key, api_secret=secret, secret_store=store)

    assert status.configured is True
    assert status.masked_value is not None
    assert status.masked_secret is not None
    assert key not in status.model_dump_json()
    assert secret not in status.model_dump_json()
    assert store.get_secret_pair("binance-testnet") == (key, secret)


def test_delete_testnet_credentials_blocks_preflight(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    set_testnet_credentials(api_key="testnet-api-key", api_secret="testnet-secret", secret_store=store)

    status = delete_testnet_credentials(store)
    result = run_paper_preflight(
        plan_path=_write_candidate_plan(tmp_path),
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
    )

    assert status.configured is False
    assert result.ok is False
    assert any("尚未配置" in blocker for blocker in result.blockers)


def test_start_without_credentials_writes_preflight_report(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)

    with pytest.raises(PaperTradingError, match="尚未配置"):
        start_paper_run(
            plan_path=_write_candidate_plan(tmp_path),
            output_base_path=tmp_path / "reports" / "paper",
            secret_store=store,
            run_id="missing-credentials",
        )

    report = (
        tmp_path
        / "reports"
        / "paper"
        / "missing-credentials-preflight"
        / "paper_preflight_report.md"
    )
    assert report.exists()
    assert "Binance 测试网 API Key / Secret 尚未配置" in report.read_text(encoding="utf-8")


def test_real_client_rejects_mainnet_endpoint() -> None:
    credentials = BinanceTestnetCredentials(api_key="key", api_secret="secret")

    with pytest.raises(PaperTradingError, match="testnet"):
        BinanceUSDMTestnetClient(credentials, base_url=BINANCE_MAINNET_BASE_URL)


def test_preflight_requires_observation_candidate_and_credentials(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    plan = _write_ineligible_plan(tmp_path)

    result = run_paper_preflight(
        plan_path=plan,
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
    )
    text = result.report_path.read_text(encoding="utf-8")

    assert result.ok is False
    assert "不能启动测试网模拟盘" in text
    assert "尚未配置" in text


def test_preflight_rejects_forged_observation_plan_text(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)

    result = run_paper_preflight(
        plan_path=_write_forged_candidate_plan(tmp_path),
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
        client=BinanceUSDMMockTestnetClient(),
    )

    assert result.ok is False
    assert any("不是只读观察候选" in blocker for blocker in result.blockers)


def test_preflight_rejects_forged_metadata_without_source_hashes(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)
    plan = _write_forged_candidate_plan(tmp_path)
    plan.with_suffix(".json").write_text(
        json.dumps({
            "artifact_type": "kronos.paper_observation_plan",
            "status": "只读观察候选",
            "eligible_for_testnet_paper": True,
            "data_kind": "local",
            "span_days": 120.0,
            "promoted": 1,
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = run_paper_preflight(
        plan_path=plan,
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
        client=BinanceUSDMMockTestnetClient(),
    )

    assert result.ok is False
    assert any("不是只读观察候选" in blocker for blocker in result.blockers)


def test_preflight_rejects_metadata_when_source_report_changes(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)
    plan = _write_candidate_plan(tmp_path)
    source_report = tmp_path / "reports" / "research" / "experiments" / "run-1" / "auto_run_report.md"
    source_report.write_text("# tampered\n", encoding="utf-8")

    result = run_paper_preflight(
        plan_path=plan,
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
        client=BinanceUSDMMockTestnetClient(),
    )

    assert result.ok is False
    assert any("不是只读观察候选" in blocker for blocker in result.blockers)


def test_preflight_passes_with_candidate_plan_credentials_and_mock_client(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)

    result = run_paper_preflight(
        plan_path=_write_candidate_plan(tmp_path),
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
        client=BinanceUSDMMockTestnetClient(),
    )
    text = result.report_path.read_text(encoding="utf-8")

    assert result.ok is True
    assert result.status == "通过"
    assert "Binance testnet" in text
    assert "testnet-api-key-123456" not in text
    assert "testnet-secret" not in text


def test_start_paper_run_writes_testnet_order_fill_status_and_report(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)

    result = start_paper_run(
        plan_path=_write_candidate_plan(tmp_path),
        output_base_path=tmp_path / "reports" / "paper",
        secret_store=store,
        client=BinanceUSDMMockTestnetClient(),
        run_id="paper-test-run",
    )

    order_raw = (result.run_dir / "paper_orders.jsonl").read_text(encoding="utf-8")
    fill_raw = (result.run_dir / "paper_fills.jsonl").read_text(encoding="utf-8")
    report = result.report_path.read_text(encoding="utf-8")
    status = json.loads(result.status_path.read_text(encoding="utf-8"))

    assert result.order is not None
    assert result.fill is not None
    assert result.order.order_id == "mock-testnet-order-1"
    assert result.fill.trade_id == "mock-testnet-trade-1"
    assert result.fill.fill_time
    assert '"environment": "testnet"' in order_raw
    assert '"environment": "testnet"' in fill_raw
    assert '"fill_time"' in fill_raw
    assert "测试资金，不影响真实账户" in report
    assert "成交时间" in report
    assert "testnet-api-key-123456" not in report
    assert status["status"] == "completed"
    assert status["environment"] == "testnet"
    assert status["report_path"] == str(result.report_path)


def test_start_validation_failure_writes_status_error_ledger_and_report(tmp_path: Path) -> None:
    output_base = tmp_path / "reports" / "paper"

    with pytest.raises(PaperTradingError, match="quantity must be positive"):
        start_paper_run(
            output_base_path=output_base,
            run_id="invalid-quantity",
            quantity=0.0,
        )

    status = json.loads((output_base / "current_status.json").read_text(encoding="utf-8"))
    errors = (output_base / "invalid-quantity" / "paper_errors.jsonl").read_text(encoding="utf-8")
    report = (output_base / "invalid-quantity" / "paper_report.md").read_text(encoding="utf-8")

    assert status["status"] == "failed"
    assert "quantity must be positive" in errors
    assert "失败原因" in report


def test_stopped_state_blocks_restart_without_explicit_reset(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    output_base = tmp_path / "reports" / "paper"
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)
    plan = _write_candidate_plan(tmp_path)
    stop_paper_run(output_base)

    with pytest.raises(PaperTradingError, match="reset-stopped"):
        start_paper_run(
            run_id="blocked-after-stop",
            plan_path=plan,
            output_base_path=output_base,
            secret_store=store,
            client=BinanceUSDMMockTestnetClient(),
        )
    blocked_status = json.loads((output_base / "current_status.json").read_text(encoding="utf-8"))

    result = start_paper_run(
        plan_path=plan,
        output_base_path=output_base,
        secret_store=store,
        client=BinanceUSDMMockTestnetClient(),
        reset_stopped=True,
    )

    assert blocked_status["status"] == "failed"
    assert blocked_status["stopped_guard"] is True
    assert result.status == "completed"


def test_preflight_failure_writes_status_error_ledger_and_report(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    output_base = tmp_path / "reports" / "paper"

    with pytest.raises(PaperTradingError, match="尚未配置"):
        start_paper_run(
            plan_path=_write_candidate_plan(tmp_path),
            output_base_path=output_base,
            secret_store=store,
            run_id="preflight-blocked",
        )

    status = json.loads((output_base / "current_status.json").read_text(encoding="utf-8"))
    errors = (output_base / "preflight-blocked" / "paper_errors.jsonl").read_text(encoding="utf-8")
    report = (output_base / "preflight-blocked" / "paper_report.md").read_text(encoding="utf-8")

    assert status["status"] == "failed"
    assert "尚未配置" in errors
    assert "失败原因" in report


def test_failed_order_writes_status_error_ledger_and_report(tmp_path: Path) -> None:
    class FailingClient(BinanceUSDMMockTestnetClient):
        def place_market_order(
            self,
            *,
            symbol: str,
            side: str,
            quantity: float,
            client_order_id: str,
        ) -> TestnetOrder:
            raise RuntimeError("testnet rejected order")

    store = _secret_store(tmp_path)
    output_base = tmp_path / "reports" / "paper"
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)

    with pytest.raises(PaperTradingError, match="下单或成交查询失败"):
        start_paper_run(
            plan_path=_write_candidate_plan(tmp_path),
            output_base_path=output_base,
            secret_store=store,
            client=FailingClient(),
            run_id="failed-run",
        )

    status = json.loads((output_base / "current_status.json").read_text(encoding="utf-8"))
    errors = (output_base / "failed-run" / "paper_errors.jsonl").read_text(encoding="utf-8")
    report = (output_base / "failed-run" / "paper_report.md").read_text(encoding="utf-8")

    assert status["status"] == "failed"
    assert "testnet rejected order" in errors
    assert "失败原因" in report


def test_notional_limit_failure_writes_status_and_report(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    output_base = tmp_path / "reports" / "paper"
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)

    with pytest.raises(PaperTradingError, match="exceeds max"):
        start_paper_run(
            plan_path=_write_candidate_plan(tmp_path),
            output_base_path=output_base,
            secret_store=store,
            client=BinanceUSDMMockTestnetClient(),
            run_id="too-large",
            max_notional_usdt=1.0,
        )

    status = json.loads((output_base / "current_status.json").read_text(encoding="utf-8"))

    assert status["status"] == "failed"
    assert "exceeds max" in status["failure_reason"]


def test_ticker_failure_writes_status_error_ledger_and_report(tmp_path: Path) -> None:
    class FailingTickerClient(BinanceUSDMMockTestnetClient):
        def ticker_price(self, symbol: str) -> float:
            raise RuntimeError("ticker unavailable")

    store = _secret_store(tmp_path)
    output_base = tmp_path / "reports" / "paper"
    set_testnet_credentials(api_key="testnet-api-key-123456", api_secret="testnet-secret", secret_store=store)

    with pytest.raises(PaperTradingError, match="行情读取失败"):
        start_paper_run(
            plan_path=_write_candidate_plan(tmp_path),
            output_base_path=output_base,
            secret_store=store,
            client=FailingTickerClient(),
            run_id="ticker-failed",
        )

    status = json.loads((output_base / "current_status.json").read_text(encoding="utf-8"))
    errors = (output_base / "ticker-failed" / "paper_errors.jsonl").read_text(encoding="utf-8")
    report = (output_base / "ticker-failed" / "paper_report.md").read_text(encoding="utf-8")

    assert status["status"] == "failed"
    assert "ticker unavailable" in errors
    assert "失败原因" in report


def test_real_testnet_client_fill_uses_trade_details() -> None:
    class TradeDetailClient(BinanceUSDMTestnetClient):
        def __init__(self) -> None:
            super().__init__(BinanceTestnetCredentials(api_key="key", api_secret="secret"))

        def _signed_request_payload(
            self,
            method: str,
            endpoint: str,
            params: dict[str, str | int | float] | None = None,
        ) -> object:
            assert endpoint == "/fapi/v1/userTrades"
            assert params is not None
            assert params["orderId"] == "42"
            return [
                {
                    "id": 7,
                    "symbol": "BTCUSDT",
                    "price": "50000",
                    "qty": "0.001",
                    "commission": "0.01",
                    "commissionAsset": "USDT",
                    "time": 1_700_000_000_000,
                    "buyer": True,
                }
            ]

    fill = TradeDetailClient().query_fill(symbol="BTCUSDT", order_id="42")

    assert fill is not None
    assert fill.trade_id == "7"
    assert fill.price == 50_000.0
    assert fill.quantity == 0.001
    assert fill.commission == 0.01
    assert fill.commission_asset == "USDT"
    assert fill.fill_time == "2023-11-14T22:13:20+00:00"


def test_stop_paper_run_persists_stopped_state(tmp_path: Path) -> None:
    output_base = tmp_path / "reports" / "paper"

    status_path = stop_paper_run(output_base)
    payload = json.loads(status_path.read_text(encoding="utf-8"))

    assert payload["status"] == "stopped"
    assert payload["environment"] == "testnet"
    assert "不会再提交新订单" in payload["message"]


def test_status_empty_credentials_are_not_configured(tmp_path: Path) -> None:
    status = get_testnet_credential_status(_secret_store(tmp_path))

    assert status.configured is False
    assert status.masked_value is None
    assert status.masked_secret is None
