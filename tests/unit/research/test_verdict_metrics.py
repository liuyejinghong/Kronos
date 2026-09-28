"""Unit tests for closed-trade verdict metrics (v0.5.0 package P09).

Every fixture is a tiny inline ``ExecutionLedger`` and every expected number is
hand-written next to its assertion.  Fixtures keep the contract identity
``net_pnl == gross_pnl - total_fees`` inside the helper so a broken metric can
never hide behind an inconsistent ledger.
"""

from __future__ import annotations

from typing import Literal

import pytest

from kronos.research.verdict.contracts import (
    ClosedTrade,
    ExecutionLedger,
    ExecutionRecord,
    MetricsBlock,
)
from kronos.research.verdict.metrics import compute_verdict_metrics, verify_conservation
from kronos.research.verdict.reference_ledger import conservation_residual

START = 10_000.0


def _trade(
    trade_id: str,
    *,
    gross: float,
    fees: float,
    holding_bars: int = 10,
    direction: Literal["long", "short"] = "long",
) -> ClosedTrade:
    """One closed round trip with ``net = gross - fees`` computed for us."""
    return ClosedTrade(
        trade_id=trade_id,
        symbol="BTCUSDT",
        direction=direction,
        entry_ts_ms=1_000,
        exit_ts_ms=2_000,
        entry_price=100.0,
        exit_price=101.0,
        qty=1.0,
        gross_pnl=gross,
        total_fees=fees,
        net_pnl=gross - fees,
        holding_bars=holding_bars,
        exit_reason="signal_exit",
    )


def _mark(ts_ms: int, equity: float) -> ExecutionRecord:
    return ExecutionRecord(ts_ms=ts_ms, event="equity_mark", symbol="BTCUSDT", equity=equity)


def _open(ts_ms: int) -> ExecutionRecord:
    return ExecutionRecord(
        ts_ms=ts_ms,
        event="position_open",
        symbol="BTCUSDT",
        side="buy",
        qty=1.0,
        price=100.0,
    )


def _close(ts_ms: int) -> ExecutionRecord:
    return ExecutionRecord(ts_ms=ts_ms, event="position_close", symbol="BTCUSDT")


def _ledger(
    trades: list[ClosedTrade],
    records: list[ExecutionRecord],
    *,
    final_equity: float | None = None,
) -> ExecutionLedger:
    if final_equity is None:
        final_equity = START + sum(trade.net_pnl for trade in trades)
    return ExecutionLedger(
        symbol="BTCUSDT",
        strategy_revision_id="rev-test",
        records=records,
        final_equity=final_equity,
        closed_trades=trades,
    )


# ---------------------------------------------------------------------------
# net pnl classification (spec scenario: fee flip)
# ---------------------------------------------------------------------------


def test_fee_flip_classifies_by_net_pnl() -> None:
    # T1: gross +100, fees 20 -> net +80   (win)
    # T2: gross +100, fees 150 -> net -50  (LOSS: fees flip a gross winner)
    trades = [
        _trade("t1", gross=100.0, fees=20.0),
        _trade("t2", gross=100.0, fees=150.0),
    ]
    # final = 10_000 + 80 - 50 = 10_030
    metrics = compute_verdict_metrics(_ledger(trades, [_mark(100, 10_020.0)]), start_equity=START)

    assert (metrics.wins, metrics.losses, metrics.ties) == (1, 1, 0)
    assert metrics.trade_count == 2
    # win_rate = 1 / (1 + 1) = 0.5 -- NOT 1.0: the fee-flipped trade is a loss.
    assert metrics.win_rate.value == pytest.approx(0.5)
    # profit_factor = sum(win net) / |sum(loss net)| = 80 / 50 = 1.6
    assert metrics.profit_factor.value == pytest.approx(1.6)
    assert metrics.avg_win.value == pytest.approx(80.0)
    assert metrics.avg_loss.value == pytest.approx(-50.0)  # negative by convention
    # net_return = 10_030 / 10_000 - 1 = 0.003
    assert metrics.net_return.value == pytest.approx(0.003)


