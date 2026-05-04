"""Mean-reversion factor implementations."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd

from kronos.factor.base import BaseFactor


class TrendPullbackEntryFactor(BaseFactor):
    """Trend-with-pullback entry candidate.

    Higher values mean price remains in an uptrend but is temporarily pulled
    back from its recent highs, creating a re-entry style setup.
    """

    name = "trend_pullback_entry"
    family = "mean_reversion"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = (
        "Trend pullback entry factor. Positive when price stays above its slower "
        "trend baseline while sitting below recent local highs."
    )

    def __init__(self, lookback: int = 20, trend_window: int = 20, pullback_window: int = 10) -> None:
        self.lookback = max(lookback, trend_window, pullback_window)
        self.trend_window = trend_window
        self.pullback_window = pullback_window
        self.warmup_bars = self.lookback

    def metadata(self) -> dict[str, Any]:
        return {
            "lookback": self.lookback,
            "trend_window": self.trend_window,
            "pullback_window": self.pullback_window,
        }

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        trend = close.rolling(self.trend_window, min_periods=self.trend_window).mean()
        recent_high = close.rolling(self.pullback_window, min_periods=self.pullback_window).max()
        pullback_depth = (recent_high - close) / recent_high.clip(lower=1e-12)
        trend_support = (close - trend) / trend.clip(lower=1e-12)
        signal = np.where(trend_support > 0, pullback_depth, np.nan)
        return pd.Series(signal, index=df.index, name=self.name)
