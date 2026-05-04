"""High-level experiment recording workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kronos.research.experiments.artifacts import (
    write_backtest_artifacts,
    write_signal_diagnostics_artifacts,
    write_validation_artifacts,
    write_walkforward_artifacts,
)
from kronos.research.experiments.ledger import append_run_record, rebuild_ledger_index
from kronos.research.experiments.schema import build_run_record

if TYPE_CHECKING:
    from kronos.research.backtest.types import BacktestResult


def record_backtest_run(
    result: BacktestResult,
    *,
    base_path: str,
    factors: list[str],
    universe: list[str],
    split_dates: dict[str, Any],
    git_commit: str | None = None,
    data_snapshot_id: str | None = None,
) -> str:
    """Write backtest artifacts and append the run to the experiment ledger."""
    artifact_paths = write_backtest_artifacts(result, base_path=base_path)
    record = build_run_record(
        module="backtest",
        run_id=result.run_id,
        git_commit=git_commit or result.git_commit,
        data_snapshot_id=data_snapshot_id or result.data_snapshot_id,
        config_snapshot=result.config_snapshot,
        factors=factors,
        universe=universe,
        split_dates=split_dates,
        results={
            "total_return": result.metrics.total_return,
            "annual_return": result.metrics.annual_return,
            "sharpe": result.metrics.sharpe,
            "max_drawdown": result.metrics.max_drawdown,
            "trade_count": result.metrics.trade_count,
        },
        artifact_paths=artifact_paths,
    )
    append_run_record(record, base_path=base_path)
    rebuild_ledger_index(base_path=base_path)
    return record.run_id


def record_validation_run(
    *,
    result: Any,
    factor_name: str,
    factor_version: str | None,
    base_path: str,
    run_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    universe: list[str],
    split_dates: dict[str, Any],
    timeframe: str | None = None,
) -> str:
    """Write validation artifacts and append the run to the experiment ledger."""
    artifact_paths = write_validation_artifacts(
        result=result,
        factor_name=factor_name,
        factor_version=factor_version,
        base_path=base_path,
        run_id=run_id,
        timeframe=timeframe,
        universe=universe,
    )
    record = build_run_record(
        module="factor_validation",
        run_id=run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot=config_snapshot,
        factors=[factor_name],
        universe=universe,
        split_dates=split_dates,
        results={
            "outcome": str(result.outcome),
            "mean_rank_ic": result.mean_rank_ic,
            "top_minus_bottom": result.top_minus_bottom,
            "median_turnover": result.median_turnover,
        },
        artifact_paths=artifact_paths,
    )
    append_run_record(record, base_path=base_path)
    rebuild_ledger_index(base_path=base_path)
    return record.run_id


def record_signal_diagnostics_run(
    *,
    result: Any,
    signal_name: str,
    base_path: str,
    run_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    factors: list[str],
    universe: list[str],
    split_dates: dict[str, Any],
) -> str:
    """Write diagnostics artifacts and append the run to the experiment ledger."""
    artifact_paths = write_signal_diagnostics_artifacts(
        result=result,
        signal_name=signal_name,
        base_path=base_path,
        run_id=run_id,
        config_snapshot=config_snapshot,
    )
    record = build_run_record(
        module="signal_diagnostics",
        run_id=run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot=config_snapshot,
        factors=factors,
        universe=universe,
        split_dates=split_dates,
        results={
            "mean_funding_drag": result.funding_drag.get("mean_drag"),
            "high_liquidity_rank_ic": result.liquidity_filter.get("high_liquidity_rank_ic"),
            "low_liquidity_rank_ic": result.liquidity_filter.get("low_liquidity_rank_ic"),
        },
        artifact_paths=artifact_paths,
    )
    append_run_record(record, base_path=base_path)
    rebuild_ledger_index(base_path=base_path)
    return record.run_id


def record_walkforward_run(
    *,
    result: Any,
    signal_name: str,
    base_path: str,
    run_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    factors: list[str],
    universe: list[str],
    split_dates: dict[str, Any],
) -> str:
    """Write walk-forward artifacts and append the run to the experiment ledger."""
    artifact_paths = write_walkforward_artifacts(
        result=result,
        signal_name=signal_name,
        base_path=base_path,
        run_id=run_id,
        config_snapshot=config_snapshot,
    )
    record = build_run_record(
        module="walkforward",
        run_id=run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot=config_snapshot,
        factors=factors,
        universe=universe,
        split_dates=split_dates,
        results={
            "validation_mean": result.cross_window_decay.get("validation_mean"),
            "test_mean": result.cross_window_decay.get("test_mean"),
            "decay_mean": result.cross_window_decay.get("decay_mean"),
            "leak_audit_passed": result.leak_audit.get("status") == "passed",
        },
        artifact_paths=artifact_paths,
    )
    append_run_record(record, base_path=base_path)
    rebuild_ledger_index(base_path=base_path)
    return record.run_id
