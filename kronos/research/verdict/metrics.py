"""Closed-trade metrics over an ExecutionLedger (v0.5.0 package P09).

Computes the review section 4.4 metric table (see
``docs/RELEASE_0.5.0_STRATEGY_VERDICT_LOOP.md`` section 4.4 and
``openspec/changes/p5-strategy-verdict-loop/specs/backtest-evidence/spec.md``)
from a :class:`~kronos.research.verdict.contracts.ExecutionLedger` and returns
a :class:`VerdictMetrics` whose :meth:`VerdictMetrics.to_metrics_block` fills
the frozen :class:`~kronos.research.verdict.contracts.MetricsBlock` cleanly.

Frozen conventions (review section 4.4 table + P09 dispatch brief)
-----------------------------------------------------------------
- Every trade-level metric classifies by **net** pnl (``gross - total_fees``):
  ``win = net > 0``, ``loss = net < 0``, ``tie = net == 0``.  A gross winner
  whose fees flip it negative counts on the LOSS side (spec scenario "fee
  flip").
- ``win_rate = wins / (wins + losses + ties)`` — ties explicitly count in the
  denominator.  Degenerate corner: when every closed trade tied (no decisive
  trade at all) win_rate is ``null + reason="all_ties"`` — reporting ``0.0``
  there would invite the forbidden "0% win rate = failure" reading (review
  section 4.6: never derive failure from a 0 win rate).
- ``profit_factor = sum(win net) / |sum(loss net)|``.  Zero gross loss (no
  losing trade) yields ``null + reason="no_losing_trades"`` — NEVER ``inf``
  (and never a misleading ``0``).  Ties contribute 0 to both sides.
- ``avg_win`` is the mean net pnl of winners; ``avg_loss`` is the mean net pnl
  of losers **as a negative number** (raw mean).  The review's payoff ratio
  (盈亏比, kept separate from profit factor) is derived downstream as
  ``avg_win / abs(avg_loss)``.
- ``avg_hold_bars`` is the mean ``holding_bars`` over ALL closed trades.
- ``net_return = final_equity / start_equity - 1``: costs and funding are
  already inside the ledger's equity, and an end-of-data open position is
  valued at mark by the producer (reference_ledger settles it into cash).
- ``max_drawdown`` is computed from the FULL equity series INCLUDING the
  initial capital point (``start_equity`` prepended at t0).  The block carries
  the fraction; :class:`VerdictMetrics` additionally carries the absolute
  value, the peak, the trough and the peak->trough window (review row
  "最大回撤: 峰、谷、期间和绝对/比例值").
- Zero denominators and zero trades produce
  ``MetricValue(value=None, reason=...)`` — never ``0`` and never
  ``Infinity``.  ``benchmark_return`` / ``excess_return`` are deliberately
  null here (``reason="benchmark_out_of_scope"``): hold/cash comparisons are
  owned by the evidence package (P10).
- ``sample_warning`` is left ``None``: sample-size policy belongs to the
  verdict policy (P11), not to this arithmetic module.

Extra (non-contract) figures for the evidence package (P10): exposure
fraction, turnover, total fees paid, total funding paid.  The conservation
cross-check :func:`verify_conservation` delegates to the reference ledger's
``conservation_residual`` when importable and recomputes the same identity
otherwise.
"""

from __future__ import annotations

import math
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from kronos.research.verdict.contracts import ExecutionLedger, MetricsBlock, MetricValue

__all__ = ["VerdictMetrics", "compute_verdict_metrics", "verify_conservation"]

_NO_TRADES: Final[str] = "no_trades"  # zero closed trades: every trade metric undefined
_ALL_TIES: Final[str] = "all_ties"  # no decisive trade: win_rate undefined, never 0.0
_NO_WINNING_TRADES: Final[str] = "no_winning_trades"  # empty win side of the ledger
_NO_LOSING_TRADES: Final[str] = "no_losing_trades"  # zero gross loss: PF never inf
_BENCHMARK_OUT_OF_SCOPE: Final[str] = "benchmark_out_of_scope"  # comparisons owned by P10
_NO_EQUITY_MARKS: Final[str] = "no_equity_marks"  # exposure needs an equity mark