def test_ties_count_in_win_rate_denominator() -> None:
    # T1: net +40 (win, 10 bars); T2: net -25 (loss, 20 bars); T3: net 0 (tie, 30 bars).
    trades = [
        _trade("t1", gross=50.0, fees=10.0, holding_bars=10),
        _trade("t2", gross=-20.0, fees=5.0, holding_bars=20),
        _trade("t3", gross=30.0, fees=30.0, holding_bars=30),  # exact tie
    ]
    metrics = compute_verdict_metrics(_ledger(trades, [_mark(100, 10_015.0)]), start_equity=START)

    assert (metrics.wins, metrics.losses, metrics.ties) == (1, 1, 1)
    assert metrics.trade_count == 3
    # win_rate = 1 / (1 + 1 + 1) = 0.3333... -- the tie is IN the denominator
    # (not 1/2 = 0.5 as a wins-vs-losses convention would give).
    assert metrics.win_rate.value == pytest.approx(1.0 / 3.0)
    # profit_factor = 40 / 25 = 1.6 (the tie adds 0 to both sides)
    assert metrics.profit_factor.value == pytest.approx(1.6)
    assert metrics.avg_win.value == pytest.approx(40.0)
    assert metrics.avg_loss.value == pytest.approx(-25.0)
    # avg_hold_bars = (10 + 20 + 30) / 3 = 20.0 -- the tie trade counts here.
    assert metrics.avg_hold_bars.value == pytest.approx(20.0)


def test_all_ties_is_null_with_reason() -> None:
    # T1: net 0 (gross 30 - fees 30); T2: net 0 (gross 10 - fees 10).
    trades = [
        _trade("t1", gross=30.0, fees=30.0, holding_bars=10),
        _trade("t2", gross=10.0, fees=10.0, holding_bars=20),
    ]
    metrics = compute_verdict_metrics(_ledger(trades, [_mark(100, 10_000.0)]), start_equity=START)

    assert (metrics.wins, metrics.losses, metrics.ties) == (0, 0, 2)
    assert metrics.trade_count == 2
    # No decisive trade: win_rate is undefined -- never a misleading 0.0.
    assert metrics.win_rate.value is None
    assert metrics.win_rate.reason == "all_ties"
    assert metrics.profit_factor.value is None
    assert metrics.profit_factor.reason == "no_losing_trades"
    assert metrics.avg_win.value is None
    assert metrics.avg_win.reason == "no_winning_trades"
    assert metrics.avg_loss.value is None
    assert metrics.avg_loss.reason == "no_losing_trades"
    # avg_hold_bars = (10 + 20) / 2 = 15.0 -- still defined, trades exist.
    assert metrics.avg_hold_bars.value == pytest.approx(15.0)


def test_all_wins_profit_factor_null_never_inf() -> None:
    # T1: net +80; T2: net +50.  No losing trade at all.
    trades = [
        _trade("t1", gross=100.0, fees=20.0),
        _trade("t2", gross=60.0, fees=10.0),
    ]
    metrics = compute_verdict_metrics(_ledger(trades, [_mark(100, 10_130.0)]), start_equity=START)

    assert metrics.win_rate.value == pytest.approx(1.0)
    # profit_factor must be null + reason, NEVER Infinity (0 gross loss).
    assert metrics.profit_factor.value is None
    assert metrics.profit_factor.reason == "no_losing_trades"
    assert metrics.avg_loss.value is None
    assert metrics.avg_loss.reason == "no_losing_trades"
    # avg_win = (80 + 50) / 2 = 65.0
    assert metrics.avg_win.value == pytest.approx(65.0)


