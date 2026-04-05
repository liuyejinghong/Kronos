"""Binance USDM exchange info loader."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

from kronos.common.errors import DataError
from kronos.common.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("kronos.data.loaders.exchange_info")

BINANCE_USDM_EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"


@dataclass
class SymbolInfo:
    """Metadata for a single trading symbol."""

    symbol: str
    onboard_date: int  # epoch-ms
    price_precision: int
    quantity_precision: int
    tick_size: float
    step_size: float
    status: str
    contract_type: str


def fetch_exchange_info() -> list[SymbolInfo]:
    """Fetch exchangeInfo from Binance USDM and extract perpetual contract metadata.

    Returns:
        List of SymbolInfo for all PERPETUAL + TRADING symbols.

    Raises:
        DataError: If the API request fails.
    """
    try:
        resp = httpx.get(BINANCE_USDM_EXCHANGE_INFO_URL, timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise DataError(f"Failed to fetch exchangeInfo: {e}") from e

    data: dict[str, Any] = resp.json()
    symbols: list[SymbolInfo] = []

    for s in data.get("symbols", []):
        contract_type = s.get("contractType", "")
        status = s.get("status", "")

        if contract_type != "PERPETUAL" or status != "TRADING":
            continue

        # Extract tick_size and step_size from filters
        tick_size = 0.0
        step_size = 0.0
        for f in s.get("filters", []):
            if f.get("filterType") == "PRICE_FILTER":
                tick_size = float(f.get("tickSize", 0))
            elif f.get("filterType") == "LOT_SIZE":
                step_size = float(f.get("stepSize", 0))

        symbols.append(
            SymbolInfo(
                symbol=s["symbol"],
                onboard_date=int(s.get("onboardDate", 0)),
                price_precision=int(s.get("pricePrecision", 0)),
                quantity_precision=int(s.get("quantityPrecision", 0)),
                tick_size=tick_size,
                step_size=step_size,
                status=status,
                contract_type=contract_type,
            )
        )

    log.info("exchange_info.fetched", symbol_count=len(symbols))
    return symbols


def save_exchange_info(symbols: list[SymbolInfo], base_path: Path) -> Path:
    """Save exchange info to Parquet file.

    Args:
        symbols: List of SymbolInfo to save.
        base_path: Base data directory (e.g. ./data).

    Returns:
        Path to the written Parquet file.
    """
    curated = base_path / "curated"
    curated.mkdir(parents=True, exist_ok=True)
    output_path = curated / "exchange_info.parquet"

    ingested_at = int(time.time() * 1000)

    table = pa.table(
        {
            "symbol": [s.symbol for s in symbols],
            "onboard_date": pa.array([s.onboard_date for s in symbols], type=pa.int64()),
            "price_precision": pa.array([s.price_precision for s in symbols], type=pa.int32()),
            "quantity_precision": pa.array(
                [s.quantity_precision for s in symbols], type=pa.int32()
            ),
            "tick_size": pa.array([s.tick_size for s in symbols], type=pa.float64()),
            "step_size": pa.array([s.step_size for s in symbols], type=pa.float64()),
            "status": [s.status for s in symbols],
            "contract_type": [s.contract_type for s in symbols],
            "ingested_at": pa.array([ingested_at] * len(symbols), type=pa.int64()),
        }
    )

    pq.write_table(table, output_path)
    log.info("exchange_info.saved", path=str(output_path), rows=len(symbols))
    return output_path


def load_exchange_info(base_path: Path) -> pa.Table:
    """Load cached exchange info from Parquet.

    Args:
        base_path: Base data directory.

    Returns:
        PyArrow Table with exchange info.

    Raises:
        DataError: If the cache file doesn't exist.
    """
    path = base_path / "curated" / "exchange_info.parquet"
    if not path.exists():
        raise DataError(
            f"Exchange info cache not found at {path}. "
            "Run 'kronos data sync' first to fetch metadata."
        )
    return pq.read_table(path)


def validate_symbol(symbol: str, base_path: Path) -> bool:
    """Check if a symbol is valid (exists in cached exchange info).

    Args:
        symbol: Symbol to validate (e.g. "BTCUSDT").
        base_path: Base data directory.

    Returns:
        True if symbol exists and is a trading perpetual.
    """
    try:
        table = load_exchange_info(base_path)
    except DataError:
        log.warning("exchange_info.not_cached", symbol=symbol)
        return False

    symbols = table.column("symbol").to_pylist()
    return symbol in symbols


def get_onboard_date(symbol: str, base_path: Path) -> int | None:
    """Get the onboard date for a symbol.

    Args:
        symbol: Symbol to look up.
        base_path: Base data directory.

    Returns:
        Onboard date as epoch-ms, or None if not found.
    """
    try:
        table = load_exchange_info(base_path)
    except DataError:
        return None

    symbols = table.column("symbol").to_pylist()
    if symbol not in symbols:
        return None

    idx = symbols.index(symbol)
    return int(table.column("onboard_date")[idx].as_py())
