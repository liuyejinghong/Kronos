"""Nested walk-forward validation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from kronos.common.errors import BacktestError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import pandas as pd


@dataclass(frozen=True)
class WalkforwardWindow:
    """Single nested train/validation/test split."""

    window_id: int
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class WindowTrial:
    """Single parameter trial inside one window."""

    params: dict[str, Any]
    validation_score: float
    test_score: float
    train_score: float


@dataclass
class WalkforwardResult:
    """Structured walk-forward validation output."""

    windows: list[WalkforwardWindow]
    best_trials: list[WindowTrial]
    trial_history: dict[int, list[WindowTrial]]
    stability: dict[int, dict[str, float]]
    leak_audit: dict[str, Any]
    cross_window_decay: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "windows": [window.__dict__ for window in self.windows],
            "best_trials": [trial.__dict__ for trial in self.best_trials],
            "trial_history": {
                window_id: [trial.__dict__ for trial in trials]
                for window_id, trials in self.trial_history.items()
            },
            "stability": self.stability,
            "leak_audit": self.leak_audit,
            "cross_window_decay": self.cross_window_decay,
        }


def generate_nested_splits(
    timestamps: Sequence[int],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None = None,
) -> list[WalkforwardWindow]:
    """Generate nested walk-forward train/validation/test splits."""
    ordered = sorted(int(ts) for ts in timestamps)
    unique = list(dict.fromkeys(ordered))
    step = step_size or test_size
    total = train_size + validation_size + test_size
    windows: list[WalkforwardWindow] = []

    start = 0
    window_id = 1
    while start + total <= len(unique):
        train_start = unique[start]
        train_end = unique[start + train_size - 1]
        validation_start = unique[start + train_size]
        validation_end = unique[start + train_size + validation_size - 1]
        test_start = unique[start + train_size + validation_size]
        test_end = unique[start + total - 1]
        windows.append(
            WalkforwardWindow(
                window_id=window_id,
                train_start=train_start,
                train_end=train_end,
                validation_start=validation_start,
                validation_end=validation_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        start += step
        window_id += 1

    return windows


def audit_lookahead_inputs(
    *,
    signals: pd.DataFrame,
    data: pd.DataFrame,
    execution_delay_bars: int,
) -> dict[str, Any]:
    """Run the automated lookahead leak audit."""
    if execution_delay_bars < 1:
        return {"status": "failed", "reason": "execution_delay_bars < 1"}

    merged = signals.merge(
        data[["symbol", "available_at", "event_time"]],
        left_on=["symbol", "timestamp"],
        right_on=["symbol", "available_at"],
        how="left",
    )
    if merged["available_at"].isna().any():
        return {"status": "failed", "reason": "signals do not align to PIT-safe data rows"}
    if (merged["available_at"] > merged["timestamp"]).any():
        return {"status": "failed", "reason": "signals reference unavailable data"}

    return {"status": "passed", "reason": None}


def run_walkforward_validation(
    *,
    timestamps: Sequence[int],
    parameter_grid: Sequence[dict[str, Any]],
    evaluator: Callable[[WalkforwardWindow, dict[str, Any]], dict[str, float]],
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None = None,
    leak_audit: dict[str, Any] | None = None,
) -> WalkforwardResult:
    """Run nested walk-forward validation with lightweight parameter search."""
    windows = generate_nested_splits(
        timestamps,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=step_size,
    )
    if not windows:
        raise BacktestError("walkforward requires at least one full train/validation/test window")

    best_trials: list[WindowTrial] = []
    trial_history: dict[int, list[WindowTrial]] = {}
    stability: dict[int, dict[str, float]] = {}

    for window in windows:
        trials: list[WindowTrial] = []
        for params in parameter_grid:
            scores = evaluator(window, params)
            trials.append(
                WindowTrial(
                    params=params,
                    train_score=float(scores.get("train_score", 0.0)),
                    validation_score=float(scores.get("validation_score", 0.0)),
                    test_score=float(scores.get("test_score", 0.0)),
                )
            )
        ordered = sorted(trials, key=lambda trial: trial.validation_score, reverse=True)
        best = ordered[0]
        best_trials.append(best)
        trial_history[window.window_id] = trials
        stability[window.window_id] = _stability_summary(best, ordered[1:4])

    decay = _cross_window_decay(best_trials)
    return WalkforwardResult(
        windows=windows,
        best_trials=best_trials,
        trial_history=trial_history,
        stability=stability,
        leak_audit=leak_audit or {"status": "not_run", "reason": None},
        cross_window_decay=decay,
    )


def _stability_summary(best: WindowTrial, neighbours: list[WindowTrial]) -> dict[str, float]:
    if not neighbours:
        return {"validation_gap_mean": float("nan"), "test_gap_mean": float("nan")}
    validation_gaps = [best.validation_score - neighbour.validation_score for neighbour in neighbours]
    test_gaps = [best.test_score - neighbour.test_score for neighbour in neighbours]
    return {
        "validation_gap_mean": float(np.mean(validation_gaps)),
        "test_gap_mean": float(np.mean(test_gaps)),
    }


def _cross_window_decay(best_trials: list[WindowTrial]) -> dict[str, float]:
    validation_scores = [trial.validation_score for trial in best_trials]
    test_scores = [trial.test_score for trial in best_trials]
    decay = [validation - test for validation, test in zip(validation_scores, test_scores, strict=False)]
    return {
        "validation_mean": float(np.mean(validation_scores)),
        "test_mean": float(np.mean(test_scores)),
        "decay_mean": float(np.mean(decay)),
        "decay_std": float(np.std(decay, ddof=0)),
    }
