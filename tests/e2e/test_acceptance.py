"""End-to-end acceptance tests for P1 Data Layer.

These tests hit the real Binance API and are marked with @pytest.mark.e2e.
Run with: pytest -m e2e
They are excluded from the default test run.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from kronos.data.loaders.binance_usdm import (
    fetch_funding_rates,
    fetch_klines,
    fetch_open_interest,
)
from kronos.data.storage.query import load
from kronos.data.sync import sync_klines

if TYPE_CHECKING:
    from pathlib import Path


E2E_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create the data directory structure."""
    (tmp_path / "curated").mkdir()
    (tmp_path / "raw").mkdir()
    return tmp_path


@pytest.mark.e2e
class TestRealAPIFetch:
    """P1-DL-9.1: End-to-end validation with real Binance API."""

    def test_fetch_klines_returns_data(self) -> None:
        """Each of the 3 symbols should return non-empty kline data."""
        now = int(time.time() * 1000)
        start = now - 120 * 60_000
        end = now - 60_000
        for symbol in E2E_SYMBOLS:
            table = fetch_klines(symbol, start_time=start, end_time=end, request_interval_ms=300)
            assert table.num_rows > 0, f"{symbol} returned no klines"
            assert "event_time" in table.column_names
            assert "symbol" in table.column_names
            symbols = table.column("symbol").to_pylist()
            assert all(s == symbol for s in symbols)

    def test_fetch_funding_returns_data(self) -> None:
        now = int(time.time() * 1000)
        start = now - 72 * 60 * 60_000
        for symbol in E2E_SYMBOLS:
            table = fetch_funding_rates(symbol, start_time=start, end_time=now, request_interval_ms=300)
            assert table.num_rows > 0, f"{symbol} returned no funding"
            assert "funding_rate" in table.column_names

    def test_fetch_oi_returns_data(self) -> None:
        now = int(time.time() * 1000)
        start = now - 6 * 60 * 60_000
        for symbol in E2E_SYMBOLS:
            table = fetch_open_interest(symbol, start_time=start, end_time=now, request_interval_ms=300)
            assert table.num_rows > 0, f"{symbol} returned no OI"
            assert "sum_open_interest" in table.column_names


@pytest.mark.e2e
class TestRealSyncPipeline:
    """P1-DL-9.1 + 9.4: Sync pipeline with real data, then verify query."""

    def test_sync_and_query(self, data_dir: Path) -> None:
        """Sync a small window of real data, then query it."""
        now = int(time.time() * 1000)
        start = now - 30 * 60_000

        count = sync_klines(
            "BTCUSDT",
            base_path=data_dir,
            since=start,
            request_interval_ms=300,
        )
        assert count > 0

        df = load("BTCUSDT", base_path=data_dir, timeframe="1m")
        assert len(df) > 0
        assert "open" in df.columns

    def test_resample_real_data(self, data_dir: Path) -> None:
        """P1-DL-9.2: Resample real synced data to 1h."""
        now = int(time.time() * 1000)
        start = now - 120 * 60_000  # 2 hours

        sync_klines(
            "BTCUSDT",
            base_path=data_dir,
            since=start,
            request_interval_ms=300,
        )

        df_1h = load("BTCUSDT", base_path=data_dir, timeframe="1h")
        assert len(df_1h) >= 1
        df_1m = load("BTCUSDT", base_path=data_dir, timeframe="1m")
        assert df_1h["volume"].sum() == pytest.approx(df_1m["volume"].sum(), rel=0.01)
