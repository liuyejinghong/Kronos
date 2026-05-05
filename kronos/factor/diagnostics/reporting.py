"""Reporting helpers for signal diagnostics artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from kronos.factor.diagnostics.core import SignalDiagnosticsResult


def persist_signal_diagnostics_result(
    result: SignalDiagnosticsResult,
    *,
    signal_name: str,
    base_dir: str | Path = "reports/signal_diagnostics",
    run_id: str | None = None,
) -> tuple[Path, dict[str, str]]:
    """Persist structured diagnostics outputs and artifact paths."""
    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(base_dir) / signal_name / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.json"
    ic_path = run_dir / "ic_timeseries.csv"
    decay_path = run_dir / "decay.csv"
    correlation_path = run_dir / "correlation_matrix.csv"
    heatmap_path = run_dir / "correlation_heatmap.png"

    summary_payload = result.to_dict()
    summary_payload["run_id"] = resolved_run_id
    summary_payload["signal_name"] = signal_name
    summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    result.ic_timeseries.to_csv(ic_path, index=False)
    result.decay.to_csv(decay_path, index=False)
    result.correlation_matrix.to_csv(correlation_path)
    _save_heatmap(result.correlation_matrix, heatmap_path, signal_name)

    artifacts = {
        "summary": str(summary_path),
        "ic_timeseries": str(ic_path),
        "decay": str(decay_path),
        "correlation_matrix": str(correlation_path),
        "correlation_heatmap": str(heatmap_path),
    }
    result.artifacts.update(artifacts)
    return run_dir, artifacts


def _save_heatmap(matrix: pd.DataFrame, output_path: Path, title: str) -> None:
    import matplotlib.pyplot as plt
    if matrix.empty:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No correlation data", ha="center", va="center")
        ax.set_axis_off()
    else:
        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(matrix.values, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(matrix.columns)))
        ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(matrix.index)))
        ax.set_yticklabels(matrix.index)
        ax.set_title(f"{title} correlation")
        fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
