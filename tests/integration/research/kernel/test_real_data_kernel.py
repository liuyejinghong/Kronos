"""Integration test: the freqtrade kernel on REAL downloaded market data.

Runs the P08 adapter end-to-end on the last 90 complete UTC days of real
BTCUSDT 1m data (P21 dataset, ~130k bars) with real funding events — the
fixture-level jitter case at production scale: venue funding stamps carry
0-26 ms jitter past the hour and must be normalized, not rejected.

Skips cleanly when the pinned venv is absent or when the real dataset is
absent (``KRONOS_REAL_DATA_DIR`` or ``./data``).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from kronos.data.storage.query import load
from kronos.research.verdict.backtest_adapter import (
    BacktestCaseInput,
    StrategyBacktestAdapter,
)
from kronos.research.verdict.contracts import ExecutionLedger
from kronos.research.verdict.kernel.freqtrade_runner import (
    FreqtradeEnvMissingError,
    ensure_freqtrade_env,
)

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

SYMBOL = "BTCUSDT"
WINDOW_DAYS = 90
DAY_MS = 86_400_000
REAL_DATA_ENV = "KRONOS_REAL_DATA_DIR"
EXPECTED_FIRST_STAMP_SLACK_MS = DAY_MS  # dataset must reach back to the window start


def _real_data_dir() -> Path:
    configured = os.environ.get(REAL_DATA_ENV)
    return Path(configured).resolve() if configured else (Path.cwd() / "data").resolve()


def _dataset_available(data_dir: Path) -> bool:
    base = data_dir / "curated" / SYMBOL
    return (base / "klines_1m").is_dir() and (base / "funding").is_dir()


def _bars_from(df: object) -> list[tuple[int, float, float, float, float]]:
    return [
        (int(row.event_time), float(row.open), float(row.high), float(row.low), float(row.close))
        for row in df.itertuples()  # type: ignore[union-attr]
    ]


@pytest.fixture(scope="session")
def kernel_adapter() -> StrategyBacktestAdapter:
    try:
        venv = ensure_freqtrade_env(skip_if_missing=True)
    except FreqtradeEnvMissingError as exc:
        pytest.skip(f"freqtrade kernel venv not available: {exc}")
    return StrategyBacktestAdapter(venv_dir=venv)


@pytest.fixture(scope="session")
def real_case_input() -> BacktestCaseInput:
    """90-day BTCUSDT case from the real curated dataset (1m -> 15m resampled)."""
    data_dir = _real_data_dir()
    if not _dataset_available(data_dir):
        pytest.skip(f"real dataset not present under {data_dir} (set {REAL_DATA_ENV})")
    try:
        probe = load(SYMBOL, base_path=data_dir, timeframe="1m")
    except Exception as exc:  # any load failure means the dataset is not usable
        pytest.skip(f"real dataset not loadable: {exc}")
    if probe.empty:
        pytest.skip(f"real dataset empty under {data_dir}")
    window_end = (int(probe["event_time"].max()) // DAY_MS) * DAY_MS
    window_start = window_end - WINDOW_DAYS * DAY_MS

    bars_1m_df = load(
        SYMBOL, base_path=data_dir, timeframe="1m", since=window_start, until=window_end
    )
    if bars_1m_df.empty or int(bars_1m_df["event_time"].min()) > (
        window_start + EXPECTED_FIRST_STAMP_SLACK_MS
    ):
        pytest.skip(f"real dataset does not cover the {WINDOW_DAYS}-day window")
    bars_15m_df = load(
        SYMBOL, base_path=data_dir, timeframe="15m", since=window_start, until=window_end
    )
    funding_df = load(
        SYMBOL, base_path=data_dir, timeframe="1m", dataset="funding",
        since=window_start, until=window_end,
    )

    return BacktestCaseInput(
        bars_15m=_bars_from(bars_15m_df),
        bars_1m=_bars_from(bars_1m_df),
        funding_events=[
            (int(row.event_time), float(row.funding_rate)) for row in funding_df.itertuples()
        ],
        atr_period=14,  # StrategySpec defaults
        volatility_multiplier=1.0,
        fee_bps=4.0,
        start_equity=10_000.0,
    )


def test_btcusdt_real_90d_through_kernel(
    kernel_adapter: StrategyBacktestAdapter,
    real_case_input: BacktestCaseInput,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    start = time.monotonic()
    ledger = kernel_adapter.run_backtest(
        real_case_input, workdir=tmp_path_factory.mktemp("kernel-real-btcusdt")
    )
    wall_s = time.monotonic() - start

    assert isinstance(ledger, ExecutionLedger)
    assert ledger.symbol == SYMBOL
    assert ledger.final_equity > 0.0
    # conservation: equity change == sum of closed net pnl (fees+funding inside)
    residual = ledger.final_equity - 10_000.0 - sum(t.net_pnl for t in ledger.closed_trades)
    assert abs(residual) <= 1e-6 * max(1.0, abs(ledger.final_equity))
    # chronological, well-formed trades
    for trade in ledger.closed_trades:
        assert trade.entry_ts_ms < trade.exit_ts_ms
        assert trade.qty > 0.0
        assert trade.exit_reason in ("signal_exit", "day_end_flat", "end_of_data_open")
    # recorded for the P21 report (visible with -s)
    funding_events = len(real_case_input.funding_events)
    print(
        f"real-data run: window_bars_15m={len(real_case_input.bars_15m)} "
        f"bars_1m={len(real_case_input.bars_1m)} funding_events={funding_events} "
        f"trades={len(ledger.closed_trades)} final_equity={ledger.final_equity:.2f} "
        f"wall_s={wall_s:.1f}"
    )
