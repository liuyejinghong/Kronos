"""Unit tests for DuckDB query layer."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pyarrow as pa
import pytest

from kronos.common.errors import DataError
from kronos.data.storage.parquet_store import write_partition
from kronos.data.storage.query import coverage, detect_gaps, load, load_universe

if TYPE_CHECKING:
    from pathlib import Path


def _make_1m_table(
    symbol: str = "BTCUSDT",
    base_ts: int = 1709251200000,  # 2024-03-01 00:00 UTC
    n: int = 60,
    open_price: float = 67000.0,
) -> pa.Table:
    """Create N 1-minute bars starting from base_ts."""
    now = int(time.time() * 1000)
    event_times = [base_ts + i * 60_000 for i in range(n)]
    return pa.table({
        "event_time": pa.array(event_times, type=pa.int64()),
        "available_at": pa.array([t + 60_000 for t in event_times], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "open": pa.array([open_price + i * 10 for i in range(n)], type=pa.float64()),
        "high": pa.array([open_price + i * 10 + 50 for i in range(n)], type=pa.float64()),
        "low": pa.array([open_price + i * 10 - 50 for i in range(n)], type=pa.float64()),
        "close": pa.array([open_price + i * 10 + 20 for i in range(n)], type=pa.float64()),
        "volume": pa.array([100.0] * n, type=pa.float64()),
    })


def _write_test_data(tmp_path: Path, symbol: str = "BTCUSDT", n: int = 60) -> None:
    """Write test 1m data to the correct partition path."""
    table = _make_1m_table(symbol=symbol, n=n)
    write_partition(table, tmp_path, symbol, "klines_1m", 2024, 3)


class TestLoad:
    """Tests for single-symbol data loading."""

    def test_load_1m(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m")
        assert len(df) == 60
        assert "event_time" in df.columns

    def test_load_1h_resamples(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path, n=120)  # 2 hours of data
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1h")
        assert len(df) == 2

    def test_resample_ohlc_correctness(self, tmp_path: Path) -> None:
        """Verify OHLC aggregation: open=first, high=max, low=min, close=last."""
        _write_test_data(tmp_path, n=60)  # 1 hour
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1h")
        assert len(df) == 1
        row = df.iloc[0]
        # open should be the first bar's open (67000.0)
        assert row["open"] == pytest.approx(67000.0)
        # high should be the last bar's high (67000 + 59*10 + 50 = 67640)
        assert row["high"] == pytest.approx(67640.0)
        # low should be the first bar's low (67000 - 50 = 66950)
        assert row["low"] == pytest.approx(66950.0)
        # close should be the last bar's close (67000 + 59*10 + 20 = 67610)
        assert row["close"] == pytest.approx(67610.0)
        # volume should be sum (100 * 60 = 6000)
        assert row["volume"] == pytest.approx(6000.0)

    def test_load_with_since(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        base = 1709251200000
        midpoint = base + 30 * 60_000
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m", since=midpoint)
        assert len(df) == 30

    def test_load_with_until(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        base = 1709251200000
        midpoint = base + 30 * 60_000
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m", until=midpoint)
        assert len(df) == 30

    def test_load_with_as_of(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        base = 1709251200000
        # available_at = event_time + 60_000
        # bars 0..9 have available_at from base+60000 to base+10*60000
        as_of_ms = base + 10 * 60_000  # 10 bars' available_at <= this
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m", as_of=as_of_ms)
        assert len(df) == 10

    def test_load_with_iso_string(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m", since="2024-03-01T00:00:00")
        assert len(df) == 60

    def test_load_no_data_returns_empty(self, tmp_path: Path) -> None:
        df = load("BTCUSDT", base_path=tmp_path, timeframe="1m")
        assert df.empty

    def test_load_invalid_timeframe(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match=r"Invalid timeframe"):
            load("BTCUSDT", base_path=tmp_path, timeframe="2m")


class TestLoadUniverse:
    """Tests for multi-symbol data loading."""

    def test_multiple_symbols(self, tmp_path: Path) -> None:
        table_btc = _make_1m_table(symbol="BTCUSDT", n=10)
        table_eth = _make_1m_table(symbol="ETHUSDT", n=10, open_price=3500.0)
        write_partition(table_btc, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        write_partition(table_eth, tmp_path, "ETHUSDT", "klines_1m", 2024, 3)

        df = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1m")
        assert len(df) == 20
        assert set(df["symbol"].unique()) == {"BTCUSDT", "ETHUSDT"}

    def test_sorted_by_time_then_symbol(self, tmp_path: Path) -> None:
        table_btc = _make_1m_table(symbol="BTCUSDT", n=5)
        table_eth = _make_1m_table(symbol="ETHUSDT", n=5, open_price=3500.0)
        write_partition(table_btc, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        write_partition(table_eth, tmp_path, "ETHUSDT", "klines_1m", 2024, 3)

        df = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1m")
        times = df["event_time"].tolist()
        assert times == sorted(times)

    def test_empty_universe(self, tmp_path: Path) -> None:
        df = load_universe(["FAKE"], base_path=tmp_path, timeframe="1m")
        assert df.empty


class TestCoverage:
    """Tests for data coverage queries."""

    def test_coverage_returns_info(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        infos = coverage("BTCUSDT", base_path=tmp_path, datasets=["klines_1m"])
        assert len(infos) == 1
        info = infos[0]
        assert info.symbol == "BTCUSDT"
        assert info.dataset == "klines_1m"
        assert info.bar_count == 60
        assert info.min_event_time == 1709251200000
        assert info.max_event_time == 1709251200000 + 59 * 60_000

    def test_coverage_no_data(self, tmp_path: Path) -> None:
        infos = coverage("BTCUSDT", base_path=tmp_path, datasets=["klines_1m"])
        assert len(infos) == 0

    def test_coverage_multiple_datasets(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path)
        infos = coverage("BTCUSDT", base_path=tmp_path)  # defaults: klines_1m, funding, oi
        assert len(infos) == 1  # only klines_1m has data

    def test_coverage_reports_gaps(self, tmp_path: Path) -> None:
        """Coverage should include gap info when gaps exist."""
        base = 1709251200000
        # 10 bars, then skip 5, then 10 more
        times_a = [base + i * 60_000 for i in range(10)]
        times_b = [base + (i + 15) * 60_000 for i in range(10)]
        all_times = times_a + times_b
        n = len(all_times)
        now = int(time.time() * 1000)
        table = pa.table({
            "event_time": pa.array(all_times, type=pa.int64()),
            "available_at": pa.array([t + 60_000 for t in all_times], type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": ["BTCUSDT"] * n,
            "open": pa.array([67000.0] * n, type=pa.float64()),
            "high": pa.array([67500.0] * n, type=pa.float64()),
            "low": pa.array([66800.0] * n, type=pa.float64()),
            "close": pa.array([67200.0] * n, type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
        })
        write_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        infos = coverage("BTCUSDT", base_path=tmp_path, datasets=["klines_1m"])
        assert len(infos) == 1
        assert len(infos[0].gaps) == 1


class TestDetectGaps:
    """Tests for gap detection logic."""

    def test_no_gaps_in_continuous_data(self, tmp_path: Path) -> None:
        _write_test_data(tmp_path, n=60)
        gaps = detect_gaps("BTCUSDT", "klines_1m", base_path=tmp_path)
        assert gaps == []

    def test_detects_gap_in_klines(self, tmp_path: Path) -> None:
        base = 1709251200000
        # 10 bars, skip 5 minutes, then 10 more bars
        times_a = [base + i * 60_000 for i in range(10)]
        times_b = [base + (i + 15) * 60_000 for i in range(10)]
        all_times = times_a + times_b
        n = len(all_times)
        now = int(time.time() * 1000)
        table = pa.table({
            "event_time": pa.array(all_times, type=pa.int64()),
            "available_at": pa.array([t + 60_000 for t in all_times], type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": ["BTCUSDT"] * n,
            "open": pa.array([67000.0] * n, type=pa.float64()),
            "high": pa.array([67500.0] * n, type=pa.float64()),
            "low": pa.array([66800.0] * n, type=pa.float64()),
            "close": pa.array([67200.0] * n, type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
        })
        write_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)

        gaps = detect_gaps("BTCUSDT", "klines_1m", base_path=tmp_path)
        assert len(gaps) == 1
        gap_start, gap_end = gaps[0]
        # Gap should be between last bar of first chunk and first bar of second chunk
        assert gap_start == times_a[-1] + 60_000
        assert gap_end == times_b[0] - 60_000

    def test_ignores_gaps_before_onboard_date(self, tmp_path: Path) -> None:
        base = 1709251200000
        onboard = base + 10 * 60_000  # Onboard at bar 10
        # Gap at bars 5-9 (before onboard), continuous after onboard
        times_a = [base + i * 60_000 for i in range(5)]
        times_b = [base + (i + 10) * 60_000 for i in range(20)]
        all_times = times_a + times_b
        n = len(all_times)
        now = int(time.time() * 1000)
        table = pa.table({
            "event_time": pa.array(all_times, type=pa.int64()),
            "available_at": pa.array([t + 60_000 for t in all_times], type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": ["BTCUSDT"] * n,
            "open": pa.array([67000.0] * n, type=pa.float64()),
            "high": pa.array([67500.0] * n, type=pa.float64()),
            "low": pa.array([66800.0] * n, type=pa.float64()),
            "close": pa.array([67200.0] * n, type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
        })
        write_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)

        gaps = detect_gaps(
            "BTCUSDT", "klines_1m",
            base_path=tmp_path,
            onboard_date=onboard,
        )
        assert gaps == []

    def test_no_data_returns_empty(self, tmp_path: Path) -> None:
        gaps = detect_gaps("BTCUSDT", "klines_1m", base_path=tmp_path)
        assert gaps == []

    def test_unknown_dataset_returns_empty(self, tmp_path: Path) -> None:
        gaps = detect_gaps("BTCUSDT", "unknown_dataset", base_path=tmp_path)
        assert gaps == []

    def test_detects_gap_in_funding(self, tmp_path: Path) -> None:
        """Funding rate has 8h intervals."""
        base = 1709251200000
        interval = 28_800_000  # 8 hours
        # 3 records, skip 1 (8h gap), then 3 more
        times_a = [base + i * interval for i in range(3)]
        times_b = [base + (i + 4) * interval for i in range(3)]
        all_times = times_a + times_b
        n = len(all_times)
        now = int(time.time() * 1000)
        table = pa.table({
            "event_time": pa.array(all_times, type=pa.int64()),
            "available_at": pa.array(all_times, type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": ["BTCUSDT"] * n,
            "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
            "mark_price": pa.array([67000.0] * n, type=pa.float64()),
        })
        write_partition(table, tmp_path, "BTCUSDT", "funding", 2024, 3)

        gaps = detect_gaps("BTCUSDT", "funding", base_path=tmp_path)
        assert len(gaps) == 1
