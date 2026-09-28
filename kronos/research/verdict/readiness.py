"""Data readiness planning for the v0.5.0 strategy-verdict loop (package P06).

Builds a :class:`DataReadinessPlan` for a target evaluation window (spec:
data-snapshot — 首次评估前必须产出数据就绪计划). For every symbol and dataset
(``klines_1m``, ``funding``) it measures current coverage in the local parquet
store (reusing :func:`kronos.data.storage.query.coverage`), lists missing head
/ missing tail / interior gaps against the target window (reusing
``detect_gaps`` via ``coverage``), and derives the minimal repair actions
(fetch intervals) needed to close only the gaps.

Scope boundaries:

- OI is deliberately excluded. The variant rules do not use OI, so OI never
  appears in the plan and OI data absence never blocks an evaluation (spec:
  不拉无关数据). The dataset field is typed with the frozen ``DatasetName``
  literal, which has no "oi" member by construction.
- Duplicate detection is a P07 quality-gate concern and is out of scope here.
- The plan feeds P07's ``DataSnapshotManifest``; the model lives here because
  it is intentionally NOT part of the frozen contracts module.

Documented operational constants:

- ``DEFAULT_MAX_FETCH_SPAN_DAYS = 120``: a single contiguous 1m-klines repair
  region wider than this is treated as un-repairable (e.g. a much earlier
  symbol listing or a fundamentally incomplete store) and BLOCKS the plan
  instead of issuing an unbounded download. Blocked entries contribute no
  repair actions ("修不了 → blocked + 原因, 不填平").
- ``FUNDING_MAX_FETCH_SPAN_MS = 30 days``: the Binance USDM funding-history
  endpoint serves bounded history windows, so funding repair regions are
  chunked into consecutive fetch actions of at most 30 days each.

``apply_repair_actions`` is pure orchestration over the existing sync
functions (:mod:`kronos.data.sync`); it contains no fetching logic of its own.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from kronos.common.log import get_logger
from kronos.data.storage.query import DATASET_INTERVAL_MS, TIMEFRAME_MINUTES, coverage
from kronos.data.sync import sync_funding, sync_klines
from kronos.research.verdict.contracts import (
    DatasetName,  # noqa: TC001 - pydantic resolves at runtime
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from kronos.common.types import CoverageInfo

log = get_logger("kronos.research.verdict.readiness")

DAY_MS: Final[int] = 86_400_000
MINUTE_MS: Final[int] = 60_000

# Datasets covered by the readiness plan. OI is intentionally absent (spec:
# data-snapshot — the plan must not gate first evaluation on OI).
PLAN_DATASETS: Final[tuple[DatasetName, ...]] = ("klines_1m", "funding")

# Largest single contiguous 1m-klines repair region (in days) before the plan
# is declared blocked instead of attempting the fetch.
DEFAULT_MAX_FETCH_SPAN_DAYS: Final[int] = 120

# Binance USDM funding history is served in bounded windows; funding repair
# regions are chunked to at most this span per fetch action.
FUNDING_MAX_FETCH_SPAN_MS: Final[int] = 30 * DAY_MS

type ReadinessStatus = Literal["ready", "needs_repair", "blocked"]


class RepairAction(BaseModel):
    """One fetch interval that closes a data gap (inclusive on both ends).

    ``since_ms`` is the first missing ``event_time`` and ``until_ms`` the last
    missing one; sync functions fetch forward from ``since_ms``, so the action
    may also refresh data after ``until_ms`` (harmless, dedup is keyed on
    symbol + event_time).
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str
    dataset: DatasetName
    since_ms: int = Field(description="First missing event_time (epoch-ms, inclusive).")
    until_ms: int = Field(description="Last missing event_time (epoch-ms, inclusive).")

    @property
    def span_ms(self) -> int:
        """Wall-clock width of the missing region."""
        return self.until_ms - self.since_ms