def test_all_losses_win_rate_is_a_true_zero() -> None:
    # T1: net -50; T2: net -10.  Decisive losses exist, so 0.0 win rate is a
    # real measurement here (unlike the all-ties corner).
    trades = [
        _trade("t1", gross=-40.0, fees=10.0),
        _trade("t2", gross=-8.0, fees=2.0),
    ]
    metrics = compute_verdict_metrics(_ledger(trades, [_mark(100, 9_940.0)]), start_equity=START)

    assert metrics.win_rate.value == pytest.approx(0.0)
    assert metrics.win_rate.reason is None
    # profit_factor = 0 / |-60| = 0.0 (defined: losses dominate an empty win side)
    assert metrics.profit_factor.value == pytest.approx(0.0)
    assert metrics.avg_win.value is None
    assert metrics.avg_win.reason == "no_winning_trades"
    # avg_loss = (-50 + -10) / 2 = -30.0
    assert metrics.avg_loss.value == pytest.approx(-30.0)


def test_zero_trades_null_with_reasons() -> None:
    # Empty ledger: no closed trades at all, equity flat at start.
    ledger = _ledger([], [_mark(100, START), _mark(200, START)], final_equity=START)
    metrics = compute_verdict_metrics(ledger, start_equity=START)

    assert metrics.trade_count == 0
    for name in ("win_rate", "profit_factor", "avg_win", "avg_loss", "avg_hold_bars"):
        metric_value = getattr(metrics, name)
        assert metric_value.value is None, name
        assert metric_value.reason == "no_trades", name
    # net_return is still defined: 10_000 / 10_000 - 1 = 0.0.
    assert metrics.net_return.value == pytest.approx(0.0)
    # exposure = 0/2 marks held = 0.0; drawdown over a flat series = 0.0.
    assert metrics.exposure_fraction.value == pytest.approx(0.0)
    assert metrics.max_drawdown.value == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# max drawdown over the full series INCLUDING the initial capital point
# ---------------------------------------------------------------------------


def test_drawdown_includes_initial_capital_point() -> None:
    # Marks: 9_800 @ t100, then 9_900 @ t200.  With the prepended start point
    # the series is [10_000, 9_800, 9_900]: peak = the INITIAL 10_000, trough
    # = 9_800, drawdown = 200 / 10_000 = 0.02.  Without the initial point the
    # rising series [9_800, 9_900] would (wrongly) report no drawdown.
    ledger = _ledger([], [_mark(100, 9_800.0), _mark(200, 9_900.0)], final_equity=9_900.0)
    metrics = compute_verdict_metrics(ledger, start_equity=START)

    assert metrics.max_drawdown.value == pytest.approx(0.02)
    assert metrics.max_drawdown.value == pytest.approx(200.0 / 10_000.0)
    assert metrics.max_drawdown_absolute == pytest.approx(200.0)
    assert metrics.max_drawdown_peak == pytest.approx(10_000.0)  # the prepended point
    assert metrics.max_drawdown_trough == pytest.approx(9_800.0)
    # The initial point is stamped at the first mark's ts (100 here).
    assert metrics.max_drawdown_peak_ts_ms == 100
    assert metrics.max_drawdown_trough_ts_ms == 100
    assert metrics.max_drawdown_window_ms == 0
    # net_return = 9_900 / 10_000 - 1 = -0.01
    assert metrics.net_return.value == pytest.approx(-0.01)


def test_drawdown_rising_then_dip_peak_trough_window() -> None:
    # Series (start prepended): 10_000, 10_000@100, 10_500@200, 10_200@300,
    # 10_400@400.  Deepest window: peak 10_500@200 -> trough 10_200@300:
    # fraction = 300 / 10_500, absolute = 300, window = 100 ms.  The later
    # 10_400 dip (100 / 10_500) is shallower and must not win.
    ledger = _ledger(
        [],
        [
            _mark(100, 10_000.0),
            _mark(200, 10_500.0),
            _mark(300, 10_200.0),
            _mark(400, 10_400.0),
        ],
        final_equity=10_400.0,
    )
    metrics = compute_verdict_metrics(ledger, start_equity=START)

    assert metrics.max_drawdown.value == pytest.approx(300.0 / 10_500.0)
    assert metrics.max_drawdown_absolute == pytest.approx(300.0)
    assert metrics.max_drawdown_peak == pytest.approx(10_500.0)
    assert metrics.max_drawdown_trough == pytest.approx(10_200.0)
    assert metrics.max_drawdown_peak_ts_ms == 200
    assert metrics.max_drawdown_trough_ts_ms == 300
    assert metrics.max_drawdown_window_ms == 100


