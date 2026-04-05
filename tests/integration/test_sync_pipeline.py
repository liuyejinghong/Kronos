"""Integration tests for the sync pipeline: adapter → raw → curated → query."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pyarrow as pa

from kronos.data.storage.query import coverage, detect_gaps, load
from kronos.data.sync import sync_all, sync_klines

if TYPE_CHECKING:
    from pathlib import Path


def _make_kline_table(
    symbol: str = "BTCUSDT",
    n: int = 60,
    base_ts: int = 1709251200000,
) -> pa.Table:
    """Create a mock kline table with N bars."""
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base_ts + i * 60_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base_ts + (i + 1) * 60_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "open": pa.array([67000.0 + i * 10 for i in range(n)], type=pa.float64()),
        "high": pa.array([67050.0 + i * 10 for i in range(n)], type=pa.float64()),
        "low": pa.array([66950.0 + i * 10 for i in range(n)], type=pa.float64()),
        "close": pa.array([67020.0 + i * 10 for i in range(n)], type=pa.float64()),
        "volume": pa.array([100.0] * n, type=pa.float64()),
        "quote_volume": pa.array([6700000.0] * n, type=pa.float64()),
        "trade_count": pa.array([50] * n, type=pa.int64()),
        "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
        "venue": ["binance"] * n,
    })


def _make_funding_table(
    symbol: str = "BTCUSDT",
    n: int = 3,
    base_ts: int = 1709251200000,
) -> pa.Table:
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base_ts + i * 28_800_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base_ts + i * 28_800_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
        "mark_price": pa.array([67000.0] * n, type=pa.float64()),
    })


def _make_oi_table(
    symbol: str = "BTCUSDT",
    n: int = 3,
    base_ts: int = 1709251200000,
) -> pa.Table:
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base_ts + i * 300_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base_ts + (i + 1) * 300_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "sum_open_interest": pa.array([50000.0] * n, type=pa.float64()),
        "sum_open_interest_value": pa.array([3350000000.0] * n, type=pa.float64()),
    })


class TestSyncToQuery:
    """End-to-end: sync → raw + curated → DuckDB query."""

    @patch("kronos.data.sync.fetch_klines")
    def test_synced_data_queryable(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        """Data synced by sync_klines should be loadable via query.load()."""
        mock_fetch.return_value = _make_kline_table(n=120)  # 2 hours
        sync_klines("BTCUSDT", base_path=tmp_path, since=1709251200000)

        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m")
        assert len(df) == 120

        df_1h = load("BTCUSDT", base_path=tmp_path, timeframe="1h")
        assert len(df_1h) == 2

    @patch("kronos.data.sync.fetch_klines")
    def test_raw_and_curated_both_written(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        """Sync should write both raw NDJSON and curated Parquet."""
        mock_fetch.return_value = _make_kline_table(n=10)
        sync_klines("BTCUSDT", base_path=tmp_path, since=1709251200000)

        # Raw layer
        raw_dir = tmp_path / "raw" / "BTCUSDT" / "klines_1m"
        raw_files = list(raw_dir.glob("*.ndjson"))
        assert len(raw_files) == 1
        lines = raw_files[0].read_text().strip().split("\n")
        assert len(lines) == 10

        # Validate NDJSON is valid JSON
        for line in lines:
            record = json.loads(line)
            assert "event_time" in record
            assert "symbol" in record

        # Curated layer
        curated_dir = tmp_path / "curated" / "BTCUSDT" / "klines_1m"
        parquet_files = list(curated_dir.rglob("*.parquet"))
        assert len(parquet_files) >= 1

    @patch("kronos.data.sync.fetch_klines")
    def test_incremental_sync(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        """Second sync should append without duplicating data."""
        base = 1709251200000
        # First sync: 30 bars
        mock_fetch.return_value = _make_kline_table(n=30, base_ts=base)
        sync_klines("BTCUSDT", base_path=tmp_path, since=base)

        # Second sync: next 30 bars
        next_base = base + 30 * 60_000
        mock_fetch.return_value = _make_kline_table(n=30, base_ts=next_base)
        sync_klines("BTCUSDT", base_path=tmp_path, since=next_base)

        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m")
        assert len(df) == 60

    @patch("kronos.data.sync.fetch_klines")
    def test_coverage_after_sync(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        """Coverage query should reflect synced data accurately."""
        mock_fetch.return_value = _make_kline_table(n=60)
        sync_klines("BTCUSDT", base_path=tmp_path, since=1709251200000)

        infos = coverage("BTCUSDT", base_path=tmp_path, datasets=["klines_1m"])
        assert len(infos) == 1
        info = infos[0]
        assert info.bar_count == 60
        assert info.gaps == []

    @patch("kronos.data.sync.fetch_klines")
    def test_gap_detection_after_sync(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        """Gap detection should find holes in synced data."""
        base = 1709251200000
        # Sync 10 bars, skip 5, then sync 10 more
        mock_fetch.return_value = _make_kline_table(n=10, base_ts=base)
        sync_klines("BTCUSDT", base_path=tmp_path, since=base)

        gap_base = base + 15 * 60_000
        mock_fetch.return_value = _make_kline_table(n=10, base_ts=gap_base)
        sync_klines("BTCUSDT", base_path=tmp_path, since=gap_base)

        gaps = detect_gaps("BTCUSDT", "klines_1m", base_path=tmp_path)
        assert len(gaps) == 1

    @patch("kronos.data.sync.fetch_open_interest")
    @patch("kronos.data.sync.fetch_funding_rates")
    @patch("kronos.data.sync.fetch_klines")
    def test_sync_all_creates_all_datasets(
        self,
        mock_klines: MagicMock,
        mock_funding: MagicMock,
        mock_oi: MagicMock,
        tmp_path: Path,
    ) -> None:
        """sync_all should produce queryable data for all three dataset types."""
        mock_klines.return_value = _make_kline_table(n=10)
        mock_funding.return_value = _make_funding_table(n=3)
        mock_oi.return_value = _make_oi_table(n=3)

        results = sync_all(["BTCUSDT"], base_path=tmp_path, since=1709251200000)
        assert results["BTCUSDT"]["klines"] == 10
        assert results["BTCUSDT"]["funding"] == 3
        assert results["BTCUSDT"]["oi"] == 3

        infos = coverage("BTCUSDT", base_path=tmp_path)
        datasets_with_data = {i.dataset for i in infos}
        assert datasets_with_data == {"klines_1m", "funding", "oi"}
