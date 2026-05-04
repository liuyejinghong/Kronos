"""Freqtrade cross-validation bridge helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from kronos.research.backtest.types import BacktestResult, CrossValidationResult

if TYPE_CHECKING:
    from kronos.research.backtest.config import BacktestConfig


def export_signals(
    signals: pd.DataFrame,
    target_weights: pd.DataFrame,
    *,
    output_path: str | Path,
    run_id: str,
) -> Path:
    """Export Kronos signals into the standard bridge format."""
    merged = signals.merge(
        target_weights[["timestamp", "symbol", "target_weight"]],
        on=["timestamp", "symbol"],
        how="left",
    )
    merged["target_weight"] = merged["target_weight"].fillna(0.0)
    merged["side"] = merged["target_weight"].apply(
        lambda value: "long" if value > 0 else ("short" if value < 0 else "flat")
    )
    merged["rebalance_id"] = merged["timestamp"].astype(str).radd(f"{run_id}-")
    merged["signal_run_id"] = run_id
    merged["timestamp"] = pd.to_datetime(merged["timestamp"], unit="ms", utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    exported = merged[
        ["timestamp", "symbol", "signal", "target_weight", "side", "rebalance_id", "signal_run_id"]
    ].copy()

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exported.to_csv(path, index=False)
    return path


def build_freqtrade_config(
    config: BacktestConfig,
    *,
    universe: list[str],
    since: int,
    until: int,
    signal_path: str | Path,
) -> dict[str, Any]:
    """Build the minimal configuration payload for bridge execution."""
    return {
        "timeframe": config.timeframe,
        "pairs": universe,
        "fee_bps": config.fee_bps,
        "slippage_bps": config.slippage_bps,
        "mode": config.mode,
        "time_window": {
            "since": since,
            "until": until,
        },
        "signal_path": str(signal_path),
    }


def build_lookahead_analysis_command(
    *,
    config_path: str | Path,
    export_dir: str | Path,
) -> list[str]:
    """Build the Freqtrade lookahead-analysis command without executing it."""
    return [
        "freqtrade",
        "lookahead-analysis",
        "--config",
        str(config_path),
        "--lookahead-analysis-exportfilename",
        str(Path(export_dir) / "lookahead_analysis.json"),
    ]


def compare_with_freqtrade(
    result: BacktestResult,
    *,
    freqtrade_equity: pd.DataFrame,
    freqtrade_summary: dict[str, Any],
    lookahead_clean: bool,
    artifacts: dict[str, str],
) -> CrossValidationResult:
    """Compare Kronos and Freqtrade summaries and return a structured verdict."""
    kronos_equity = result.equity_curve[["timestamp", "equity"]].rename(columns={"equity": "kronos_equity"})
    freqtrade = freqtrade_equity[["timestamp", "equity"]].rename(columns={"equity": "freqtrade_equity"})
    aligned = kronos_equity.merge(freqtrade, on="timestamp", how="inner")
    if aligned.empty:
        equity_diff_metrics = {
            "mae": float("inf"),
            "rmse": float("inf"),
            "final_equity_abs_diff": float("inf"),
        }
    else:
        delta = aligned["kronos_equity"] - aligned["freqtrade_equity"]
        equity_diff_metrics = {
            "mae": float(delta.abs().mean()),
            "rmse": float((delta.pow(2).mean()) ** 0.5),
            "final_equity_abs_diff": float(
                abs(aligned["kronos_equity"].iloc[-1] - aligned["freqtrade_equity"].iloc[-1])
            ),
        }

    thresholds = result.config_snapshot["validation"]
    failure_reason = _failure_reason(
        equity_diff_metrics=equity_diff_metrics,
        kronos_summary=_kronos_summary(result),
        freqtrade_summary=freqtrade_summary,
        thresholds=thresholds,
        lookahead_clean=lookahead_clean,
    )
    status = "passed" if failure_reason is None else "failed"

    return CrossValidationResult(
        status=status,
        kronos_summary=_kronos_summary(result),
        freqtrade_summary=freqtrade_summary,
        equity_diff_metrics=equity_diff_metrics,
        thresholds=thresholds,
        lookahead_check_status="passed" if lookahead_clean else "failed",
        artifacts=artifacts,
        failure_reason=failure_reason,
    )


def run_cross_validation(
    *,
    result: BacktestResult,
    signals: pd.DataFrame,
    freqtrade_equity: pd.DataFrame,
    freqtrade_summary: dict[str, Any],
    output_dir: str | Path,
    universe: list[str],
    lookahead_output: dict[str, Any] | None = None,
) -> CrossValidationResult:
    """Execute the bridge workflow: export -> config -> lookahead -> compare."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    signal_path = export_signals(
        signals,
        result.target_weights,
        output_path=output_root / "signals.csv",
        run_id=result.run_id,
    )
    config_payload = build_freqtrade_config(
        _config_from_snapshot(result.config_snapshot),
        universe=universe,
        since=int(signals["timestamp"].min()),
        until=int(signals["timestamp"].max()),
        signal_path=signal_path,
    )
    config_path = output_root / "freqtrade_config.json"
    config_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    lookahead_result = evaluate_lookahead_output(lookahead_output or {"status": "passed"})
    lookahead_command = build_lookahead_analysis_command(
        config_path=config_path,
        export_dir=output_root,
    )
    artifacts = {
        "signals": str(signal_path),
        "config": str(config_path),
        "lookahead_command": " ".join(lookahead_command),
        "lookahead_report": str(output_root / "lookahead_analysis.json"),
    }

    return compare_with_freqtrade(
        result,
        freqtrade_equity=freqtrade_equity,
        freqtrade_summary=freqtrade_summary,
        lookahead_clean=lookahead_result["passed"],
        artifacts=artifacts,
    )


