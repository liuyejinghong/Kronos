"""Integration tests: golden cases G01-G11 through the real freqtrade kernel.

Runs the P08 StrategyBacktestAdapter end-to-end (staged data -> pinned
freqtrade 2026.8 subprocess -> normalized ExecutionLedger) and cross-checks
against the independent P04 reference ledger on identical contiguous data.

Tolerances (lot rounding is canonical per D-20260928-003):
- structure (trade count / direction / entry ts / exit reason): EXACT
- exit timestamp: EXACT except G11 (documented end-of-data force-exit delta)
- entry/exit prices: EXACT
- qty: <= 0.6% (exchange lot 0.001 floor vs 6dp reference)
- final equity: <= 0.05% (G11 end-of-data exception: <= 0.1%)

Skips cleanly when the pinned venv is absent (bootstrap with
``ensure_freqtrade_env()`` or point ``KRONOS_FREQTRADE_VENV`` at one).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kronos.research.verdict.backtest_adapter import (
    BacktestCaseInput,
    StrategyBacktestAdapter,
)
from kronos.research.verdict.golden.loader import CASE_IDS, load_case
from kronos.research.verdict.kernel.freqtrade_runner import (
    FreqtradeEnvMissingError,
    ensure_freqtrade_env,
    expand_15m_to_1m,
)
from kronos.research.verdict.reference_ledger import CostPolicy, run_reference_backtest
from kronos.strategy.spec import VariantParams

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

QTY_TOL = 0.006
EQUITY_TOL = 0.0005
G11_EQUITY_TOL = 0.001


def _case_input(case_id: str) -> BacktestCaseInput:
    """Golden case with the M0 contiguous-1m expansion applied."""
    case = load_case(case_id)
    bars_15m = [(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_15m]
    ns = SimpleNamespace(
        bars_15m=bars_15m,
        bars_1m=[tuple(row[:5]) for row in expand_15m_to_1m(bars_15m)],
        funding_events=[(f.ts_ms, f.rate) for f in case.funding_events],
        params=case.params,
        cost=case.cost,
        start_equity=case.start_equity,
    )
    return BacktestCaseInput.from_golden_bundle(ns)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def kernel_adapter() -> StrategyBacktestAdapter:
    """Adapter bound to the pinned venv; skips the module if it is absent."""
    try:
        venv = ensure_freqtrade_env(skip_if_missing=True)
    except FreqtradeEnvMissingError as exc:
        pytest.skip(f"freqtrade kernel venv not available: {exc}")
    return StrategyBacktestAdapter(venv_dir=venv)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_golden_case_through_kernel(
    case_id: str,
    kernel_adapter: StrategyBacktestAdapter,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    case = load_case(case_id)
    bars_15m = [(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_15m]
    bars_1m = [tuple(row[:5]) for row in expand_15m_to_1m(bars_15m)]

    ledger = kernel_adapter.run_backtest(
        _case_input(case_id), workdir=tmp_path_factory.mktemp(f"kernel-{case_id}")
    )
    reference = run_reference_backtest(
        bars_15m,
        bars_1m,
        params=VariantParams(
            atr_period=case.params.atr_period,
            volatility_multiplier=case.params.volatility_multiplier,
        ),
        cost=CostPolicy(fee_bps=case.cost.fee_bps, slippage_bps=0.0),
        start_equity=case.start_equity,
        funding_events=[(f.ts_ms, f.rate) for f in case.funding_events],
    )

    # structure: count / direction / entry ts / exit reason EXACT
    assert len(ledger.closed_trades) == len(reference.closed_trades), case_id
    is_g11 = case_id == "G11"
    for ft_trade, ref_trade in zip(ledger.closed_trades, reference.closed_trades, strict=True):
        assert ft_trade.direction == ref_trade.direction, case_id
        assert ft_trade.entry_ts_ms == ref_trade.entry_ts_ms, case_id
        if not is_g11:
            assert ft_trade.exit_ts_ms == ref_trade.exit_ts_ms, case_id
        assert ft_trade.exit_reason == ref_trade.exit_reason, case_id
        # prices exact (entry and exit)
        assert ft_trade.entry_price == ref_trade.entry_price, case_id
        assert ft_trade.exit_price == ref_trade.exit_price, case_id
        # qty: lot rounding is canonical; reference is the checker
        qty_delta = abs(ft_trade.qty - ref_trade.qty) / ref_trade.qty
        assert qty_delta <= QTY_TOL, (case_id, ft_trade.qty, ref_trade.qty)

    # final equity
    equity_delta = abs(ledger.final_equity - reference.final_equity) / reference.final_equity
    limit = G11_EQUITY_TOL if is_g11 else EQUITY_TOL
    assert equity_delta <= limit, (case_id, ledger.final_equity, reference.final_equity)