class DatasetReadiness(BaseModel):
    """Coverage status of one symbol/dataset pair against the target window."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    dataset: DatasetName
    status: ReadinessStatus
    reasons: list[str] = Field(default_factory=list)
    min_event_time: int | None = None
    max_event_time: int | None = None
    bar_count: int = Field(default=0, ge=0)
    missing_head: tuple[int, int] | None = None
    missing_tail: tuple[int, int] | None = None
    interior_gaps: list[tuple[int, int]] = Field(default_factory=list)


class DataReadinessPlan(BaseModel):
    """Readiness of the local data store for one evaluation window.

    ``data_start_ms`` / ``data_end_ms`` are the UTC-day-aligned bounds of the
    required data (target window plus warmup); all gap analysis is performed
    against these bounds. This model is owned by P06 and feeds P07's frozen
    ``DataSnapshotManifest``.
    """

    model_config = ConfigDict(extra="forbid")

    window_start_ms: int
    window_end_ms: int
    warmup_bars: int = Field(ge=0)
    signal_timeframe: str
    warmup_start_ms: int
    data_start_ms: int = Field(
        description="UTC-day-aligned start of the required data window (includes warmup).",
    )
    data_end_ms: int = Field(
        description="UTC-day-aligned exclusive end of the required data window.",
    )
    max_fetch_span_days: int = Field(ge=1)
    entries: list[DatasetReadiness] = Field(min_length=1)
    actions: list[RepairAction]
    overall_status: ReadinessStatus
    generated_at: int


class RepairOutcome(BaseModel):
    """Result of applying one :class:`RepairAction` via the sync pipeline."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    dataset: DatasetName
    since_ms: int
    until_ms: int
    status: Literal["ok", "error"]
    rows_fetched: int = Field(ge=0)
    error: str | None = None


