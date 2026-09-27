"""Derivatives-based factor implementations (funding rate, OI, basis)."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd

from kronos.factor.base import BaseFactor


def _event_series(values: pd.Series) -> pd.Series:
    """Deduplicate piecewise-constant rows so rolling windows count events.

    After the PIT as-of join, funding/OI values are constant across the bars
    between two venue events. Rolling over raw bar rows makes the window
    length depend on the bar timeframe; rolling over deduplicated events
    restores the documented event-count semantics (audit FSR-011).
    """
    changed = values.ne(values.shift()) & values.notna()
    return values[changed]


class FundingRegimeFactor(BaseFactor):
    """Funding Regime factor based on rolling z-score of funding rate.

    Funding rate is low-frequency (every 8h on Binance). Registry.compute_all()
    is responsible for PIT-safe as-of joining the funding_rate column into df
    before calling compute().

    Interpretation of raw funding:
        Positive funding means longs pay shorts, market is bullish/overextended.
        Contrarian signal: fade crowded longs, flip sign.

    Direction after flip: higher value means higher expected return.
    """

    name = "funding_regime"
    family = "derivatives"
    version = "1.0.0"
    lookback = 21   # ~1 week of 8h funding intervals (21 x 8h = 168h)
    warmup_bars = 21
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["funding_rate"]
    description = (
        "Funding rate regime factor: rolling z-score of funding_rate, sign-flipped "
        "so that extreme positive funding (overcrowded longs) produces a negative signal."
    )

    def __init__(self, lookback: int = 21) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        fr = df["funding_rate"]
        events = _event_series(fr)

        roll_mean = (
            events.rolling(self.lookback, min_periods=self.lookback)
            .mean()
            .reindex(fr.index)
            .ffill()
        )
        roll_std = (
            events.rolling(self.lookback, min_periods=self.lookback)
            .std(ddof=1)
            .reindex(fr.index)
            .ffill()
        )

        # z-score: NaN when std ~= 0 (flat funding) is intentional
        zscore = np.where(
            roll_std > 1e-12,
            (fr - roll_mean) / roll_std,
            np.nan,
        )

        # Flip: positive funding (longs pay) is a contrarian short signal
        signal = -pd.Series(zscore, index=df.index, name=self.name)
        return signal


class OIMomentumFactor(BaseFactor):
    """Open-interest momentum factor.

    Higher values mean open interest is rising faster than its recent baseline.
    """

    name = "oi_momentum"
    family = "derivatives"
    version = "1.0.0"
    lookback = 12
    warmup_bars = 12
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["sum_open_interest"]
    description = (
        "Rolling z-score of open-interest change. Positive values indicate "
        "OI expansion relative to recent history."
    )

    def __init__(self, lookback: int = 12) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        oi = df["sum_open_interest"]
        oi_delta = _event_series(oi).pct_change().replace([np.inf, -np.inf], np.nan)
        mean = (
            oi_delta.rolling(self.lookback, min_periods=self.lookback)
            .mean()
            .reindex(oi.index)
            .ffill()
        )
        std = (
            oi_delta.rolling(self.lookback, min_periods=self.lookback)
            .std(ddof=1)
            .reindex(oi.index)
            .ffill()
        )
        momentum = np.where(std > 1e-12, mean / std, np.nan)
        return pd.Series(momentum, index=df.index, name=self.name)


class LiquidationFlowFactor(BaseFactor):
    """Net liquidation imbalance factor.

    Higher values mean short liquidations dominate long liquidations,
    which is treated as bullish short-squeeze pressure.
    """

    name = "liquidation_flow"
    family = "derivatives"
    version = "1.0.0"
    lookback = 12
    warmup_bars = 12
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["long_liquidation_volume", "short_liquidation_volume"]
    description = (
        "Rolling net liquidation imbalance. Positive when short liquidation flow "
        "outweighs long liquidation flow over the recent window."
    )

    def __init__(self, lookback: int = 12) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        total = (df["long_liquidation_volume"] + df["short_liquidation_volume"]).clip(lower=1e-12)
        imbalance = (df["short_liquidation_volume"] - df["long_liquidation_volume"]) / total
        events = _event_series(imbalance)
        return (
            events.rolling(self.lookback, min_periods=self.lookback)
            .mean()
            .reindex(imbalance.index)
            .ffill()
        )
