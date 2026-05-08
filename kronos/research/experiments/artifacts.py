"""Experiment artifact directory helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w

from kronos.factor.diagnostics.reporting import persist_signal_diagnostics_result
from kronos.factor.validation.reporting import persist_validation_result
from kronos.research.backtest.reporting import write_replay_report
from kronos.research.walkforward.reporting import persist_walkforward_result

if TYPE_CHECKING:
    from kronos.research.backtest.types import BacktestResult


def experiment_root(base_path: str | Path, run_id: str) -> Path:
    root = Path(base_path) / "experiments" / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_backtest_artifacts(result: BacktestResult, *, base_path: str | Path) -> dict[str, str]:
    """Write the standard backtest artifact set under `experiments/{run_id}`."""
    run_root = experiment_root(base_path, result.run_id)
    metrics_path = run_root / "metrics.json"
    config_snapshot_path = run_root / "config_snapshot.toml"
    equity_path = run_root / "equity.parquet"
    trades_path = run_root / "trades.parquet"
    replay_report_path = run_root / "backtest_replay_report.md"

    metrics_payload = {
        "run_id": result.run_id,
        "git_commit": result.git_commit,
        "data_snapshot_id": result.data_snapshot_id,
        "metrics": asdict(result.metrics),
        "tearsheet": result.tearsheet,
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    config_snapshot_path.write_text(tomli_w.dumps(result.config_snapshot), encoding="utf-8")
    result.equity_curve.to_parquet(equity_path, index=False)
    result.trades.to_parquet(trades_path, index=False)
    write_replay_report(result, replay_report_path)

    return {
        "metrics": str(metrics_path),
        "config_snapshot": str(config_snapshot_path),
        "equity": str(equity_path),
        "trades": str(trades_path),
        "replay_report": str(replay_report_path),
    }


def write_validation_artifacts(
    *,
    result: Any,
    factor_name: str,
    factor_version: str | None,
    base_path: str | Path,
    run_id: str,
    timeframe: str | None = None,
    universe: str | list[str] | None = None,
) -> dict[str, str]:
    """Write standard validation artifacts under `experiments/{run_id}`."""
    run_root = experiment_root(base_path, run_id)
    config_snapshot_path = run_root / "config_snapshot.toml"
    config_snapshot_path.write_text(tomli_w.dumps(result.config.model_dump(mode="json")), encoding="utf-8")

    report_dir = persist_validation_result(
        result,
        factor_name,
        base_dir=run_root / "reports",
        run_id=run_id,
        factor_version=factor_version,
        timeframe=timeframe,
        universe=universe,
        extra_report_metadata={"run_id": run_id},
    )
    detailed_metrics_path = report_dir / "metrics.json"
    root_metrics_path = run_root / "metrics.json"
    root_metrics_path.write_text(detailed_metrics_path.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "metrics": str(root_metrics_path),
        "config_snapshot": str(config_snapshot_path),
        "report_dir": str(report_dir),
    }


def write_signal_diagnostics_artifacts(
    *,
    result: Any,
    signal_name: str,
    base_path: str | Path,
    run_id: str,
    config_snapshot: dict[str, Any],
) -> dict[str, str]:
    """Write standard signal diagnostics artifacts under `experiments/{run_id}`."""
    run_root = experiment_root(base_path, run_id)
    config_snapshot_path = run_root / "config_snapshot.toml"
    config_snapshot_path.write_text(tomli_w.dumps(config_snapshot), encoding="utf-8")

    report_dir, artifact_paths = persist_signal_diagnostics_result(
        result,
        signal_name=signal_name,
        base_dir=run_root / "diagnostics",
        run_id=run_id,
    )
    root_metrics_path = run_root / "metrics.json"
    root_metrics_path.write_text((report_dir / "summary.json").read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "metrics": str(root_metrics_path),
        "config_snapshot": str(config_snapshot_path),
        **artifact_paths,
    }


def write_walkforward_artifacts(
    *,
    result: Any,
    signal_name: str,
    base_path: str | Path,
    run_id: str,
    config_snapshot: dict[str, Any],
) -> dict[str, str]:
    """Write standard walk-forward artifacts under `experiments/{run_id}`."""
    run_root = experiment_root(base_path, run_id)
    config_snapshot_path = run_root / "config_snapshot.toml"
    config_snapshot_path.write_text(tomli_w.dumps(config_snapshot), encoding="utf-8")

    report_dir, artifact_paths = persist_walkforward_result(
        result,
        signal_name=signal_name,
        base_dir=run_root / "walkforward",
        run_id=run_id,
    )
    root_metrics_path = run_root / "metrics.json"
    root_metrics_path.write_text((report_dir / "summary.json").read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "metrics": str(root_metrics_path),
        "config_snapshot": str(config_snapshot_path),
        **artifact_paths,
    }
