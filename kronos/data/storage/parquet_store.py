"""Month-partitioned Parquet storage with atomic writes."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.parquet as pq

from kronos.common.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("kronos.data.storage.parquet_store")


def partition_path(
    base_path: Path,
    symbol: str,
    dataset: str,
    year: int,
    month: int,
) -> Path:
    """Build the canonical partition file path.

    Convention: data/curated/{symbol}/{dataset}/{year}/{month:02d}.parquet
    """
    return base_path / "curated" / symbol / dataset / str(year) / f"{month:02d}.parquet"


def _temp_path(final_path: Path) -> Path:
    """Build temp file path for atomic write."""
    return final_path.with_suffix(".parquet.tmp")


def _year_month_from_epoch_ms(epoch_ms: int) -> tuple[int, int]:
    """Extract (year, month) from epoch-ms timestamp."""
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
    return dt.year, dt.month


def write_partition(
    table: pa.Table,
    base_path: Path,
    symbol: str,
    dataset: str,
    year: int,
    month: int,
) -> Path:
    """Write a PyArrow Table to a month partition atomically.

    Args:
        table: Data to write.
        base_path: Base data directory.
        symbol: Trading symbol.
        dataset: Dataset name (e.g. "klines_1m", "funding", "oi").
        year: Partition year.
        month: Partition month.

    Returns:
        Path to the written file.
    """
    final = partition_path(base_path, symbol, dataset, year, month)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(final)

    try:
        pq.write_table(table, tmp)
        os.replace(str(tmp), str(final))
    except Exception:
        # Clean up temp file on failure
        if tmp.exists():
            tmp.unlink()
        raise

    log.info(
        "partition.written",
        symbol=symbol,
        dataset=dataset,
        year=year,
        month=month,
        rows=table.num_rows,
    )
    return final


def read_partition(
    base_path: Path,
    symbol: str,
    dataset: str,
    year: int,
    month: int,
) -> pa.Table | None:
    """Read a single month partition.

    Returns None if the partition file doesn't exist.
    """
    path = partition_path(base_path, symbol, dataset, year, month)
    if not path.exists():
        return None
    return pq.read_table(path)


def read_partitions(
    base_path: Path,
    symbol: str,
    dataset: str,
    year_months: list[tuple[int, int]] | None = None,
) -> pa.Table | None:
    """Read multiple month partitions for a symbol/dataset.

    Args:
        base_path: Base data directory.
        symbol: Trading symbol.
        dataset: Dataset name.
        year_months: List of (year, month) to read. If None, reads all.

    Returns:
        Combined PyArrow Table, or None if no data found.
    """
    base_dir = base_path / "curated" / symbol / dataset

    if not base_dir.exists():
        return None

    if year_months is not None:
        paths = []
        for y, m in year_months:
            p = partition_path(base_path, symbol, dataset, y, m)
            if p.exists():
                paths.append(p)
    else:
        paths = sorted(base_dir.rglob("*.parquet"))

    if not paths:
        return None

    tables = [pq.read_table(p) for p in paths]
    return pa.concat_tables(tables)


def append_to_partition(
    new_data: pa.Table,
    base_path: Path,
    symbol: str,
    dataset: str,
    year: int,
    month: int,
    dedup_columns: list[str],
) -> Path:
    """Append data to an existing partition with dedup.

    Reads existing data, concatenates with new data,
    deduplicates by dedup_columns (keeping last occurrence),
    sorts by event_time, and atomically rewrites.

    Args:
        new_data: New data to append.
        base_path: Base data directory.
        symbol: Trading symbol.
        dataset: Dataset name.
        year: Partition year.
        month: Partition month.
        dedup_columns: Columns to use for deduplication.

    Returns:
        Path to the written file.
    """
    existing = read_partition(base_path, symbol, dataset, year, month)

    combined = pa.concat_tables([existing, new_data]) if existing is not None else new_data

    # Dedup: convert to pandas for dedup, then back to arrow
    df = combined.to_pandas()
    df = df.drop_duplicates(subset=dedup_columns, keep="last")
    df = df.sort_values("event_time").reset_index(drop=True)
    deduped = pa.Table.from_pandas(df, preserve_index=False)

    return write_partition(deduped, base_path, symbol, dataset, year, month)


def write_records_partitioned(
    table: pa.Table,
    base_path: Path,
    symbol: str,
    dataset: str,
    dedup_columns: list[str],
) -> list[Path]:
    """Write records to month-partitioned files, handling cross-month data.

    Splits data by (year, month) based on event_time,
    then appends each chunk to the corresponding partition.

    Args:
        table: Data to write (must contain event_time column).
        base_path: Base data directory.
        symbol: Trading symbol.
        dataset: Dataset name.
        dedup_columns: Columns for deduplication.

    Returns:
        List of paths written.
    """
    if table.num_rows == 0:
        return []

    df = table.to_pandas()
    df["_year"] = df["event_time"].apply(lambda x: _year_month_from_epoch_ms(int(x))[0])
    df["_month"] = df["event_time"].apply(lambda x: _year_month_from_epoch_ms(int(x))[1])

    paths = []
    for (year, month), group in df.groupby(["_year", "_month"]):
        chunk = group.drop(columns=["_year", "_month"])
        chunk_table = pa.Table.from_pandas(chunk, preserve_index=False)
        path = append_to_partition(
            chunk_table, base_path, symbol, dataset,
            int(year), int(month), dedup_columns,
        )
        paths.append(path)

    return paths


def cleanup_temp_files(base_path: Path) -> int:
    """Clean up leftover .parquet.tmp files from interrupted writes.

    Args:
        base_path: Base data directory to scan.

    Returns:
        Number of temp files cleaned up.
    """
    count = 0
    curated = base_path / "curated"
    if not curated.exists():
        return 0

    for tmp in curated.rglob("*.parquet.tmp"):
        tmp.unlink()
        log.info("temp_file.cleaned", path=str(tmp))
        count += 1

    return count
