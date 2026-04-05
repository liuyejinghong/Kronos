"""Unit tests for the sync pipeline (mocked, no real API calls)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pyarrow as pa

from kronos.data.sync import sync_all, sync_funding, sync_klines, sync_oi

if TYPE_CHECKING:
    from pathlib import Path


def _make_kline_table(symbol: str = "BTCUSDT", n: int = 5) -> pa.Table:
    """Create a mock kline table."""
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 60_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 60_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "open": pa.array([67000.0] * n, type=pa.float64()),
        "high": pa.array([67500.0] * n, type=pa.float64()),
        "low": pa.array([66800.0] * n, type=pa.float64()),
        "close": pa.array([67200.0] * n, type=pa.float64()),
        "volume": pa.array([100.0] * n, type=pa.float64()),
        "quote_volume": pa.array([6720000.0] * n, type=pa.float64()),
        "trade_count": pa.array([100] * n, type=pa.int64()),
        "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
        "venue": ["binance"] * n,
    })


def _make_funding_table(symbol: str = "BTCUSDT", n: int = 3) -> pa.Table:
    """Create a mock funding table."""
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 28800000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + i * 28800000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
        "mark_price": pa.array([67000.0] * n, type=pa.float64()),
    })


def _make_oi_table(symbol: str = "BTCUSDT", n: int = 3) -> pa.Table:
    """Create a mock OI table."""
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 300000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 300000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "sum_open_interest": pa.array([50000.0] * n, type=pa.float64()),
        "sum_open_interest_value": pa.array([3350000000.0] * n, type=pa.float64()),
    })


class TestSyncKlines:
    @patch("kronos.data.sync.fetch_klines")
    def test_writes_data(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_fetch.return_value = _make_kline_table()
        count = sync_klines("BTCUSDT", base_path=tmp_path, since=1709251200000)
        assert count == 5

    @patch("kronos.data.sync.fetch_klines")
    def test_no_data_returns_zero(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_fetch.return_value = pa.table({
            "event_time": pa.array([], type=pa.int64()),
            "available_at": pa.array([], type=pa.int64()),
            "ingested_at": pa.array([], type=pa.int64()),
            "symbol": pa.array([], type=pa.string()),
            "open": pa.array([], type=pa.float64()),
            "high": pa.array([], type=pa.float64()),
            "low": pa.array([], type=pa.float64()),
            "close": pa.array([], type=pa.float64()),
            "volume": pa.array([], type=pa.float64()),
            "quote_volume": pa.array([], type=pa.float64()),
            "trade_count": pa.array([], type=pa.int64()),
            "taker_buy_volume": pa.array([], type=pa.float64()),
            "venue": pa.array([], type=pa.string()),
        })
        count = sync_klines("BTCUSDT", base_path=tmp_path)
        assert count == 0


class TestSyncFunding:
    @patch("kronos.data.sync.fetch_funding_rates")
    def test_writes_data(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_fetch.return_value = _make_funding_table()
        count = sync_funding("BTCUSDT", base_path=tmp_path, since=1709251200000)
        assert count == 3


class TestSyncOI:
    @patch("kronos.data.sync.fetch_open_interest")
    def test_writes_data(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_fetch.return_value = _make_oi_table()
        count = sync_oi("BTCUSDT", base_path=tmp_path, since=1709251200000)
        assert count == 3


class TestSyncAll:
    @patch("kronos.data.sync.fetch_open_interest")
    @patch("kronos.data.sync.fetch_funding_rates")
    @patch("kronos.data.sync.fetch_klines")
    def test_syncs_multiple_symbols(
        self,
        mock_klines: MagicMock,
        mock_funding: MagicMock,
        mock_oi: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_klines.return_value = _make_kline_table()
        mock_funding.return_value = _make_funding_table()
        mock_oi.return_value = _make_oi_table()

        results = sync_all(
            ["BTCUSDT", "ETHUSDT"],
            base_path=tmp_path,
            since=1709251200000,
        )
        assert len(results) == 2
        assert results["BTCUSDT"]["klines"] == 5
        assert results["ETHUSDT"]["klines"] == 5
