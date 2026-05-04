"""Unit tests for TrendPullbackToleranceFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.trend import TrendPullbackToleranceFactor


def _make_df(n: int = 50) -> pd.DataFrame:
    base = 1_700_000_000_000
    close = [100 + i * 0.5 for i in range(n)]
    close[-10:] = [close[-11] + offset * 0.1 for offset in range(10)]
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "close": close,
    })


class TestTrendPullbackToleranceFactor:
    def test_basic_metadata(self) -> None:
        factor = TrendPullbackToleranceFactor()
        assert factor.family == "trend_momentum"
        assert factor.name == "trend_pullback_tolerance"

    def test_warmup_outputs_nan(self) -> None:
        factor = TrendPullbackToleranceFactor(lookback=10, trend_window=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_signal_is_finite_after_warmup(self) -> None:
        factor = TrendPullbackToleranceFactor(lookback=10, trend_window=10)
        result = factor.compute(_make_df()).dropna()
        assert result.notna().all()

    def test_missing_input_raises(self) -> None:
        factor = TrendPullbackToleranceFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["close"]))
