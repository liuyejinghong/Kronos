"""Unit tests for TrendPullbackEntryFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.mean_reversion import TrendPullbackEntryFactor


def _make_df(n: int = 50) -> pd.DataFrame:
    base = 1_700_000_000_000
    close = [100 + i * 0.5 for i in range(n)]
    close[-10:] = [close[-11] - 0.5 + offset * 0.05 for offset in range(10)]
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "close": close,
    })


class TestTrendPullbackEntryFactor:
    def test_basic_metadata(self) -> None:
        factor = TrendPullbackEntryFactor()
        assert factor.family == "mean_reversion"
        assert factor.name == "trend_pullback_entry"

    def test_warmup_outputs_nan(self) -> None:
        factor = TrendPullbackEntryFactor(lookback=10, trend_window=10, pullback_window=5)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_pullback_inside_uptrend_produces_positive_signal(self) -> None:
        factor = TrendPullbackEntryFactor(lookback=10, trend_window=10, pullback_window=5)
        result = factor.compute(_make_df()).dropna()
        assert (result >= 0).all()

    def test_missing_input_raises(self) -> None:
        factor = TrendPullbackEntryFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["close"]))
