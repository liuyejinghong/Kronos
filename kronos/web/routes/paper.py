"""Testnet paper-trading status routes for the local Web API."""
# ruff: noqa: RUF001

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from kronos.execution.paper import read_paper_status
from kronos.web.app import WebAppContext, get_context
from kronos.web.routes._mappers import validate_run_id
from kronos.web.schemas import (
    PaperErrorResponse,
    PaperFillResponse,
    PaperOrderResponse,
    PaperRunReportResponse,
    PaperStatusResponse,
)

router = APIRouter(prefix="/api/paper", tags=["paper"])

_LEDGER_LIMIT = 5
_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|apikey|api[_-]?secret|secret|signature|token)([=:]\s*)([^&\s]+)"
)
_URL_QUERY_PATTERN = re.compile(r"(https?://[^\s?]+)\?[^\s]+")


@router.get("/status", response_model=PaperStatusResponse)
def get_paper_status(request: Request) -> PaperStatusResponse:
    """Return the current Binance testnet paper status and latest evidence."""
    context = get_context(request)
    status_payload = read_paper_status(context.paper_path)
    if status_payload is None:
        return PaperStatusResponse(
            status="not_started",
            environment="testnet",
            message_zh="还没有测试网模拟盘运行记录。",
            next_action_zh=(
                "先准备合格观察候选并通过 paper preflight；有测试网凭证后再由 CLI "
                "提交最小 Binance testnet 订单。"
            ),
        )

    status = str(status_payload.get("status") or "unknown")
    run_id = _optional_string(status_payload.get("run_id"))
    run_dir = _resolve_run_dir(context, status_payload, run_id)
    report_path = _resolve_report_path(context, status_payload, run_id, run_dir)
    orders_raw = _read_jsonl(run_dir / "paper_orders.jsonl") if run_dir is not None else []
    fills_raw = _read_jsonl(run_dir / "paper_fills.jsonl") if run_dir is not None else []
    errors_raw = _read_jsonl(run_dir / "paper_errors.jsonl") if run_dir is not None else []
    if not orders_raw and isinstance(status_payload.get("order"), dict):
        orders_raw = [status_payload["order"]]
    if not fills_raw and isinstance(status_payload.get("fill"), dict):
        fills_raw = [status_payload["fill"]]

    latest_errors = [_error_response(item, run_id) for item in errors_raw]
    failure_reason = _optional_string(status_payload.get("failure_reason"))
    if status == "failed" and failure_reason and not latest_errors:
        latest_errors.append(PaperErrorResponse(run_id=run_id, reason=_safe_text(failure_reason)))

    return PaperStatusResponse(
        status=status,
        environment="testnet",
        run_id=run_id,
        updated_at=_updated_at(status_payload, fills_raw, latest_errors),
        message_zh=_status_message(status, status_payload),
        next_action_zh=_next_action(status, status_payload),
        run_dir=str(run_dir) if run_dir is not None else None,
        report_path=str(report_path) if report_path is not None else None,
        report_available=report_path is not None,
        truncated=_has_more(run_dir),
        latest_orders=[_order_response(item, status_payload) for item in orders_raw],
        latest_fills=[_fill_response(item, status_payload) for item in fills_raw],
        latest_errors=latest_errors,
    )


@router.get("/runs/{run_id}/report", response_model=PaperRunReportResponse)
def get_paper_run_report(run_id: str, request: Request) -> PaperRunReportResponse:
    """Return the readable Markdown report for one testnet paper run."""
    validate_run_id(run_id)
    context = get_context(request)
    report_path = (context.paper_path / run_id / "paper_report.md").resolve()
    if not _is_inside(report_path, context.paper_path) or not report_path.is_file():
        raise HTTPException(status_code=404, detail=f"No paper report found for run: {run_id}")
    content = _safe_text(report_path.read_text(encoding="utf-8"))
    return PaperRunReportResponse(
        run_id=run_id,
        title_zh=_report_title(content),
        report_path=str(report_path),
        content_md=content,
    )


def _resolve_run_dir(
    context: WebAppContext,
    payload: dict[str, Any],
    run_id: str | None,
) -> Path | None:
    raw_run_dir = _optional_string(payload.get("run_dir"))
    if raw_run_dir:
        candidate = _resolve_path(context, raw_run_dir)
        if _is_inside(candidate, context.paper_path) and candidate.is_dir():
            return candidate
    if run_id is None:
        return None
    candidate = (context.paper_path / run_id).resolve()
    return candidate if candidate.is_dir() else None


