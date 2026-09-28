"""EvidenceBundle builder (package P10, v0.5.0 strategy-verdict loop).

Assembles the frozen
:class:`~kronos.research.verdict.contracts.EvidenceBundle` around one engine
run: baselines (buy-and-hold vs cash), pre-registered time slices, symbol
slices, the pre-registered parameter neighborhood with activation semantics,
the dev/holdout split with exposure accounting, and the cost/delay stress
scenarios (spec: backtest-evidence; task card P10 in
``openspec/changes/p5-strategy-verdict-loop/tasks.md``).

Engines are pluggable
---------------------
``EvidenceEngine`` is any callable ``RunInput -> ExecutionLedger``.  The
reference ledger engine (P04) and the freqtrade adapter (P08) both fit:
:func:`make_reference_engine` and :func:`make_adapter_engine` wrap them and
tag the result with an engine kind.  The kind is used for exactly one
decision — whether the *delay* stress can run — and never changes any
other number.

Pre-registered rules (declared here, before results are seen)
-------------------------------------------------------------
- Time slices (rule id ``trailing_10d_vol_tercile``): the dev window is
  bucketed into ``low`` / ``mid`` / ``high`` by the *trailing 10-day
  realized vol* of each bar, where the vol of bar ``t`` is the population
  std of 15m close-to-close returns over the 10 UTC days ending exactly one
  day before ``t`` (``[t - 11d, t - 1d)``) — never future data.  The tercile
  cuts are the 1/3 and 2/3 quantiles of the same trailing-vol statistic over
  the *pre-dev* (warmup) region, so a bar's slice membership depends only on
  data at least one day older than the bar plus the frozen pre-dev cuts:
  mutating bars after ``t`` cannot change the slice of any bar at or before
  ``t``.  If the warmup region provides fewer than two valid vol values the
  window has no pre-registerable vol history and ``time_slices`` is empty
  (documented limitation, not a silent zero).  Each slice's ``trade_count``
  comes from its own engine run on ``[window_start, last member bar close)``
  (warmup carried from the full window start); a trade counts toward the
  slice whose member 15m bar contains the entry fill
  (``bucket = ((entry_ts - 1) // TF) * TF`` — exact for boundary-aligned
  fills, the shape produced by the reference engine and the golden cases).
- Neighborhood activation (conservative reading of the G09/G10 semantics):
  ``trades_changed`` is true when the grid point's dev-window trade count or
  any entry timestamp differs from the center dev run.  ``param_activated``
  is False **only** when the grid point's dev ledger AND the center dev
  ledger both have zero trades: with nothing trading anywhere, the evidence
  cannot show that the parameter entered the decision path, so claiming
  robustness would be unfounded (G09).  A point that trades identically to
  the center while other points trade keeps ``param_activated=True`` (the
  parameter demonstrably feeds |q|) but is reported through
  ``pseudo_robust_note`` as *not* robustness evidence (G10).  The contract
  validator on :class:`~kronos.research.verdict.contracts.NeighborhoodBlock`
  enforces the note whenever any point is inactive.
- Holdout: the dev run carries warmup from the full window start but its
  data ends at the dev window end; the holdout run starts flat at the
  holdout window start with fresh capital and re-accrues its own warmup, so
  no dev price information leaks into holdout decisions.  Parameters are
  never re-optimized on holdout; the frozen contract records only the split
  windows and the exposure counters.
- Baselines: ``hold_same_symbol`` buys at the first post-warmup 1m open with
  the same fee+slippage treatment as the engine (entry fill
  ``open * (1 + slippage)``, entry fee; exit at the last 15m close with an
  exit fee) and counts funding while holding (long pays each settlement,
  ``-rate * qty * last completed 15m close``).  It is computed by a small
  deterministic function here, not by an engine run, and the comparison note
  states that funding IS counted.  ``cash`` is the zero-return baseline.
- Stress: ``cost_up`` reruns the full center window with ``fee_bps``
  doubled (slippage unchanged: a slippage stress is only expressible through
  the reference engine, and the adapter rejects nonzero slippage by design).
  ``delay`` reruns the full center window with the 1m execution series
  shifted back by one 15m bar, which makes the reference fill rule pick the
  first 1m open at least one signal bar after the signal close
  (``min{t' : t' >= C}`` over ``ts - TF == min{t : t >= C + TF}`` over the
  original series — identical price selection, recorded between the signal
  close and the delayed bar's own stamp).  For an engine not tagged
  ``reference`` the delay scenario is recorded as *not run*.

Single-symbol limitation: the builder loops over symbols generically, but
v0.5.0 carries one bar series, so any symbol other than the series' own
symbol fails closed with ``ValueError``; a single-symbol input yields exactly
one symbol slice that reuses the center run (no re-run).

No I/O, no clock, no randomness: identical inputs produce a byte-identical
bundle (``model_dump_json`` equality), which the test suite pins.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import fsum, sqrt
from typing import TYPE_CHECKING, Final, Literal, Protocol

from kronos.research.verdict.backtest_adapter import BacktestCaseInput
from kronos.research.verdict.contracts import (
    Comparison,
    EvidenceBundle,
    ExecutionLedger,
    GridPoint,
    HoldoutBlock,
    MetricsBlock,
    MetricValue,
    NeighborhoodBlock,
    Slice,
    StressRun,
)
from kronos.research.verdict.metrics import compute_verdict_metrics
from kronos.research.verdict.reference_ledger import (
    BARS_PER_DAY,
    DAY_MS,
    TF_MS,
    Bar,
    CostPolicy,
    run_reference_backtest,
)
from kronos.strategy.spec import VariantParams
from kronos.strategy.variant_rules import required_warmup_bars

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "DELAY_NOT_RUN_NOTE",
    "SLICE_LABELS",
    "SLICE_RULE_ID",
    "SYMBOL_SLICE_RULE_ID",
    "AdapterLike",
    "CostPolicyLike",
    "EngineKind",
    "EvidenceEngine",
    "RunInput",
    "assign_vol_tercile_memberships",
    "build_evidence_bundle",
    "make_adapter_engine",
    "make_reference_engine",
    "tag_engine",
    "trailing_realized_vol_series",
]

_EPOCH: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)

#: Pre-registered time-slice rule recorded on every time slice.
SLICE_RULE_ID: Final[str] = "trailing_10d_vol_tercile"
#: Pre-registered symbol-slice rule recorded on every symbol slice.
SYMBOL_SLICE_RULE_ID: Final[str] = "single_symbol_universe"
#: Slice labels in canonical low..high order.
SLICE_LABELS: Final[tuple[str, str, str]] = ("low", "mid", "high")

#: Trailing realized-vol window (UTC days) and its information lag (days).
VOL_WINDOW_DAYS: Final[int] = 10
VOL_LAG_DAYS: Final[int] = 1
#: Minimum warmup vol observations required to pre-register tercile cuts.
MIN_WARMUP_VOL_VALUES: Final[int] = 2

#: Null-metric reasons for the baseline rows (never silent zeros).
BASELINE_NULL_REASON: Final[str] = "baseline_no_closed_trades"
BASELINE_SELF_REASON: Final[str] = "baseline_row_is_benchmark"
CASH_NULL_REASON: Final[str] = "cash_baseline_has_no_trades"
HOLD_NO_ENTRY_REASON: Final[str] = "hold_baseline_no_entry_fill"
HOLD_NO_POST_WARMUP_REASON: Final[str] = "hold_baseline_no_post_warmup_bar"

#: Description recorded for a delay scenario that cannot run on this engine.
DELAY_NOT_RUN_NOTE: Final[str] = (
    "delay stress requires the reference engine (delayed fills are expressed "
    "by shifting the 1m execution series, which an arbitrary engine may not "
    "honor); not run"
)

_ENGINE_KIND_ATTR: Final[str] = "__kronos_evidence_engine_kind__"

type EngineKind = Literal["reference", "adapter", "unknown"]
type FundingEvent = tuple[int, float]


class CostPolicyLike(Protocol):
    """Structural cost input: accepts the reference- and golden-case policies."""

    fee_bps: float
    slippage_bps: float


class AdapterLike(Protocol):
    """Structural adapter input: satisfied by ``StrategyBacktestAdapter``."""

    def run_backtest(
        self,
        case_input: BacktestCaseInput,
        *,
        workdir: Path | None = None,
    ) -> ExecutionLedger: ...


@dataclass(frozen=True)
class RunInput:
    """One engine invocation: bars, params, cost, capital, funding, identity."""

    bars_15m: tuple[Bar, ...]
    bars_1m: tuple[Bar, ...]
    params: VariantParams
    fee_bps: float
    slippage_bps: float
    start_equity: float
    funding_events: tuple[FundingEvent, ...]
    symbol: str = "BTCUSDT"
    equity_fraction: float = 1.0
    strategy_revision_id: str = "kronos_threshold_v1"


EvidenceEngine = Callable[[RunInput], ExecutionLedger]


def tag_engine(engine: EvidenceEngine, kind: EngineKind) -> EvidenceEngine:
    """Attach the engine-kind tag used for the delay-stress capability check."""
    setattr(engine, _ENGINE_KIND_ATTR, kind)
    return engine


def _engine_kind(engine: EvidenceEngine) -> EngineKind:
    kind = getattr(engine, _ENGINE_KIND_ATTR, "unknown")
    if kind == "reference":
        return "reference"
    if kind == "adapter":
        return "adapter"
    return "unknown"


def make_reference_engine() -> EvidenceEngine:
    """Wrap the P04 reference ledger as a tagged, delay-capable engine."""

    def engine(run_input: RunInput) -> ExecutionLedger:
        return run_reference_backtest(
            run_input.bars_15m,
            run_input.bars_1m,
            params=run_input.params,
            cost=CostPolicy(fee_bps=run_input.fee_bps, slippage_bps=run_input.slippage_bps),
            start_equity=run_input.start_equity,
            funding_events=list(run_input.funding_events),
            symbol=run_input.symbol,
            equity_fraction=run_input.equity_fraction,
        )

    return tag_engine(engine, "reference")


def make_adapter_engine(adapter: AdapterLike) -> EvidenceEngine:
    """Wrap the P08 freqtrade adapter as a tagged engine (delay not runnable)."""

    def engine(run_input: RunInput) -> ExecutionLedger:
        return adapter.run_backtest(
            BacktestCaseInput(
                bars_15m=[_tuple_bar(bar) for bar in run_input.bars_15m],
                bars_1m=[_tuple_bar(bar) for bar in run_input.bars_1m],
                funding_events=list(run_input.funding_events),
                atr_period=run_input.params.atr_period,
                volatility_multiplier=run_input.params.volatility_multiplier,
                fee_bps=run_input.fee_bps,
                slippage_bps=run_input.slippage_bps,
                start_equity=run_input.start_equity,
                equity_fraction=run_input.equity_fraction,
                symbol=run_input.symbol,
                strategy_revision_id=run_input.strategy_revision_id,
                funding_declared_absent=not run_input.funding_events,
            )
        )

    return tag_engine(engine, "adapter")


# --- small shared helpers -------------------------------------------------------


def _tuple_bar(bar: Bar) -> tuple[int, float, float, float, float]:
    return (int(bar[0]), float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4]))


def _iso_utc(ms: int) -> str:
    """Epoch-ms -> exact UTC instant string (integer arithmetic, no float drift)."""
    return (_EPOCH + timedelta(milliseconds=ms)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _max_drawdown_fraction(series: Sequence[tuple[int, float]]) -> float:
    """Deepest peak->trough fraction over ``(ts, equity)`` points (P09 convention)."""
    peak = series[0][1]
    best = 0.0
    for _ts, equity in series:
        if equity > peak:
            peak = equity
        fraction = (peak - equity) / peak
        if fraction > best:
            best = fraction
    return best


def _last_completed_close(bars_15m: Sequence[Bar], event_ts: int) -> float:
    """Close of the last 15m bar completed at ``event_ts`` (reference mark rule)."""
    mark = bars_15m[0][1]
    for bar in bars_15m:
        if bar[0] + TF_MS <= event_ts:
            mark = bar[4]
        else:
            break
    return mark


def _null_block(reason: str) -> MetricsBlock:
    """A MetricsBlock whose optional figures are all explicit null + reason."""
    return MetricsBlock(
        net_return=MetricValue(value=None, reason=reason),
        benchmark_return=MetricValue(value=None, reason=BASELINE_SELF_REASON),
        excess_return=MetricValue(value=None, reason=BASELINE_SELF_REASON),
        max_drawdown=MetricValue(value=None, reason=reason),
        win_rate=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        profit_factor=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        trade_count=0,
        avg_hold_bars=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        avg_win=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        avg_loss=MetricValue(value=None, reason=BASELINE_NULL_REASON),
    )


# --- buy-and-hold baseline (deterministic arithmetic, not an engine run) --------


def _hold_baseline_metrics(
    bars_15m: Sequence[Bar],
    bars_1m: Sequence[Bar],
    *,
    warmup_bars: int,
    fee_bps: float,
    slippage_bps: float,
    start_equity: float,
    funding_events: Sequence[FundingEvent],
) -> MetricsBlock:
    """Buy-and-hold row: entry at the first post-warmup 1m open, exit at last close.

    Same cost treatment as the engine (entry fill ``open * (1 + slippage)`` plus
    an entry fee; exit at the last 15m close plus an exit fee) and funding IS
    counted while holding (long pays ``-rate * qty * mark`` at each settlement).
    Only ``net_return`` / ``max_drawdown`` are meaningful; the closed-trade
    figures are null + reason because a baseline has no strategy round trips.
    """
    if warmup_bars >= len(bars_15m):
        return _null_block(HOLD_NO_POST_WARMUP_REASON)
    signal_close_ts = bars_15m[warmup_bars][0] + TF_MS
    entry = next((bar for bar in bars_1m if bar[0] >= signal_close_ts), None)
    if entry is None:
        return _null_block(HOLD_NO_ENTRY_REASON)

    fee_rate = fee_bps / 10_000.0
    entry_price = entry[1] * (1.0 + slippage_bps / 10_000.0)
    qty = round(start_equity / entry_price, 6)
    entry_fee = fee_rate * qty * entry_price
    entry_ts = entry[0]
    exit_close = bars_15m[-1][4]
    exit_fee = fee_rate * qty * exit_close

    funding = sorted(funding_events, key=lambda event: event[0])
    funding_paid = 0.0
    funding_marks: list[tuple[int, float]] = []
    for event_ts, rate in funding:
        if event_ts < entry_ts:
            continue
        mark = _last_completed_close(bars_15m, event_ts)
        impact = -rate * qty * mark  # long pays when rate > 0
        funding_paid += -impact
        funding_marks.append((event_ts, funding_paid))

    net = (exit_close - entry_price) * qty - entry_fee - exit_fee - funding_paid
    final_equity = start_equity + net

    # Mark-to-market equity at every 15m close from entry on, funding included.
    marks: list[tuple[int, float]] = []
    funding_idx = 0
    paid_so_far = 0.0
    for bar in bars_15m:
        close_ts = bar[0] + TF_MS
        if close_ts < entry_ts:
            continue
        while funding_idx < len(funding_marks) and funding_marks[funding_idx][0] <= close_ts:
            paid_so_far = funding_marks[funding_idx][1]
            funding_idx += 1
        equity = start_equity + (bar[4] - entry_price) * qty - entry_fee - paid_so_far
        marks.append((close_ts, equity))
    if marks:
        drawdown_series: list[tuple[int, float]] = [(marks[0][0], start_equity), *marks]
    else:
        drawdown_series = [(entry_ts, start_equity)]

    return MetricsBlock(
        net_return=MetricValue(value=final_equity / start_equity - 1.0, reason=None),
        benchmark_return=MetricValue(value=None, reason=BASELINE_SELF_REASON),
        excess_return=MetricValue(value=None, reason=BASELINE_SELF_REASON),
        max_drawdown=MetricValue(value=_max_drawdown_fraction(drawdown_series), reason=None),
        win_rate=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        profit_factor=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        trade_count=0,
        avg_hold_bars=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        avg_win=MetricValue(value=None, reason=BASELINE_NULL_REASON),
        avg_loss=MetricValue(value=None, reason=BASELINE_NULL_REASON),
    )


def _cash_baseline_metrics() -> MetricsBlock:
    """Zero-return cash row: no position, no costs, no funding."""
    return MetricsBlock(
        net_return=MetricValue(value=0.0, reason=None),
        benchmark_return=MetricValue(value=None, reason=BASELINE_SELF_REASON),
        excess_return=MetricValue(value=None, reason=BASELINE_SELF_REASON),
        max_drawdown=MetricValue(value=0.0, reason=None),
        win_rate=MetricValue(value=None, reason=CASH_NULL_REASON),
        profit_factor=MetricValue(value=None, reason=CASH_NULL_REASON),
        trade_count=0,
        avg_hold_bars=MetricValue(value=None, reason=CASH_NULL_REASON),
        avg_win=MetricValue(value=None, reason=CASH_NULL_REASON),
        avg_loss=MetricValue(value=None, reason=CASH_NULL_REASON),
    )


# --- pre-registered trailing-vol time slices ------------------------------------


def trailing_realized_vol_series(bars_15m: Sequence[Bar]) -> list[float | None]:
    """Trailing 10-day realized vol per bar, lagged one full day (never future).

    For bar ``i`` the statistic uses the 15m close-to-close simple returns of
    the bars whose close time falls in ``[ts_i - (window + lag) d, ts_i - lag d)``
    (960 closes -> 959 returns); the population std is taken with ``fsum`` so
    the result is permutation-stable to the last bit.  ``None`` when the series
    does not cover that lagged window completely.
    """
    closes = [bar[4] for bar in bars_15m]
    close_ts = [bar[0] + TF_MS for bar in bars_15m]
    window_ms = (VOL_WINDOW_DAYS + VOL_LAG_DAYS) * DAY_MS
    lag_ms = VOL_LAG_DAYS * DAY_MS
    need = VOL_WINDOW_DAYS * BARS_PER_DAY
    n_returns = need - 1

    out: list[float | None] = []
    lo = 0
    hi = 0
    for bar in bars_15m:
        start_ts = bar[0] - window_ms
        end_ts = bar[0] - lag_ms
        while lo < len(close_ts) and close_ts[lo] < start_ts:
            lo += 1
        while hi < len(close_ts) and close_ts[hi] < end_ts:
            hi += 1
        if hi - lo != need:
            out.append(None)
            continue
        returns = [closes[k + 1] / closes[k] - 1.0 for k in range(lo, hi - 1)]
        mean = fsum(returns) / n_returns
        variance = fsum((value - mean) ** 2 for value in returns) / n_returns
        out.append(sqrt(variance))
    return out


def assign_vol_tercile_memberships(
    bars_15m: Sequence[Bar],
    *,
    dev_start_ms: int,
    dev_end_ms: int,
) -> dict[str, list[int]] | None:
    """Bucket dev-window bars into low/mid/high by lagged trailing vol.

    The tercile cuts are the 1/3 and 2/3 quantiles of the trailing-vol values
    over the pre-dev region (fully available before the dev window opens), so
    membership of bar ``t`` depends only on bars at least one day older than
    ``t`` plus frozen pre-dev cuts.  Returns ``None`` when the pre-dev region
    provides fewer than two valid vol values (no pre-registerable history);
    raises ``ValueError`` when cuts exist but a dev bar lacks its lagged vol
    (an interior data gap — fail closed rather than guess).
    """
    vols = trailing_realized_vol_series(bars_15m)
    warmup_values = [
        vol
        for index, vol in enumerate(vols)
        if vol is not None and bars_15m[index][0] < dev_start_ms
    ]
    if len(warmup_values) < MIN_WARMUP_VOL_VALUES:
        return None
    ordered = sorted(warmup_values)
    cut_low = ordered[(len(ordered) - 1) // 3]
    cut_high = ordered[2 * (len(ordered) - 1) // 3]

    memberships: dict[str, list[int]] = {label: [] for label in SLICE_LABELS}
    for index, bar in enumerate(bars_15m):
        if not dev_start_ms <= bar[0] < dev_end_ms:
            continue
        vol = vols[index]
        if vol is None:
            raise ValueError(
                f"dev bar at ts={bar[0]} has no lagged {VOL_WINDOW_DAYS}-day vol: "
                "the snapshot does not cover the pre-registered slice history"
            )
        label = "low" if vol < cut_low else ("mid" if vol < cut_high else "high")
        memberships[label].append(index)
    return memberships


def _bucket_ts_of(entry_ts_ms: int) -> int:
    """15m bar-open bucket containing an entry fill (exact at bar boundaries)."""
    return ((entry_ts_ms - 1) // TF_MS) * TF_MS


# --- windowed engine runs --------------------------------------------------------


def _funding_within(
    funding_events: Sequence[FundingEvent], start_ms: int, end_ms: int
) -> list[FundingEvent]:
    return [event for event in funding_events if start_ms <= event[0] < end_ms]


def _bars_through(bars: Sequence[Bar], end_ms: int) -> list[Bar]:
    return [bar for bar in bars if bar[0] < end_ms]


def _bars_from(bars: Sequence[Bar], start_ms: int) -> list[Bar]:
    return [bar for bar in bars if bar[0] >= start_ms]


def _run_window(
    engine: EvidenceEngine,
    *,
    bars_15m: Sequence[Bar],
    bars_1m: Sequence[Bar],
    params: VariantParams,
    fee_bps: float,
    slippage_bps: float,
    start_equity: float,
    funding: Sequence[FundingEvent],
    symbol: str,
    strategy_revision_id: str,
) -> ExecutionLedger | None:
    """Run one sub-window; ``None`` when the window carries no 15m bars."""
    if not bars_15m:
        return None
    return engine(
        RunInput(
            bars_15m=tuple(_tuple_bar(bar) for bar in bars_15m),
            bars_1m=tuple(_tuple_bar(bar) for bar in bars_1m),
            params=params,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            start_equity=start_equity,
            funding_events=tuple(funding),
            symbol=symbol,
            strategy_revision_id=strategy_revision_id,
        )
    )


# --- neighborhood ----------------------------------------------------------------


def _default_grid(center: VariantParams) -> list[tuple[int, float]]:
    """Center +/- one step on ``atr_period`` and ``volatility_multiplier``.

    Steps are absolute (+/-1 bar, +/-1.0 multiplier, matching the G09/G10
    golden semantics); points outside the ``VariantParams`` domain are dropped
    and duplicates removed, in fixed scan order.
    """
    grid: list[tuple[int, float]] = []
    for d_atr in (-1, 0, 1):
        for d_mult in (-1.0, 0.0, 1.0):
            atr = center.atr_period + d_atr
            mult = center.volatility_multiplier + d_mult
            if atr < 2 or mult <= 0.0:
                continue
            point = (atr, mult)
            if point not in grid:
                grid.append(point)
    return grid


def _entry_key(ledger: ExecutionLedger) -> tuple[int, tuple[int, ...]]:
    trades = ledger.closed_trades
    return len(trades), tuple(trade.entry_ts_ms for trade in trades)


def _point_coords(point: GridPoint) -> str:
    return f"(atr_period={point.atr_period}, volatility_multiplier={point.volatility_multiplier})"


def _build_neighborhood(
    engine: EvidenceEngine,
    *,
    center_params: VariantParams,
    center_dev_ledger: ExecutionLedger,
    bars_15m: Sequence[Bar],
    bars_1m: Sequence[Bar],
    fee_bps: float,
    slippage_bps: float,
    start_equity: float,
    funding: Sequence[FundingEvent],
    symbol: str,
    strategy_revision_id: str,
    grid: Sequence[tuple[int, float]] | None,
) -> NeighborhoodBlock:
    """Pre-registered neighborhood on the dev window (center point reuses the run)."""
    points: list[GridPoint] = []
    center_key = (center_params.atr_period, center_params.volatility_multiplier)
    center_entry_key = _entry_key(center_dev_ledger)
    center_zero = len(center_dev_ledger.closed_trades) == 0

    grid_points = list(grid) if grid is not None else _default_grid(center_params)
    for atr_period, multiplier in grid_points:
        point_params = VariantParams(atr_period=atr_period, volatility_multiplier=multiplier)
        ledger: ExecutionLedger | None
        if (atr_period, multiplier) == center_key:
            ledger = center_dev_ledger
        else:
            ledger = _run_window(
                engine,
                bars_15m=bars_15m,
                bars_1m=bars_1m,
                params=point_params,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                start_equity=start_equity,
                funding=funding,
                symbol=symbol,
                strategy_revision_id=strategy_revision_id,
            )
            if ledger is None:  # pragma: no cover - dev window validated non-empty
                raise ValueError("neighborhood grid run on an empty dev window")
        changed = _entry_key(ledger) != center_entry_key
        activated = not (len(ledger.closed_trades) == 0 and center_zero)
        points.append(
            GridPoint(
                atr_period=atr_period,
                volatility_multiplier=multiplier,
                trades_changed=changed,
                param_activated=activated,
                net_pnl=ledger.final_equity - start_equity,
            )
        )

    inactive = [point for point in points if not point.param_activated]
    # The center point is trivially trade-identical to itself; only NON-center
    # points count as "changed the parameter without changing any trade".
    unchanged = [
        point
        for point in points
        if point.param_activated
        and not point.trades_changed
        and (point.atr_period, point.volatility_multiplier) != center_key
    ]
    notes: list[str] = []
    if inactive:
        coords = ", ".join(_point_coords(point) for point in inactive)
        notes.append(
            f"parameter not activated at grid point(s) {coords}: no trades at these "
            "points or at the center on the dev window, so the conservative activation "
            "rule cannot confirm the parameter entered the decision path; this must "
            "not be read as robustness."
        )
    if unchanged:
        coords = ", ".join(_point_coords(point) for point in unchanged)
        notes.append(
            f"grid point(s) {coords} changed the parameter without changing any trade: "
            "the parameter is wired into the decision path but does not move decisions "
            "here; identical trades are NOT evidence of robustness."
        )
    return NeighborhoodBlock(
        grid=points,
        pseudo_robust_note=" ".join(notes) if notes else None,
    )


# --- stress ----------------------------------------------------------------------


def _net_return_of(ledger: ExecutionLedger, start_equity: float) -> float:
    return ledger.final_equity / start_equity - 1.0


def _describe_run(ledger: ExecutionLedger, start_equity: float) -> str:
    return (
        f"{len(ledger.closed_trades)} closed trades, "
        f"net_return={_net_return_of(ledger, start_equity):.8f}"
    )


def _shift_bars_1m_for_delay(bars_1m: Sequence[Bar]) -> list[Bar]:
    """Shift the 1m series back one 15m bar (drop anything that would go negative).

    Matching ``min{t' >= C}`` over the shifted series equals
    ``min{t >= C + TF}`` over the original series, so every fill uses the first
    1m open at least one signal bar after the signal close.
    """
    return [
        (bar[0] - TF_MS, bar[1], bar[2], bar[3], bar[4]) for bar in bars_1m if bar[0] - TF_MS >= 0
    ]


# --- bundle assembly --------------------------------------------------------------


def build_evidence_bundle(
    *,
    engine: EvidenceEngine,
    bars_15m: Sequence[Bar],
    bars_1m: Sequence[Bar],
    params: VariantParams,
    cost: CostPolicyLike,
    start_equity: float,
    funding_events: Sequence[FundingEvent],
    snapshot_id: str,
    run_id: str,
    strategy_revision_id: str,
    spec_hash: str,
    dev_window_ms: tuple[int, int],
    holdout_window_ms: tuple[int, int],
    holdout_exposed_count: int,
    neighborhood_grid: Sequence[tuple[int, float]] | None = None,
    symbol: str = "BTCUSDT",
) -> EvidenceBundle:
    """Build the frozen evidence package for one evaluation run.

    Every engine invocation goes through ``engine`` (reference engine or P08
    adapter — never hardcoded).  Deterministic: the same inputs yield a
    byte-identical bundle.

    Raises:
        ValueError: on malformed identifiers, overlapping/misordered windows,
            a dev window without bars, or a dev bar missing its lagged vol
            history while cuts exist.
    """
    for name, value in (
        ("run_id", run_id),
        ("strategy_revision_id", strategy_revision_id),
        ("snapshot_id", snapshot_id),
        ("spec_hash", spec_hash),
        ("symbol", symbol),
    ):
        if not value or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not start_equity > 0.0:
        raise ValueError(f"start_equity must be > 0, got {start_equity!r}")
    if holdout_exposed_count < 0:
        raise ValueError(f"holdout_exposed_count must be >= 0, got {holdout_exposed_count!r}")
    if not bars_15m:
        raise ValueError("bars_15m must not be empty")
    dev_start, dev_end = dev_window_ms
    holdout_start, holdout_end = holdout_window_ms
    if not dev_start < dev_end:
        raise ValueError(f"dev window must satisfy start < end, got {dev_window_ms!r}")
    if not holdout_start < holdout_end:
        raise ValueError(f"holdout window must satisfy start < end, got {holdout_window_ms!r}")
    if dev_end > holdout_start:
        raise ValueError(
            f"dev window must not overlap the holdout window (dev_end={dev_end} > "
            f"holdout_start={holdout_start})"
        )
    if dev_start < bars_15m[0][0]:
        raise ValueError(
            f"dev window starts before the bar series (dev_start={dev_start} < "
            f"first bar ts={bars_15m[0][0]}); the dev run needs its warmup carried "
            "from the full window start"
        )
    if not any(dev_start <= bar[0] < dev_end for bar in bars_15m):
        raise ValueError("dev window contains no 15m bars")
    # spec_hash binds the bundle to the judged revision for the verdict layer
    # (P11); the frozen EvidenceBundle contract carries only strategy_revision_id.
    _ = spec_hash

    funding = sorted(funding_events, key=lambda event: event[0])
    fee_bps = float(cost.fee_bps)
    slippage_bps = float(cost.slippage_bps)

    # 1. Center run: full window, center params, P09 metrics.
    center_ledger = _run_window(
        engine,
        bars_15m=bars_15m,
        bars_1m=bars_1m,
        params=params,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        funding=funding,
        symbol=symbol,
        strategy_revision_id=strategy_revision_id,
    )
    if center_ledger is None:  # pragma: no cover - guarded above
        raise ValueError("center window is empty")
    metrics = compute_verdict_metrics(center_ledger, start_equity=start_equity).to_metrics_block()

    # 2. Baselines (deterministic arithmetic, never engine runs).
    hold_metrics = _hold_baseline_metrics(
        bars_15m,
        bars_1m,
        warmup_bars=required_warmup_bars(params.atr_period, "15m"),
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        funding_events=funding,
    )
    comparisons = [
        Comparison(
            baseline="hold_same_symbol",
            note=(
                "buy-and-hold same-symbol baseline: entry at the first post-warmup 1m "
                "open with entry fee and slippage, exit at the last 15m close with an "
                "exit fee; funding IS counted while holding (long pays each settlement "
                "at its mark)"
            ),
            metrics=hold_metrics,
        ),
        Comparison(
            baseline="cash",
            note="cash baseline: no position held; zero return, zero costs, no funding.",
            metrics=_cash_baseline_metrics(),
        ),
    ]

    # 3. Pre-registered time slices (lagged info only); empty when the window
    # has no pre-registerable vol history.
    time_slices: list[Slice] = []
    memberships = assign_vol_tercile_memberships(
        bars_15m, dev_start_ms=dev_start, dev_end_ms=dev_end
    )
    if memberships is not None:
        for label in SLICE_LABELS:
            members = memberships[label]
            if not members:
                time_slices.append(
                    Slice(
                        rule_id=SLICE_RULE_ID,
                        label=label,
                        sample_bars=0,
                        trade_count=0,
                    )
                )
                continue
            slice_end = max(bars_15m[index][0] for index in members) + TF_MS
            ledger = _run_window(
                engine,
                bars_15m=_bars_through(bars_15m, slice_end),
                bars_1m=_bars_through(bars_1m, slice_end),
                params=params,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                start_equity=start_equity,
                funding=_funding_within(funding, bars_15m[0][0], slice_end),
                symbol=symbol,
                strategy_revision_id=strategy_revision_id,
            )
            trades = ledger.closed_trades if ledger is not None else []
            member_ts = {bars_15m[index][0] for index in members}
            trade_count = sum(
                1 for trade in trades if _bucket_ts_of(trade.entry_ts_ms) in member_ts
            )
            time_slices.append(
                Slice(
                    rule_id=SLICE_RULE_ID,
                    label=label,
                    sample_bars=len(members),
                    trade_count=trade_count,
                )
            )

    # 4. Symbol slices: generic loop; a single-symbol input reuses the center
    # run for its own symbol, any other symbol fails closed (one bar series).
    symbol_slices = [
        Slice(
            rule_id=SYMBOL_SLICE_RULE_ID,
            label=symbol,
            sample_bars=len(bars_15m),
            trade_count=metrics.trade_count,
        )
    ]

    # 5. Neighborhood on the dev window (warmup carried from the window start).
    dev_bars_15m = _bars_through(bars_15m, dev_end)
    dev_bars_1m = _bars_through(bars_1m, dev_end)
    dev_ledger = _run_window(
        engine,
        bars_15m=dev_bars_15m,
        bars_1m=dev_bars_1m,
        params=params,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        funding=_funding_within(funding, bars_15m[0][0], dev_end),
        symbol=symbol,
        strategy_revision_id=strategy_revision_id,
    )
    if dev_ledger is None:  # pragma: no cover - validated above
        raise ValueError("dev window is empty")
    neighborhood = _build_neighborhood(
        engine,
        center_params=params,
        center_dev_ledger=dev_ledger,
        bars_15m=dev_bars_15m,
        bars_1m=dev_bars_1m,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        funding=_funding_within(funding, bars_15m[0][0], dev_end),
        symbol=symbol,
        strategy_revision_id=strategy_revision_id,
        grid=neighborhood_grid,
    )

    # 6. Holdout: split record only (windows + exposure); the holdout run uses
    # center params, starts flat with fresh capital, and never re-optimizes.
    holdout_bars_15m = _bars_from(bars_15m, holdout_start)
    holdout_bars_1m = _bars_from(bars_1m, holdout_start)
    _run_window(
        engine,
        bars_15m=holdout_bars_15m,
        bars_1m=holdout_bars_1m,
        params=params,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        funding=_funding_within(funding, holdout_start, holdout_end),
        symbol=symbol,
        strategy_revision_id=strategy_revision_id,
    )
    holdout = HoldoutBlock(
        dev_window=f"{_iso_utc(dev_start)}..{_iso_utc(dev_end)}",
        holdout_window=f"{_iso_utc(holdout_start)}..{_iso_utc(holdout_end)}",
        exposed_count=holdout_exposed_count,
        exposed=holdout_exposed_count > 0,
    )

    # 7. Stress scenarios on the full center window.
    cost_up_fee = fee_bps * 2.0
    cost_up_ledger = _run_window(
        engine,
        bars_15m=bars_15m,
        bars_1m=bars_1m,
        params=params,
        fee_bps=cost_up_fee,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        funding=funding,
        symbol=symbol,
        strategy_revision_id=strategy_revision_id,
    )
    assert cost_up_ledger is not None  # same non-empty window as the center run
    stress: list[StressRun] = [
        StressRun(
            kind="cost_up",
            description=(
                f"cost_up stress: fee_bps doubled from {fee_bps} to {cost_up_fee} on the "
                "full center window (slippage unchanged; a slippage stress is only "
                f"expressible through the reference engine); {_describe_run(cost_up_ledger, start_equity)}"
            ),
        )
    ]
    if _engine_kind(engine) == "reference":
        delay_bars_1m = _shift_bars_1m_for_delay(bars_1m)
        delay_ledger = _run_window(
            engine,
            bars_15m=bars_15m,
            bars_1m=delay_bars_1m,
            params=params,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            start_equity=start_equity,
            funding=funding,
            symbol=symbol,
            strategy_revision_id=strategy_revision_id,
        )
        assert delay_ledger is not None
        stress.append(
            StressRun(
                kind="delay",
                description=(
                    "delay stress: every 1m fill opportunity shifted one 15m bar later "
                    "(a fill uses the first 1m open at least one signal bar after the "
                    f"signal close); {_describe_run(delay_ledger, start_equity)}"
                ),
            )
        )
    else:
        stress.append(StressRun(kind="delay", description=DELAY_NOT_RUN_NOTE))

    # 8. Assemble; pydantic validators enforce the frozen contract on the way out.
    return EvidenceBundle(
        run_id=run_id,
        strategy_revision_id=strategy_revision_id,
        snapshot_id=snapshot_id,
        metrics=metrics,
        comparisons=comparisons,
        time_slices=time_slices,
        symbol_slices=symbol_slices,
        neighborhood=neighborhood,
        holdout=holdout,
        stress=stress,
    )
