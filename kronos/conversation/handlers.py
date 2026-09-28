# ruff: noqa: RUF001 -- Chinese user-facing error messages use fullwidth punctuation.
"""Real evaluation pipeline task handlers (package P14b).

This module is the final wiring that makes a submitted conversation task
actually RUN the deterministic chain on real local data:

    ensure_data        P06 plan -> real sync repair -> rebuild plan -> report
    evaluate_strategy  P07 build+freeze+verify snapshot -> engine run ->
                       P10 evidence bundle -> P11 verdict -> artifacts ->
                       budget spend receipts

Both handlers consume the payload keys already written by
:class:`kronos.conversation.service.ConversationService` (``session_id``,
``spec_hash``, ``spec_content``, ``snapshot_policy``, ``budget_round_id``,
``budget_reservation_id``) — the service was NOT edited for this package.

Lead rulings implemented here
-----------------------------
1. **Warmup policy = 14 days** (``EVAL_WARMUP_DAYS``).  The evaluation window
   requests 90 complete UTC days (``EVAL_WINDOW_DAYS``, ruling D-20260928-002)
   PLUS 14 days of warmup data ahead of it.  The old default (~2.1 days from
   ``required_warmup_bars``) left P10's pre-registered trailing-10-day-vol
   tercile slices without enough pre-dev history to compute (P21 measured
   ``time_slices=0`` on real windows).  The warmup is a *data availability*
   policy: engines keep their own internal decision warmup; the extra days
   exist so the trailing-vol history (10d window + 1d lag) is fully covered
   before the first dev bar.  The window parameters are keyword-overridable on
   :func:`make_handler_map` so tests can run a micro window (e.g. 4d eval +
   14d warmup) against a constructed store.
2. **Engine selection**: ``KRONOS_EVAL_ENGINE`` (or the explicit
   ``engine_env`` argument) selects ``"adapter"`` (default) or
   ``"reference"``.  The adapter path calls
   :func:`kronos.research.verdict.kernel.ensure_freqtrade_env` with
   ``skip_if_missing=True`` and FALLS BACK to the reference ledger engine when
   the venv is absent — never silently: a task event ``engine_fallback`` is
   appended and the verdict's ``engine_version`` field records which engine
   actually ran.  Both engines produce
   :class:`~kronos.research.verdict.contracts.ExecutionLedger`; the evidence
   builder receives the engine through P10's injection seam.
3. **Bars loading**: ``bars_15m`` (query.load resample) + ``bars_1m`` (raw)
   + funding events for the frozen span come from the local parquet store via
   :func:`kronos.data.storage.query.load`.  ``mock_available_at`` semantics
   follow the snapshot manifest: when knowable-time is historically simulated
   (mock) no PIT filter is applied; with real ingestion semantics the load is
   filtered to ``available_at <= window_end``.

Idempotency: artifacts live under ``<state_dir>/runs/<run_id>/`` where
``run_id = eval-<session8>-<spec_hash16>``.  A re-run (attempt >= 2 after
lease recovery) that finds an existing ``verdict.json`` plus a matching
payload hash in ``run_meta.json`` reuses the artifacts instead of recomputing
(the verdict file is written LAST, so its presence implies a complete set).

Costs: fee 4 bps on notional + slippage 5 bps in fill price (canonical,
D-20260928-003) on the reference engine.  The freqtrade kernel executes
slippage-free and rejects nonzero slippage fail-closed, so adapter runs use
slippage 0 — recorded in the result payload alongside the engine version.

Single-symbol boundary: v0.5.0 carries one bar series per evaluation, so a
spec with more than one symbol fails closed with a visible reason (P10's
evidence builder has the same boundary).  Signal timeframe is pinned to
``"15m"``: the pre-registered slice rules and both engines are 15m semantics
(the ruled 1h "coarse comparison" is not part of the v0.5.0 evidence chain).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from kronos.common.errors import KronosError
from kronos.common.log import get_logger
from kronos.conversation.service import SNAPSHOT_POLICY_ID
from kronos.data.storage.query import load
from kronos.research.verdict.backtest_adapter import (
    BacktestCaseInput,
)
from kronos.research.verdict.backtest_adapter import (
    run_backtest as adapter_run_backtest,
)
from kronos.research.verdict.contracts import (
    ExecutionLedger,
    StrategyVerdict,
)
from kronos.research.verdict.evidence import (
    EvidenceEngine,
    RunInput,
    build_evidence_bundle,
    make_adapter_engine,
    make_reference_engine,
)
from kronos.research.verdict.kernel import ensure_freqtrade_env
from kronos.research.verdict.policy import VerdictPolicy
from kronos.research.verdict.readiness import (
    apply_repair_actions,
    build_readiness_plan,
    render_readiness_report,
)
from kronos.research.verdict.snapshot import (
    build_snapshot,
    freeze_snapshot,
    render_snapshot_report,
    verify_snapshot_frozen,
)
from kronos.research.verdict.verdict import evaluate_verdict
from kronos.runtime.budget import ROUND_ID_PAYLOAD_KEY, BudgetLedger, SpendKind
from kronos.runtime.tasks import TaskStore, canonical_payload_sha256
from kronos.strategy.spec import StrategySpec
from kronos.strategy.variant_rules import BARS_PER_UTC_DAY

if TYPE_CHECKING:
    import pandas as pd

log = get_logger("kronos.conversation.handlers")

#: Env var selecting the evaluation engine ("adapter" | "reference").
ENGINE_ENV_VAR: Final[str] = "KRONOS_EVAL_ENGINE"

#: Lead ruling 1: the evaluation window is 90 complete UTC days (D-20260928-002).
EVAL_WINDOW_DAYS: Final[int] = 90
#: Lead ruling 1: data warmup ahead of the evaluation window, in UTC days.
#: Raised from ~2.1d to 14d so P10's trailing-10d-vol tercile slices (10d
#: window + 1d lag) are computable on real windows (P21 measured
#: time_slices=0 with the short warmup).
EVAL_WARMUP_DAYS: Final[int] = 14

DAY_MS: Final[int] = 86_400_000

#: Canonical cost policy (D-20260928-003): fee 4 bps on notional.
DEFAULT_FEE_BPS: Final[float] = 4.0
#: Canonical slippage 5 bps in fill price — reference-engine runs only.
DEFAULT_REFERENCE_SLIPPAGE_BPS: Final[float] = 5.0
#: The freqtrade kernel is slippage-free and rejects nonzero slippage.
ADAPTER_SLIPPAGE_BPS: Final[float] = 0.0

#: Starting equity for every engine run (no capital dimension in the spec yet).
DEFAULT_START_EQUITY: Final[float] = 10_000.0

ENGINE_VERSION_REFERENCE: Final[str] = "reference_ledger:p04"
ENGINE_VERSION_ADAPTER: Final[str] = "freqtrade_kernel_adapter:p08"

_RUNS_DIRNAME: Final[str] = "runs"
_VERDICT_FILENAME: Final[str] = "verdict.json"
_LEDGER_FILENAME: Final[str] = "ledger.json"
_EVIDENCE_FILENAME: Final[str] = "evidence.json"
_RUN_META_FILENAME: Final[str] = "run_meta.json"
_CONVERSATIONS_DB_FILENAME: Final[str] = "conversations.sqlite3"
#: Task event appended when the adapter engine falls back to the reference.
ENGINE_FALLBACK_EVENT: Final[str] = "engine_fallback"


class PipelineHandlerError(KronosError):
    """Base class for task-handler failures (task fails with a visible reason)."""


class DataNotReadyError(PipelineHandlerError):
    """The readiness plan is blocked; the plan report is the failure reason."""


class SnapshotInvalidError(PipelineHandlerError):
    """The frozen snapshot failed its quality gates or re-verification."""


class EngineSelectionError(PipelineHandlerError):
    """Unknown engine selection (expected ``adapter`` or ``reference``)."""


class EvaluationBudgetExhaustedError(PipelineHandlerError):
    """The round's wall-clock budget has no headroom before the run."""