class VerdictMetrics(BaseModel):
    """P09 metric results: the MetricsBlock fields plus drawdown/exposure extras.

    ``to_metrics_block`` projects this onto the frozen
    :class:`~kronos.research.verdict.contracts.MetricsBlock` (the extras stay
    P09-local so the shared contract never grows engine-specific fields).
    """

    model_config = ConfigDict(extra="forbid")

    # --- MetricsBlock mirror (filled cleanly by to_metrics_block) ----------
    net_return: MetricValue
    benchmark_return: MetricValue
    excess_return: MetricValue
    max_drawdown: MetricValue  # fraction; the absolute value lives below
    win_rate: MetricValue
    profit_factor: MetricValue
    trade_count: int = Field(ge=0)
    avg_hold_bars: MetricValue
    avg_win: MetricValue
    avg_loss: MetricValue  # mean net pnl of losing trades, NEGATIVE by convention
    sample_warning: str | None = None  # owned by the verdict policy (P11), left None

    # --- trade composition (audit trail for the tie/fee-flip semantics) ----
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    ties: int = Field(ge=0)

    # --- drawdown anatomy (review 4.4: peak, trough, window, absolute) -----
    max_drawdown_absolute: float = Field(
        description="peak_equity - trough_equity of the deepest peak->trough window.",
    )
    max_drawdown_peak: float
    max_drawdown_trough: float
    max_drawdown_peak_ts_ms: int = Field(
        description="Timestamp of the peak; the prepended start_equity point is stamped "
        "at the first equity mark's ts (0 when the ledger has no marks).",
    )
    max_drawdown_trough_ts_ms: int
    max_drawdown_window_ms: int = Field(
        ge=0,
        description="trough_ts_ms - peak_ts_ms of the deepest drawdown window.",
    )

    # --- exposure / turnover / cost totals (consumed by P10) ---------------
    exposure_fraction: MetricValue = Field(
        description="Share of equity-mark observations taken while a position was open.",
    )
    total_fees_paid: float = Field(
        description="Sum of fee-record fees (funding accounted separately).",
    )
    total_funding_paid: float = Field(
        description="Net funding cash outflow: -sum(signed funding impacts); negative "
        "when funding was received in net terms.",
    )
    total_fill_notional: float = Field(
        description="Sum of |qty * price| over fill records.",
    )
    turnover: float = Field(
        description="total_fill_notional / start_equity (equity basis per review 4.4).",
    )

    def to_metrics_block(self) -> MetricsBlock:
        """Project onto the frozen shared contract."""
        return MetricsBlock(
            net_return=self.net_return,
            benchmark_return=self.benchmark_return,
            excess_return=self.excess_return,
            max_drawdown=self.max_drawdown,
            win_rate=self.win_rate,
            profit_factor=self.profit_factor,
            trade_count=self.trade_count,
            avg_hold_bars=self.avg_hold_bars,
            avg_win=self.avg_win,
            avg_loss=self.avg_loss,
            sample_warning=self.sample_warning,
        )


def verify_conservation(ledger: ExecutionLedger, *, start_equity: float) -> float:
    """Return the conservation residual ``final - start - sum(closed net pnl)``.

    Delegates to the reference ledger's
    :func:`~kronos.research.verdict.reference_ledger.conservation_residual`
    (the independent arithmetic checker) and only recomputes the identical
    identity when that module is unavailable.  A ledger produced by the
    reference engine force-closes at end of data, so a healthy residual is 0
    up to float rounding; a non-zero residual must block a formal verdict
    (spec: backtest-evidence, 账本守恒).
    """
    try:
        from kronos.research.verdict.reference_ledger import conservation_residual
    except ImportError:  # pragma: no cover - reference_ledger ships in the same package
        closed_net = math.fsum(trade.net_pnl for trade in ledger.closed_trades)
        return ledger.final_equity - start_equity - closed_net
    return conservation_residual(ledger, start_equity=start_equity)


