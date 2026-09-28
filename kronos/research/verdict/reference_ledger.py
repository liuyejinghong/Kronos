"""Explicit, dependency-light reference backtest ledger (v0.5.0 package P04).

A minimal single-position, event-driven walk over 15m bars that produces an
:class:`~kronos.research.verdict.contracts.ExecutionLedger` by direct
arithmetic.  It is the *independent* arithmetic reference for the ranking
engine in ``kronos/research/backtest/`` — that package is deliberately NOT
imported or consulted here, so a disagreement between the two is evidence of a
bug rather than a shared blind spot.

Decision math is NOT reimplemented: entry/exit/q/true-range/warmup all come
from :mod:`kronos.strategy.variant_rules` and :class:`~kronos.strategy.spec.VariantParams`.

Frozen semantics (P04 brief)
----------------------------
- Walk completed 15m bars on a UTC 96-bars/day grid.  Decisions start only
  after ``required_warmup_bars`` completed bars AND a complete previous UTC
  day exists (the pivot needs that day's H/L/C).
- ATR = simple rolling mean of true range over ``atr_period`` bars
  (``min_periods=atr_period``); the first bar's TR is ``high - low``.  An ATR
  window of zero (degenerate synthetic data) yields ``q=None`` (no decisions);
  day-end force-close still applies via :func:`evaluate_exit`.
- Per completed bar: compute ``q``; while holding, only
  :func:`evaluate_exit` applies (``is_day_end`` = this bar's close crosses the
  UTC day boundary); while flat and not day-end, :func:`evaluate_entry`
  applies.  No same-bar reversal by construction.
- Fill: signal at a bar close -> first 1m bar with ``ts >= close_ts``
  (searching forward; that is the first 1m bar of the next UTC day for a
  day-end signal).  Fill price = 1m open x (1 +/- slippage_bps/1e4); the fee
  (``fee_bps/1e4`` x notional) is charged separately at fill.  A signal whose
  fill never appears before the 1m data ends lapses: an entry opens nothing,
  an exit falls through to the end-of-data close below.  No new order is sent
  once the 1m series is exhausted, and only one order is live at a time.
- Position: ``qty = round(equity * equity_fraction / fill_price, 6)`` at
  entry, fixed while holding.  Single position, no pyramiding.
- Funding: at each funding event while holding, cash impact is
  ``-rate * qty * mark`` for longs (sign flips for shorts) with ``mark`` =
  last completed 15m close at the event time; the signed impact is attributed
  to the open trade's ``total_fees`` (funding received counts negative).
  Events while flat are ignored.
- Equity marks are appended after every fill/funding event and at every 15m
  close (``equity = cash + unrealized`` at the prevailing mark price).
- End of data with an open position: closed as ``exit_reason="end_of_data_open"``
  at the last 15m close — a mark, not an invented fill: no fill/fee records,
  no exit fee, no slippage; cash is settled at the mark so conservation holds.
- Conservation (asserted and exposed via :func:`conservation_residual`):
  ``final_equity - start_equity == sum(closed net_pnl)`` (open unrealized is
  zero at the end because the engine always force-closes).

No I/O, no clock: fully deterministic.  Plain lists/loops only.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from kronos.research.verdict.contracts import ClosedTrade, ExecutionLedger, ExecutionRecord
from kronos.strategy.variant_rules import (
    BARS_PER_UTC_DAY,
    compute_q,
    evaluate_entry,
    evaluate_exit,
    required_warmup_bars,
    true_range,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kronos.strategy.spec import VariantParams

__all__ = [
    "REFERENCE_REVISION_ID",
    "Bar",
    "CostPolicy",
    "FundingEvent",
    "conservation_residual",
    "run_reference_backtest",
]

Bar = tuple[int, float, float, float, float]
"""One OHLC bar: ``(ts_ms, open, high, low, close)``."""

FundingEvent = tuple[int, float]
"""One funding settlement: ``(ts_ms, rate)``."""

DAY_MS: Final[int] = 86_400_000
TF_MS: Final[int] = 900_000  # 15m signal timeframe
BARS_PER_DAY: Final[int] = BARS_PER_UTC_DAY["15m"]  # 96
REFERENCE_REVISION_ID: Final[str] = "reference_ledger"
_CONSERVATION_ABS_TOL: Final[float] = 1e-6

Direction = Literal["long", "short"]
_OrderKind = Literal["entry_long", "entry_short", "exit_long", "exit_short"]
_SignalExitReason = Literal["signal_exit", "day_end_flat"]


@dataclass(frozen=True)
class CostPolicy:
    """Taker cost policy: fee and slippage in basis points of notional.

    Slippage is applied to the fill price (buys pay ``open * (1 + slip)``,
    sells receive ``open * (1 - slip)``); the fee is charged separately on the
    notional at fill time.
    """

    fee_bps: float = 4.0
    slippage_bps: float = 5.0

    def __post_init__(self) -> None:
        if self.fee_bps < 0.0:
            raise ValueError(f"fee_bps must be >= 0, got {self.fee_bps}")
        if self.slippage_bps < 0.0:
            raise ValueError(f"slippage_bps must be >= 0, got {self.slippage_bps}")


@dataclass
class _DayAggregate:
    """UTC-day H/L/C aggregate built from the day's 15m bars."""

    high: float = float("-inf")
    low: float = float("inf")
    close: float = 0.0
    count: int = 0


