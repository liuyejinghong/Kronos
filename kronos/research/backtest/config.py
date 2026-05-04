"""Backtest configuration models."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

SUPPORTED_TIMEFRAMES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
SUPPORTED_MODES = {"long_only", "short_only", "market_neutral"}


class CrossValidationConfig(BaseModel):
    """Freqtrade cross-validation tolerances."""

    final_equity_abs_diff: float = 0.05
    max_drawdown_abs_diff: float = 0.05
    sharpe_abs_diff: float = 0.5
    trade_count_abs_diff: int = 10
    equity_curve_mae: float = 0.05

    model_config = {"frozen": True}


class BacktestConfig(BaseModel):
    """Research backtest engine configuration."""

    timeframe: str = "1h"
    rebalance_frequency: str = "1h"
    mode: str = "market_neutral"
    top_n: int = 20
    fee_bps: float = 4.0
    slippage_bps: float = 5.0
    apply_funding: bool = False
    signal_forward_fill: bool = False
    execution_delay_bars: int = 1
    periods_per_year: int | None = None
    worst_period_window: int = 5
    universe: list[str] = Field(default_factory=list)
    validation: CrossValidationConfig = Field(default_factory=CrossValidationConfig)

    model_config = {"frozen": True}

    @field_validator("timeframe", "rebalance_frequency")
    @classmethod
    def timeframe_supported(cls, value: str) -> str:
        if value not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {value}")
        return value

    @field_validator("mode")
    @classmethod
    def mode_supported(cls, value: str) -> str:
        if value not in SUPPORTED_MODES:
            raise ValueError(f"unsupported backtest mode: {value}")
        return value

    @field_validator("top_n")
    @classmethod
    def top_n_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("top_n must be > 0")
        return value

    @field_validator("execution_delay_bars")
    @classmethod
    def delay_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("execution_delay_bars must be >= 1")
        return value

    @field_validator("worst_period_window")
    @classmethod
    def worst_period_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("worst_period_window must be >= 1")
        return value

    def resolved_periods_per_year(self) -> int:
        if self.periods_per_year is not None:
            return self.periods_per_year
        minutes = SUPPORTED_TIMEFRAMES[self.timeframe]
        return (365 * 24 * 60) // minutes