# ---------------------------------------------------------------------------
# exposure, fees, funding, turnover (figures consumed by P10)
# ---------------------------------------------------------------------------


def test_exposure_fraction_from_records() -> None:
    # Records: mark@0 (flat), open@100, mark@100 (open, same-ts replace),
    # mark@200 (open), close@300, mark@300 (flat), mark@400 (flat).
    # Observations: (0,F) (100,T) (200,T) (300,F) (400,F) -> 2/5 = 0.4.
    trade = _trade("t1", gross=20.0, fees=5.0)  # net +15
    ledger = _ledger(
        [trade],
        [
            _mark(0, START),
            _open(100),
            _mark(100, 10_010.0),
            _mark(200, 10_020.0),
            _close(300),
            _mark(300, 10_015.0),
            _mark(400, 10_015.0),
        ],
        final_equity=10_015.0,  # 10_000 + 15: conservation holds
    )
    metrics = compute_verdict_metrics(ledger, start_equity=START)

    assert metrics.exposure_fraction.value == pytest.approx(0.4)


def test_multi_fee_funding_and_turnover_totals() -> None:
    # fee records: 3.0 + 4.5          -> total_fees_paid = 7.5
    # funding impacts: -2.0 (paid), +0.5 (received)
    #   -> total_funding_paid = -(-2.0 + 0.5) = 1.5 (net paid)
    # fills: buy 0.1 @ 50_000 (5_000), sell 0.1 @ 51_000 (5_100)
    #   -> total_fill_notional = 10_100; turnover = 10_100 / 10_000 = 1.01
    trade = _trade("t1", gross=100.0, fees=20.0)  # net +80
    records: list[ExecutionRecord] = [
        _mark(100, 10_020.0),
        ExecutionRecord(
            ts_ms=110, event="fill", symbol="BTCUSDT", side="buy", qty=0.1, price=50_000.0
        ),
        ExecutionRecord(ts_ms=120, event="fee", symbol="BTCUSDT", fee=3.0, fee_asset="USDT"),
        _open(150),
        _mark(150, 10_090.0),
        _mark(200, 10_070.0),
        ExecutionRecord(ts_ms=250, event="fee", symbol="BTCUSDT", fee=4.5, fee_asset="USDT"),
        _close(250),
        _mark(250, 10_080.0),
        ExecutionRecord(
            ts_ms=300, event="funding", symbol="BTCUSDT", fee=-2.0, funding_rate=0.0001
        ),
        ExecutionRecord(
            ts_ms=310, event="fill", symbol="BTCUSDT", side="sell", qty=0.1, price=51_000.0
        ),
        ExecutionRecord(
            ts_ms=400, event="funding", symbol="BTCUSDT", fee=0.5, funding_rate=-0.000025
        ),
    ]
    # final = 10_000 + 80 = 10_080
    metrics = compute_verdict_metrics(_ledger([trade], records), start_equity=START)

    assert metrics.total_fees_paid == pytest.approx(7.5)
    assert metrics.total_funding_paid == pytest.approx(1.5)
    assert metrics.total_fill_notional == pytest.approx(10_100.0)
    assert metrics.turnover == pytest.approx(1.01)
    assert metrics.net_return.value == pytest.approx(0.008)
    # Observations: (100,F) (150,T after same-ts replace) (200,T) (250,F) -> 2/4.
    assert metrics.exposure_fraction.value == pytest.approx(0.5)