@dataclass
class _Position:
    """Open position state; qty is fixed between entry and exit."""

    trade_id: str
    direction: Direction
    qty: float
    entry_price: float  # fill price (slippage included)
    entry_fee: float
    entry_ts_ms: int  # fill timestamp
    signal_bar_index: int  # 15m bar index whose close produced the entry signal
    funding_fees: float = 0.0  # funding fee contribution to total_fees (= -cash impact)


@dataclass
class _PendingOrder:
    """One live order awaiting its next-1m-open fill."""

    kind: _OrderKind
    signal_ts_ms: int  # close boundary of the signal bar
    signal_bar_index: int
    exit_reason: _SignalExitReason | None = None  # exits only
    q_at_signal: float | None = None


def _validate_bars(bars: Sequence[Bar], name: str) -> None:
    """Reject non-monotonic timestamps and malformed OHLC up front."""
    prev_ts: int | None = None
    for index, bar in enumerate(bars):
        ts, o, high, low, close = bar
        if ts < 0:
            raise ValueError(f"{name}[{index}]: ts_ms must be >= 0, got {ts}")
        if not (high >= low and high >= o and high >= close and low <= o and low <= close):
            raise ValueError(
                f"{name}[{index}]: malformed OHLC "
                f"(o={o}, h={high}, l={low}, c={close}); need l <= o,c <= h"
            )
        if prev_ts is not None and ts <= prev_ts:
            raise ValueError(f"{name}[{index}]: timestamps must be strictly increasing")
        prev_ts = ts


def conservation_residual(ledger: ExecutionLedger, *, start_equity: float) -> float:
    """Return ``final_equity - start_equity - sum(closed net_pnl)``.

    The reference engine always force-closes at end of data, so open
    unrealized is zero by construction and a healthy ledger has a residual of
    exactly 0 (up to float rounding).
    """
    closed_net = sum(trade.net_pnl for trade in ledger.closed_trades)
    return ledger.final_equity - start_equity - closed_net


