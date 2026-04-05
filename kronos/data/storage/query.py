"""DuckDB query layer over Parquet files."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import duckdb
import pandas as pd

from kronos.common.errors import DataError
from kronos.common.log import get_logger
from kronos.common.types import CoverageInfo

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("kronos.data.storage.query")

# Valid resample timeframes and their minute multipliers
TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def _parse_datetime_to_ms(value: str | int | None) -> int | None:
    """Convert a datetime string or epoch-ms to epoch-ms."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    dt = datetime.fromisoformat(value).replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _glob_pattern(base_path: Path, symbol: str, dataset: str) -> str:
    """Build a glob pattern for DuckDB to scan Parquet files."""
    return str(base_path / "curated" / symbol / dataset / "**" / "*.parquet")


def load(
    symbol: str,
    *,
    base_path: Path,
    timeframe: str = "1m",
    dataset: str = "klines_1m",
    since: str | int | None = None,
    until: str | int | None = None,
    as_of: str | int | None = None,
) -> pd.DataFrame:
    """Load market data for a single symbol.

    Args:
        symbol: Trading symbol (e.g. "BTCUSDT").
        base_path: Base data directory.
        timeframe: Desired timeframe ("1m", "5m", "15m", "1h", "4h", "1d").
        dataset: Dataset to query (default "klines_1m").
        since: Start time (ISO string or epoch-ms).
        until: End time (ISO string or epoch-ms).
        as_of: PIT filter — only data with available_at <= as_of.

    Returns:
        Pandas DataFrame with market data.

    Raises:
        DataError: If timeframe is invalid or no data found.
    """
    if timeframe not in TIMEFRAME_MINUTES:
        raise DataError(f"Invalid timeframe: {timeframe}. Valid: {list(TIMEFRAME_MINUTES.keys())}")

    glob = _glob_pattern(base_path, symbol, dataset)
    since_ms = _parse_datetime_to_ms(since)
    until_ms = _parse_datetime_to_ms(until)
    as_of_ms = _parse_datetime_to_ms(as_of)

    conditions: list[str] = []
    params: dict[str, Any] = {}

    if since_ms is not None:
        conditions.append("event_time >= $since_ms")
        params["since_ms"] = since_ms

    if until_ms is not None:
        conditions.append("event_time < $until_ms")
        params["until_ms"] = until_ms

    if as_of_ms is not None:
        conditions.append("available_at <= $as_of_ms")
        params["as_of_ms"] = as_of_ms

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    minutes = TIMEFRAME_MINUTES[timeframe]

    con = duckdb.connect()
    try:
        if minutes == 1:
            # No resampling needed
            sql = f"""
                SELECT *
                FROM read_parquet('{glob}', union_by_name=true)
                {where_clause}
                ORDER BY event_time
            """
        else:
            # Resample from 1m data using integer floor division for bucket alignment
            interval_ms = minutes * 60 * 1000
            sql = f"""
                SELECT
                    (event_time // {interval_ms}) * {interval_ms} AS event_time,
                    MAX(available_at) AS available_at,
                    MAX(ingested_at) AS ingested_at,
                    symbol,
                    arg_min(open, event_time) AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    arg_max(close, event_time) AS close,
                    SUM(volume) AS volume
                FROM (
                    SELECT *
                    FROM read_parquet('{glob}', union_by_name=true)
                    {where_clause}
                    ORDER BY event_time
                )
                GROUP BY symbol, (event_time // {interval_ms}) * {interval_ms}
                ORDER BY event_time
            """

        result: pd.DataFrame = con.execute(sql, params).fetchdf()
    except duckdb.IOException:
        # No parquet files found
        log.warning("query.no_data", symbol=symbol, dataset=dataset)
        return pd.DataFrame()
    finally:
        con.close()

    log.info("query.loaded", symbol=symbol, timeframe=timeframe, rows=len(result))
    return result


def load_universe(
    symbols: list[str],
    *,
    base_path: Path,
    timeframe: str = "1m",
    dataset: str = "klines_1m",
    since: str | int | None = None,
    until: str | int | None = None,
    as_of: str | int | None = None,
) -> pd.DataFrame:
    """Load market data for multiple symbols.

    Args:
        symbols: List of trading symbols.
        base_path: Base data directory.
        timeframe: Desired timeframe.
        dataset: Dataset to query.
        since: Start time.
        until: End time.
        as_of: PIT filter.

    Returns:
        Combined Pandas DataFrame with symbol column.
    """
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        df = load(
            symbol,
            base_path=base_path,
            timeframe=timeframe,
            dataset=dataset,
            since=since,
            until=until,
            as_of=as_of,
        )
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(["event_time", "symbol"]).reset_index(drop=True)
    return result


def coverage(
    symbol: str,
    *,
    base_path: Path,
    datasets: list[str] | None = None,
) -> list[CoverageInfo]:
    """Get data coverage info for a symbol.

    Args:
        symbol: Trading symbol.
        base_path: Base data directory.
        datasets: Datasets to check. Defaults to ["klines_1m", "funding", "oi"].

    Returns:
        List of CoverageInfo, one per dataset.
    """
    if datasets is None:
        datasets = ["klines_1m", "funding", "oi"]

    results: list[CoverageInfo] = []

    for dataset in datasets:
        glob = _glob_pattern(base_path, symbol, dataset)

        con = duckdb.connect()
        try:
            sql = f"""
                SELECT
                    MIN(event_time) AS min_event_time,
                    MAX(event_time) AS max_event_time,
                    COUNT(*) AS bar_count
                FROM read_parquet('{glob}', union_by_name=true)
            """
            row = con.execute(sql).fetchone()
        except duckdb.IOException:
            continue
        finally:
            con.close()

        if row is None or row[0] is None:
            continue

        results.append(CoverageInfo(
            symbol=symbol,
            dataset=dataset,
            min_event_time=int(row[0]),
            max_event_time=int(row[1]),
            bar_count=int(row[2]),
        ))

    return results