@dataclass
class AppliedCost:
    """Cost policy actually applied to engine runs (see module docstring).

    Mutable on purpose: P10's ``CostPolicyLike`` protocol declares settable
    attributes, so a frozen dataclass would not satisfy it structurally.
    """

    fee_bps: float
    slippage_bps: float


@dataclass(frozen=True)
class HandlerContext:
    """Everything the two handlers need; built once by :func:`make_handler_map`."""

    base_path: Path
    state_dir: Path
    snapshots_dir: Path
    engine_env: str | None
    venv_dir: Path | None
    task_store: TaskStore
    budget_ledger: BudgetLedger
    conversations_db: Path
    eval_window_days: int
    warmup_days: int
    now_ms: int | None


class _VenvAdapter:
    """``AdapterLike`` wrapper around the adapter's public ``run_backtest``."""

    def __init__(self, venv_dir: Path | None) -> None:
        self._venv_dir = venv_dir

    def run_backtest(
        self,
        case_input: BacktestCaseInput,
        *,
        workdir: Path | None = None,
    ) -> ExecutionLedger:
        return adapter_run_backtest(case_input, venv_dir=self._venv_dir, workdir=workdir)


# --------------------------------------------------------------------- window


def resolve_window(
    *,
    now_ms_value: int | None = None,
    eval_window_days: int = EVAL_WINDOW_DAYS,
) -> tuple[int, int]:
    """Evaluation window = the last ``eval_window_days`` complete UTC days.

    The exclusive end is the start of the current UTC day (so every covered
    day is complete); the start is exactly ``eval_window_days`` days earlier,
    which keeps both bounds UTC-midnight aligned (required by the snapshot's
    bucket-grid alignment gate).
    """
    if eval_window_days < 1:
        raise ValueError(f"eval_window_days must be >= 1, got {eval_window_days}")
    now = int(now_ms_value if now_ms_value is not None else time.time() * 1000)
    window_end = (now // DAY_MS) * DAY_MS
    return window_end - eval_window_days * DAY_MS, window_end


# -------------------------------------------------------------------- helpers


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PipelineHandlerError(f"payload field {key!r} must be a non-empty string")
    return value


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` atomically (tmp file + os.replace in the same dir)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _find_task_id(store: TaskStore, payload: Mapping[str, Any]) -> str | None:
    """Resolve the serving task id by its unique payload content hash."""
    sha = canonical_payload_sha256(payload)
    for task in store.list_tasks():
        if task.payload_sha256 == sha:
            return task.task_id
    return None


def _read_holdout_exposure_count(db_path: Path, session_id: str) -> int:
    """Read the session store's holdout-exposure counter (0 when absent).

    Adapts the handler to the EXISTING service payload (no service edit): the
    counter lives in ``conversations.sqlite3`` (service-managed schema) and is
    looked up through the payload's ``session_id``.
    """
    if str(db_path) == ":memory:" or not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT count FROM holdout_exposure_count WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Older store without the table: no exposure was ever recorded.
        return 0
    finally:
        conn.close()
    return int(row[0]) if row is not None else 0


def _guard_round_clock(ledger: BudgetLedger, payload: Mapping[str, Any]) -> None:
    """Pre-run budget guard: refuse work when the round clock is spent."""
    round_id = payload.get(ROUND_ID_PAYLOAD_KEY)
    if not isinstance(round_id, str) or not round_id:
        return
    try:
        remaining = ledger.remaining_ms(round_id)
    except ValueError:
        return  # unknown round (e.g. direct submission) — nothing to guard
    if remaining <= 0:
        raise EvaluationBudgetExhaustedError(
            f"本轮墙钟预算已用尽（轮次 {round_id} 剩余 0 ms），任务拒绝执行，"
            "不得通过重开同义任务绕过。"
        )


def _record_spend(
    ledger: BudgetLedger,
    payload: Mapping[str, Any],
    kind: SpendKind,
    amount: float,
    meta: Mapping[str, Any],
) -> None:
    """Best-effort spend receipt bound to the payload's budget ids."""
    round_id = payload.get(ROUND_ID_PAYLOAD_KEY)
    if not isinstance(round_id, str) or not round_id:
        return
    raw_rid = payload.get("budget_reservation_id")
    bound = (
        raw_rid
        if isinstance(raw_rid, str) and raw_rid and ledger.reservation(raw_rid) is not None
        else None
    )
    try:
        ledger.spend(round_id, kind, amount, reservation_id=bound, meta=dict(meta))
    except ValueError as exc:
        log.warning("pipeline.budget_spend_skipped", kind=kind, error=str(exc))


# -------------------------------------------------------------------- engines


def _resolve_engine(
    ctx: HandlerContext, task_id: str | None
) -> tuple[EvidenceEngine, str, str, str | None]:
    """Select the engine per ruling 2; fall back to the reference loudly.

    Returns ``(engine, engine_kind, engine_version, fallback_reason)`` where
    ``fallback_reason`` is set only when the adapter path found no usable
    freqtrade venv and fell back to the reference ledger (a task event
    ``engine_fallback`` records it — never a silent downgrade).
    """
    selection = (ctx.engine_env or os.environ.get(ENGINE_ENV_VAR) or "adapter").strip().lower()
    if selection not in ("adapter", "reference"):
        raise EngineSelectionError(
            f"未知引擎选择 {selection!r}（{ENGINE_ENV_VAR} 必须是 'adapter' 或 'reference'）"
        )
    if selection == "reference":
        return make_reference_engine(), "reference", ENGINE_VERSION_REFERENCE, None
    try:
        ensure_freqtrade_env(ctx.venv_dir, skip_if_missing=True)
    except Exception as exc:
        reason = f"freqtrade venv unavailable ({type(exc).__name__}: {exc})"
        if task_id is not None:
            ctx.task_store.append_event(task_id, ENGINE_FALLBACK_EVENT, detail=reason[:512])
        log.warning("pipeline.engine_fallback", reason=reason)
        return make_reference_engine(), "reference", ENGINE_VERSION_REFERENCE, reason
    return make_adapter_engine(_VenvAdapter(ctx.venv_dir)), "adapter", ENGINE_VERSION_ADAPTER, None


def _cost_for(engine_kind: str) -> AppliedCost:
    """Canonical cost per engine kind (see module docstring: adapter is
    slippage-free by kernel design; the reference applies the 5bps ruling)."""
    if engine_kind == "adapter":
        return AppliedCost(fee_bps=DEFAULT_FEE_BPS, slippage_bps=ADAPTER_SLIPPAGE_BPS)
    return AppliedCost(fee_bps=DEFAULT_FEE_BPS, slippage_bps=DEFAULT_REFERENCE_SLIPPAGE_BPS)


# ---------------------------------------------------------------- bars loading


def _frame_to_bars(frame: pd.DataFrame) -> tuple[tuple[int, float, float, float, float], ...]:
    """Convert a kline frame to ``(ts, open, high, low, close)`` bar tuples."""
    if frame.empty:
        return ()
    times = frame["event_time"].tolist()
    opens = frame["open"].tolist()
    highs = frame["high"].tolist()
    lows = frame["low"].tolist()
    closes = frame["close"].tolist()
    return tuple(
        (int(ts), float(o), float(h), float(low), float(c))
        for ts, o, h, low, c in zip(times, opens, highs, lows, closes, strict=True)
    )


def _load_window_bars(
    symbol: str,
    *,
    base_path: Path,
    span_start: int,
    span_end: int,
    mock_available_at: bool,
) -> tuple[
    tuple[tuple[int, float, float, float, float], ...],
    tuple[tuple[int, float, float, float, float], ...],
    list[tuple[int, float]],
]:
    """Load 15m (resampled), 1m (raw) bars and funding events for the span.

    ``mock_available_at`` semantics follow the snapshot manifest (ruling 3):
    mock knowable-time means available_at is historically simulated and no PIT
    filter is applied; real ingestion semantics filter the load to
    ``available_at <= span_end`` (nothing knowable after the window counts).
    """
    as_of: int | None = None if mock_available_at else span_end
    bars_15m = _frame_to_bars(
        load(
            symbol,
            base_path=base_path,
            timeframe="15m",
            dataset="klines_1m",
            since=span_start,
            until=span_end,
            as_of=as_of,
        )
    )
    bars_1m = _frame_to_bars(
        load(
            symbol,
            base_path=base_path,
            timeframe="1m",
            dataset="klines_1m",
            since=span_start,
            until=span_end,
            as_of=as_of,
        )
    )
    funding_frame = load(
        symbol,
        base_path=base_path,
        timeframe="1m",
        dataset="funding",
        since=span_start,
        until=span_end,
        as_of=as_of,
    )
    funding = (
        [
            (int(row[0]), float(row[1]))
            for row in funding_frame[["event_time", "funding_rate"]].itertuples(
                index=False, name=None
            )
        ]
        if not funding_frame.empty
        else []
    )
    return bars_15m, bars_1m, funding


# ------------------------------------------------------------------- handlers


def make_handler_map(
    *,
    base_path: Path,
    state_dir: Path,
    snapshots_dir: Path,
    engine_env: str | None = None,
    venv_dir: Path | None = None,
    task_store: TaskStore | None = None,
    budget_ledger: BudgetLedger | None = None,
    conversations_db: Path | None = None,
    eval_window_days: int = EVAL_WINDOW_DAYS,
    warmup_days: int = EVAL_WARMUP_DAYS,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Build the real handler map for the runtime worker.

    Args:
        base_path: Parquet data store root (``./data`` in production).
        state_dir: Runtime state dir (``runtime.sqlite3`` / ``budget.sqlite3``
            / ``conversations.sqlite3`` live here per the service layout;
            artifacts under ``<state_dir>/runs/<run_id>/``).
        snapshots_dir: Directory for frozen snapshot manifests.
        engine_env: Explicit engine selection ("adapter" | "reference");
            ``None`` reads ``KRONOS_EVAL_ENGINE`` (default "adapter").
        venv_dir: Pinned freqtrade venv for the adapter path.
        task_store: Shared task store (default: reopen
            ``<state_dir>/runtime.sqlite3`` — used for ``engine_fallback``
            task events).
        budget_ledger: Shared budget ledger (default: reopen
            ``<state_dir>/budget.sqlite3`` — used for spend receipts).
        conversations_db: Session store path for the holdout-exposure counter
            (default ``<state_dir>/conversations.sqlite3``).
        eval_window_days: Evaluation window in complete UTC days (ruling:
            90; override for micro-window tests).
        warmup_days: Data warmup ahead of the window in UTC days (ruling:
            14; tests may override but slices need >= 12 to pre-register).
        now_ms: Pins "now" for the window (tests); default wall clock.

    Returns:
        ``{"ensure_data": ..., "evaluate_strategy": ...}`` handler map.
    """
    if eval_window_days < 2:
        raise ValueError(
            f"eval_window_days must be >= 2 (dev+holdout split), got {eval_window_days}"
        )
    if warmup_days < 0:
        raise ValueError(f"warmup_days must be >= 0, got {warmup_days}")
    resolved_state = Path(state_dir)
    ctx = HandlerContext(
        base_path=Path(base_path),
        state_dir=resolved_state,
        snapshots_dir=Path(snapshots_dir),
        engine_env=engine_env,
        venv_dir=Path(venv_dir) if venv_dir is not None else None,
        task_store=task_store or TaskStore(resolved_state / "runtime.sqlite3"),
        budget_ledger=budget_ledger or BudgetLedger(resolved_state / "budget.sqlite3"),
        conversations_db=conversations_db or resolved_state / _CONVERSATIONS_DB_FILENAME,
        eval_window_days=eval_window_days,
        warmup_days=warmup_days,
        now_ms=now_ms,
    )
    return {
        "ensure_data": _make_ensure_data(ctx),
        "evaluate_strategy": _make_evaluate_strategy(ctx),
    }


def _make_ensure_data(ctx: HandlerContext) -> Any:
    """``ensure_data``: plan -> real sync repair -> rebuild -> {plan_status, report}."""

    def ensure_data(payload: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        symbol = _required_str(payload, "symbol")
        timeframe = payload.get("timeframe")
        if timeframe is not None and timeframe not in BARS_PER_UTC_DAY:
            raise PipelineHandlerError(
                f"unsupported timeframe {timeframe!r}; valid: {sorted(BARS_PER_UTC_DAY)}"
            )
        signal_timeframe = str(timeframe or "15m")
        _guard_round_clock(ctx.budget_ledger, payload)
        window_start, window_end = resolve_window(
            now_ms_value=ctx.now_ms, eval_window_days=ctx.eval_window_days
        )
        warmup_bars = ctx.warmup_days * BARS_PER_UTC_DAY[signal_timeframe]
        plan = build_readiness_plan(
            [symbol],
            base_path=ctx.base_path,
            window_start_ms=window_start,
            window_end_ms=window_end,
            warmup_bars=warmup_bars,
            signal_timeframe=signal_timeframe,
        )
        if plan.overall_status == "blocked":
            blocked = ", ".join(
                f"{entry.symbol}/{entry.dataset}({','.join(entry.reasons)})"
                for entry in plan.entries
                if entry.status == "blocked"
            )
            raise DataNotReadyError(
                f"数据就绪计划阻塞，无法自动修复：{blocked}\n{render_readiness_report(plan)}"
            )
        # Real sync against the venue (network); tests monkeypatch the sync
        # functions in kronos.research.verdict.readiness — the ONLY mock seam.
        outcomes = apply_repair_actions(plan, base_path=ctx.base_path)
        final_plan = build_readiness_plan(
            [symbol],
            base_path=ctx.base_path,
            window_start_ms=window_start,
            window_end_ms=window_end,
            warmup_bars=warmup_bars,
            signal_timeframe=signal_timeframe,
        )
        if final_plan.overall_status == "blocked":
            raise DataNotReadyError(
                f"数据就绪计划在修复后仍阻塞：\n{render_readiness_report(final_plan)}"
            )
        _record_spend(
            ctx.budget_ledger,
            payload,
            "wall_clock_s",
            time.perf_counter() - started,
            {"task": "ensure_data", "symbol": symbol},
        )
        log.info(
            "pipeline.ensure_data_done",
            symbol=symbol,
            plan_status=final_plan.overall_status,
            repairs=len(outcomes),
        )
        return {
            "plan_status": final_plan.overall_status,
            "report": render_readiness_report(final_plan),
            "repairs_applied": len(outcomes),
            "repairs_failed": sum(1 for outcome in outcomes if outcome.status == "error"),
        }

    return ensure_data


def _make_evaluate_strategy(ctx: HandlerContext) -> Any:
    """``evaluate_strategy``: snapshot -> engine -> evidence -> verdict -> artifacts."""

    def evaluate_strategy(payload: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        session_id = _required_str(payload, "session_id")
        policy_id = payload.get("snapshot_policy")
        if policy_id is not None and policy_id != SNAPSHOT_POLICY_ID:
            raise PipelineHandlerError(
                f"unsupported snapshot_policy {policy_id!r}; this pipeline implements "
                f"{SNAPSHOT_POLICY_ID!r}"
            )
        raw_content = payload.get("spec_content")
        if not isinstance(raw_content, Mapping):
            raise PipelineHandlerError("payload field 'spec_content' must be a JSON object")
        spec = StrategySpec.model_validate(dict(raw_content))
        spec_hash = _required_str(payload, "spec_hash")
        if spec_hash != spec.spec_hash:
            raise PipelineHandlerError(
                f"payload spec_hash {spec_hash!r} does not match spec content {spec.spec_hash!r}"
            )
        # v0.5.0 boundaries (fail closed with a visible reason):
        if len(spec.symbols) > 1:
            raise PipelineHandlerError(
                f"评估仅支持单一交易对（v0.5.0 单数据系列边界），收到 {spec.symbols}"
            )
        if spec.signal_timeframe != "15m":
            raise PipelineHandlerError(
                f"评估证据链预注册在 15m（收到 {spec.signal_timeframe!r}）；"
                "1h 粗对比不在 v0.5.0 证据链内"
            )
        symbol = spec.symbols[0]

        run_id = f"eval-{session_id[:8]}-{spec_hash[:16]}"
        run_dir = ctx.state_dir / _RUNS_DIRNAME / run_id
        verdict_path = run_dir / _VERDICT_FILENAME
        meta_path = run_dir / _RUN_META_FILENAME
        payload_sha = canonical_payload_sha256(payload)

        # Idempotency (attempt >= 2 after recovery): a verdict whose recorded
        # payload hash matches means this logical task already completed.
        if verdict_path.exists() and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            if meta.get("payload_sha256") == payload_sha:
                verdict = StrategyVerdict.model_validate_json(
                    verdict_path.read_text(encoding="utf-8")
                )
                log.info("pipeline.evaluate_reused", run_id=run_id)
                return _result(
                    verdict=verdict,
                    run_id=run_id,
                    refs=dict(verdict.artifact_refs),
                    engine="cached",
                    engine_version=verdict.engine_version,
                    fallback=None,
                    reused=True,
                    backtests_used=meta.get("backtests_used"),
                    wall_clock_s=meta.get("wall_clock_s"),
                )

        _guard_round_clock(ctx.budget_ledger, payload)
        window_start, window_end = resolve_window(
            now_ms_value=ctx.now_ms, eval_window_days=ctx.eval_window_days
        )
        warmup_bars = ctx.warmup_days * BARS_PER_UTC_DAY[spec.signal_timeframe]
        plan = build_readiness_plan(
            spec.symbols,
            base_path=ctx.base_path,
            window_start_ms=window_start,
            window_end_ms=window_end,
            warmup_bars=warmup_bars,
            signal_timeframe=spec.signal_timeframe,
        )
        if plan.overall_status == "blocked":
            raise DataNotReadyError(
                f"数据就绪计划阻塞，评估拒绝执行：\n{render_readiness_report(plan)}"
            )

        # P07: build + freeze + re-verify; NEVER proceed to a verdict on
        # invalid data — the task fails with the rendered snapshot report.
        manifest = build_snapshot(plan, base_path=ctx.base_path)
        if manifest.overall_status != "valid":
            failed = sorted(gate for gate, ok in manifest.quality_checks.items() if not ok)
            raise SnapshotInvalidError(
                f"数据快照无效（质量门未通过: {', '.join(failed) or '合成数据污染'}），"
                f"拒绝评估：快照 {manifest.snapshot_id}\n{render_snapshot_report(manifest)}"
            )
        snap_path = freeze_snapshot(manifest, snapshots_dir=ctx.snapshots_dir)
        if not verify_snapshot_frozen(snap_path, base_path=ctx.base_path):
            raise SnapshotInvalidError(f"冻结快照复验失败（内容哈希不匹配或文件损坏）：{snap_path}")

        task_id = _find_task_id(ctx.task_store, payload)
        engine, engine_kind, engine_version, fallback = _resolve_engine(ctx, task_id)
        cost = _cost_for(engine_kind)
        counter = [0]

        def counting_engine(run_input: RunInput) -> ExecutionLedger:
            counter[0] += 1
            return engine(run_input)

        bars_15m, bars_1m, funding = _load_window_bars(
            symbol,
            base_path=ctx.base_path,
            span_start=plan.data_start_ms,
            span_end=plan.data_end_ms,
            mock_available_at=manifest.mock_available_at,
        )
        if not bars_15m or not bars_1m:
            raise PipelineHandlerError(
                f"快照有效但窗口内无K线（{symbol} span {plan.data_start_ms}..{plan.data_end_ms}）；"
                "拒绝在空窗口上评估"
            )

        # Dev = first 2/3 of the evaluation window, holdout = last 1/3
        # (90d window -> 60d dev + 30d holdout per the P10 ruling).
        dev_days = (ctx.eval_window_days * 2) // 3
        dev_end = window_start + dev_days * DAY_MS

        def run_input(fee_bps: float) -> RunInput:
            return RunInput(
                bars_15m=tuple(bars_15m),
                bars_1m=tuple(bars_1m),
                params=spec.params,
                fee_bps=fee_bps,
                slippage_bps=cost.slippage_bps,
                start_equity=DEFAULT_START_EQUITY,
                funding_events=tuple(funding),
                symbol=symbol,
                strategy_revision_id=spec.strategy_revision_id,
            )

        bundle = build_evidence_bundle(
            engine=counting_engine,
            bars_15m=bars_15m,
            bars_1m=bars_1m,
            params=spec.params,
            cost=cost,
            start_equity=DEFAULT_START_EQUITY,
            funding_events=funding,
            snapshot_id=manifest.snapshot_id,
            run_id=run_id,
            strategy_revision_id=spec.strategy_revision_id,
            spec_hash=spec_hash,
            dev_window_ms=(window_start, dev_end),
            holdout_window_ms=(dev_end, window_end),
            holdout_exposed_count=_read_holdout_exposure_count(ctx.conversations_db, session_id),
            symbol=symbol,
        )

        # The bundle's StressRun contract carries descriptions only, so the
        # cost_up scenario runs once more outside the builder to feed P11's
        # explicit cost_up_net_return input (same deterministic inputs).
        cost_up_ledger = counting_engine(run_input(cost.fee_bps * 2.0))
        cost_up_net_return = cost_up_ledger.final_equity / DEFAULT_START_EQUITY - 1.0
        # Ledger artifact: the center-window engine run (full span).
        center_ledger = counting_engine(run_input(cost.fee_bps))

        verdict = evaluate_verdict(
            bundle,
            VerdictPolicy(),
            run_id=run_id,
            strategy_revision_id=spec.strategy_revision_id,
            spec_hash=spec_hash,
            snapshot_id=manifest.snapshot_id,
            engine_version=engine_version,
            artifact_refs={},
            snapshot_valid=True,
            generated_at_ms=int(time.time() * 1000),
            cost_up_net_return=cost_up_net_return,
        )
        refs = {
            "snapshot": str(snap_path),
            "ledger": str(run_dir / _LEDGER_FILENAME),
            "evidence": str(run_dir / _EVIDENCE_FILENAME),
            "verdict": str(verdict_path),
        }
        verdict = verdict.model_copy(update={"artifact_refs": refs})

        _atomic_write(run_dir / _LEDGER_FILENAME, center_ledger.model_dump_json())
        _atomic_write(run_dir / _EVIDENCE_FILENAME, bundle.model_dump_json())
        _atomic_write(
            meta_path,
            json_dumps(
                {
                    "payload_sha256": payload_sha,
                    "backtests_used": counter[0],
                    "wall_clock_s": time.perf_counter() - started,
                }
            ),
        )
        # Verdict LAST: its presence implies a complete artifact set.
        _atomic_write(verdict_path, verdict.model_dump_json())

        elapsed = time.perf_counter() - started
        _record_spend(
            ctx.budget_ledger,
            payload,
            "backtest",
            float(counter[0]),
            {"run_id": run_id, "engine": engine_kind},
        )
        _record_spend(
            ctx.budget_ledger,
            payload,
            "wall_clock_s",
            elapsed,
            {"run_id": run_id},
        )
        log.info(
            "pipeline.evaluate_done",
            run_id=run_id,
            engine=engine_kind,
            engine_version=engine_version,
            evidence_status=verdict.evidence_status,
            backtests=counter[0],
            wall_clock_s=round(elapsed, 3),
        )
        return _result(
            verdict=verdict,
            run_id=run_id,
            refs=refs,
            engine=engine_kind,
            engine_version=engine_version,
            fallback=fallback,
            reused=False,
            backtests_used=counter[0],
            wall_clock_s=elapsed,
        )

    return evaluate_strategy


def _result(
    *,
    verdict: StrategyVerdict,
    run_id: str,
    refs: dict[str, str],
    engine: str,
    engine_version: str,
    fallback: str | None,
    reused: bool,
    backtests_used: int | None,
    wall_clock_s: float | None,
) -> dict[str, Any]:
    """Publishable task result (service evidence path reads verdict+refs)."""
    return {
        "verdict_path": str(refs.get("verdict", "")),
        "run_id": run_id,
        "disposition": verdict.disposition,
        "evidence_status": verdict.evidence_status,
        "verdict": verdict.model_dump(mode="json"),
        "artifact_refs": refs,
        "engine": engine,
        "engine_version": engine_version,
        "engine_fallback": fallback,
        "reused": reused,
        "backtests_used": backtests_used,
        "wall_clock_s": wall_clock_s,
        "snapshot_id": verdict.snapshot_id,
    }


def json_dumps(payload: Mapping[str, Any]) -> str:
    """Compact sorted-key JSON for run metadata files."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
