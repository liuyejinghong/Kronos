"""R-breaker intraday breakout strategy — Kronos builtin example.

R-breaker uses the previous day's OHLC to compute breakout levels for today.
It is a classic intraday strategy, well-known among traders, with clear logic
and only a few tunable parameters.

Implements the ``Factor`` protocol: ``compute(df) → pd.Series``.
"""

from __future__ import annotations

import pandas as pd

from kronos.common.types import FactorFamily
from kronos.factor.base import BaseFactor
from kronos.factor.schemas import FactorMeta


class RBreakerFactor(BaseFactor):
    """R-breaker intraday breakout factor.

    For each bar, computes a normalized signal based on the previous day's
    pivot and breakout levels. Positive values indicate bullish bias
    (price near/past B-break), negative values indicate bearish bias.

    Configurable parameters:
        atr_period: ATR lookback for volatility normalization (default 14)
        volatility_multiplier: breakout threshold multiplier (default 1.5)
    """

    name = "r_breaker"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 254  # ATR(14) + ~240 bars (1 day of 1m)
    warmup_bars = 254
    universe = "crypto_perp"
    required_columns = ["open", "high", "low", "close", "event_time", "symbol"]
    description = "R-breaker 日内突破策略（基于前一日 OHLC 计算突破价位）"

    def __init__(
        self,
        atr_period: int = 14,
        volatility_multiplier: float = 1.5,
    ) -> None:
        super().__init__()
        self.atr_period = atr_period
        self.volatility_multiplier = volatility_multiplier

    def metadata(self) -> FactorMeta:
        return FactorMeta(
            name="r_breaker",
            version="1.0.0",
            family=FactorFamily.TREND_MOMENTUM,
            lookback=self.atr_period,
            warmup_bars=self.atr_period + 240,
            universe=["crypto"],
            required_columns=["open", "high", "low", "close", "event_time", "symbol"],
            description="R-breaker 日内突破策略（基于前一日 OHLC 计算突破价位）",
        )

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute R-breaker signal for each bar.

        Expects columns: open, high, low, close, event_time, symbol.
        Returns normalized signal: >0 = bullish bias, <0 = bearish bias.
        """
        required = {"open", "high", "low", "close", "event_time"}
        if not required.issubset(df.columns):
            missing = required - set(df.columns)
            raise ValueError(f"R-breaker requires columns: {missing}")

        if df.empty:
            return pd.Series(dtype=float)

        df = df.copy()
        df["date"] = pd.to_datetime(df["event_time"], unit="ms").dt.date

        # Compute daily OHLC
        daily = df.groupby("date").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
        )

        # Shift to get previous day's values
        daily["prev_high"] = daily["high"].shift(1)
        daily["prev_low"] = daily["low"].shift(1)
        daily["prev_close"] = daily["close"].shift(1)

        # R-breaker levels
        daily["pivot"] = (daily["prev_high"] + daily["prev_low"] + daily["prev_close"]) / 3.0
        daily["b_break"] = daily["prev_high"] + 2.0 * (daily["pivot"] - daily["prev_low"])
        daily["s_break"] = daily["prev_low"] - 2.0 * (daily["prev_high"] - daily["pivot"])

        # Merge levels back to intraday bars
        level_cols = daily[["pivot", "b_break", "s_break"]]
        df = df.merge(level_cols, on="date", how="left")

        # ATR for volatility normalization
        df["tr"] = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        df["atr"] = df["tr"].rolling(self.atr_period).mean()

        # Signal: distance from pivot, normalized by ATR and volatility multiplier
        df["signal"] = 0.0
        valid = (df["atr"] > 0) & df["pivot"].notna() & df["b_break"].notna()
        df.loc[valid, "signal"] = (
            (df.loc[valid, "close"] - df.loc[valid, "pivot"])
            / (df.loc[valid, "atr"] * self.volatility_multiplier)
        )

        result = df["signal"].astype(float)
        result.name = "r_breaker"
        return result


def create_r_breaker(**params: float) -> RBreakerFactor:
    """Factory for creating R-breaker with custom parameters."""
    return RBreakerFactor(
        atr_period=int(params.get("atr_period", 14)),
        volatility_multiplier=params.get("volatility_multiplier", 1.5),
    )