def _resolve_report_path(
    context: WebAppContext,
    payload: dict[str, Any],
    run_id: str | None,
    run_dir: Path | None,
) -> Path | None:
    raw_report_path = _optional_string(payload.get("report_path"))
    if raw_report_path:
        candidate = _resolve_path(context, raw_report_path)
        if _is_inside(candidate, context.paper_path) and candidate.is_file():
            return candidate
    candidates = []
    if run_dir is not None:
        candidates.append(run_dir / "paper_report.md")
    if run_id is not None:
        candidates.append(context.paper_path / run_id / "paper_report.md")
    for candidate in candidates:
        resolved = candidate.resolve()
        if _is_inside(resolved, context.paper_path) and resolved.is_file():
            return resolved
    return None


def _resolve_path(context: WebAppContext, value: str) -> Path:
    path = Path(value.replace("\\", "/"))
    if not path.is_absolute():
        path = context.project_root / path
    return path.resolve()


def _read_jsonl(path: Path, *, limit: int = _LEDGER_LIMIT) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def _order_response(item: dict[str, Any], status_payload: dict[str, Any]) -> PaperOrderResponse:
    return PaperOrderResponse(
        order_id=_optional_string(item.get("order_id")),
        client_order_id=_optional_string(item.get("client_order_id")),
        symbol=str(item.get("symbol") or status_payload.get("symbol") or "UNKNOWN"),
        side=str(item.get("side") or status_payload.get("side") or "UNKNOWN"),
        order_type=_optional_string(item.get("order_type")),
        quantity=_optional_float(item.get("quantity")),
        status=str(item.get("status") or "UNKNOWN"),
        environment="testnet",
        created_at=_optional_string(item.get("created_at")),
    )


def _fill_response(item: dict[str, Any], status_payload: dict[str, Any]) -> PaperFillResponse:
    return PaperFillResponse(
        order_id=_optional_string(item.get("order_id")),
        trade_id=_optional_string(item.get("trade_id")),
        symbol=str(item.get("symbol") or status_payload.get("symbol") or "UNKNOWN"),
        side=str(item.get("side") or status_payload.get("side") or "UNKNOWN"),
        price=_optional_float(item.get("price")),
        quantity=_optional_float(item.get("quantity")),
        commission=_optional_float(item.get("commission")),
        commission_asset=_optional_string(item.get("commission_asset")),
        fill_time=_optional_string(item.get("fill_time")),
        environment="testnet",
    )


def _error_response(item: dict[str, Any], run_id: str | None) -> PaperErrorResponse:
    return PaperErrorResponse(
        run_id=_optional_string(item.get("run_id")) or run_id,
        environment="testnet",
        reason=_safe_text(item.get("reason") or "测试网模拟盘记录了错误，但没有提供详细原因。"),
        created_at=_optional_string(item.get("created_at")),
    )


def _status_message(status: str, payload: dict[str, Any]) -> str:
    if status == "completed":
        return "最近一轮 Binance testnet 模拟盘已完成。"
    if status == "failed":
        return "最近一轮 Binance testnet 模拟盘失败，未进入真实资金。"
    if status == "stopped":
        return "测试网模拟盘已停止，本地循环不会再提交新测试网订单。"
    if status in {"running", "started"}:
        return "测试网模拟盘状态记录显示正在运行，请继续观察订单和成交证据。"
    message = _optional_string(payload.get("message"))
    return message or "已读取测试网模拟盘状态。"


def _next_action(status: str, payload: dict[str, Any]) -> str:
    if status == "completed":
        return "复核订单、成交、手续费和报告；testnet 结果只能作为模拟盘证据，不能直接升级实盘。"
    if status == "failed":
        reason = _optional_string(payload.get("failure_reason"))
        if reason:
            return f"先处理阻塞项：{_safe_text(reason)}"
        return "先查看错误记录，再重新运行 paper preflight。"
    if status == "stopped":
        return "如需重新验证，先确认观察候选和 preflight，再用 CLI 显式 reset-stopped。"
    return "继续保留 testnet 只读边界，下一步仍需通过凭证、候选、观察计划和 preflight 闸门。"


def _updated_at(
    payload: dict[str, Any],
    fills: list[dict[str, Any]],
    errors: list[PaperErrorResponse],
) -> str | None:
    for key in ("stopped_at", "updated_at", "created_at"):
        value = _optional_string(payload.get(key))
        if value:
            return value
    if fills:
        value = _optional_string(fills[-1].get("fill_time"))
        if value:
            return value
    if errors:
        return errors[-1].created_at
    return None


def _has_more(run_dir: Path | None) -> bool:
    if run_dir is None:
        return False
    for name in ("paper_orders.jsonl", "paper_fills.jsonl", "paper_errors.jsonl"):
        path = run_dir / name
        if path.exists() and len(path.read_text(encoding="utf-8").splitlines()) > _LEDGER_LIMIT:
            return True
    return False


def _report_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or "测试网模拟盘报告"
    return "测试网模拟盘报告"


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _safe_text(value: object) -> str:
    text = str(value)
    text = _URL_QUERY_PATTERN.sub(r"\1?<redacted>", text)
    return _SECRET_PATTERN.sub(r"\1\2<redacted>", text)


def _is_inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True
