"""Factor Registry — in-process, explicit registration.

Design: D2 (explicit registration, no auto-scan)
Registry maintains a dict keyed by (name, version) and a defaults table.

Usage:
    from kronos.factor.registry import registry
    registry.register(MyFactor())
    factor = registry.get("my_factor", version="1.0.0")
    df_scores = registry.compute_all(df)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow.parquet as pq

from kronos.common.errors import FactorInputError, FactorRegistryError, FactorVersionError
from kronos.common.types import FactorStatus

if TYPE_CHECKING:
    from kronos.factor.base import BaseFactor


class FactorRegistry:
    """In-memory factor registry with explicit registration and default version support."""

    def __init__(self) -> None:
        # (name, version) → factor instance
        self._factors: dict[tuple[str, str], BaseFactor] = {}
        # name → default version string
        self._defaults: dict[str, str] = {}
        # (name, version) → FactorStatus
        self._status: dict[tuple[str, str], FactorStatus] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, factor: BaseFactor, *, set_default: bool = False) -> None:
        """Register a factor instance.

        Raises FactorRegistryError if the (name, version) pair already exists.
        """
        key = (factor.name, factor.version)
        if key in self._factors:
            raise FactorRegistryError(
                f"duplicate factor version: '{factor.name}@{factor.version}' is already registered"
            )
        self._factors[key] = factor
        self._status[key] = FactorStatus.DRAFT
        if set_default:
            self._defaults[factor.name] = factor.version

    def set_default(self, name: str, version: str) -> None:
        """Set the default version for a factor name.

        Raises FactorVersionError if name or version is not registered.
        """
        if (name, version) not in self._factors:
            raise FactorVersionError(
                f"Cannot set default: '{name}@{version}' is not registered"
            )
        self._defaults[name] = version

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str, version: str | None = None) -> BaseFactor:
        """Return a registered factor by name and optional version.

        If version is None, uses the configured default.
        Raises FactorVersionError if version is not found or no default is configured.
        """
        resolved = version or self._defaults.get(name)
        if resolved is None:
            raise FactorVersionError(
                f"No default version configured for factor '{name}'. "
                "Call set_default() or pass an explicit version."
            )
        key = (name, resolved)
        if key not in self._factors:
            raise FactorVersionError(f"Factor '{name}@{resolved}' is not registered")
        return self._factors[key]

    def list_factors(self) -> list[dict[str, Any]]:
        """Return metadata summary for all registered factors."""
        result = []
        for (name, version), factor in self._factors.items():
            result.append({
                "name": name,
                "version": version,
                "family": factor.family,
                "lookback": factor.lookback,
                "warmup_bars": factor.warmup_bars,
                "required_columns": factor.required_columns,
                "status": self._status[(name, version)],
                "is_default": self._defaults.get(name) == version,
            })
        return result

    def list_validated_factors(self) -> list[dict[str, Any]]:
        """Return metadata summary for factors currently in VALIDATED state."""
        return [
            item for item in self.list_factors()
            if item["status"] == FactorStatus.VALIDATED
        ]

    def status(
        self,
        name: str,
        version: str | None = None,
        *,
        base_path: str | Path = "data",
    ) -> dict[str, Any]:
        """Return status info for a specific factor.

        Raises FactorVersionError if not registered.
        """
        factor = self.get(name, version)
        key = (factor.name, factor.version)
        cache_state = _collect_materialization_status(Path(base_path), factor.name, factor.version)
        return {
            "name": factor.name,
            "version": factor.version,
            "family": factor.family,
            "registered": True,
            "status": self._status[key],
            "validation_status": self._status[key],
            "required_columns": factor.required_columns,
            "lookback": factor.lookback,
            "warmup_bars": factor.warmup_bars,
            "is_default": self._defaults.get(factor.name) == factor.version,
            "latest_materialized_at": cache_state["latest_materialized_at"],
            "cache_coverage": cache_state["cache_coverage"],
        }

    def update_status(self, name: str, version: str, new_status: FactorStatus) -> None:
        """Update a factor's lifecycle status."""
        key = (name, version)
        if key not in self._factors:
            raise FactorVersionError(f"Factor '{name}@{version}' is not registered")
        self._status[key] = new_status

    def promote_validated(
        self,
        name: str,
        version: str,
        *,
        validation_passed: bool,
        walkforward_passed: bool,
    ) -> None:
        """Promote a candidate factor to validated only when both gates pass."""
        key = (name, version)
        if key not in self._factors:
            raise FactorVersionError(f"Factor '{name}@{version}' is not registered")
        if self._status[key] not in {FactorStatus.CANDIDATE, FactorStatus.VALIDATING}:
            raise FactorRegistryError(
                f"Factor '{name}@{version}' must be candidate/validating before validated promotion"
            )
        if not (validation_passed and walkforward_passed):
            raise FactorRegistryError(
                f"Factor '{name}@{version}' cannot be promoted without validation + walkforward passing"
            )
        self._status[key] = FactorStatus.VALIDATED

    # ------------------------------------------------------------------
    # Batch computation
    # ------------------------------------------------------------------

    def compute_all(
        self,
        df: pd.DataFrame,
        *,
        factor_names: list[str] | None = None,
        version_map: dict[str, str] | None = None,
        low_freq_data: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        """Compute all (or selected) factors on the input DataFrame.

        Args:
            df: PIT-safe DataFrame from kronos.data.load() or load_universe().
                Must contain event_time, available_at, symbol columns.
            factor_names: Restrict to these factor names. None = all registered.
            version_map: Override version per factor name.
            low_freq_data: Dict of column_name → DataFrame with columns
                [available_at, <column_name>] for PIT-safe as-of join.
                Required when any factor declares low-frequency columns
                (e.g. funding_rate) in required_columns.

        Returns:
            Long-table DataFrame with columns:
                event_time, available_at, symbol, factor_name, factor_version,
                family, value (float64), score (float64, NaN for single-symbol)
        """
        targets = self._resolve_targets(factor_names, version_map)
        if df.empty or not targets:
            return _empty_output()

        multi_symbol = "symbol" in df.columns and df["symbol"].nunique() > 1
        parts: list[pd.DataFrame] = []

        symbols = df["symbol"].unique() if "symbol" in df.columns else [None]
        for symbol in symbols:
            sym_df = df[df["symbol"] == symbol].copy() if symbol is not None else df.copy()
            sym_df = sym_df.reset_index(drop=True)

            for factor in targets:
                enriched = _join_low_freq(sym_df, factor.required_columns, low_freq_data)
                try:
                    series = factor.compute(enriched)
                except FactorInputError:
                    raise

                part = pd.DataFrame({
                    "event_time": enriched["event_time"].values,
                    "available_at": enriched["available_at"].values,
                    "symbol": symbol if symbol is not None else enriched.get("symbol", ""),
                    "factor_name": factor.name,
                    "factor_version": factor.version,
                    "family": factor.family,
                    "value": series.values,
                    "score": float("nan"),  # single-symbol → always NaN
                })
                parts.append(part)

        if not parts:
            return _empty_output()

        result = pd.concat(parts, ignore_index=True)

        # Cross-symbol normalization (rank-normalize) only when multi-symbol
        if multi_symbol:
            result = _add_cross_symbol_score(result)

        return result

    def compute_validated(
        self,
        df: pd.DataFrame,
        *,
        version_map: dict[str, str] | None = None,
        low_freq_data: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        """Compute the default downstream score set using only validated factors."""
        validated_names = sorted({
            name
            for (name, version), status in self._status.items()
            if status == FactorStatus.VALIDATED and self._defaults.get(name) == version
        })
        if not validated_names:
            return _empty_output()
        return self.compute_all(
            df,
            factor_names=validated_names,
            version_map=version_map,
            low_freq_data=low_freq_data,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_targets(
        self,
        factor_names: list[str] | None,
        version_map: dict[str, str] | None,
    ) -> list[BaseFactor]:
        """Resolve which factor instances to compute."""
        vm = version_map or {}
        if factor_names is None:
            factor_names = list({name for name, _ in self._factors})

        targets: list[BaseFactor] = []
        for name in factor_names:
            version = vm.get(name)
            targets.append(self.get(name, version))
        return targets


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

registry = FactorRegistry()


# ------------------------------------------------------------------
# Helpers (module-private)
# ------------------------------------------------------------------

def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "event_time", "available_at", "symbol",
        "factor_name", "factor_version", "family",
        "value", "score",
    ])


def _join_low_freq(
    df: pd.DataFrame,
    required_columns: list[str],
    low_freq_data: dict[str, pd.DataFrame] | None,
) -> pd.DataFrame:
    """PIT-safe as-of join for low-frequency columns.

    For each column in required_columns that is absent from df but present in
    low_freq_data, performs an as-of merge on available_at (forward-fill with
    last known value ≤ current available_at).
    """
    if not low_freq_data:
        return df

    result = df.copy()
    missing = [c for c in required_columns if c not in result.columns]

    for col in missing:
        if col not in low_freq_data:
            continue
        ref = low_freq_data[col].sort_values("available_at")
        # pd.merge_asof requires sorted keys
        merged = pd.merge_asof(
            result.sort_values("available_at"),
            ref.rename(columns={"available_at": "_ref_at"}),
            left_on="available_at",
            right_on="_ref_at",
            direction="backward",
        )
        merged = merged.drop(columns=["_ref_at"], errors="ignore")
        # Restore original row order
        result = merged.sort_values("event_time").reset_index(drop=True)

    return result


def _add_cross_symbol_score(df: pd.DataFrame) -> pd.DataFrame:
    """Add cross-symbol rank-normalized score column.

    For each (event_time, factor_name, factor_version) cross-section,
    rank-normalize value → score in [0, 1].  Rows with NaN value stay NaN.
    """
    df = df.copy()
    df["score"] = float("nan")

    group_cols = ["event_time", "factor_name", "factor_version"]
    for _, grp_idx in df.groupby(group_cols).groups.items():
        vals = df.loc[grp_idx, "value"]
        valid = vals.notna()
        if valid.sum() < 2:
            continue
        ranks = vals[valid].rank(pct=True)
        df.loc[ranks.index, "score"] = ranks.values

    return df


def _collect_materialization_status(
    base_path: Path,
    factor_name: str,
    version: str,
) -> dict[str, Any]:
    """Summarise materialized cache state for a factor version."""
    root = base_path / "features" / factor_name / version
    if not root.exists():
        return {
            "latest_materialized_at": None,
            "cache_coverage": None,
        }

    latest_materialized_at: int | None = None
    for meta_file in root.rglob("*_meta.json"):
        try:
            payload = json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        generated_at = payload.get("generated_at")
        if isinstance(generated_at, int):
            latest_materialized_at = max(latest_materialized_at or generated_at, generated_at)

    parquet_files = sorted(root.rglob("*.parquet"))
    if not parquet_files:
        return {
            "latest_materialized_at": latest_materialized_at,
            "cache_coverage": None,
        }

    timeframes: set[str] = set()
    symbols: set[str] = set()
    min_event_time: int | None = None
    max_event_time: int | None = None
    bar_count = 0

    for parquet_file in parquet_files:
        relative_parts = parquet_file.relative_to(root).parts
        if len(relative_parts) >= 4:
            timeframes.add(relative_parts[0])
            symbols.add(relative_parts[1])

        metadata = pq.ParquetFile(parquet_file).metadata
        bar_count += metadata.num_rows

        event_times = pq.read_table(parquet_file, columns=["event_time"]).column("event_time").to_pylist()
        if not event_times:
            continue
        file_min = min(int(ts) for ts in event_times)
        file_max = max(int(ts) for ts in event_times)
        min_event_time = file_min if min_event_time is None else min(min_event_time, file_min)
        max_event_time = file_max if max_event_time is None else max(max_event_time, file_max)

    return {
        "latest_materialized_at": latest_materialized_at,
        "cache_coverage": {
            "timeframes": sorted(timeframes),
            "symbols": sorted(symbols),
            "min_event_time": min_event_time,
            "max_event_time": max_event_time,
            "bar_count": bar_count,
            "partition_count": len(parquet_files),
        },
    }


def compute_params_hash(metadata: dict[str, Any]) -> str:
    """Generate a deterministic 12-char SHA-256 hash from factor metadata.

    Keys are sorted alphabetically, values converted to strings.
    """
    serialized = json.dumps(
        {k: str(v) for k, v in sorted(metadata.items())},
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]