def test_exposure_without_marks_is_null() -> None:
    trade = _trade("t1", gross=100.0, fees=20.0)
    ledger = _ledger([trade], [_open(100), _close(200)])  # no equity_mark at all
    metrics = compute_verdict_metrics(ledger, start_equity=START)

    assert metrics.exposure_fraction.value is None
    assert metrics.exposure_fraction.reason == "no_equity_marks"


# ---------------------------------------------------------------------------
# contract projection, conservation, and input validation
# ---------------------------------------------------------------------------


def test_metrics_block_round_trip() -> None:
    # Mixed ledger: 1 win (+40), 1 fee-flipped loss (-50), marks and a position.
    trades = [
        _trade("t1", gross=50.0, fees=10.0),
        _trade("t2", gross=100.0, fees=150.0),
    ]
    records = [
        _mark(100, 10_040.0),
        _open(150),
        _mark(150, 10_045.0),
        _close(200),
        _mark(200, 10_030.0),
    ]
    metrics = compute_verdict_metrics(_ledger(trades, records), start_equity=START)

    block = metrics.to_metrics_block()
    assert isinstance(block, MetricsBlock)
    assert block.trade_count == 2
    assert block.win_rate.value == pytest.approx(0.5)  # 1 win / 2 trades
    assert block.profit_factor.value == pytest.approx(40.0 / 50.0)
    assert block.max_drawdown.value == pytest.approx(15.0 / 10_045.0)  # 10_045 -> 10_030
    # Benchmark pair stays null with the stable out-of-scope reason (P10 owns it).
    assert block.benchmark_return.value is None
    assert block.benchmark_return.reason == "benchmark_out_of_scope"
    assert block.excess_return.value is None
    assert block.excess_return.reason == "benchmark_out_of_scope"
    assert block.sample_warning is None  # sample policy belongs to P11

    # Round-trip through the frozen schema: must validate cleanly (MetricValue
    # exactly-one-of value/reason fires here on any contract violation).
    rebuilt = MetricsBlock(**block.model_dump())
    assert rebuilt == block


def test_verify_conservation_matches_reference_residual() -> None:
    trades = [
        _trade("t1", gross=100.0, fees=20.0),  # net +80
        _trade("t2", gross=100.0, fees=150.0),  # net -50
    ]
    healthy = _ledger(trades, [_mark(100, 10_030.0)])  # final = 10_030 = 10_000 + 30
    # Healthy ledger: 10_030 - 10_000 - (80 - 50) = 0.
    assert verify_conservation(healthy, start_equity=START) == 0.0
    # Delegation: identical to the reference ledger's own residual function.
    assert verify_conservation(healthy, start_equity=START) == conservation_residual(
        healthy, start_equity=START
    )

    broken = _ledger(trades, [_mark(100, 10_030.0)], final_equity=10_037.5)
    # Broken ledger: 10_037.5 - 10_000 - 30 = 7.5 residual, surfaced (not raised).
    assert verify_conservation(broken, start_equity=START) == pytest.approx(7.5)
    assert conservation_residual(broken, start_equity=START) == pytest.approx(7.5)


def test_start_equity_must_be_positive() -> None:
    ledger = _ledger([], [_mark(100, START)])
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError, match="start_equity"):
            compute_verdict_metrics(ledger, start_equity=bad)


def test_records_out_of_order_are_sorted_before_use() -> None:
    # Same ledger as test_exposure_fraction_from_records with records shuffled
    # ACROSS timestamps; the module must sort by ts before walking exposure /
    # drawdown state.  The sort is stable, so the same-ts pair (open@100 then
    # mark@100) keeps its order and the mark still observes a held position.
    trade = _trade("t1", gross=20.0, fees=5.0)
    shuffled = [
        _mark(200, 10_020.0),
        _close(300),
        _mark(0, START),
        _open(100),
        _mark(300, 10_015.0),
        _mark(100, 10_010.0),
        _mark(400, 10_015.0),
    ]
    metrics = compute_verdict_metrics(_ledger([trade], shuffled), start_equity=START)
    assert metrics.exposure_fraction.value == pytest.approx(0.4)
