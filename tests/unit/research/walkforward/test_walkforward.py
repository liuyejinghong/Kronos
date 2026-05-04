"""Unit tests for walk-forward validation."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import BacktestError
from kronos.research.walkforward import (
    audit_lookahead_inputs,
    generate_nested_splits,
    run_walkforward_validation,
)


class TestGenerateNestedSplits:
    def test_generates_nested_windows(self) -> None:
        timestamps = list(range(12))
        windows = generate_nested_splits(
            timestamps,
            train_size=4,
            validation_size=2,
            test_size=2,
            step_size=2,
        )
        assert len(windows) == 3
        assert windows[0].train_start == 0
        assert windows[0].test_end == 7


class TestLookaheadAudit:
    def test_passes_for_pit_safe_alignment(self) -> None:
        signals = pd.DataFrame({"timestamp": [1, 1], "symbol": ["BTC", "ETH"], "signal": [1.0, -1.0]})
        data = pd.DataFrame({
            "event_time": [1, 1],
            "available_at": [1, 1],
            "symbol": ["BTC", "ETH"],
        })
        audit = audit_lookahead_inputs(signals=signals, data=data, execution_delay_bars=1)
        assert audit["status"] == "passed"

    def test_fails_when_delay_is_invalid(self) -> None:
        signals = pd.DataFrame({"timestamp": [1], "symbol": ["BTC"], "signal": [1.0]})
        data = pd.DataFrame({"event_time": [1], "available_at": [1], "symbol": ["BTC"]})
        audit = audit_lookahead_inputs(signals=signals, data=data, execution_delay_bars=0)
        assert audit["status"] == "failed"


class TestRunWalkforwardValidation:
    def test_runs_parameter_search_and_decay_summary(self) -> None:
        timestamps = list(range(12))
        grid = [{"speed": 1}, {"speed": 2}, {"speed": 3}]

        def evaluator(window, params):
            score = float(params["speed"])
            return {
                "train_score": score + 1.0,
                "validation_score": score,
                "test_score": score - 0.2,
            }

        result = run_walkforward_validation(
            timestamps=timestamps,
            parameter_grid=grid,
            evaluator=evaluator,
            train_size=4,
            validation_size=2,
            test_size=2,
            step_size=2,
            leak_audit={"status": "passed", "reason": None},
        )

        assert len(result.windows) == 3
        assert len(result.best_trials) == 3
        assert result.best_trials[0].params["speed"] == 3
        assert result.leak_audit["status"] == "passed"
        assert "decay_mean" in result.cross_window_decay

    def test_rejects_when_no_full_window_exists(self) -> None:
        with pytest.raises(BacktestError):
            run_walkforward_validation(
                timestamps=[1, 2, 3],
                parameter_grid=[{"speed": 1}],
                evaluator=lambda window, params: {"train_score": 1.0, "validation_score": 1.0, "test_score": 1.0},
                train_size=4,
                validation_size=2,
                test_size=2,
            )