def _day_floor(ms: int) -> int:
    """Floor an epoch-ms timestamp to the start of its UTC day."""
    return (ms // DAY_MS) * DAY_MS


def _day_ceil(ms: int) -> int:
    """Ceil an epoch-ms timestamp to the start of the next UTC day unless aligned."""
    return ((ms + DAY_MS - 1) // DAY_MS) * DAY_MS


def _repair_actions(
    symbol: str,
    dataset: DatasetName,
    regions: list[tuple[int, int]],
) -> list[RepairAction]:
    """Turn missing regions into fetch actions, chunking funding to venue limits."""
    interval = DATASET_INTERVAL_MS[dataset]
    actions: list[RepairAction] = []
    for since_ms, until_ms in regions:
        if dataset == "funding" and until_ms - since_ms >= FUNDING_MAX_FETCH_SPAN_MS:
            cursor = since_ms
            while cursor <= until_ms:
                chunk_end = min(until_ms, cursor + FUNDING_MAX_FETCH_SPAN_MS - interval)
                actions.append(
                    RepairAction(
                        symbol=symbol, dataset=dataset, since_ms=cursor, until_ms=chunk_end
                    )
                )
                cursor = chunk_end + interval
        else:
            actions.append(
                RepairAction(symbol=symbol, dataset=dataset, since_ms=since_ms, until_ms=until_ms)
            )
    return actions


def _evaluate_dataset(
    symbol: str,
    dataset: DatasetName,
    info: CoverageInfo | None,
    *,
    data_start_ms: int,
    data_end_ms: int,
    max_span_ms: int,
) -> tuple[DatasetReadiness, list[RepairAction]]:
    """Compare one symbol/dataset coverage against the required window.

    ``info is None`` (or an empty store) means the whole window is missing and
    is reported as a missing head spanning the full data window.
    """
    interval = DATASET_INTERVAL_MS[dataset]
    # Last event_time (inclusive) that must exist for full window coverage.
    last_expected = data_end_ms - interval

    missing_head: tuple[int, int] | None = None
    missing_tail: tuple[int, int] | None = None
    interior_gaps: list[tuple[int, int]] = []
    reasons: list[str] = []
    min_t: int | None = None
    max_t: int | None = None
    bar_count = 0

    if info is None or info.bar_count == 0:
        reasons.append("no_local_data")
        missing_head = (data_start_ms, last_expected)
    else:
        min_t = int(info.min_event_time)
        max_t = int(info.max_event_time)
        bar_count = int(info.bar_count)
        if min_t > data_start_ms:
            head_until = min(min_t - interval, last_expected)
            if head_until >= data_start_ms:
                missing_head = (data_start_ms, head_until)
        if max_t < last_expected:
            tail_since = max(max_t + interval, data_start_ms)
            if tail_since <= last_expected:
                missing_tail = (tail_since, last_expected)
        for gap_start, gap_end in info.gaps:
            lo = max(int(gap_start), data_start_ms)
            hi = min(int(gap_end), last_expected)
            if lo <= hi:
                interior_gaps.append((lo, hi))

    if missing_head is not None:
        reasons.append("missing_head")
    if missing_tail is not None:
        reasons.append("missing_tail")
    if interior_gaps:
        reasons.append("interior_gap")

    regions = [r for r in (missing_head, *interior_gaps, missing_tail) if r is not None]
    # Blocking condition: a single contiguous 1m-klines repair region wider
    # than max_span_ms would require an unbounded download -> refuse to fill.
    overspan = dataset == "klines_1m" and any(u - s > max_span_ms for s, u in regions)
    if overspan:
        reasons.append("repair_span_exceeds_limit")

    status: ReadinessStatus
    if overspan:
        status = "blocked"
    elif regions:
        status = "needs_repair"
    else:
        status = "ready"

    entry = DatasetReadiness(
        symbol=symbol,
        dataset=dataset,
        status=status,
        reasons=reasons,
        min_event_time=min_t,
        max_event_time=max_t,
        bar_count=bar_count,
        missing_head=missing_head,
        missing_tail=missing_tail,
        interior_gaps=interior_gaps,
    )
    # Blocked entries contribute no actions: never attempt an oversized fetch.
    actions = [] if overspan else _repair_actions(symbol, dataset, regions)
    return entry, actions


def build_readiness_plan(
    symbols: list[str],
    *,
    base_path: Path,
    window_start_ms: int,
    window_end_ms: int,
    warmup_bars: int,
    signal_timeframe: str,
    max_fetch_span_days: int = DEFAULT_MAX_FETCH_SPAN_DAYS,
) -> DataReadinessPlan:
    """Compute the data readiness plan for a target evaluation window.

    Args:
        symbols: Trading symbols to check (deduplicated, order preserved).
        base_path: Base directory of the parquet store.
        window_start_ms: Evaluation window start (epoch-ms).
        window_end_ms: Evaluation window end (epoch-ms, exclusive).
        warmup_bars: Signal-timeframe bars of warmup required before
            ``window_start_ms``.
        signal_timeframe: Timeframe the strategy signals run on
            ("1m".."1d", same vocabulary as the query layer).
        max_fetch_span_days: Blocking threshold for a single contiguous
            1m-klines repair region (default 120 days).

    Returns:
        The readiness plan: per symbol/dataset status, gap details and the
        list of repair actions (never containing OI).

    Raises:
        ValueError: On invalid window, timeframe, warmup or symbol list.
    """
    if not symbols:
        raise ValueError("symbols must not be empty")
    if window_end_ms <= window_start_ms:
        raise ValueError("window_end_ms must be after window_start_ms")
    if warmup_bars < 0:
        raise ValueError("warmup_bars must be >= 0")
    if max_fetch_span_days < 1:
        raise ValueError("max_fetch_span_days must be >= 1")
    if signal_timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(
            f"Invalid signal_timeframe: {signal_timeframe}. Valid: {sorted(TIMEFRAME_MINUTES)}"
        )

    tf_ms = TIMEFRAME_MINUTES[signal_timeframe] * MINUTE_MS
    warmup_start_ms = window_start_ms - warmup_bars * tf_ms
    data_start_ms = _day_floor(warmup_start_ms)
    data_end_ms = _day_ceil(window_end_ms)
    max_span_ms = max_fetch_span_days * DAY_MS

    entries: list[DatasetReadiness] = []
    actions: list[RepairAction] = []
    ordered_symbols = list(dict.fromkeys(symbols))
    for symbol in ordered_symbols:
        infos = coverage(symbol, base_path=base_path, datasets=["klines_1m", "funding"])
        info_by_dataset = {info.dataset: info for info in infos}
        for dataset in PLAN_DATASETS:
            entry, dataset_actions = _evaluate_dataset(
                symbol,
                dataset,
                info_by_dataset.get(dataset),
                data_start_ms=data_start_ms,
                data_end_ms=data_end_ms,
                max_span_ms=max_span_ms,
            )
            entries.append(entry)
            actions.extend(dataset_actions)

    if any(e.status == "blocked" for e in entries):
        overall: ReadinessStatus = "blocked"
    elif any(e.status == "needs_repair" for e in entries):
        overall = "needs_repair"
    else:
        overall = "ready"

    plan = DataReadinessPlan(
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        warmup_bars=warmup_bars,
        signal_timeframe=signal_timeframe,
        warmup_start_ms=warmup_start_ms,
        data_start_ms=data_start_ms,
        data_end_ms=data_end_ms,
        max_fetch_span_days=max_fetch_span_days,
        entries=entries,
        actions=actions,
        overall_status=overall,
        generated_at=int(time.time() * 1000),
    )
    log.info(
        "readiness.plan_built",
        symbols=len(ordered_symbols),
        overall_status=overall,
        actions=len(actions),
    )
    return plan


def _sync_fn_for(dataset: DatasetName) -> Callable[..., int]:
    """Resolve the sync function at call time (keeps the function monkeypatchable)."""
    if dataset == "klines_1m":
        return sync_klines
    return sync_funding


def apply_repair_actions(
    plan: DataReadinessPlan,
    *,
    base_path: Path,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> list[RepairOutcome]:
    """Execute a plan's repair actions via the existing sync functions.

    Pure orchestration: each action maps to ``sync_klines`` / ``sync_funding``
    with ``since`` set to the action's first missing event_time (the sync
    functions fetch forward from there). ``sync_oi`` is unreachable — the plan
    cannot contain OI actions by construction. Individual failures are
    captured per action (status="error") and never abort the remaining
    actions. Callers must not apply a blocked plan.

    Returns:
        One outcome per action, in action order.
    """
    outcomes: list[RepairOutcome] = []
    for action in plan.actions:
        sync_fn = _sync_fn_for(action.dataset)
        try:
            rows = sync_fn(
                action.symbol,
                base_path=base_path,
                since=action.since_ms,
                max_retries=max_retries,
                request_interval_ms=request_interval_ms,
            )
        except Exception as exc:
            outcome = RepairOutcome(
                symbol=action.symbol,
                dataset=action.dataset,
                since_ms=action.since_ms,
                until_ms=action.until_ms,
                status="error",
                rows_fetched=0,
                error=f"{type(exc).__name__}: {exc}",
            )
        else:
            outcome = RepairOutcome(
                symbol=action.symbol,
                dataset=action.dataset,
                since_ms=action.since_ms,
                until_ms=action.until_ms,
                status="ok",
                rows_fetched=int(rows),
            )
        outcomes.append(outcome)
        log.info(
            "readiness.repair_applied",
            symbol=action.symbol,
            dataset=action.dataset,
            status=outcome.status,
            rows=outcome.rows_fetched,
        )
    return outcomes


_DATASET_LABELS: Final[dict[str, str]] = {"klines_1m": "1m K线", "funding": "资金费率"}
_STATUS_LABELS: Final[dict[str, str]] = {
    "ready": "就绪",
    "needs_repair": "需修复",
    "blocked": "阻塞",
}
_REASON_LABELS: Final[dict[str, str]] = {
    "no_local_data": "无本地数据",
    "missing_head": "缺失头部",
    "missing_tail": "缺失尾部",
    "interior_gap": "内部缺口",
    "repair_span_exceeds_limit": "补拉区间超过单次上限",
}


def _fmt_ms(ms: int) -> str:
    """Format epoch-ms as a UTC 'YYYY-MM-DD HH:MM' string."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")


def _entry_detail(entry: DatasetReadiness, max_fetch_span_days: int) -> str:
    """Human-readable gap detail for one symbol/dataset entry (Chinese)."""
    interval = DATASET_INTERVAL_MS[entry.dataset]
    parts: list[str] = []
    if entry.min_event_time is not None and entry.max_event_time is not None:
        parts.append(
            f"本地 {entry.bar_count} 条"
            f"({_fmt_ms(entry.min_event_time)} ~ {_fmt_ms(entry.max_event_time)})"
        )
    else:
        parts.append("本地无数据")
    if entry.missing_head is not None:
        head_bars = (entry.missing_head[1] - entry.missing_head[0]) // interval + 1
        parts.append(f"缺头部 {head_bars} 根({_fmt_ms(entry.missing_head[0])} 起)")
    if entry.missing_tail is not None:
        tail_bars = (entry.missing_tail[1] - entry.missing_tail[0]) // interval + 1
        parts.append(f"缺尾部 {tail_bars} 根(至 {_fmt_ms(entry.missing_tail[1])})")
    if entry.interior_gaps:
        first_start, first_end = entry.interior_gaps[0]
        parts.append(
            f"内部缺口 {len(entry.interior_gaps)} 处"
            f"(首处 {_fmt_ms(first_start)} ~ {_fmt_ms(first_end)})"
        )
    has_gaps = (
        entry.missing_head is not None
        or entry.missing_tail is not None
        or bool(entry.interior_gaps)
    )
    if not has_gaps and entry.status == "ready":
        parts.append("窗口内无缺口")
    if "repair_span_exceeds_limit" in entry.reasons:
        parts.append(f"超过 {max_fetch_span_days} 天上限, 无法自动修复, 不填平")
    return " | ".join(parts)


def render_readiness_report(plan: DataReadinessPlan) -> str:
    """Render a PM-readable Chinese readiness report (one line per dataset)."""
    days = (plan.window_end_ms - plan.window_start_ms) // DAY_MS
    lines = [
        "数据就绪计划",
        f"总体状态: {_STATUS_LABELS[plan.overall_status]}",
        (
            f"目标窗口: {_fmt_ms(plan.window_start_ms)} ~ {_fmt_ms(plan.window_end_ms)} UTC"
            f"({days} 个完整 UTC 日)"
        ),
        (
            f"数据窗口(含预热): {_fmt_ms(plan.data_start_ms)} ~ {_fmt_ms(plan.data_end_ms)} UTC"
            f"(信号周期 {plan.signal_timeframe}, 预热 {plan.warmup_bars} 根,"
            f"单次补拉上限 {plan.max_fetch_span_days} 天)"
        ),
    ]
    current_symbol: str | None = None
    for entry in plan.entries:
        if entry.symbol != current_symbol:
            current_symbol = entry.symbol
            lines.append(f"—— {entry.symbol} ——")
        label = _DATASET_LABELS[entry.dataset]
        reason_txt = "、".join(_REASON_LABELS[r] for r in entry.reasons)
        reason_suffix = f" | 原因: {reason_txt}" if entry.reasons else ""
        detail = _entry_detail(entry, plan.max_fetch_span_days)
        lines.append(
            f"  {label}[{entry.dataset}]: {_STATUS_LABELS[entry.status]} | {detail}{reason_suffix}"
        )
    lines.append(
        f"修复任务: {len(plan.actions)} 个补拉区间"
        + ("(无需补拉或已阻塞)" if not plan.actions else "")
    )
    return "\n".join(lines)