def _equity_series(ledger: ExecutionLedger, *, start_equity: float) -> list[tuple[int, float]]:
    """Full equity series as ``(ts_ms, equity)`` with the initial point prepended.

    The initial capital point sits at t0, stamped at the first equity mark's
    timestamp (0 when the ledger has no marks) so the drawdown window stays
    sortable; every record carrying an ``equity`` value is a point.
    """
    marks = [
        (record.ts_ms, record.equity) for record in ledger.records if record.equity is not None
    ]
    marks.sort(key=lambda point: point[0])  # stable: preserves intra-ts order
    t0_ts = marks[0][0] if marks else 0
    return [(t0_ts, start_equity), *marks]


def _max_drawdown(
    series: list[tuple[int, float]],
) -> tuple[float, float, float, float, int, int]:
    """Deepest peak->trough drawdown over the series.

    Returns ``(fraction, absolute, peak, trough, peak_ts, trough_ts)``.  The
    running-peak walk keeps the FIRST occurrence on exact ties (strict ``>``
    update).  ``series[0]`` is the prepended ``start_equity`` point, so a
    decline before the first mark still registers; the fraction is measured
    against the running peak (> 0 because ``start_equity > 0`` is the first
    point).
    """
    first_ts, first_equity = series[0]
    peak_ts, peak = first_ts, first_equity
    best_fraction = 0.0
    best_absolute = 0.0
    best_peak, best_peak_ts = peak, peak_ts
    best_trough, best_trough_ts = peak, peak_ts
    for ts, equity in series:
        if equity > peak:
            peak_ts, peak = ts, equity
        fraction = (peak - equity) / peak
        if fraction > best_fraction:
            best_fraction = fraction
            best_absolute = peak - equity
            best_peak, best_peak_ts = peak, peak_ts
            best_trough, best_trough_ts = equity, ts
    return (
        best_fraction,
        best_absolute,
        best_peak,
        best_trough,
        best_peak_ts,
        best_trough_ts,
    )


def _exposure_fraction(ledger: ExecutionLedger) -> MetricValue:
    """Share of equity-mark observations taken while a position was open.

    Walks the records in timestamp order (stable sort), toggling holding state
    on ``position_open`` / ``position_close`` and observing it at every
    ``equity_mark``.  Marks sharing a timestamp collapse into ONE observation
    carrying the state AFTER all same-ts events (a fill landing exactly on a
    bar close counts that bar as held).
    """
    in_position = False
    observations: list[tuple[int, bool]] = []
    for record in sorted(ledger.records, key=lambda item: item.ts_ms):
        if record.event == "position_open":
            in_position = True
        elif record.event == "position_close":
            in_position = False
        elif record.event == "equity_mark":
            if observations and observations[-1][0] == record.ts_ms:
                observations[-1] = (record.ts_ms, in_position)
            else:
                observations.append((record.ts_ms, in_position))
    if not observations:
        return MetricValue(value=None, reason=_NO_EQUITY_MARKS)
    held = sum(1 for _, is_open in observations if is_open)
    return MetricValue(value=held / len(observations), reason=None)


