"""Factor materialization — Parquet storage with _meta.json cache identity.

Path structure (D6):
    data/features/{factor_name}/{version}/{timeframe}/{symbol}/{year}/{month:02d}.parquet
    data/features/{factor_name}/{version}/{timeframe}/{symbol}/{year}/{month:02d}_meta.json

Cache identity is carried by _meta.json, not the path.  params_hash is a
12-char SHA-256 of the sorted JSON-serialized metadata() dict.
"""

from __future__ import annotations

import datetime
import json
import os
import time
from typing import TYPE_CHECKING, Any, cast

import pyarrow as pa
import pyarrow.parquet as pq

from kronos.factor.registry import compute_params_hash

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd
    pass


# ------------------------------------------------------------------
# Path helpers
# ------------------------------------------------------------------

def feature_partition_path(
    base_path: Path,
    factor_name: str,
    version: str,
    timeframe: str,
    symbol: str,
    year: int,
    month: int,
) -> Path:
    return (
        base_path
        / "features"
        / factor_name
        / version
        / timeframe
        / symbol
        / str(year)
        / f"{month:02d}.parquet"
    )


def meta_path(parquet_path: Path) -> Path:
    """Return the _meta.json path that lives alongside a parquet partition."""
    stem = parquet_path.stem  # e.g. "03"
    return parquet_path.parent / f"{stem}_meta.json"


# ------------------------------------------------------------------
# Write
# ------------------------------------------------------------------

def write_factor_partition(
    df: pd.DataFrame,
    base_path: Path,
    factor_name: str,
    version: str,
    timeframe: str,
    symbol: str,
    factor_metadata: dict[str, Any],
    source_max_ingested_at: int,
) -> list[Path]:
    """Materialize a factor DataFrame to month-partitioned Parquet files.

    df must have columns: event_time (int64), available_at (int64), and value.
    Each partition also writes a sibling _meta.json with cache identity.

    Returns list of written parquet paths.
    """
    if df.empty:
        return []

    df = df.copy()
    df["_year"] = df["event_time"].apply(
        lambda t: datetime.datetime.fromtimestamp(t / 1000, tz=datetime.UTC).year
    )
    df["_month"] = df["event_time"].apply(
        lambda t: datetime.datetime.fromtimestamp(t / 1000, tz=datetime.UTC).month
    )

    params_hash = compute_params_hash(factor_metadata)
    generated_at = int(time.time() * 1000)
    written: list[Path] = []

    for group_key, partition in df.groupby(["_year", "_month"]):
        gk = cast("tuple[int, int]", group_key)
        year_val = gk[0]
        month_val = gk[1]
        path = feature_partition_path(
            base_path, factor_name, version, timeframe, symbol, year_val, month_val
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        out = partition.drop(columns=["_year", "_month"]).reset_index(drop=True)
        table = pa.Table.from_pandas(out, preserve_index=False)

        # Atomic write
        tmp = path.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp)
        os.replace(tmp, path)

        # Write manifest
        manifest: dict[str, Any] = {
            "factor_name": factor_name,
            "factor_version": version,
            "timeframe": timeframe,
            "symbol": symbol,
            "params_hash": params_hash,
            "source_max_ingested_at": source_max_ingested_at,
            "generated_at": generated_at,
        }
        mpath = meta_path(path)
        mpath.write_text(json.dumps(manifest, indent=2))
        written.append(path)

    return written


# ------------------------------------------------------------------
# Read
# ------------------------------------------------------------------

def read_factor_partition(
    base_path: Path,
    factor_name: str,
    version: str,
    timeframe: str,
    symbol: str,
    year: int,
    month: int,
) -> pd.DataFrame | None:
    path = feature_partition_path(base_path, factor_name, version, timeframe, symbol, year, month)
    if not path.exists():
        return None
    result: pd.DataFrame = pq.read_table(path).to_pandas()
    return result


def read_factor_all(
    base_path: Path,
    factor_name: str,
    version: str,
    timeframe: str,
    symbol: str,
) -> pd.DataFrame | None:
    """Read all materialized partitions for a factor/version/timeframe/symbol."""
    root = base_path / "features" / factor_name / version / timeframe / symbol
    if not root.exists():
        return None
    files = sorted(root.rglob("*.parquet"))
    if not files:
        return None
    tables = [pq.read_table(f) for f in files]
    result: pd.DataFrame = pa.concat_tables(tables).to_pandas().sort_values("event_time").reset_index(drop=True)
    return result


# ------------------------------------------------------------------
# Cache check
# ------------------------------------------------------------------

def is_cache_valid(
    base_path: Path,
    factor_name: str,
    version: str,
    timeframe: str,
    symbol: str,
    year: int,
    month: int,
    expected_params_hash: str,
    current_source_max_ingested_at: int,
) -> bool:
    """Return True if the cached partition is still valid.

    Invalid when:
    - The parquet file doesn't exist
    - params_hash doesn't match (factor parameters changed)
    - source_max_ingested_at advanced (new source data available)
    """
    path = feature_partition_path(base_path, factor_name, version, timeframe, symbol, year, month)
    if not path.exists():
        return False
    mpath = meta_path(path)
    if not mpath.exists():
        return False

    try:
        manifest = json.loads(mpath.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    if manifest.get("params_hash") != expected_params_hash:
        return False
    cached_ingested = manifest.get("source_max_ingested_at", 0)
    return int(cached_ingested) >= current_source_max_ingested_at
