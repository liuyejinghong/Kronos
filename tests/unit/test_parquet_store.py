"""Unit tests for Parquet storage layer."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pyarrow as pa

if TYPE_CHECKING:
    from pathlib import Path

from kronos.data.storage.parquet_store import (
    _year_month_from_epoch_ms,
    append_to_partition,
    cleanup_temp_files,
    partition_path,
    read_partition,
    read_partitions,
    write_partition,
    write_records_partitioned,
)


def _make_candle_table(
    symbol: str = "BTCUSDT",
    event_times: list[int] | None = None,
    n: int = 5,
) -> pa.Table:
    """Create a minimal candle-like table for testing."""
    if event_times is None:
        base = 1709251200000  # 2024-03-01 00:00 UTC
        event_times = [base + i * 60_000 for i in range(n)]

    n = len(event_times)
    return pa.table({
        "event_time": pa.array(event_times, type=pa.int64()),
        "available_at": pa.array([t + 60_000 for t in event_times], type=pa.int64()),
        "ingested_at": pa.array([int(time.time() * 1000)] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "open": pa.array([67000.0] * n, type=pa.float64()),
        "high": pa.array([67500.0] * n, type=pa.float64()),
        "low": pa.array([66800.0] * n, type=pa.float64()),
        "close": pa.array([67200.0] * n, type=pa.float64()),
        "volume": pa.array([100.0] * n, type=pa.float64()),
    })


class TestPartitionPath:
    def test_kline_path(self, tmp_path: Path) -> None:
        p = partition_path(tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert str(p).endswith("curated/BTCUSDT/klines_1m/2024/03.parquet")

    def test_funding_path(self, tmp_path: Path) -> None:
        p = partition_path(tmp_path, "ETHUSDT", "funding", 2024, 12)
        assert str(p).endswith("curated/ETHUSDT/funding/2024/12.parquet")

    def test_month_zero_padded(self, tmp_path: Path) -> None:
        p = partition_path(tmp_path, "BTCUSDT", "klines_1m", 2024, 1)
        assert "01.parquet" in str(p)


class TestYearMonthExtraction:
    def test_march_2024(self) -> None:
        # 2024-03-01 00:00 UTC
        assert _year_month_from_epoch_ms(1709251200000) == (2024, 3)

    def test_december_2023(self) -> None:
        # 2023-12-15 00:00 UTC
        assert _year_month_from_epoch_ms(1702598400000) == (2023, 12)


class TestWriteAndRead:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        table = _make_candle_table()
        path = write_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert path.exists()

    def test_read_returns_data(self, tmp_path: Path) -> None:
        table = _make_candle_table()
        write_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        result = read_partition(tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert result is not None
        assert result.num_rows == 5

    def test_read_missing_returns_none(self, tmp_path: Path) -> None:
        result = read_partition(tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert result is None

    def test_atomic_write_no_temp_leftover(self, tmp_path: Path) -> None:
        table = _make_candle_table()
        write_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        temps = list((tmp_path / "curated").rglob("*.parquet.tmp"))
        assert len(temps) == 0


class TestReadPartitions:
    def test_read_all(self, tmp_path: Path) -> None:
        t1 = _make_candle_table(event_times=[1709251200000 + i * 60_000 for i in range(3)])
        t2 = _make_candle_table(event_times=[1711929600000 + i * 60_000 for i in range(2)])  # 2024-04
        write_partition(t1, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        write_partition(t2, tmp_path, "BTCUSDT", "klines_1m", 2024, 4)
        result = read_partitions(tmp_path, "BTCUSDT", "klines_1m")
        assert result is not None
        assert result.num_rows == 5

    def test_read_specific_months(self, tmp_path: Path) -> None:
        t1 = _make_candle_table(event_times=[1709251200000])
        t2 = _make_candle_table(event_times=[1711929600000])
        write_partition(t1, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        write_partition(t2, tmp_path, "BTCUSDT", "klines_1m", 2024, 4)
        result = read_partitions(tmp_path, "BTCUSDT", "klines_1m", [(2024, 3)])
        assert result is not None
        assert result.num_rows == 1

    def test_read_empty_returns_none(self, tmp_path: Path) -> None:
        result = read_partitions(tmp_path, "BTCUSDT", "klines_1m")
        assert result is None


class TestAppend:
    def test_append_deduplicates(self, tmp_path: Path) -> None:
        base_ts = 1709251200000
        t1 = _make_candle_table(event_times=[base_ts, base_ts + 60_000])
        t2 = _make_candle_table(event_times=[base_ts + 60_000, base_ts + 120_000])  # overlap
        write_partition(t1, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        append_to_partition(t2, tmp_path, "BTCUSDT", "klines_1m", 2024, 3, ["symbol", "event_time"])
        result = read_partition(tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert result is not None
        assert result.num_rows == 3  # deduped

    def test_append_to_empty(self, tmp_path: Path) -> None:
        table = _make_candle_table(n=3)
        append_to_partition(table, tmp_path, "BTCUSDT", "klines_1m", 2024, 3, ["symbol", "event_time"])
        result = read_partition(tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert result is not None
        assert result.num_rows == 3

    def test_append_preserves_sort(self, tmp_path: Path) -> None:
        base = 1709251200000
        t1 = _make_candle_table(event_times=[base + 120_000])  # later
        t2 = _make_candle_table(event_times=[base])  # earlier
        write_partition(t1, tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        append_to_partition(t2, tmp_path, "BTCUSDT", "klines_1m", 2024, 3, ["symbol", "event_time"])
        result = read_partition(tmp_path, "BTCUSDT", "klines_1m", 2024, 3)
        assert result is not None
        times = result.column("event_time").to_pylist()
        assert times == sorted(times)


class TestWriteRecordsPartitioned:
    def test_splits_across_months(self, tmp_path: Path) -> None:
        march_ts = 1709251200000  # 2024-03-01
        april_ts = 1711929600000  # 2024-04-01
        table = _make_candle_table(event_times=[march_ts, april_ts])
        paths = write_records_partitioned(table, tmp_path, "BTCUSDT", "klines_1m", ["symbol", "event_time"])
        assert len(paths) == 2

    def test_empty_table(self, tmp_path: Path) -> None:
        table = _make_candle_table(event_times=[])
        paths = write_records_partitioned(table, tmp_path, "BTCUSDT", "klines_1m", ["symbol", "event_time"])
        assert len(paths) == 0


class TestCleanup:
    def test_cleans_temp_files(self, tmp_path: Path) -> None:
        curated = tmp_path / "curated" / "BTCUSDT" / "klines_1m" / "2024"
        curated.mkdir(parents=True)
        (curated / "03.parquet.tmp").touch()
        (curated / "04.parquet.tmp").touch()
        count = cleanup_temp_files(tmp_path)
        assert count == 2
        assert not list(curated.glob("*.tmp"))

    def test_no_temps_returns_zero(self, tmp_path: Path) -> None:
        assert cleanup_temp_files(tmp_path) == 0
