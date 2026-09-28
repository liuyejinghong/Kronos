"""Unit tests for the P10 EvidenceBundle builder (``verdict/evidence.py``).

Fixture worlds
--------------
- ``tiny``: one warmup day + three day-1 bars (G01-shaped) with a single 1m
  fill bar and one funding event; hand-checked hold-baseline arithmetic.
- ``G09`` / ``G10``: the frozen P02 golden cases, reused verbatim for the
  conservative activation semantics (G09: nothing trades anywhere ->
  ``param_activated=False``) and the identical-trades pseudo-robustness case
  (G10: multiplier changes, trades do not).
- ``big``: a 29-day regime world.  Warmup days 0-13 carry wild days
  (amplitude 150 on days 3/9/10 and 200 on day 12) so the pre-dev trailing-vol
  distribution has a spread; the dev window (days 14-25) is saw-flat except
  three engineered spike/hold/dip triples (one entry each, at day-14 slot 10,
  day-17 slot 60 and day-24 slot 10) plus a 200-amplitude wild day 12 still
  aging out of the 10-day vol windows.  1m bars are dense with step prices
  (each minute takes the last completed 15m close).  Verified empirically:
  center = 9 closed trades; vol slices low/mid/high = 287/0/865 dev bars with
  trade counts 1/0/2.

Every engine expectation is satisfied by the P04 reference engine injected
through :func:`make_reference_engine` (or an explicit spy/untagged wrapper);
the builder itself never imports an engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kronos.research.verdict.contracts import EvidenceBundle, Slice
from kronos.research.verdict.evidence import (
    DELAY_NOT_RUN_NOTE,
    SLICE_RULE_ID,
    SYMBOL_SLICE_RULE_ID,
    EvidenceEngine,
    RunInput,
    assign_vol_tercile_memberships,
    build_evidence_bundle,
    make_reference_engine,
    tag_engine,
    trailing_realized_vol_series,
)
from kronos.research.verdict.golden.loader import load_case
from kronos.research.verdict.metrics import compute_verdict_metrics
from kronos.research.verdict.reference_ledger import (
    TF_MS,
    Bar,
    CostPolicy,
    run_reference_backtest,
)
from kronos.strategy.spec import VariantParams

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kronos.research.verdict.contracts import ExecutionLedger

DAY_MS = 86_400_000

PARAMS = VariantParams(atr_period=2, volatility_multiplier=1.0)
COST = CostPolicy()  # fee_bps=4, slippage_bps=5
START_EQUITY = 10_000.0
IDENTITY = {
    "snapshot_id": "snap-1",
    "run_id": "run-evidence-1",
    "strategy_revision_id": "rev-evidence-1",
    "spec_hash": "a" * 64,
}
SYMBOL = "BTCUSDT"


# --- bar helpers -----------------------------------------------------------------


def _saw(day: int, slot: int, price: float = 100.0) -> tuple[int, float, float, float, float]:
    return (day * DAY_MS + slot * TF_MS, price, price + 1.0, price - 1.0, price)


def _wild(day: int, amp: float) -> list[tuple[int, float, float, float, float]]:
    return [(day * DAY_MS + s * TF_MS, amp, amp + 2.0, amp - 2.0, amp) for s in range(96)]


def _spike(day: int, slot: int) -> tuple[int, float, float, float, float]:
    return (day * DAY_MS + slot * TF_MS, 104.0, 105.0, 103.0, 104.0)


def _hold_bar(day: int, slot: int) -> tuple[int, float, float, float, float]:
    return (day * DAY_MS + slot * TF_MS, 101.0, 102.0, 100.0, 101.0)


def _dip(day: int, slot: int) -> tuple[int, float, float, float, float]:
    return (day * DAY_MS + slot * TF_MS, 99.0, 100.0, 98.0, 99.0)


def _tiny_world() -> tuple[list[Bar], list[Bar]]:
    """One warmup day + spike/dip day-1 with a single 1m fill bar."""
    bars = [_saw(0, s) for s in range(96)]
    bars += [_saw(1, 0), _spike(1, 1), _dip(1, 2)]
    one_m = [(DAY_MS + 3 * TF_MS, 100.0, 100.0, 100.0, 100.0)]
    return bars, one_m


_WILD_DAYS: dict[int, float] = {3: 150.0, 9: 150.0, 10: 150.0, 12: 200.0}
_TRIPLE_SLOTS: dict[int, int] = {14: 10, 17: 60, 24: 10}
DEV_WINDOW = (14 * DAY_MS, 26 * DAY_MS)
HOLDOUT_WINDOW = (26 * DAY_MS, 29 * DAY_MS)
DEV_BAR_COUNT = 12 * 96


def _big_bars() -> list[Bar]:
    bars: list[Bar] = []
    for day in range(29):
        if day in _WILD_DAYS:
            bars += _wild(day, _WILD_DAYS[day])
        elif day in _TRIPLE_SLOTS:
            slot = _TRIPLE_SLOTS[day]
            bars += [_saw(day, k) for k in range(slot)]
            bars += [_spike(day, slot), _hold_bar(day, slot + 1), _dip(day, slot + 2)]
            bars += [_saw(day, k) for k in range(slot + 3, 96)]
        else:
            bars += [_saw(day, k) for k in range(96)]
    return bars


def _dense_1m(bars: Sequence[Bar]) -> list[Bar]:
    """One 1m bar per minute; its price is the last completed 15m close."""
    one_m: list[Bar] = []
    for ts, _o, _h, _l, close in bars:
        for minute in range(15):
            one_m.append((ts + TF_MS + minute * 60_000, close, close, close, close))
    return one_m


@pytest.fixture(scope="module")
def big_world() -> tuple[list[Bar], list[Bar]]:
    bars = _big_bars()
    return bars, _dense_1m(bars)


def _big_bundle(
    big_world: tuple[list[Bar], list[Bar]],
    engine: EvidenceEngine | None = None,
    **overrides: object,
) -> EvidenceBundle:
    bars, one_m = big_world
    kwargs: dict[str, object] = {
        "engine": engine if engine is not None else make_reference_engine(),
        "bars_15m": bars,
        "bars_1m": one_m,
        "params": PARAMS,
        "cost": COST,
        "start_equity": START_EQUITY,
        "funding_events": [],
        "dev_window_ms": DEV_WINDOW,
        "holdout_window_ms": HOLDOUT_WINDOW,
        "holdout_exposed_count": 0,
        "symbol": SYMBOL,
        **IDENTITY,
    }
    kwargs.update(overrides)
    return build_evidence_bundle(**kwargs)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def big_bundle(big_world: tuple[list[Bar], list[Bar]]) -> EvidenceBundle:
    return _big_bundle(big_world)


def _tiny_bundle(**overrides: object) -> EvidenceBundle:
    bars, one_m = _tiny_world()
    kwargs: dict[str, object] = {
        "engine": make_reference_engine(),
        "bars_15m": bars,
        "bars_1m": one_m,
        "params": PARAMS,
        "cost": COST,
        "start_equity": 10_005.0,  # qty is exactly 100 at the 100.05 entry fill
        "funding_events": [(DAY_MS + 3 * TF_MS + 300_000, 0.0001)],
        "dev_window_ms": (DAY_MS + 2 * TF_MS, DAY_MS + 4 * TF_MS),
        "holdout_window_ms": (DAY_MS + 4 * TF_MS, DAY_MS + 5 * TF_MS),
        "holdout_exposed_count": 0,
        "symbol": SYMBOL,
        **IDENTITY,
    }
    kwargs.update(overrides)
    return build_evidence_bundle(**kwargs)  # type: ignore[arg-type]


def _golden_bundle(
    case_id: str, grid: list[tuple[int, float]], **overrides: object
) -> EvidenceBundle:
    case = load_case(case_id)
    bars = [(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_15m]
    one_m = [(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_1m]
    day_start = bars[0][0]  # day-0 open; dev = day 1, holdout = day 2
    kwargs: dict[str, object] = {
        "engine": make_reference_engine(),
        "bars_15m": bars,
        "bars_1m": one_m,
        "params": VariantParams(
            atr_period=case.params.atr_period,
            volatility_multiplier=case.params.volatility_multiplier,
        ),
        "cost": case.cost,
        "start_equity": case.start_equity,
        "funding_events": [],
        "dev_window_ms": (day_start + DAY_MS, day_start + 2 * DAY_MS),
        "holdout_window_ms": (day_start + 2 * DAY_MS, day_start + 3 * DAY_MS),
        "holdout_exposed_count": 0,
        "neighborhood_grid": grid,
        "symbol": SYMBOL,
        **IDENTITY,
    }
    kwargs.update(overrides)
    return build_evidence_bundle(**kwargs)  # type: ignore[arg-type]


def _spy_engine(calls: list[RunInput]) -> EvidenceEngine:
    base = make_reference_engine()

    def spy(run_input: RunInput) -> ExecutionLedger:
        calls.append(run_input)
        return base(run_input)

    return tag_engine(spy, "reference")


# --- baselines --------------------------------------------------------------------


def test_hold_baseline_exact_math_with_funding() -> None:
    """Hand-checked hold row: entry 100.05 x100, fees 4.002 + 3.96, funding 0.99."""
    bundle = _tiny_bundle()
    hold = bundle.comparisons[0]
    assert hold.baseline == "hold_same_symbol"
    assert "funding IS counted" in hold.note

    metrics = hold.metrics
    # gross (99 - 100.05) * 100 = -105; fees 4.002 + 3.96; funding 0.99
    # net = -113.952 on 10_005 starting equity.
    assert metrics.net_return.value == pytest.approx(-113.952 / 10_005.0, rel=1e-12)
    # Equity marks: start 10_005 -> 9895.998 at the last close (funding lands later).
    assert metrics.max_drawdown.value == pytest.approx(109.002 / 10_005.0, rel=1e-12)


def test_hold_row_trade_metrics_null_with_reasons() -> None:
    bundle = _tiny_bundle()
    metrics = bundle.comparisons[0].metrics
    assert metrics.trade_count == 0
    assert metrics.win_rate.value is None
    assert metrics.win_rate.reason == "baseline_no_closed_trades"
    for name in ("profit_factor", "avg_hold_bars", "avg_win", "avg_loss"):
        metric = getattr(metrics, name)
        assert metric.value is None
        assert metric.reason == "baseline_no_closed_trades"
    # A baseline row is its own benchmark; excess is not defined on it.
    assert metrics.benchmark_return.reason == "baseline_row_is_benchmark"
    assert metrics.excess_return.reason == "baseline_row_is_benchmark"


def test_cash_baseline_zero_return() -> None:
    bundle = _tiny_bundle()
    cash = bundle.comparisons[1]
    assert cash.baseline == "cash"
    assert cash.metrics.net_return.value == 0.0
    assert cash.metrics.max_drawdown.value == 0.0
    assert cash.metrics.win_rate.value is None
    assert cash.metrics.win_rate.reason == "cash_baseline_has_no_trades"
    assert cash.metrics.trade_count == 0


def test_hold_baseline_without_fills_is_null_not_zero() -> None:
    """G09 carries no 1m bars: the hold row cannot even enter -> null + reason."""
    bundle = _golden_bundle("G09", grid=[(2, 3.0)])
    metrics = bundle.comparisons[0].metrics
    assert metrics.net_return.value is None
    assert metrics.net_return.reason == "hold_baseline_no_entry_fill"


def test_center_metrics_match_p09_on_full_window(big_world: tuple[list[Bar], list[Bar]]) -> None:
    bars, one_m = big_world
    direct = run_reference_backtest(
        bars, one_m, params=PARAMS, cost=COST, start_equity=START_EQUITY, symbol=SYMBOL
    )
    expected = compute_verdict_metrics(direct, start_equity=START_EQUITY).to_metrics_block()
    bundle = _big_bundle(big_world)
    assert bundle.metrics == expected
    assert bundle.metrics.trade_count == 9


def test_symbol_slice_single_symbol_reuses_center_run(big_bundle: EvidenceBundle) -> None:
    assert len(big_bundle.symbol_slices) == 1
    only = big_bundle.symbol_slices[0]
    assert only.rule_id == SYMBOL_SLICE_RULE_ID
    assert only.label == SYMBOL
    assert only.sample_bars == 29 * 96
    # Reuse, no re-run: the count equals the center run's closed trades.
    assert only.trade_count == big_bundle.metrics.trade_count


# --- pre-registered time slices ----------------------------------------------------


def test_time_slices_labels_partition_and_trade_counts(big_bundle: EvidenceBundle) -> None:
    slices = big_bundle.time_slices
    assert [s.label for s in slices] == ["low", "mid", "high"]
    assert all(s.rule_id == SLICE_RULE_ID for s in slices)
    assert sum(s.sample_bars for s in slices) == DEV_BAR_COUNT
    # Every dev trade's entry bar belongs to exactly one bucket; the high-vol
    # slice carries the day-14/17 entries, the low-vol tail the day-24 entry.
    assert [(s.sample_bars, s.trade_count) for s in slices] == [(287, 1), (0, 0), (865, 2)]
    assert sum(s.trade_count for s in slices) == 3


def test_time_slices_lagged_under_future_mutation(
    big_world: tuple[list[Bar], list[Bar]],
) -> None:
    """Mutating bars at/after t cannot move any bar older than t between slices."""
    bars, _one_m = big_world
    t = 20 * DAY_MS
    mutated = [
        _saw(bar[0] // DAY_MS, (bar[0] % DAY_MS) // TF_MS, 101.0) if bar[0] >= t else bar
        for bar in bars
    ]
    original = assign_vol_tercile_memberships(
        bars, dev_start_ms=DEV_WINDOW[0], dev_end_ms=DEV_WINDOW[1]
    )
    shifted = assign_vol_tercile_memberships(
        mutated, dev_start_ms=DEV_WINDOW[0], dev_end_ms=DEV_WINDOW[1]
    )
    assert original is not None and shifted is not None
    label_of_original = {
        bars[index][0]: label for label, members in original.items() for index in members
    }
    label_of_shifted = {
        mutated[index][0]: label for label, members in shifted.items() for index in members
    }
    past = [ts for ts in label_of_original if ts < t]
    assert past, "fixture must have pre-t dev bars"
    assert {ts: label_of_original[ts] for ts in past} == {ts: label_of_shifted[ts] for ts in past}
    # And the vol of a pre-t bar itself is bit-identical under the mutation.
    vols_original = trailing_realized_vol_series(bars)
    vols_mutated = trailing_realized_vol_series(mutated)
    for index, bar in enumerate(bars):
        if bar[0] < t:
            assert vols_original[index] == vols_mutated[index]


def test_time_slices_unchanged_when_holdout_mutated(
    big_world: tuple[list[Bar], list[Bar]],
) -> None:
    bars, _one_m = big_world
    mutated = [
        _saw(bar[0] // DAY_MS, (bar[0] % DAY_MS) // TF_MS, 101.0)
        if bar[0] >= HOLDOUT_WINDOW[0]
        else bar
        for bar in bars
    ]
    bundle_a = _big_bundle(big_world)
    bundle_b = _big_bundle((mutated, _dense_1m(mutated)))
    assert bundle_a.time_slices == bundle_b.time_slices
    assert bundle_a.neighborhood == bundle_b.neighborhood


def test_tiny_window_without_vol_history_has_no_slices() -> None:
    """No pre-registerable 10-day lagged history -> empty slices, never guessed."""
    bundle = _tiny_bundle()
    assert bundle.time_slices == []


# --- neighborhood -------------------------------------------------------------------


def test_neighborhood_default_grid_and_change_detection() -> None:
    """Center reuse, +/-1-step clamped grid, and trades_changed on dead points."""
    bundle = _tiny_bundle()
    grid = bundle.neighborhood.grid
    assert [(p.atr_period, p.volatility_multiplier) for p in grid] == [
        (2, 1.0),
        (2, 2.0),
        (3, 1.0),
        (3, 2.0),
    ]
    center = grid[0]
    assert (center.atr_period, center.volatility_multiplier) == (2, 1.0)
    assert center.trades_changed is False
    assert center.param_activated is True
    assert center.net_pnl == pytest.approx(-109.992, abs=1e-6)
    # m=2 halves the entry q below the threshold: no trades -> changed.
    dead = grid[1]
    assert (dead.atr_period, dead.volatility_multiplier) == (2, 2.0)
    assert dead.trades_changed is True
    assert dead.param_activated is True  # center trades, so the q path is live
    assert dead.net_pnl == 0.0
    # Every non-center point changed its trades: no pseudo-robustness here.
    assert bundle.neighborhood.pseudo_robust_note is None


def test_neighborhood_pseudo_robust_note_on_identical_trades() -> None:
    """A multiplier change that keeps every trade must be flagged, not praised."""
    bundle = _tiny_bundle(neighborhood_grid=[(2, 1.0), (2, 0.9)])
    points = bundle.neighborhood.grid
    assert [(p.trades_changed, p.param_activated) for p in points] == [
        (False, True),
        (False, True),
    ]
    note = bundle.neighborhood.pseudo_robust_note
    assert note is not None
    assert "volatility_multiplier=0.9" in note
    assert "NOT evidence of robustness" in note


def test_neighborhood_g10_golden_identical_multiplier() -> None:
    """G10: m=1 -> m=2 keeps the ledger identical; never report as robustness."""
    bundle = _golden_bundle("G10", grid=[(3, 1.0), (3, 2.0)])
    points = bundle.neighborhood.grid
    assert [(p.atr_period, p.volatility_multiplier) for p in points] == [(3, 1.0), (3, 2.0)]
    assert all(not point.trades_changed for point in points)
    assert all(point.param_activated for point in points)  # trades exist on the dev window
    case = load_case("G10")
    assert points[0].net_pnl == pytest.approx(
        case.expected.final_equity - case.start_equity, abs=1e-6
    )
    note = bundle.neighborhood.pseudo_robust_note
    assert note is not None
    assert "NOT evidence of robustness" in note


def test_neighborhood_g09_all_zero_trades_not_activated() -> None:
    """G09: nothing trades anywhere -> conservative 'not activated' + note."""
    bundle = _golden_bundle("G09", grid=[(2, 2.0), (2, 3.0), (2, 4.0)])
    points = bundle.neighborhood.grid
    assert len(points) == 3
    assert all(point.trades_changed is False for point in points)
    assert all(point.param_activated is False for point in points)
    assert all(point.net_pnl == 0.0 for point in points)
    note = bundle.neighborhood.pseudo_robust_note
    assert note is not None and note.strip()
    assert "parameter not activated" in note
    assert "must not be read as robustness" in note


# --- holdout ------------------------------------------------------------------------


def test_holdout_windows_and_exposure_flag() -> None:
    bundle = _tiny_bundle(holdout_exposed_count=2)
    assert bundle.holdout.exposed is True
    assert bundle.holdout.exposed_count == 2
    assert bundle.holdout.dev_window == "1970-01-02T00:30:00Z..1970-01-02T01:00:00Z"
    assert bundle.holdout.holdout_window == "1970-01-02T01:00:00Z..1970-01-02T01:15:00Z"

    clean = _tiny_bundle(holdout_exposed_count=0)
    assert clean.holdout.exposed is False
    assert clean.holdout.exposed_count == 0


def test_holdout_run_never_reoptimizes(
    big_world: tuple[list[Bar], list[Bar]],
) -> None:
    calls: list[RunInput] = []
    bundle = _big_bundle(big_world, engine=_spy_engine(calls))
    assert bundle.holdout.exposed is False

    holdout_calls = [
        call for call in calls if call.bars_15m and call.bars_15m[0][0] >= HOLDOUT_WINDOW[0]
    ]
    assert len(holdout_calls) == 1
    run_input = holdout_calls[0]
    # Flat start, center params, center cost: nothing was re-optimized.
    assert run_input.params == PARAMS
    assert run_input.fee_bps == COST.fee_bps
    assert run_input.slippage_bps == COST.slippage_bps
    assert run_input.start_equity == START_EQUITY
    assert run_input.bars_15m[0][0] == HOLDOUT_WINDOW[0]
    # No run of any kind sees holdout data with non-center parameters.
    for call in calls:
        if any(bar[0] >= HOLDOUT_WINDOW[0] for bar in call.bars_15m):
            assert call.params == PARAMS


# --- stress -------------------------------------------------------------------------


def test_cost_up_doubles_fee_and_is_recorded(
    big_world: tuple[list[Bar], list[Bar]],
) -> None:
    calls: list[RunInput] = []
    bundle = _big_bundle(big_world, engine=_spy_engine(calls))
    doubled = [call for call in calls if call.fee_bps == 2 * COST.fee_bps]
    assert len(doubled) == 1
    assert doubled[0].slippage_bps == COST.slippage_bps  # slippage untouched
    assert doubled[0].bars_15m[0][0] == big_world[0][0][0]  # full center window

    assert len(bundle.stress) == 2
    cost_up = bundle.stress[0]
    assert cost_up.kind == "cost_up"
    assert "fee_bps doubled from 4.0 to 8.0" in cost_up.description
    assert "slippage unchanged" in cost_up.description


def test_delay_stress_runs_on_reference_engine(
    big_world: tuple[list[Bar], list[Bar]],
) -> None:
    calls: list[RunInput] = []
    bundle = _big_bundle(big_world, engine=_spy_engine(calls))
    first_1m_ts = big_world[1][0][0]
    delayed = [call for call in calls if call.bars_1m and call.bars_1m[0][0] == first_1m_ts - TF_MS]
    assert len(delayed) == 1
    assert len(delayed[0].bars_1m) == len(big_world[1])  # same series, shifted

    delay = bundle.stress[1]
    assert delay.kind == "delay"
    assert delay.description.startswith("delay stress: every 1m fill opportunity shifted")


def test_delay_fallback_for_untagged_engine() -> None:
    """An adapter-shaped (slippage-strict, untagged) engine records 'not run'."""
    seen_slippage: list[float] = []
    base = make_reference_engine()

    def adapter_shaped(run_input: RunInput) -> ExecutionLedger:
        seen_slippage.append(run_input.slippage_bps)
        if run_input.slippage_bps != 0.0:  # the adapter rejects nonzero slippage
            raise ValueError("nonzero slippage rejected")
        return base(run_input)

    # Production adapter configuration: slippage-free execution (fail closed).
    bundle = _tiny_bundle(
        engine=adapter_shaped,
        cost=CostPolicy(fee_bps=4.0, slippage_bps=0.0),
    )
    assert seen_slippage and all(value == 0.0 for value in seen_slippage)
    kinds = [stress.kind for stress in bundle.stress]
    assert kinds == ["cost_up", "delay"]
    assert bundle.stress[0].kind == "cost_up"  # cost stress still ran
    assert bundle.stress[1].description == DELAY_NOT_RUN_NOTE


# --- contract + determinism -----------------------------------------------------------


def test_bundle_round_trips_through_frozen_contracts(big_bundle: EvidenceBundle) -> None:
    payload = big_bundle.model_dump(mode="json")
    reparsed = EvidenceBundle.model_validate(payload)
    assert reparsed == big_bundle
    # The conservative activation rule keeps the NeighborhoodBlock validator
    # satisfied: every inactive point comes with a non-empty note.
    if any(not point.param_activated for point in big_bundle.neighborhood.grid):
        assert big_bundle.neighborhood.pseudo_robust_note
    assert big_bundle.run_id == IDENTITY["run_id"]
    assert big_bundle.snapshot_id == IDENTITY["snapshot_id"]
    assert big_bundle.strategy_revision_id == IDENTITY["strategy_revision_id"]


def test_idempotent_bundle_json(big_world: tuple[list[Bar], list[Bar]]) -> None:
    first = _big_bundle(big_world)
    second = _big_bundle(big_world)
    assert first.model_dump_json() == second.model_dump_json()


def test_slice_rule_ids_are_pre_registered(big_bundle: EvidenceBundle) -> None:
    for slice_row in [*big_bundle.time_slices, *big_bundle.symbol_slices]:
        assert isinstance(slice_row, Slice)
    assert {s.rule_id for s in big_bundle.time_slices} == {SLICE_RULE_ID}
    assert {s.rule_id for s in big_bundle.symbol_slices} == {SYMBOL_SLICE_RULE_ID}
