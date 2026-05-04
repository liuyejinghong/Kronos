"""Factor validation reporting — persist ValidationResult to disk.

Output layout:
    {base_dir}/{factor_name}/{factor_version}/
        metrics.json      — scalar metrics + IC table + decay table
        outcome.txt       — single-line: pass / review / fail

run_id is report metadata, not a path segment. When factor_version is omitted,
the report is written under an explicit "unversioned" segment.
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import pandas as pd

    from kronos.factor.validation.pipeline import ValidationResult

UNVERSIONED_REPORT_SEGMENT = "unversioned"


def _resolve_report_dir(
    base_dir: str | Path,
    factor_name: str,
    factor_version: str | None,
) -> Path:
    version_segment = factor_version or UNVERSIONED_REPORT_SEGMENT
    return Path(base_dir) / factor_name / version_segment


def _sanitise(obj: object) -> object:
    """Recursively convert NaN/Inf floats to None for JSON serialisation."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise(v) for v in obj]
    return obj


def persist_validation_result(
    result: ValidationResult,
    factor_name: str,
    base_dir: str | Path = "reports/factor_validation",
    run_id: str | None = None,
    *,
    factor_version: str | None = None,
    timeframe: str | None = None,
    universe: str | list[str] | None = None,
    extra_report_metadata: dict[str, object] | None = None,
) -> Path:
    """Write ValidationResult to disk as metrics.json + outcome.txt.

    Args:
        result: The ValidationResult from validate_factor().
        factor_name: Human-readable factor name (used as sub-directory).
        base_dir: Root directory for validation outputs.
        run_id: Optional run identifier stored in report metadata; defaults to UTC ISO timestamp.
        factor_version: Optional factor version for report path and metadata. Missing versions are
            written under the explicit "unversioned" path segment.
        timeframe: Optional timeframe label for report metadata.
        universe: Optional universe label for report metadata.
        extra_report_metadata: Optional extra report metadata to merge in.

    Returns:
        Path to the versioned report directory where files were written.
    """
    if run_id is None:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    report_dir = _resolve_report_dir(base_dir, factor_name, factor_version)
    report_dir.mkdir(parents=True, exist_ok=True)

    # Serialise
    payload = cast("dict[str, object]", _sanitise(result.to_dict()))
    payload["report_metadata"] = _sanitise({
        "factor_name": factor_name,
        "factor_version": factor_version,
        "run_id": run_id,
        "report_path_segment": factor_version or UNVERSIONED_REPORT_SEGMENT,
        "timeframe": timeframe,
        "universe": universe,
        "thresholds": {
            "min_mean_rank_ic": result.config.min_mean_rank_ic,
            "min_rank_ic_positive_ratio": result.config.min_rank_ic_positive_ratio,
            "min_top_minus_bottom_return": result.config.min_top_minus_bottom_return,
            "max_median_turnover": result.config.max_median_turnover,
        },
        "periods": list(result.config.periods),
        "quantiles": result.config.quantiles,
    })
    if extra_report_metadata:
        cast("dict[str, object]", payload["report_metadata"]).update(
            cast("dict[str, object]", _sanitise(extra_report_metadata))
        )

    metrics_path = report_dir / "metrics.json"
    outcome_path = report_dir / "outcome.txt"

    # Atomic write for metrics.json
    tmp_metrics = metrics_path.with_suffix(".json.tmp")
    tmp_metrics.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_metrics, metrics_path)

    outcome_path.write_text(str(result.outcome) + "\n", encoding="utf-8")

    return report_dir


def export_alphalens_report(
    factor_data: pd.DataFrame,
    *,
    factor_name: str,
    factor_version: str,
    periods: list[int],
    base_dir: str | Path = "reports/factor_validation",
    run_id: str | None = None,
) -> tuple[Path, list[Path]]:
    """Write Alphalens tear sheet images into the versioned validation report directory."""
    from kronos.factor.validation.alphalens_adapter import export_alphalens_tear_sheets

    if run_id is None:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    report_dir = _resolve_report_dir(base_dir, factor_name, factor_version)
    report_dir.mkdir(parents=True, exist_ok=True)
    exported = export_alphalens_tear_sheets(factor_data, report_dir, periods=periods)
    return report_dir, exported


def load_validation_result_dict(report_dir: str | Path) -> dict[str, object]:
    """Load a previously persisted metrics.json from a report directory.

    Returns:
        Raw dict; callers are responsible for parsing into typed structures.
    """
    metrics_path = Path(report_dir) / "metrics.json"
    return json.loads(metrics_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
