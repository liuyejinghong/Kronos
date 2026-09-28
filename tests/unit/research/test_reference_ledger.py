"""Micro-scenario tests for the P04 reference ledger (explicit arithmetic).

Every scenario is built from tiny inline bar arrays; every asserted number is
derived by hand in the comments (fee 4 bps, slippage 5 bps -> buy fill
``open * 1.0005``, sell fill ``open * 0.9995``).  Decision params for all
scenarios: ``atr_period=2``, ``volatility_multiplier=1.0`` (warmup = 96 + 2
= 98 completed bars).

Canonical bar shapes (all keep TR > 0 so ATR never degenerates):

- ``_saw(day, slot, p)``    = (p, p+1, p-1, p)      -> interior TR = 2
- ``_spike_up(day, slot)``  = (103, 104, 102, 103)  -> TR = 4 after a 100 close
- ``_crash(day, slot)``     = (90, 91, 89, 90)      -> TR = 14 after a 103 close

Day 0 is always 96 saw bars at 100: H=101, L=99, C=100 -> pivot = 100, and the
ATR window is full of 2s from bar 1 onward.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kronos.research.verdict.reference_ledger import (
    Bar,
    CostPolicy,
    conservation_residual,
    run_reference_backtest,
)
from kronos.strategy.spec import VariantParams

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from kronos.research.verdict.contracts import ExecutionLedger, ExecutionRecord

DAY_MS = 86_400_000
TF_MS = 900_000

PARAMS = VariantParams(atr_period=2, volatility_multiplier=1.0)
COST = CostPolicy()  # fee_bps=4, slippage_bps=5

# Canonical timestamps
D1_S1_CLOSE = DAY_MS + 2 * TF_MS  # day-1 slot-1 bar close (first decision bar)
D1_S2_CLOSE = DAY_MS + 3 * TF_MS  # day-1 slot-2 bar close
D2_START = 2 * DAY_MS  # first 1m bar open of UTC day 2
FUNDING_TS = DAY_MS + 2 * TF_MS + 300_000  # inside day-1 slot 2


def _bar(day: int, slot: int, o: float, h: float, low: float, c: float) -> Bar:
    return (day * DAY_MS + slot * TF_MS, o, h, low, c)


def _saw(day: int, slot: int, price: float = 100.0) -> Bar:
    return _bar(day, slot, price, price + 1.0, price - 1.0, price)


def _spike_up(day: int, slot: int) -> Bar:
    return _bar(day, slot, 103.0, 104.0, 102.0, 103.0)


def _spike_down(day: int, slot: int) -> Bar:
    return _bar(day, slot, 97.0, 98.0, 96.0, 97.0)


def _crash(day: int, slot: int) -> Bar:
    return _bar(day, slot, 90.0, 91.0, 89.0, 90.0)


def _day0() -> list[Bar]:
    return [_saw(0, slot) for slot in range(96)]


def _one_m(day: int, slot: int, offset_ms: int = 0, price: float = 100.0) -> Bar:
    return (day * DAY_MS + slot * TF_MS + offset_ms, price, price, price, price)


def _run(
    bars_15m: Sequence[Bar],
    bars_1m: Sequence[Bar],
    *,
    start_equity: float = 10_000.0,
    funding_events: Sequence[tuple[int, float]] | None = None,
) -> ExecutionLedger:
    return run_reference_backtest(
        bars_15m,
        bars_1m,
        params=PARAMS,
        cost=COST,
        start_equity=start_equity,
        funding_events=funding_events,
    )


def _events(ledger: ExecutionLedger, event: str) -> list[ExecutionRecord]:
    return [record for record in ledger.records if record.event == event]


def _assert_conservation(ledger: ExecutionLedger, start_equity: float) -> None:
    residual = conservation_residual(ledger, start_equity=start_equity)
    assert abs(residual) <= 1e-6, f"conservation residual {residual}"


def _long_entry_bars() -> list[Bar]:
    """Day 0 + day-1 slot 0 saw, slot 1 spike up (entry long), slot 2 dip.

    q(idx96) = (100 - 100) / 2 = 0            -> hold (flat)
    q(idx97) = (103 - 100) / ((2 + 4) / 2) = 1.0  -> open_long (threshold inclusive)
    q(idx98) = (99 - 100) / ((4 + 5) / 2) = -2/9  -> long exit (q <= 0)
    """
    return [*_day0(), _saw(1, 0), _spike_up(1, 1), _bar(1, 2, 99.0, 100.0, 98.0, 99.0)]


def test_warmup_gates_first_decision() -> None:
    # slot 0 (idx96, 97 completed bars < 98 warmup): q = (103-100)/((2+4)/2) = 1.0
    # would fire, but warmup blocks it.  slot 1 (idx97, 98 bars): fires.
    bars = [*_day0(), _spike_up(1, 0), _spike_up(1, 1)]
    ledger = _run(bars, [_one_m(1, 2)])

    orders = _events(ledger, "order")
    assert len(orders) == 1
    assert orders[0].ts_ms == D1_S1_CLOSE  # first possible decision bar close
    assert all(record.ts_ms >= D1_S1_CLOSE for record in ledger.records if record.event == "order")
    fills = _events(ledger, "fill")
    assert len(fills) == 1 and fills[0].ts_ms == D1_S1_CLOSE
    # 1m data is exhausted after the entry fill, so the position is mark-closed.
    assert ledger.closed_trades[0].exit_reason == "end_of_data_open"
    _assert_conservation(ledger, 10_000.0)


def test_long_round_trip_exact_fees() -> None:
    # start_equity = 10005 so qty is exactly 100:
    #   entry fill = 1m open 100 * 1.0005 = 100.05; qty = 10005 / 100.05 = 100
    #   entry fee  = 0.0004 * (100 * 100.05) = 4.002;  cash = -4.002
    #   exit fill  = 1m open 100 * 0.9995 = 99.95
    #   exit fee   = 0.0004 * (100 * 99.95) = 3.998;  cash = -4.002 + 9995 - 3.998 = 9987
    #   gross = (99.95 - 100.05) * 100 = -10;  fees = 8;  net = -18;  final = 9987
    bars = _long_entry_bars()
    ledger = _run(bars, [_one_m(1, 2), _one_m(1, 3)], start_equity=10_005.0)

    assert len(ledger.closed_trades) == 1
    trade = ledger.closed_trades[0]
    assert trade.direction == "long"
    assert trade.qty == 100.0
    assert trade.entry_price == pytest.approx(100.05, abs=1e-9)
    assert trade.exit_price == pytest.approx(99.95, abs=1e-9)
    assert trade.entry_ts_ms == D1_S1_CLOSE
    assert trade.exit_ts_ms == D1_S2_CLOSE
    assert trade.holding_bars == 1  # exit signal bar 98 - entry signal bar 97
    assert trade.exit_reason == "signal_exit"
    assert trade.gross_pnl == pytest.approx(-10.0, abs=1e-6)
    assert trade.total_fees == pytest.approx(8.0, abs=1e-6)
    assert trade.net_pnl == pytest.approx(-18.0, abs=1e-6)
    assert ledger.final_equity == pytest.approx(9987.0, abs=1e-6)
    fees = _events(ledger, "fee")
    assert [round(fee.fee, 6) for fee in fees] == pytest.approx([4.002, 3.998], abs=1e-6)
    _assert_conservation(ledger, 10_005.0)


def test_short_entry_threshold_inclusive_exact_fees() -> None:
    # Day-1 slot 1 spike down (97, 98, 96, 97) after a 100 close:
    #   TR = max(2, |98-100|, |96-100|) = 4 -> ATR = (2 + 4)/2 = 3
    #   q = (97 - 100) / 3 = -1.0 -> open_short (threshold inclusive)
    # Day-1 slot 2 (101, 102, 100, 101): TR = max(2, 5, 3) = 5 -> ATR = 4.5
    #   q = (101 - 100) / 4.5 > 0 -> short exit (q >= 0)
    # start_equity = 9995 so qty = 9995 / 99.95 = 100 exactly:
    #   entry sell fill = 100 * 0.9995 = 99.95, fee = 0.0004 * 9995 = 3.998
    #   exit buy fill  = 100 * 1.0005 = 100.05, fee = 0.0004 * 10005 = 4.002
    #   gross = (99.95 - 100.05) * 100 = -10;  fees = 8;  net = -18;  final = 9977
    bars = [*_day0(), _saw(1, 0), _spike_down(1, 1), _bar(1, 2, 101.0, 102.0, 100.0, 101.0)]
    ledger = _run(bars, [_one_m(1, 2), _one_m(1, 3)], start_equity=9_995.0)

    trade = ledger.closed_trades[0]
    assert trade.direction == "short"
    assert trade.qty == 100.0
    assert trade.entry_price == pytest.approx(99.95, abs=1e-9)
    assert trade.exit_price == pytest.approx(100.05, abs=1e-9)
    assert trade.exit_reason == "signal_exit"
    assert trade.gross_pnl == pytest.approx(-10.0, abs=1e-6)
    assert trade.total_fees == pytest.approx(8.0, abs=1e-6)
    assert trade.net_pnl == pytest.approx(-18.0, abs=1e-6)
    assert ledger.final_equity == pytest.approx(9977.0, abs=1e-6)
    _assert_conservation(ledger, 9_995.0)


def test_day_end_flat_exit_fills_at_next_day_first_1m_open() -> None:
    # Entry long at idx97 (q = 1.0); saw-101 bars keep q = (101-100)/ATR > 0 so the
    # position survives until the day-end bar (idx191) force-closes it; the exit
    # fills at the FIRST 1m bar open of UTC day 2 (ts = 2*DAY).
    bars = _day0() + [_saw(1, 0), _spike_up(1, 1)] + [_saw(1, slot, 101.0) for slot in range(2, 96)]
    ledger = _run(bars, [_one_m(1, 2), _one_m(2, 0)], start_equity=10_005.0)

    trade = ledger.closed_trades[0]
    assert trade.exit_reason == "day_end_flat"
    assert trade.exit_ts_ms == D2_START  # first 1m bar of the next UTC day
    assert trade.holding_bars == 191 - 97  # exit signal bar - entry signal bar
    assert trade.net_pnl == pytest.approx(-18.0, abs=1e-6)
    _assert_conservation(ledger, 10_005.0)


def test_no_entry_on_day_end_bar_even_when_threshold_fires() -> None:
    # All of day 1 is saw (q = 0, no signal); the day-end bar spikes to close 105:
    #   TR = max(2, |106-100|, |104-100|) = 6 -> ATR = (2 + 6)/2 = 4
    #   q = (105 - 100) / 4 = 1.25 >= 1, but entries never fire on a day-end bar.
    bars = (
        _day0() + [_saw(1, slot) for slot in range(95)] + [_bar(1, 95, 105.0, 106.0, 104.0, 105.0)]
    )
    ledger = _run(bars, [_one_m(2, 0)], start_equity=10_005.0)

    assert _events(ledger, "order") == []
    assert ledger.closed_trades == []
    assert ledger.final_equity == pytest.approx(10_005.0, abs=1e-9)
    _assert_conservation(ledger, 10_005.0)


def test_no_same_bar_reversal_on_exit_bar() -> None:
    # Entry long at idx97 (q = 1.0).  idx98 crash (90, 91, 89, 90):
    #   TR = max(2, |91-103|, |89-103|) = 14 -> ATR = (4 + 14)/2 = 9
    #   q = (90 - 100) / 9 = -1.111 <= 0  -> long exit, AND q <= -1 would open a
    #   short if same-bar reversal were allowed.  Only the exit order may appear.
    bars = [*_day0(), _saw(1, 0), _spike_up(1, 1), _crash(1, 2)]
    ledger = _run(bars, [_one_m(1, 2), _one_m(1, 3)], start_equity=10_005.0)

    orders = _events(ledger, "order")
    assert [(order.ts_ms, order.side) for order in orders] == [
        (D1_S1_CLOSE, "buy"),
        (D1_S2_CLOSE, "sell"),
    ]
    assert len(ledger.closed_trades) == 1
    assert ledger.closed_trades[0].direction == "long"
    assert ledger.closed_trades[0].exit_reason == "signal_exit"
    _assert_conservation(ledger, 10_005.0)


def test_funding_applied_once_while_long() -> None:
    # Same round trip as test_long_round_trip_exact_fees plus one funding event
    # at DAY+2TF+5min (inside slot 2).  Mark = last completed 15m close = the
    # slot-1 bar close 103.  Impact = -0.0001 * 100 * 103 = -1.03 (long pays).
    #   total_fees = 4.002 + 3.998 + 1.03 = 9.03;  net = -10 - 9.03 = -19.03
    #   final = 10005 - 19.03 = 9985.97
    bars = _long_entry_bars()
    ledger = _run(
        bars,
        [_one_m(1, 2), _one_m(1, 3)],
        start_equity=10_005.0,
        funding_events=[(FUNDING_TS, 0.0001)],
    )

    funding_records = _events(ledger, "funding")
    assert len(funding_records) == 1  # applied exactly once across settlement
    assert funding_records[0].fee == pytest.approx(-1.03, abs=1e-9)
    assert funding_records[0].price == pytest.approx(103.0, abs=1e-9)
    assert funding_records[0].funding_rate == pytest.approx(0.0001, abs=1e-15)
    trade = ledger.closed_trades[0]
    assert trade.total_fees == pytest.approx(9.03, abs=1e-6)
    assert trade.net_pnl == pytest.approx(-19.03, abs=1e-6)
    assert ledger.final_equity == pytest.approx(9985.97, abs=1e-6)
    _assert_conservation(ledger, 10_005.0)


def test_funding_zero_when_flat() -> None:
    # Two quiet days (q = 0 everywhere, no trades): funding events must be
    # ignored entirely while flat - no records, no cash impact.
    bars = _day0() + [_saw(1, slot) for slot in range(96)]
    ledger = _run(
        bars,
        [],
        funding_events=[(DAY_MS + 3_600_000, 0.0001), (DAY_MS + 43_200_000, -0.0002)],
    )

    assert _events(ledger, "funding") == []
    assert ledger.closed_trades == []
    assert ledger.final_equity == pytest.approx(10_000.0, abs=1e-9)
    _assert_conservation(ledger, 10_000.0)


def test_funding_short_receives_sign_flip() -> None:
    # Short scenario (see test_short_entry_threshold_inclusive_exact_fees) with
    # one funding event; mark = slot-1 close 97.  A short RECEIVES with a
    # positive rate: impact = +0.0001 * 100 * 97 = +0.97 (counts negative fee).
    #   total_fees = 3.998 + 4.002 - 0.97 = 7.03;  net = -10 - 7.03 = -17.03
    #   final = 9995 - 17.03 = 9977.97
    bars = [*_day0(), _saw(1, 0), _spike_down(1, 1), _bar(1, 2, 101.0, 102.0, 100.0, 101.0)]
    ledger = _run(
        bars,
        [_one_m(1, 2), _one_m(1, 3)],
        start_equity=9_995.0,
        funding_events=[(FUNDING_TS, 0.0001)],
    )

    funding_records = _events(ledger, "funding")
    assert len(funding_records) == 1
    assert funding_records[0].fee == pytest.approx(0.97, abs=1e-9)
    trade = ledger.closed_trades[0]
    assert trade.total_fees == pytest.approx(7.03, abs=1e-6)
    assert trade.net_pnl == pytest.approx(-17.03, abs=1e-6)
    assert ledger.final_equity == pytest.approx(9977.97, abs=1e-6)
    _assert_conservation(ledger, 9_995.0)


def test_end_of_data_open_exit_signal_unfillable() -> None:
    # Entry fills, then the slot-2 dip (q = -2/9 <= 0) fires an exit, but no 1m
    # bar exists after the entry fill: the close is a MARK at the last 15m
    # close 99 - no invented fill, no exit fee, no slippage.
    #   gross = (99 - 100.05) * 100 = -105;  fees = 4.002;  net = -109.002
    #   final = 10005 - 109.002 = 9895.998
    bars = _long_entry_bars()
    ledger = _run(bars, [_one_m(1, 2)], start_equity=10_005.0)

    assert len(_events(ledger, "fill")) == 1  # entry only, no invented exit fill
    assert len(_events(ledger, "fee")) == 1  # entry fee only
    trade = ledger.closed_trades[0]
    assert trade.exit_reason == "end_of_data_open"
    assert trade.exit_ts_ms == D1_S2_CLOSE
    assert trade.exit_price == pytest.approx(99.0, abs=1e-9)
    assert trade.total_fees == pytest.approx(4.002, abs=1e-6)
    assert trade.net_pnl == pytest.approx(-109.002, abs=1e-6)
    assert ledger.final_equity == pytest.approx(9895.998, abs=1e-6)
    _assert_conservation(ledger, 10_005.0)


def test_end_of_data_open_without_exit_signal() -> None:
    # Position still open (q = 1/3.5 > 0 on the last bar) when data ends mid-day:
    # mark-closed at the last 15m close 101.
    #   gross = (101 - 100.05) * 100 = 95;  fees = 4.002;  net = 90.998
    bars = [*_day0(), _saw(1, 0), _spike_up(1, 1), _bar(1, 2, 101.0, 102.0, 100.0, 101.0)]
    ledger = _run(bars, [_one_m(1, 2)], start_equity=10_005.0)

    trade = ledger.closed_trades[0]
    assert trade.exit_reason == "end_of_data_open"
    assert trade.exit_price == pytest.approx(101.0, abs=1e-9)
    assert trade.holding_bars == 1
    assert trade.net_pnl == pytest.approx(90.998, abs=1e-6)
    assert ledger.final_equity == pytest.approx(10_095.998, abs=1e-6)
    _assert_conservation(ledger, 10_005.0)


def test_fill_search_skips_missing_1m_bar() -> None:
    # The 1m bar at the signal boundary is missing; the engine must search
    # forward to the next available 1m open (3 minutes later) for both fills.
    bars = _long_entry_bars()
    ledger = _run(
        bars,
        [_one_m(1, 2, offset_ms=180_000), _one_m(1, 3, offset_ms=180_000)],
        start_equity=10_005.0,
    )

    fills = _events(ledger, "fill")
    assert [fill.ts_ms for fill in fills] == [
        D1_S1_CLOSE + 180_000,
        D1_S2_CLOSE + 180_000,
    ]
    trade = ledger.closed_trades[0]
    assert trade.net_pnl == pytest.approx(-18.0, abs=1e-6)
    assert ledger.final_equity == pytest.approx(9987.0, abs=1e-6)
    _assert_conservation(ledger, 10_005.0)


def test_conservation_identity_across_all_scenarios() -> None:
    """The exposed conservation residual must be ~0 for every scenario shape."""

    def quiet_two_days() -> tuple[Sequence[Bar], Sequence[Bar], float]:
        return (_day0() + [_saw(1, slot) for slot in range(96)], [], 10_000.0)

    def long_round_trip() -> tuple[Sequence[Bar], Sequence[Bar], float]:
        return (_long_entry_bars(), [_one_m(1, 2), _one_m(1, 3)], 10_005.0)

    def short_round_trip() -> tuple[Sequence[Bar], Sequence[Bar], float]:
        bars = [
            *_day0(),
            _saw(1, 0),
            _spike_down(1, 1),
            _bar(1, 2, 101.0, 102.0, 100.0, 101.0),
        ]
        return (bars, [_one_m(1, 2), _one_m(1, 3)], 9_995.0)

    def two_trades_two_days() -> tuple[Sequence[Bar], Sequence[Bar], float]:
        # Day 1: long entry (idx97), held over saw-101 bars, day-end flat exit.
        # Day 2 (pivot = (104 + 99 + 101)/3 = 304/3): spike-down at slot 2 gives
        # q = (99 - 304/3) / 2 <= -1 -> short entry; day-end force-close.
        day1 = [_saw(1, 0), _spike_up(1, 1)] + [_saw(1, slot, 101.0) for slot in range(2, 96)]
        day2 = [_saw(2, 0), _saw(2, 1), _bar(2, 2, 99.0, 100.0, 98.0, 99.0)] + [
            _saw(2, slot) for slot in range(3, 96)
        ]
        ones = [
            _one_m(1, 2),
            _one_m(2, 0),
            _one_m(2, 3),
            _one_m(3, 0),
        ]
        return (_day0() + day1 + day2, ones, 10_005.0)

    def funding_scenario() -> tuple[Sequence[Bar], Sequence[Bar], float]:
        return (
            _long_entry_bars(),
            [_one_m(1, 2), _one_m(1, 3)],
            10_005.0,
        )

    scenarios: list[tuple[str, Callable[[], tuple[Sequence[Bar], Sequence[Bar], float]]]] = [
        ("quiet_two_days", quiet_two_days),
        ("long_round_trip", long_round_trip),
        ("short_round_trip", short_round_trip),
        ("two_trades_two_days", two_trades_two_days),
        ("funding_scenario", funding_scenario),
    ]
    for name, build in scenarios:
        bars_15m, bars_1m, start = build()
        ledger = _run(bars_15m, bars_1m, start_equity=start)
        _assert_conservation(ledger, start)
        assert all(
            trade.net_pnl == pytest.approx(trade.gross_pnl - trade.total_fees, abs=1e-9)
            for trade in ledger.closed_trades
        ), name


def test_engine_is_deterministic() -> None:
    bars = _long_entry_bars()
    ones = [_one_m(1, 2), _one_m(1, 3)]
    first = _run(bars, ones, start_equity=10_005.0)
    second = _run(bars, ones, start_equity=10_005.0)
    assert first == second


def test_input_validation_rejects_bad_bars() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        _run([(0, 100.0, 101.0, 99.0, 100.0), (0, 100.0, 101.0, 99.0, 100.0)], [])
    with pytest.raises(ValueError, match="malformed OHLC"):
        _run([(0, 100.0, 50.0, 99.0, 100.0)], [])
    empty = _run([], [])
    assert empty.final_equity == 10_000.0
    assert empty.records == [] and empty.closed_trades == []
