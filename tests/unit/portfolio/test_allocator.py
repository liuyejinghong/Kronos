"""Unit tests for portfolio construction."""

from __future__ import annotations

import pandas as pd

from kronos.common.types import Constraints
from kronos.portfolio import construct, mix_scores, should_rebalance


def _scores() -> pd.DataFrame:
    return pd.DataFrame({
        "event_time": [1, 1, 1, 1],
        "symbol": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"],
        "factor_name": ["mom", "mom", "mom", "mom"],
        "score": [0.8, 0.4, -0.2, -0.6],
    })


class TestMixScores:
    def test_mix_scores_preserves_sources(self) -> None:
        scores = pd.DataFrame({
            "event_time": [1, 1, 1, 1],
            "symbol": ["BTCUSDT", "BTCUSDT", "ETHUSDT", "ETHUSDT"],
            "factor_name": ["trend", "carry", "trend", "carry"],
            "strategy_id": ["trend", "carry", "trend", "carry"],
            "score": [1.0, 0.5, -1.0, -0.5],
        })
        mixed, metadata = mix_scores(scores)
        assert len(mixed) == 2
        assert metadata["sources"] == ["carry", "trend"]
        assert metadata["strategy_weights"] == {"carry": 0.5, "trend": 0.5}


class TestAllocator:
    def test_construct_returns_target_portfolio_contract(self) -> None:
        target = construct(_scores(), current_positions={"BTCUSDT": 0.0}, constraints=Constraints())
        assert target.timestamp == 1
        assert set(target.positions) == {"BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"}
        assert "sources" in target.metadata

    def test_construct_respects_max_single_weight_and_leverage(self) -> None:
        constraints = Constraints(max_leverage=1.0, max_single_weight=0.3)
        target = construct(_scores(), current_positions={}, constraints=constraints)
        assert all(abs(weight) <= 0.3 for weight in target.positions.values())
        assert sum(abs(weight) for weight in target.positions.values()) <= 1.0 + 1e-9

    def test_construct_respects_long_and_short_exposure_caps(self) -> None:
        constraints = Constraints(
            max_leverage=2.0,
            max_single_weight=1.0,
            max_long_exposure=0.6,
            max_short_exposure=0.4,
        )
        target = construct(_scores(), current_positions={}, constraints=constraints)
        long_sum = sum(weight for weight in target.positions.values() if weight > 0)
        short_sum = abs(sum(weight for weight in target.positions.values() if weight < 0))
        assert long_sum <= 0.6 + 1e-9
        assert short_sum <= 0.4 + 1e-9

    def test_construct_applies_volatility_target_when_available(self) -> None:
        scores = pd.DataFrame({
            "event_time": [1, 1, 1, 1],
            "symbol": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"],
            "factor_name": ["mom", "mom", "mom", "mom"],
            "score": [0.8, 0.4, -0.2, -0.6],
            "asset_volatility": [4.0, 1.0, 4.0, 1.0],
        })
        constraints = Constraints(max_leverage=2.0, max_single_weight=1.0, target_volatility=0.2)
        target = construct(scores, current_positions={}, constraints=constraints)
        assert target.positions["ETHUSDT"] > target.positions["BTCUSDT"]
        assert abs(target.positions["SOLUSDT"]) < abs(target.positions["DOGEUSDT"])

    def test_construct_carries_rebalance_and_decay_metadata(self) -> None:
        scores = _scores()
        scores.attrs["rebalance_frequency_ms"] = 3_600_000
        scores.attrs["decay_hint"] = {"preferred_horizon": "4h"}

        target = construct(scores, current_positions={}, constraints=Constraints())

        assert target.metadata["rebalance_frequency_ms"] == 3_600_000
        assert target.metadata["decay_hint"] == {"preferred_horizon": "4h"}


class TestRebalancePolicy:
    def test_should_rebalance_true_on_first_run(self) -> None:
        assert should_rebalance(current_timestamp=10, last_rebalance_timestamp=None, rebalance_frequency_ms=5)

    def test_should_rebalance_respects_frequency(self) -> None:
        assert should_rebalance(current_timestamp=20, last_rebalance_timestamp=10, rebalance_frequency_ms=10)
        assert not should_rebalance(current_timestamp=15, last_rebalance_timestamp=10, rebalance_frequency_ms=10)
