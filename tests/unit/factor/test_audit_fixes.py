"""Regression tests for the 2026-09-27 audit factor fixes (FSR-011/022)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from kronos.factor.implementations.derivatives import FundingRegimeFactor
from kronos.strategy.r_breaker import RBreakerFactor


def test_funding_regime_rolls_over_funding_events_not_bars() -> None:
    """1m bars with 8h-spaced funding changes must stay mostly non-NaN.

    Before the fix, rolling over bar rows made std>0 only within ~21 bars of
    each funding change (~4% coverage, boundary artifacts).
    """
    bars = 30 * 1440
    change_every = 8 * 60  # one funding event per 480 bars
    rng = np.random.default_rng(7)
    event_values = rng.normal(0.0, 1e-4, bars // change_every + 1)
    fr = np.repeat(event_values, change_every)[:bars]
    df = pd.DataFrame({"funding_rate": fr})

    out = FundingRegimeFactor()._compute(df)

    coverage = float(out.notna().mean())
    # ~90 events, 21-event lookup → ≈77% bar coverage (old behavior ≈4%).
    assert coverage > 0.7, f"coverage={coverage}"
    # 8h funding grid over 30 days → ~90 - 21 lookback events must produce
    # full bar coverage, not a handful of boundary windows.
    assert int(out.notna().sum()) > bars * 0.7


def test_r_breaker_warmup_scales_with_timeframe() -> None:
    factor = RBreakerFactor(atr_period=14)
    assert factor.warmup_for_timeframe("1d") <= 20
    assert factor.warmup_for_timeframe("15m") >= 14 + 96
    assert factor.warmup_for_timeframe("1m") >= 14 + 1440

    # _compute must retune warmup_bars to the actual bar interval.
    day_ms = 86_400_000
    bars_1d = 40
    df = pd.DataFrame({
        "open": np.linspace(100, 110, bars_1d),
        "high": np.linspace(101, 111, bars_1d),
        "low": np.linspace(99, 109, bars_1d),
        "close": np.linspace(100.5, 110.5, bars_1d),
        "event_time": np.arange(bars_1d) * day_ms,
        "symbol": ["BTCUSDT"] * bars_1d,
    })
    factor.warmup_bars = 254
    factor._compute(df)
    assert factor.warmup_bars <= 14 + 1 + 2, factor.warmup_bars
