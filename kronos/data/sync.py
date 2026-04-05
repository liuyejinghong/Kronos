"""Data synchronization pipeline: adapter → schema validation → raw → curated."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from kronos.common.log import get_logger
from kronos.data.loaders.binance_usdm import (
    fetch_funding_rates,
    fetch_klines,
    fetch_open_interest,
)
from kronos.data.schemas.candle import CANDLE_DEDUP_KEY
from kronos.data.schemas.funding import FUNDING_DEDUP_KEY
from kronos.data.schemas.oi import OI_DEDUP_KEY
from kronos.data.storage.parquet_store import (
    cleanup_temp_files,
    write_records_partitioned,
)
from kronos.data.storage.query import coverage

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("kronos.data.sync")


def _save_raw(
    data: list[dict[str, Any]],
    base_path: Path,
    symbol: str,
    dataset: str,
) -> None:
    """Save raw API response as NDJSON for audit trail."""
    from pathlib import Path as _Path

    raw_dir = _Path(base_path) / "raw" / symbol / dataset
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    raw_file = raw_dir / f"{timestamp}.ndjson"

    with open(raw_file, "w") as f:
        for record in data:
            f.write(json.dumps(record) + "\n")

    log.info("raw.saved", path=str(raw_file), records=len(data))


def _get_last_event_time(
    symbol: str,
    dataset: str,
    base_path: Path,
) -> int | None:
    """Get the last event_time for incremental sync."""
    infos = coverage(symbol, base_path=base_path, datasets=[dataset])
    if not infos:
        return None
    return infos[0].max_event_time


def sync_klines(
    symbol: str,
    *,
    base_path: Path,
    since: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> int:
    """Sync 1m kline data for a symbol.

    Args:
        symbol: Trading pair.
        base_path: Base data directory.
        since: Start time (epoch-ms). Auto-detects for incremental.
        max_retries: Max API retries.
        request_interval_ms: Min interval between requests.

    Returns:
        Number of bars written.
    """
    # Determine start time
    if since is None:
        last = _get_last_event_time(symbol, "klines_1m", base_path)
        if last is not None:
            since = last + 60_000  # Next minute after last bar
            log.info("sync.incremental", symbol=symbol, dataset="klines_1m", from_ms=since)

    table = fetch_klines(
        symbol,
        start_time=since,
        max_retries=max_retries,
        request_interval_ms=request_interval_ms,
    )

    n_rows = int(table.num_rows)
    if n_rows == 0:
        log.info("sync.no_new_data", symbol=symbol, dataset="klines_1m")
        return 0

    _save_raw(table.to_pylist(), base_path, symbol, "klines_1m")

    paths = write_records_partitioned(
        table, base_path, symbol, "klines_1m", CANDLE_DEDUP_KEY,
    )

    log.info(
        "sync.klines_complete",
        symbol=symbol,
        bars=n_rows,
        partitions=len(paths),
    )
    return n_rows


def sync_funding(
    symbol: str,
    *,
    base_path: Path,
    since: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> int:
    """Sync funding rate data for a symbol.

    Returns:
        Number of records written.
    """
    if since is None:
        last = _get_last_event_time(symbol, "funding", base_path)
        if last is not None:
            since = last + 1
            log.info("sync.incremental", symbol=symbol, dataset="funding", from_ms=since)

    table = fetch_funding_rates(
        symbol,
        start_time=since,
        max_retries=max_retries,
        request_interval_ms=request_interval_ms,
    )

    n_rows = int(table.num_rows)
    if n_rows == 0:
        log.info("sync.no_new_data", symbol=symbol, dataset="funding")
        return 0

    _save_raw(table.to_pylist(), base_path, symbol, "funding")

    paths = write_records_partitioned(
        table, base_path, symbol, "funding", FUNDING_DEDUP_KEY,
    )

    log.info(
        "sync.funding_complete",
        symbol=symbol,
        records=n_rows,
        partitions=len(paths),
    )
    return n_rows


def sync_oi(
    symbol: str,
    *,
    base_path: Path,
    since: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> int:
    """Sync open interest data for a symbol.

    Returns:
        Number of records written.
    """
    if since is None:
        last = _get_last_event_time(symbol, "oi", base_path)
        if last is not None:
            since = last + 1
            log.info("sync.incremental", symbol=symbol, dataset="oi", from_ms=since)

    table = fetch_open_interest(
        symbol,
        start_time=since,
        max_retries=max_retries,
        request_interval_ms=request_interval_ms,
    )

    n_rows = int(table.num_rows)
    if n_rows == 0:
        log.info("sync.no_new_data", symbol=symbol, dataset="oi")
        return 0

    _save_raw(table.to_pylist(), base_path, symbol, "oi")

    paths = write_records_partitioned(
        table, base_path, symbol, "oi", OI_DEDUP_KEY,
    )

    log.info(
        "sync.oi_complete",
        symbol=symbol,
        records=n_rows,
        partitions=len(paths),
    )
    return n_rows


def sync_symbol(
    symbol: str,
    *,
    base_path: Path,
    since: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> dict[str, int]:
    """Sync all data types for a symbol.

    Returns:
        Dict with counts: {"klines": N, "funding": N, "oi": N}.
    """
    log.info("sync.symbol_start", symbol=symbol)

    klines = sync_klines(
        symbol, base_path=base_path, since=since,
        max_retries=max_retries, request_interval_ms=request_interval_ms,
    )
    funding = sync_funding(
        symbol, base_path=base_path, since=since,
        max_retries=max_retries, request_interval_ms=request_interval_ms,
    )
    oi = sync_oi(
        symbol, base_path=base_path, since=since,
        max_retries=max_retries, request_interval_ms=request_interval_ms,
    )

    log.info(
        "sync.symbol_complete",
        symbol=symbol,
        klines=klines,
        funding=funding,
        oi=oi,
    )
    return {"klines": klines, "funding": funding, "oi": oi}


def sync_all(
    symbols: list[str],
    *,
    base_path: Path,
    since: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> dict[str, dict[str, int]]:
    """Sync all data for multiple symbols.

    Cleans up temp files before starting.

    Returns:
        Dict of symbol -> counts.
    """
    cleaned = cleanup_temp_files(base_path)
    if cleaned > 0:
        log.info("sync.temp_cleaned", count=cleaned)

    results: dict[str, dict[str, int]] = {}
    for symbol in symbols:
        results[symbol] = sync_symbol(
            symbol, base_path=base_path, since=since,
            max_retries=max_retries, request_interval_ms=request_interval_ms,
        )

    total_klines = sum(r["klines"] for r in results.values())
    total_funding = sum(r["funding"] for r in results.values())
    total_oi = sum(r["oi"] for r in results.values())
    log.info(
        "sync.all_complete",
        symbols=len(symbols),
        total_klines=total_klines,
        total_funding=total_funding,
        total_oi=total_oi,
    )
    return results