def run_reference_backtest(
    bars_15m: Sequence[Bar],
    bars_1m: Sequence[Bar],
    *,
    params: VariantParams,
    cost: CostPolicy,
    start_equity: float = 10_000.0,
    funding_events: Sequence[FundingEvent] | None = None,
    symbol: str = "BTCUSDT",
    equity_fraction: float = 1.0,
) -> ExecutionLedger:
    """Run the explicit reference backtest and return its execution ledger.

    Args:
        bars_15m: Completed 15m bars ``(ts_ms, o, h, l, c)`` on a UTC
            96-bars/day grid, strictly ascending.
        bars_1m: Sparse 1m bars ``(ts_ms, o, h, l, c)`` used for fills,
            strictly ascending; only the open is read.
        params: Frozen decision parameters (``atr_period`,
            ``volatility_multiplier``).
        cost: Fee/slippage policy in basis points.
        start_equity: Initial cash.
        funding_events: Optional ``(ts_ms, rate)`` settlements, any order.
        symbol: Ledger symbol label.
        equity_fraction: Fraction of equity converted to qty at entry,
            in ``(0, 1]``.

    Returns:
        ExecutionLedger with the full event stream, closed trades and final
        equity.  Raises AssertionError if the conservation identity breaks.
    """
    _validate_bars(bars_15m, "bars_15m")
    _validate_bars(bars_1m, "bars_1m")
    if start_equity <= 0.0:
        raise ValueError(f"start_equity must be > 0, got {start_equity}")
    if not 0.0 < equity_fraction <= 1.0:
        raise ValueError(f"equity_fraction must be in (0, 1], got {equity_fraction}")
    if not bars_15m:
        return ExecutionLedger(
            symbol=symbol,
            strategy_revision_id=REFERENCE_REVISION_ID,
            records=[],
            final_equity=start_equity,
            closed_trades=[],
        )

    fee_rate = cost.fee_bps / 10_000.0
    slippage = cost.slippage_bps / 10_000.0
    warmup = required_warmup_bars(params.atr_period, "15m")
    funding = sorted(funding_events or [], key=lambda event: event[0])

    # --- UTC-day aggregates for pivots (previous day's H/L/C) -------------
    day_of = [bar[0] // DAY_MS for bar in bars_15m]
    day_agg: dict[int, _DayAggregate] = {}
    for index, bar in enumerate(bars_15m):
        agg = day_agg.setdefault(day_of[index], _DayAggregate())
        _o, high, low, close = bar[1], bar[2], bar[3], bar[4]
        agg.high = max(agg.high, high)
        agg.low = min(agg.low, low)
        agg.close = close
        agg.count += 1

    # --- mutable engine state ---------------------------------------------
    records: list[ExecutionRecord] = []
    trades: list[ClosedTrade] = []
    cash = start_equity
    position: _Position | None = None
    pending: _PendingOrder | None = None
    trade_seq = 0
    one_m_idx = 0  # fill-search pointer into bars_1m
    fund_idx = 0  # pointer into funding (sorted)
    mark_idx = -1  # index of the last 15m bar completed at processed event times
    tr_window: deque[float] = deque()
    tr_sum = 0.0
    prev_close: float | None = None

    def unrealized(mark: float) -> float:
        if position is None:
            return 0.0
        if position.direction == "long":
            return (mark - position.entry_price) * position.qty
        return (position.entry_price - mark) * position.qty

    def emit_equity_mark(ts_ms: int, mark: float) -> None:
        u = unrealized(mark)
        records.append(
            ExecutionRecord(
                ts_ms=ts_ms,
                event="equity_mark",
                symbol=symbol,
                price=mark,
                unrealized_pnl=u,
                equity=cash + u,
            )
        )

    def apply_funding_through(limit_ts: int) -> None:
        """Apply funding events with ts <= limit_ts under the *current* holding state.

        The mark for each event is the last 15m close completed at the event
        time.  Events while flat are ignored (no cash impact, no record).
        """
        nonlocal fund_idx, mark_idx, cash
        while fund_idx < len(funding) and funding[fund_idx][0] <= limit_ts:
            event_ts, rate = funding[fund_idx]
            fund_idx += 1
            while mark_idx + 1 < len(bars_15m) and bars_15m[mark_idx + 1][0] + TF_MS <= event_ts:
                mark_idx += 1
            if position is None or mark_idx < 0:
                continue
            mark = bars_15m[mark_idx][4]
            if position.direction == "long":
                impact = -rate * position.qty * mark
            else:
                impact = rate * position.qty * mark
            cash += impact
            # Fee contribution is the negative cash impact: a long paying
            # funding adds to total_fees, a short receiving counts negative.
            position.funding_fees -= impact
            records.append(
                ExecutionRecord(
                    ts_ms=event_ts,
                    event="funding",
                    symbol=symbol,
                    price=mark,
                    fee=impact,
                    funding_rate=rate,
                    note=f"funding_{position.direction}|{position.trade_id}",
                )
            )
            emit_equity_mark(event_ts, mark)

    def find_fill(signal_ts_ms: int) -> tuple[int, float] | None:
        """First 1m bar with ts >= signal_ts_ms as (ts, open); consumes the bar."""
        nonlocal one_m_idx
        while one_m_idx < len(bars_1m) and bars_1m[one_m_idx][0] < signal_ts_ms:
            one_m_idx += 1
        if one_m_idx >= len(bars_1m):
            return None
        fill_bar = bars_1m[one_m_idx]
        one_m_idx += 1  # each fill consumes its own 1m bar
        return fill_bar[0], fill_bar[1]

    def settle_trade(
        pos: _Position,
        exit_price: float,
        exit_ts_ms: int,
        exit_fee: float,
        exit_reason: Literal["signal_exit", "day_end_flat", "end_of_data_open"],
        exit_bar_index: int,
    ) -> None:
        """Close ``pos`` at ``exit_price``, book the trade and its records."""
        nonlocal cash, position
        if pos.direction == "long":
            gross = (exit_price - pos.entry_price) * pos.qty
            cash += pos.qty * exit_price - exit_fee
        else:
            gross = (pos.entry_price - exit_price) * pos.qty
            cash -= pos.qty * exit_price + exit_fee
        total_fees = pos.entry_fee + exit_fee + pos.funding_fees
        net = gross - total_fees
        records.append(
            ExecutionRecord(
                ts_ms=exit_ts_ms,
                event="position_close",
                symbol=symbol,
                realized_pnl=net,
                note=f"{exit_reason}|{pos.trade_id}",
            )
        )
        trades.append(
            ClosedTrade(
                trade_id=pos.trade_id,
                symbol=symbol,
                direction=pos.direction,
                entry_ts_ms=pos.entry_ts_ms,
                exit_ts_ms=exit_ts_ms,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                qty=pos.qty,
                gross_pnl=gross,
                total_fees=total_fees,
                net_pnl=net,
                holding_bars=exit_bar_index - pos.signal_bar_index,
                exit_reason=exit_reason,
            )
        )
        position = None

    def execute_order(order: _PendingOrder, fill_ts_ms: int, raw_open: float) -> None:
        """Fill ``order`` at ``raw_open`` with slippage; charge the fee separately."""
        nonlocal cash, position, trade_seq
        if order.kind == "entry_long":
            price = raw_open * (1.0 + slippage)
            qty = round(cash * equity_fraction / price, 6)
            notional = qty * price
            fee = fee_rate * notional
            cash -= notional + fee
            trade_seq += 1
            trade_id = f"{symbol}-{trade_seq:04d}"
            position = _Position(
                trade_id=trade_id,
                direction="long",
                qty=qty,
                entry_price=price,
                entry_fee=fee,
                entry_ts_ms=fill_ts_ms,
                signal_bar_index=order.signal_bar_index,
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="fill",
                    symbol=symbol,
                    side="buy",
                    qty=qty,
                    price=price,
                    note="entry_long",
                )
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="fee",
                    symbol=symbol,
                    fee=fee,
                    fee_asset="USDT",
                    note=f"entry_fee|{trade_id}",
                )
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="position_open",
                    symbol=symbol,
                    side="buy",
                    qty=qty,
                    price=price,
                    note=trade_id,
                )
            )
        elif order.kind == "entry_short":
            price = raw_open * (1.0 - slippage)
            qty = round(cash * equity_fraction / price, 6)
            notional = qty * price
            fee = fee_rate * notional
            cash += notional - fee
            trade_seq += 1
            trade_id = f"{symbol}-{trade_seq:04d}"
            position = _Position(
                trade_id=trade_id,
                direction="short",
                qty=qty,
                entry_price=price,
                entry_fee=fee,
                entry_ts_ms=fill_ts_ms,
                signal_bar_index=order.signal_bar_index,
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="fill",
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    price=price,
                    note="entry_short",
                )
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="fee",
                    symbol=symbol,
                    fee=fee,
                    fee_asset="USDT",
                    note=f"entry_fee|{trade_id}",
                )
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="position_open",
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    price=price,
                    note=trade_id,
                )
            )
        else:
            assert position is not None, "exit order without an open position"
            pos = position
            if order.kind == "exit_long":
                price = raw_open * (1.0 - slippage)
                side: Literal["buy", "sell"] = "sell"
            else:
                price = raw_open * (1.0 + slippage)
                side = "buy"
            fee = fee_rate * pos.qty * price
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="fill",
                    symbol=symbol,
                    side=side,
                    qty=pos.qty,
                    price=price,
                    note=order.kind,
                )
            )
            records.append(
                ExecutionRecord(
                    ts_ms=fill_ts_ms,
                    event="fee",
                    symbol=symbol,
                    fee=fee,
                    fee_asset="USDT",
                    note=f"exit_fee|{pos.trade_id}",
                )
            )
            assert order.exit_reason is not None, "exit order must carry an exit reason"
            settle_trade(
                pos,
                exit_price=price,
                exit_ts_ms=fill_ts_ms,
                exit_fee=fee,
                exit_reason=order.exit_reason,
                exit_bar_index=order.signal_bar_index,
            )
        emit_equity_mark(fill_ts_ms, price)

    def emit_order_record(order: _PendingOrder) -> None:
        if order.kind in ("entry_long", "exit_short"):
            side: Literal["buy", "sell"] = "buy"
        else:
            side = "sell"
        note = (
            order.kind if order.q_at_signal is None else f"{order.kind} q={order.q_at_signal:.6f}"
        )
        records.append(
            ExecutionRecord(
                ts_ms=order.signal_ts_ms,
                event="order",
                symbol=symbol,
                side=side,
                note=note,
            )
        )

    # --- main walk over completed 15m bars --------------------------------
    for index, bar in enumerate(bars_15m):
        ts, _open, high, low, close = bar
        close_ts = ts + TF_MS

        # (A) Fill the order emitted at the previous bar close.  Funding
        # events up to the fill time see the *pre-fill* holding state.
        if pending is not None:
            fill = find_fill(pending.signal_ts_ms)
            if fill is not None:
                fill_ts, raw_open = fill
                apply_funding_through(fill_ts)
                execute_order(pending, fill_ts, raw_open)
                pending = None
            else:
                # 1m data exhausted: an entry lapses, an exit falls through
                # to the end-of-data close at finalization.
                pending = None

        # (B) Funding events up to this bar close (post-fill holding state).
        apply_funding_through(close_ts)

        # (C) Equity mark at the bar close.
        emit_equity_mark(close_ts, close)

        # (D) True range / ATR / q for this completed bar.
        tr = high - low if prev_close is None else true_range(high, low, prev_close)
        tr_window.append(tr)
        tr_sum += tr
        if len(tr_window) > params.atr_period:
            tr_sum -= tr_window.popleft()
        prev_close = close
        is_day_end = (close_ts // DAY_MS) != (ts // DAY_MS)

        prev = day_agg.get(day_of[index] - 1)
        prev_day_complete = prev is not None and prev.count == BARS_PER_DAY
        q: float | None = None
        if (
            prev_day_complete
            and prev is not None
            and len(tr_window) == params.atr_period
            and tr_sum > 0.0
        ):
            atr = tr_sum / params.atr_period
            q = compute_q(
                close=close,
                prev_high=prev.high,
                prev_low=prev.low,
                prev_close=prev.close,
                atr=atr,
                volatility_multiplier=params.volatility_multiplier,
            )

        if index + 1 >= warmup and pending is None and one_m_idx < len(bars_1m):
            if position is not None:
                if evaluate_exit(q, position.direction, is_day_end):
                    reason: _SignalExitReason = "day_end_flat" if is_day_end else "signal_exit"
                    kind: _OrderKind = "exit_long" if position.direction == "long" else "exit_short"
                    pending = _PendingOrder(
                        kind=kind,
                        signal_ts_ms=close_ts,
                        signal_bar_index=index,
                        exit_reason=reason,
                        q_at_signal=q,
                    )
                    emit_order_record(pending)
            elif not is_day_end and q is not None:
                action = evaluate_entry(q, "flat")
                if action != "hold":
                    pending = _PendingOrder(
                        kind="entry_long" if action == "open_long" else "entry_short",
                        signal_ts_ms=close_ts,
                        signal_bar_index=index,
                        q_at_signal=q,
                    )
                    emit_order_record(pending)

    # --- finalization ------------------------------------------------------
    last_ts, _lo, _ho, _hi, last_close = bars_15m[-1]
    last_close_ts = last_ts + TF_MS
    if pending is not None:
        fill = find_fill(pending.signal_ts_ms)
        if fill is not None:
            fill_ts, raw_open = fill
            apply_funding_through(fill_ts)
            execute_order(pending, fill_ts, raw_open)
            pending = None
    apply_funding_through(2**62)  # remaining events under the end-state holding
    if position is not None:
        # End of data with an open position: mark closed at the last 15m
        # close.  No fill is invented: no fill/fee records, no exit fee,
        # no slippage; cash settles at the mark so conservation holds.
        pos = position
        settle_trade(
            pos,
            exit_price=last_close,
            exit_ts_ms=last_close_ts,
            exit_fee=0.0,
            exit_reason="end_of_data_open",
            exit_bar_index=len(bars_15m) - 1,
        )
    emit_equity_mark(last_close_ts, last_close)

    records.sort(key=lambda record: record.ts_ms)  # stable: keeps intra-ts order

    # --- conservation (assert + expose) ------------------------------------
    for trade in trades:
        identity_gap = abs(trade.net_pnl - (trade.gross_pnl - trade.total_fees))
        assert identity_gap <= _CONSERVATION_ABS_TOL, (
            f"trade {trade.trade_id}: net != gross - total_fees (gap={identity_gap})"
        )
    final_equity = cash
    ledger = ExecutionLedger(
        symbol=symbol,
        strategy_revision_id=REFERENCE_REVISION_ID,
        records=records,
        final_equity=final_equity,
        closed_trades=trades,
    )
    residual = conservation_residual(ledger, start_equity=start_equity)
    assert abs(residual) <= _CONSERVATION_ABS_TOL * max(1.0, abs(start_equity)), (
        f"conservation broken: residual={residual!r}"
    )
    return ledger
