"""Golden-case comparison: P04 reference ledger vs hand-computed P02 fixtures.

The assertion targets the ARITHMETIC projection with a 1e-6 tolerance —
hand-authored expected values stay independent of the engine, while
presentation details (equity-mark granularity, id/naming conventions,
6dp fixture rounding) are normalized away. This is the M0 hard gate.
"""

from __future__ import annotations

import pytest

TOL = 1e-6


def _close(a: float, b: float, label: str, ctx: str) -> None:
    assert abs(a - b) <= TOL, f"{ctx}: {label} engine={a} expected={b}"


def test_golden_cases_match_reference_ledger() -> None:
    loader = pytest.importorskip(
        "kronos.research.verdict.golden.loader",
        reason="P02 golden loader (kronos.research.verdict.golden.loader) not present yet",
    )
    load_cases = getattr(loader, "load_golden_cases", None)
    if load_cases is None:
        pytest.skip("golden loader does not expose load_golden_cases() yet")
    from kronos.research.verdict.reference_ledger import run_reference_backtest

    for case in load_cases():
        ctx = case.case_id if hasattr(case, "case_id") else str(case)
        ledger = run_reference_backtest(
            case.bars_15m,
            case.bars_1m,
            params=case.params,
            cost=case.cost,
            start_equity=case.start_equity,
            funding_events=case.funding_events,
        )
        expected = case.expected_ledger

        # Trade structure: counts, directions, timestamps, reasons — exact.
        assert len(ledger.closed_trades) == len(expected.closed_trades), (
            f"{ctx}: trade count {len(ledger.closed_trades)} vs {len(expected.closed_trades)}"
        )
        for got, exp in zip(ledger.closed_trades, expected.closed_trades, strict=True):
            assert got.direction == exp.direction, f"{ctx}: direction"
            assert got.entry_ts_ms == exp.entry_ts_ms, f"{ctx}: entry ts"
            assert got.exit_ts_ms == exp.exit_ts_ms, f"{ctx}: exit ts"
            assert got.exit_reason == exp.exit_reason, f"{ctx}: exit reason"
            assert got.holding_bars == exp.holding_bars, f"{ctx}: holding bars"
            _close(got.entry_price, exp.entry_price, "entry price", ctx)
            _close(got.exit_price, exp.exit_price, "exit price", ctx)
            _close(got.qty, exp.qty, "qty", ctx)
            _close(got.gross_pnl, exp.gross_pnl, "gross pnl", ctx)
            _close(got.total_fees, exp.total_fees, "total fees", ctx)
            _close(got.net_pnl, exp.net_pnl, "net pnl", ctx)

        # Money: final equity and per-event fill/fee/funding arithmetic.
        _close(ledger.final_equity, expected.final_equity, "final equity", ctx)

        def _event_money(records: list, kinds: set[str]) -> dict[str, list[float]]:
            out: dict[str, list[float]] = {}
            for rec in records:
                if rec.event in kinds:
                    key = f"{rec.event}:{rec.ts_ms}"
                    value = rec.price if rec.event == "fill" else (
                        rec.fee if rec.event == "fee" else (rec.funding_rate or 0.0)
                    )
                    out.setdefault(key, []).append(float(value or 0.0))
            return out

        got_money = _event_money(ledger.records, {"fill", "fee", "funding"})
        exp_money = _event_money(expected.records, {"fill", "fee", "funding"})
        assert set(got_money) == set(exp_money), (
            f"{ctx}: event keys differ: {set(got_money) ^ set(exp_money)}"
        )
        for key, exp_values in exp_money.items():
            got_values = got_money[key]
            assert len(got_values) == len(exp_values), f"{ctx}: {key} count"
            for g, e in zip(sorted(got_values), sorted(exp_values), strict=True):
                if key.startswith("funding"):
                    # Funding magnitude is the money term; sign conventions
                    # differ between fixtures (paid>0) and engine (impact<0).
                    _close(abs(g), abs(e), f"funding {key}", ctx)
                else:
                    _close(g, e, key, ctx)
