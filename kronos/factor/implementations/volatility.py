"""Volatility/path factor implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from kronos.factor.base import BaseFactor

if TYPE_CHECKING:
    import pandas as pd


class BodyEnergyFactor(BaseFactor):
    """Signed body-to-range pressure accumulator.

    Higher values mean closes repeatedly land near the direction of the body,
    which is treated as bullish persistence.
    """

    name = "body_energy"
    family = "volatility_path"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["open", "high", "low", "close"]
    description = (
        "Signed body-energy accumulation over a rolling window. Measures whether "
        "bars repeatedly close in the same directional body pressure."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        body = df["close"] - df["open"]
        range_ = (df["high"] - df["low"]).clip(lower=1e-12)
        signed_pressure = body / range_
        return signed_pressure.rolling(self.lookback, min_periods=self.lookback).mean()


class BarClosePressureFactor(BaseFactor):
    """Close-location pressure within each bar.

    Higher values mean closes repeatedly finish near the high of the bar.
    """

    name = "bar_close_pressure"
    family = "volatility_path"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["high", "low", "close"]
    description = (
        "Rolling close-location pressure. Measures whether bars repeatedly close "
        "near the high rather than the low of the realised range."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        range_ = (df["high"] - df["low"]).clip(lower=1e-12)
        close_location = ((df["close"] - df["low"]) / range_) * 2.0 - 1.0
        return close_location.rolling(self.lookback, min_periods=self.lookback).mean()


class MidpointPowerFactor(BaseFactor):
    """Asymmetric position versus the previous bar midpoint.

    Higher values mean the current close sits persistently above the prior bar midpoint.
    """

    name = "midpoint_power"
    family = "volatility_path"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["high", "low", "close"]
    description = (
        "Rolling midpoint-power asymmetry versus the previous bar midpoint. "
        "Captures directional control around prior-bar balance levels."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        prev_midpoint = ((df["high"].shift(1) + df["low"].shift(1)) / 2.0).astype(float)
        range_ = (df["high"] - df["low"]).clip(lower=1e-12)
        midpoint_power = (df["close"] - prev_midpoint) / range_
        return midpoint_power.rolling(self.lookback, min_periods=self.lookback).mean()


class RangeChopFilterFactor(BaseFactor):
    """High realised range with low net displacement filter.

    Higher values mean the window behaves more like noisy chop than directional trend.
    """

    name = "range_chop_filter"
    family = "volatility_path"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["high", "low", "close"]
    description = (
        "Range-chop filter. Measures realised path range relative to net close displacement "
        "to identify sideways, high-noise regimes."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        realised_range = (df["high"] - df["low"]).rolling(self.lookback, min_periods=self.lookback).sum()
        net_move = (df["close"] - df["close"].shift(self.lookback - 1)).abs().clip(lower=1e-12)
        return realised_range / net_move
