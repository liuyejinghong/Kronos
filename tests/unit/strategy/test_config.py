"""Unit tests for strategy TOML config handling."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kronos.factor.candidates import clear_candidates, list_candidate_factors
from kronos.strategy.config import (
    StrategyConfig,
    default_r_breaker_config,
    load_strategy_config,
    register_strategy_config,
    write_strategy_config,
)


class TestStrategyConfig:
    def setup_method(self) -> None:
        clear_candidates()

    def teardown_method(self) -> None:
        clear_candidates()

    def test_writes_and_loads_default_r_breaker_config(self, tmp_path) -> None:
        config = default_r_breaker_config(symbols=["BTCUSDT"], timeframe="15m")
        path = write_strategy_config(config, directory=tmp_path)

        loaded = load_strategy_config(path)

        assert loaded.strategy.id == "r_breaker"
        assert loaded.strategy.kind == "r_breaker"
        assert loaded.universe.symbols == ["BTCUSDT"]
        assert loaded.universe.timeframe == "15m"
        assert loaded.params.atr_period == 14

    def test_rejects_unsafe_strategy_id(self) -> None:
        with pytest.raises(ValidationError):
            StrategyConfig.model_validate({
                "strategy": {"id": "../bad", "name": "Bad", "kind": "r_breaker"},
                "universe": {"symbols": ["BTCUSDT"], "timeframe": "15m"},
                "params": {"atr_period": 14, "volatility_multiplier": 1.5},
            })

    def test_rejects_invalid_timeframe(self) -> None:
        with pytest.raises(ValidationError):
            default_r_breaker_config(symbols=["BTCUSDT"], timeframe="2m")

    def test_rejects_unknown_params(self) -> None:
        with pytest.raises(ValidationError):
            StrategyConfig.model_validate({
                "strategy": {"id": "r_breaker", "name": "R", "kind": "r_breaker"},
                "universe": {"symbols": ["BTCUSDT"], "timeframe": "15m"},
                "params": {
                    "atr_period": 14,
                    "volatility_multiplier": 1.5,
                    "unknown": 1,
                },
            })

    def test_register_strategy_config_is_idempotent(self) -> None:
        config = default_r_breaker_config(symbols=["BTCUSDT"], timeframe="15m")

        register_strategy_config(config)
        register_strategy_config(config)

        candidates = list_candidate_factors()
        assert len(candidates) == 1
        assert candidates[0].candidate_id == "r_breaker"
        assert candidates[0].origin == "user_config"
