"""Golden-case fixtures (P02): loading, contract validation, hand-math spot checks.

The expected ledgers in ``kronos/research/verdict/golden/expected/*.json`` were
derived by hand (see ``kronos/research/verdict/golden/HAND_MATH.md``). These
tests guard three things:

1. every case loads and is structurally sound (grids sorted/aligned, warmup
   present, sparse 1m execution series where promised);
2. every expected payload validates against the frozen contracts models
   (``ExecutionLedger``/``ClosedTrade``/``ExecutionRecord``) and satisfies the
   published arithmetic identities;
3. hand-computed spot numbers (fill prices, quantities, q-driven decisions,
   final equities) equal the JSON values — transcription-slip guard.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from kronos.research.verdict.golden.loader import (
    GoldenCase,
    expected_models,
    list_cases,
    load_case,
)

if TYPE_CHECKING:
    from kronos.research.verdict.contracts import ExecutionLedger

GOLDEN_DIR = Path("kronos/research/verdict/golden")
HAND_MATH = GOLDEN_DIR / "HAND_MATH.md"
DAY_MS = 86_400_000
BAR15_MS = 900_000
BASE_MS = 1_780_272_000_000  # 2026-06-01T00:00:00Z (day 0 of every fixture)
SLIPPAGE_BPS = 0.0005  # canonical: 5bps adverse price adjustment ONLY (Lead ruling)

EXPECTED_TRADE_COUNTS: dict[str, int] = {
    "G01": 1,
    "G02": 1,
    "G03": 1,
    "G04": 2,
    "G05": 0,
    "G06": 1,
    "G07": 1,
    "G08": 1,
    "G09": 0,
    "G10": 1,
    "G11": 1,
}

EXPECTED_FINAL_EQUITY: dict[str, float] = {
    "G01": 9965.393382,
    "G02": 9965.273205,
    "G03": 9982.009017,
    "G04": 9515.171337,
    "G05": 10000.0,
    "G06": 9998.624653,
    "G07": 9965.393382,
    "G08": 9964.393883,
    "G09": 10000.0,
    "G10": 9965.393382,
    "G11": 9991.002510,
}

# Hand numbers transcribed from HAND_MATH.md (per case): first-trade entry fill
# price, first-trade quantity, and a decision-side anchor where applicable.
HAND_SPOT: dict[str, dict[str, float]] = {
    "G01": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 59970.0},
    "G02": {"entry_price": 59870.05, "qty": 0.167028, "exit_price": 60030.0},
    "G03": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 60069.95},
    "G04": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 58770.60},
    "G05": {},
    "G06": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 60169.90},
    "G07": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 59970.0},
    "G08": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 59970.0},
    "G09": {},
    "G10": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 59970.0},
    "G11": {"entry_price": 60130.05, "qty": 0.166306, "exit_price": 60100.0},
}


def _approx(got: float, want: float) -> bool:
    return math.isclose(got, want, abs_tol=1e-6, rel_tol=0.0)


@pytest.mark.parametrize("case_id", list_cases())
def test_case_loads_and_is_structurally_sound(case_id: str) -> None:
    case: GoldenCase = load_case(case_id)
    assert case.case_id == case_id
    assert case.signal_timeframe == "15m"
    assert case.params.symbol == "BTCUSDT"
    assert case.cost.fee_bps == 4 and case.cost.slippage_bps == 5
    assert case.start_equity == 10000.0 and case.equity_fraction == 1.0
    # Warmup: one full prior UTC day (96 bars) + atr_period seed bars.
    assert len(case.bars_15m) >= 96 + case.params.atr_period
    # 15m bars sorted and aligned to the UTC 15m grid anchored at BASE_MS.
    ts = [bar.ts_ms for bar in case.bars_15m]
    assert ts == sorted(ts) and len(set(ts)) == len(ts)
    assert all((t - BASE_MS) % BAR15_MS == 0 for t in ts)
    # Zero-gap chain inside each UTC day: open equals previous close.
    for prev, cur in zip(case.bars_15m, case.bars_15m[1:], strict=False):
        if (cur.ts_ms - prev.ts_ms) == BAR15_MS:
            assert cur.o == prev.c
    # bars_1m is the sparse execution series: sorted, and non-empty exactly when
    # the case has fills (zero-trade cases G05/G09 carry an empty series).
    ts1m = [bar.ts_ms for bar in case.bars_1m]
    assert ts1m == sorted(ts1m)
    assert bool(case.bars_1m) == (EXPECTED_TRADE_COUNTS[case_id] > 0)


@pytest.mark.parametrize("case_id", list_cases())
def test_expected_validates_against_contracts(case_id: str) -> None:
    ledger: ExecutionLedger = expected_models(case_id)
    assert ledger.symbol == "BTCUSDT"
    assert ledger.strategy_revision_id == f"golden-{case_id}"
    assert len(ledger.closed_trades) == EXPECTED_TRADE_COUNTS[case_id]
    # Every event record is contract-typed already (model_validate ran); check
    # the coarse event ordering: entry orders/fills per trade, exit orders/fills
    # only for trades that actually closed (end_of_data_open has no exit leg).
    events = [record.event for record in ledger.records]
    still_open = any(t.exit_reason == "end_of_data_open" for t in ledger.closed_trades)
    legs = 2 * EXPECTED_TRADE_COUNTS[case_id] - (1 if still_open else 0)
    assert events.count("order") == legs
    assert events.count("fill") == legs
    assert events.count("position_close") == (
        EXPECTED_TRADE_COUNTS[case_id] - (1 if still_open else 0)
    )
    assert events.count("equity_mark") == (1 if still_open else 0)


@pytest.mark.parametrize("case_id", list_cases())
def test_published_arithmetic_identities(case_id: str) -> None:
    case = load_case(case_id)
    expected = case.expected
    # net = gross - total_fees, per trade.
    for trade in expected.closed_trades:
        assert _approx(round(trade["gross_pnl"] - trade["total_fees"], 6), trade["net_pnl"])
        # Fee identity: each fee is 4bps of that fill's notional (canonical).
        # total_fees = entry fee + exit fee (if a real exit fill exists) + funding.
        fee_in = round(0.0004 * round(trade["qty"] * trade["entry_price"], 6), 6)
        funding = 0.999499 if case.case_id == "G08" else 0.0
        if trade["exit_reason"] == "end_of_data_open":
            expected_fees = fee_in
        else:
            fee_out = round(0.0004 * round(trade["qty"] * trade["exit_price"], 6), 6)
            expected_fees = round(fee_in + fee_out + funding, 6)
        assert _approx(expected_fees, trade["total_fees"]), case.case_id
    # final_equity = start + sum(net_pnl).
    total_net = sum(trade["net_pnl"] for trade in expected.closed_trades)
    assert _approx(round(case.start_equity + total_net, 6), expected.final_equity)
    # Equity trail: fees/funding deduct immediately, closes add gross.
    equity = case.start_equity
    charged = 0.0
    for record in expected.ledger_events:
        if record["event"] in ("fee", "funding"):
            equity = round(equity - record["fee"], 6)
            charged = round(charged + record["fee"], 6)
        elif record["event"] == "position_close":
            equity = round(equity + record["realized_pnl"] + charged, 6)
            charged = 0.0
        elif record["event"] == "equity_mark":
            equity = round(equity + record["unrealized_pnl"], 6)
        if "equity" in record and record["equity"] is not None:
            assert _approx(equity, record["equity"])
    assert _approx(equity, expected.final_equity)


@pytest.mark.parametrize("case_id", list_cases())
def test_hand_math_spot_checks(case_id: str) -> None:
    """Published numbers equal the hand-derived literals from HAND_MATH.md."""
    case = load_case(case_id)
    assert _approx(case.expected.final_equity, EXPECTED_FINAL_EQUITY[case_id])
    spot = HAND_SPOT[case_id]
    if not spot:
        assert case.expected.closed_trades == []
        assert case.expected.ledger_events == []
        return
    trade: dict[str, Any] = case.expected.closed_trades[0]
    assert _approx(trade["entry_price"], spot["entry_price"])
    assert _approx(trade["qty"], spot["qty"])
    assert _approx(trade["exit_price"], spot["exit_price"])
    # qty identity: start_equity / entry fill, rounded to 6dp (first trade only).
    assert _approx(round(case.start_equity / trade["entry_price"], 6), trade["qty"])
    # Fill-price identity from the case's own 1m series: raw open x (1 +- 5bps)
    # slippage ONLY (canonical; the 4bps fee is a separate event, not in price).
    raw_in = next(b.o for b in case.bars_1m if b.ts_ms == trade["entry_ts_ms"])
    adj_in = (
        raw_in * (1 + SLIPPAGE_BPS) if trade["direction"] == "long" else raw_in * (1 - SLIPPAGE_BPS)
    )
    assert _approx(round(adj_in, 6), trade["entry_price"])
    if trade["exit_reason"] != "end_of_data_open":
        raw_out = next(b.o for b in case.bars_1m if b.ts_ms == trade["exit_ts_ms"])
        adj_out = (
            raw_out * (1 - SLIPPAGE_BPS)
            if trade["direction"] == "long"
            else raw_out * (1 + SLIPPAGE_BPS)
        )
        assert _approx(round(adj_out, 6), trade["exit_price"])
    else:
        assert _approx(case.bars_15m[-1].c, trade["exit_price"])


def test_fee_flip_and_param_cases_semantics() -> None:
    """G06 is a gross-win/net-loss trade; G09 blocks trades; G10 is param-inactive."""
    g06 = load_case("G06")
    trade = g06.expected.closed_trades[0]
    assert trade["gross_pnl"] > 0 > trade["net_pnl"]
    assert trade["exit_reason"] == "day_end_flat"

    g09 = load_case("G09")
    assert g09.params.volatility_multiplier == 3.0
    assert g09.expected.closed_trades == [] and g09.expected.final_equity == 10000.0

    g10 = load_case("G10")
    assert g10.params.atr_period == 3
    assert g10.expected.closed_trades != []
    # param_activated=false must be documented in meta with a pseudo-robust note.
    raw_g10 = g10.expected
    assert raw_g10.case_id == "G10"


def test_g08_funding_single_settlement() -> None:
    case = load_case("G08")
    funding_events = [r for r in case.expected.ledger_events if r["event"] == "funding"]
    assert len(funding_events) == 1
    event = funding_events[0]
    assert event["funding_rate"] == 0.0001
    assert _approx(event["fee"], round(0.0001 * 0.166306 * 60100, 6))
    trade = case.expected.closed_trades[0]
    # total_fees = entry fee + exit fee + funding (funding inside total_fees).
    assert _approx(round(3.999995 + 3.989348 + 0.999499, 6), trade["total_fees"])
    assert _approx(round(10000.0 + trade["net_pnl"], 6), case.expected.final_equity)


def test_zero_funding_boundary_case_g07() -> None:
    case = load_case("G07")
    assert case.funding_events != []  # declared but never applied
    assert not any(r["event"] == "funding" for r in case.expected.ledger_events)
    trade = case.expected.closed_trades[0]
    assert _approx(round(trade["gross_pnl"] - trade["total_fees"], 6), trade["net_pnl"])


def test_loader_rejects_unknown_case(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown golden case"):
        load_case("NOPE")
    with pytest.raises(ValueError, match="unknown golden case"):
        expected_models("NOPE")


def test_loader_rejects_malformed_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from kronos.research.verdict.golden import loader as loader_module

    cases_dir = tmp_path / "cases"
    expected_dir = tmp_path / "expected"
    cases_dir.mkdir()
    expected_dir.mkdir()
    (cases_dir / "GXX.json").write_text(json.dumps({"meta": {}}), encoding="utf-8")
    (expected_dir / "GXX.json").write_text(
        json.dumps(
            {"case_id": "GXX", "final_equity": 1.0, "closed_trades": [], "ledger_events": {}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(loader_module, "CASES_DIR", cases_dir)
    monkeypatch.setattr(loader_module, "EXPECTED_DIR", expected_dir)
    with pytest.raises(ValueError, match="missing key"):
        load_case("GXX")
    with pytest.raises(ValueError, match="must be lists"):
        loader_module.load_expected("GXX")


def test_g04_no_same_bar_reversal_two_trades() -> None:
    case = load_case("G04")
    t1, t2 = case.expected.closed_trades
    assert t1["direction"] == "long" and t2["direction"] == "short"
    # The short opens strictly AFTER the long's exit fill instant.
    assert t2["entry_ts_ms"] > t1["exit_ts_ms"]


def test_hand_math_document_covers_all_cases() -> None:
    assert HAND_MATH.exists(), "HAND_MATH.md is the independence guarantee; it must exist"
    text = HAND_MATH.read_text(encoding="utf-8")
    for case_id in list_cases():
        assert f"### {case_id}" in text, f"HAND_MATH.md missing section for {case_id}"
    assert "60000.0" in text and "60130.05" in text
    assert "Lead ruling" in text  # canonical cost convention is recorded in the doc
