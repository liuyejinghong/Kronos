"""Reporting helpers for walk-forward validation artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from kronos.research.walkforward.core import WalkforwardResult


def persist_walkforward_result(
    result: WalkforwardResult,
    *,
    signal_name: str,
    base_dir: str | Path = "reports/walkforward",
    run_id: str | None = None,
) -> tuple[Path, dict[str, str]]:
    """Persist walk-forward summaries and artifact paths."""
    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(base_dir) / signal_name / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.json"
    windows_path = run_dir / "windows.csv"
    best_trials_path = run_dir / "best_trials.json"
    stability_path = run_dir / "stability.json"

    summary_payload = result.to_dict()
    summary_payload["run_id"] = resolved_run_id
    summary_payload["signal_name"] = signal_name
    summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    pd.DataFrame([window.__dict__ for window in result.windows]).to_csv(windows_path, index=False)
    best_trials_path.write_text(
        json.dumps([trial.__dict__ for trial in result.best_trials], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    stability_path.write_text(json.dumps(result.stability, indent=2, ensure_ascii=False), encoding="utf-8")

    artifacts = {
        "summary": str(summary_path),
        "windows": str(windows_path),
        "best_trials": str(best_trials_path),
        "stability": str(stability_path),
    }
    return run_dir, artifacts
