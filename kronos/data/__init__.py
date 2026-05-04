"""Public Layer 1 data loading API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kronos.data.storage.query import load, load_universe

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def load_funding(
    symbol: str,
    *,
    base_path: Path,
    since: str | int | None = None,
    until: str | int | None = None,
    as_of: str | int | None = None,
) -> pd.DataFrame:
    """Load PIT-safe funding data for a single symbol."""
    return load(
        symbol,
        base_path=base_path,
        timeframe="1m",
        dataset="funding",
        since=since,
        until=until,
        as_of=as_of,
    )


def load_oi(
    symbol: str,
    *,
    base_path: Path,
    since: str | int | None = None,
    until: str | int | None = None,
    as_of: str | int | None = None,
) -> pd.DataFrame:
    """Load PIT-safe open-interest data for a single symbol."""
    return load(
        symbol,
        base_path=base_path,
        timeframe="1m",
        dataset="oi",
        since=since,
        until=until,
        as_of=as_of,
    )


def load_liquidations(
    symbol: str,
    *,
    base_path: Path,
    since: str | int | None = None,
    until: str | int | None = None,
    as_of: str | int | None = None,
) -> pd.DataFrame:
    """Load PIT-safe liquidation flow data for a single symbol if available."""
    return load(
        symbol,
        base_path=base_path,
        timeframe="1m",
        dataset="liquidations",
        since=since,
        until=until,
        as_of=as_of,
    )


__all__ = ["load", "load_funding", "load_liquidations", "load_oi", "load_universe"]
