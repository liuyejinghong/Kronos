"""Trend & momentum factor implementations."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd

from kronos.factor.base import BaseFactor


class ASISpreadFactor(BaseFactor):
    """Accumulation Swing Index Spread factor.

    Computes the ASI (Wilder's Accumulation Swing Index) and takes the
    difference between a short-window and long-window smoothed ASI.
    Positive spread means short-term momentum exceeds long-term trend (bullish).

    Direction: higher value means higher expected return (no flip needed).
    """

    name = "asi_spread"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 50  # long window dominates warmup
    warmup_bars = 50
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["open", "high", "low", "close"]
    description = (
        "ASI spread: short-window minus long-window smoothed Accumulation Swing Index. "
        "Captures intraday-to-daily momentum divergence."
    )

    def __init__(self, short_window: int = 14, long_window: int = 50) -> None:
        self.short_window = short_window
        self.long_window = long_window
        # Update lookback / warmup_bars to reflect actual windows
        self.lookback = long_window
        self.warmup_bars = long_window

    def metadata(self) -> dict[str, Any]:
        return {"short_window": self.short_window, "long_window": self.long_window}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        open_ = df["open"]
        high = df["high"]
        low = df["low"]

        # Wilder's Swing Index per bar (simplified single-bar SI)
        prev_close = close.shift(1)
        prev_open = open_.shift(1)

        # K = max range over the bar
        r = (high - low).clip(lower=1e-10)  # avoid div by zero

        # SI numerator components
        a = close - prev_close
        b = close - open_
        c = prev_close - prev_open

        # Limiting value T (simplified: use constant 3 as per Wilder)
        t = 3.0

        si = 50.0 * (a + 0.5 * b + 0.25 * c) / r * (r / t)

        # Cumulative ASI (running sum, forward-only via cumsum)
        asi = si.cumsum()

        short_smooth = asi.rolling(self.short_window, min_periods=self.short_window).mean()
        long_smooth = asi.rolling(self.long_window, min_periods=self.long_window).mean()

        spread = short_smooth - long_smooth
        spread.name = self.name
        return spread


class CMOMomentumFactor(BaseFactor):
    """Chande Momentum Oscillator (CMO) factor.

    CMO = 100 * (sum_up - sum_down) / (sum_up + sum_down) over lookback bars,
    where sum_up = sum of positive close changes and sum_down = |sum of negative
    close changes|.

    Range: [-100, 100]. Positive means net upward momentum.
    Direction: higher value means higher expected return (no flip needed).
    """

    name = "cmo_momentum"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = (
        "Chande Momentum Oscillator: ratio of net upward to total price movement "
        "over a rolling window. Range [-100, 100]."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff()
        up = delta.clip(lower=0)
        down = (-delta).clip(lower=0)

        sum_up = up.rolling(self.lookback, min_periods=self.lookback).sum()
        sum_down = down.rolling(self.lookback, min_periods=self.lookback).sum()

        denom = sum_up + sum_down
        # Avoid division by zero (flat price means denominator = 0 means NaN is correct)
        cmo = np.where(denom > 0, 100.0 * (sum_up - sum_down) / denom, np.nan)
        result = pd.Series(cmo, index=df.index, name=self.name)
        return result


class SignalPersistenceDensityFactor(BaseFactor):
    """Persistence density of directional closes.

    Higher values mean bullish closes dominate a larger share of the recent window.
    """

    name = "signal_persistence_density"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["open", "close"]
    description = (
        "Rolling persistence density of bullish closes. Captures how consistently "
        "recent bars keep extending in the same directional sign."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        direction = np.where(df["close"] > df["open"], 1.0, np.where(df["close"] < df["open"], -1.0, 0.0))
        density = pd.Series(direction, index=df.index, name=self.name)
        return density.rolling(self.lookback, min_periods=self.lookback).mean()


class BandPositionConditioningFactor(BaseFactor):
    """Momentum conditioned by Bollinger-style band location.

    Higher values mean price is persistently strong and sitting above its rolling centre.
    """

    name = "band_position_conditioning"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = (
        "Rolling band-position conditioning factor. Combines distance from the "
        "rolling mean with local volatility so momentum is discounted when price "
        "sits in an unfavourable band position."
    )

    def __init__(self, lookback: int = 20, std_window: int = 20) -> None:
        self.lookback = lookback
        self.std_window = std_window
        self.warmup_bars = max(lookback, std_window)
        self.lookback = self.warmup_bars

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback, "std_window": self.std_window}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        rolling_mean = df["close"].rolling(self.lookback, min_periods=self.lookback).mean()
        rolling_std = df["close"].rolling(self.std_window, min_periods=self.std_window).std(ddof=1)
        position = np.where(rolling_std > 1e-12, (df["close"] - rolling_mean) / rolling_std, np.nan)
        return pd.Series(position, index=df.index, name=self.name)


class TrendPullbackToleranceFactor(BaseFactor):
    """Maximum acceptable pullback while trend remains intact.

    Higher values mean price holds trend support despite recent pullback pressure.
    """

    name = "trend_pullback_tolerance"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = (
        "Trend pullback tolerance factor. Measures whether current drawdown from "
        "recent highs stays moderate while the slower trend baseline remains positive."
    )

    def __init__(self, lookback: int = 20, trend_window: int = 20) -> None:
        self.lookback = max(lookback, trend_window)
        self.trend_window = trend_window
        self.warmup_bars = self.lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback, "trend_window": self.trend_window}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        recent_high = close.rolling(self.lookback, min_periods=self.lookback).max()
        drawdown = (close - recent_high) / recent_high.clip(lower=1e-12)
        trend = close.rolling(self.trend_window, min_periods=self.trend_window).mean()
        trend_support = (close - trend) / trend.clip(lower=1e-12)
        tolerance = trend_support + drawdown
        return pd.Series(tolerance, index=df.index, name=self.name)


class MultiTimeframeConfirmationFactor(BaseFactor):
    """Fast/slow trend confirmation factor.

    Higher values mean the fast trend stays above the slower confirmation path.
    """

    name = "multi_timeframe_confirmation"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 48
    warmup_bars = 48
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = (
        "Multi-timeframe confirmation factor. Compares fast and slow smoothed "
        "close paths to confirm local trend with a slower background trend."
    )

    def __init__(self, fast_window: int = 12, slow_window: int = 48) -> None:
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.lookback = slow_window
        self.warmup_bars = slow_window

    def metadata(self) -> dict[str, Any]:
        return {"fast_window": self.fast_window, "slow_window": self.slow_window}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        fast = close.rolling(self.fast_window, min_periods=self.fast_window).mean()
        slow = close.rolling(self.slow_window, min_periods=self.slow_window).mean()
        confirmation = (fast - slow) / slow.clip(lower=1e-12)
        return pd.Series(confirmation, index=df.index, name=self.name)