def evaluate_lookahead_output(output: dict[str, Any]) -> dict[str, Any]:
    """Interpret a Freqtrade lookahead-analysis style output payload."""
    status = str(output.get("status", "failed")).lower()
    passed = status == "passed" and not output.get("violations")
    return {
        "passed": passed,
        "status": "passed" if passed else "failed",
        "violations": list(output.get("violations", [])),
    }


def _kronos_summary(result: BacktestResult) -> dict[str, Any]:
    return {
        "final_equity": float(result.equity_curve["equity"].iloc[-1]),
        "max_drawdown": result.metrics.max_drawdown,
        "sharpe": result.metrics.sharpe,
        "trade_count": result.metrics.trade_count,
    }


def _config_from_snapshot(snapshot: dict[str, Any]) -> BacktestConfig:
    from kronos.research.backtest.config import BacktestConfig

    return BacktestConfig.model_validate(snapshot)


def _failure_reason(
    *,
    equity_diff_metrics: dict[str, float],
    kronos_summary: dict[str, Any],
    freqtrade_summary: dict[str, Any],
    thresholds: dict[str, Any],
    lookahead_clean: bool,
) -> str | None:
    if not lookahead_clean:
        return "lookahead_check_failed"
    if equity_diff_metrics["final_equity_abs_diff"] > thresholds["final_equity_abs_diff"]:
        return "final_equity_diff_exceeded"
    if abs(kronos_summary["max_drawdown"] - freqtrade_summary["max_drawdown"]) > thresholds["max_drawdown_abs_diff"]:
        return "max_drawdown_diff_exceeded"
    if abs(kronos_summary["sharpe"] - freqtrade_summary["sharpe"]) > thresholds["sharpe_abs_diff"]:
        return "sharpe_diff_exceeded"
    if abs(kronos_summary["trade_count"] - freqtrade_summary["trade_count"]) > thresholds["trade_count_abs_diff"]:
        return "trade_count_diff_exceeded"
    if equity_diff_metrics["mae"] > thresholds["equity_curve_mae"]:
        return "equity_curve_mae_exceeded"
    return None