def compute_verdict_metrics(ledger: ExecutionLedger, *, start_equity: float) -> VerdictMetrics:
    """Compute every review-4.4 closed-trade metric from ``ledger``.

    Raises:
        ValueError: if ``start_equity`` is not strictly positive (both
            ``net_return`` and the drawdown fractions need a positive scale).
    """
    if not start_equity > 0.0:  # also rejects NaN
        raise ValueError(f"start_equity must be > 0, got {start_equity!r}")

    trades = ledger.closed_trades
    net_pnls = [trade.net_pnl for trade in trades]
    wins = [pnl for pnl in net_pnls if pnl > 0.0]
    losses = [pnl for pnl in net_pnls if pnl < 0.0]
    trade_count = len(trades)

    # --- net return (costs already inside the ledger's equity) ------------
    net_return = MetricValue(value=ledger.final_equity / start_equity - 1.0, reason=None)

    # --- benchmark pair: owned by the evidence package (P10) ---------------
    benchmark_return = MetricValue(value=None, reason=_BENCHMARK_OUT_OF_SCOPE)
    excess_return = MetricValue(value=None, reason=_BENCHMARK_OUT_OF_SCOPE)

    # --- drawdown over the full series INCLUDING the initial capital point -
    fraction, absolute, peak, trough, peak_ts, trough_ts = _max_drawdown(
        _equity_series(ledger, start_equity=start_equity)
    )

    # --- trade-level metrics (NET pnl classification; null + reason rules) --
    if trade_count == 0:
        win_rate = MetricValue(value=None, reason=_NO_TRADES)
        profit_factor = MetricValue(value=None, reason=_NO_TRADES)
        avg_win = MetricValue(value=None, reason=_NO_TRADES)
        avg_loss = MetricValue(value=None, reason=_NO_TRADES)
        avg_hold_bars = MetricValue(value=None, reason=_NO_TRADES)
    else:
        if not wins and not losses:
            # Every trade tied: a 0.0 win rate would read as "lost everything".
            win_rate = MetricValue(value=None, reason=_ALL_TIES)
        else:
            win_rate = MetricValue(value=len(wins) / trade_count, reason=None)
        gross_profit = math.fsum(wins)
        gross_loss = math.fsum(losses)  # <= 0; ties contribute exactly 0
        if gross_loss == 0.0:
            # No losing trade (all wins, or ties only): never report inf.
            profit_factor = MetricValue(value=None, reason=_NO_LOSING_TRADES)
        else:
            profit_factor = MetricValue(value=gross_profit / abs(gross_loss), reason=None)
        avg_win = (
            MetricValue(value=gross_profit / len(wins), reason=None)
            if wins
            else MetricValue(value=None, reason=_NO_WINNING_TRADES)
        )
        # Raw mean of losing net pnl: NEGATIVE by convention; the review's
        # payoff ratio is avg_win / abs(avg_loss) downstream.
        avg_loss = (
            MetricValue(value=gross_loss / len(losses), reason=None)
            if losses
            else MetricValue(value=None, reason=_NO_LOSING_TRADES)
        )
        avg_hold_bars = MetricValue(
            value=math.fsum(trade.holding_bars for trade in trades) / trade_count,
            reason=None,
        )

    # --- cost / funding / turnover totals over the raw records -------------
    total_fees = math.fsum(
        record.fee for record in ledger.records if record.event == "fee" and record.fee is not None
    )
    # Funding records carry the SIGNED cash impact in ``fee`` (reference
    # convention): paying is negative, receiving positive.  "Paid" flips sign.
    total_funding_paid = -math.fsum(
        record.fee
        for record in ledger.records
        if record.event == "funding" and record.fee is not None
    )
    total_fill_notional = math.fsum(
        abs(record.qty * record.price)
        for record in ledger.records
        if record.event == "fill" and record.qty is not None and record.price is not None
    )

    return VerdictMetrics(
        net_return=net_return,
        benchmark_return=benchmark_return,
        excess_return=excess_return,
        max_drawdown=MetricValue(value=fraction, reason=None),
        win_rate=win_rate,
        profit_factor=profit_factor,
        trade_count=trade_count,
        avg_hold_bars=avg_hold_bars,
        avg_win=avg_win,
        avg_loss=avg_loss,
        wins=len(wins),
        losses=len(losses),
        ties=trade_count - len(wins) - len(losses),
        max_drawdown_absolute=absolute,
        max_drawdown_peak=peak,
        max_drawdown_trough=trough,
        max_drawdown_peak_ts_ms=peak_ts,
        max_drawdown_trough_ts_ms=trough_ts,
        max_drawdown_window_ms=trough_ts - peak_ts,
        exposure_fraction=_exposure_fraction(ledger),
        total_fees_paid=total_fees,
        total_funding_paid=total_funding_paid,
        total_fill_notional=total_fill_notional,
        turnover=total_fill_notional / start_equity,
    )
