"""Unit tests for MultiTimeframeConfirmationFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.trend import MultiTimeframeConfirmationFactor


def _make_df(n: int = 80) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "close": [100.0 + i * 0.3 for i in range(n)],
    })


class TestMultiTimeframeConfirmationFactor:
    def test_basic_metadata(self) -> None:
        factor = MultiTimeframeConfirmationFactor()
        assert factor.family == "trend_momentum"
        assert factor.name == "multi_timeframe_confirmation"

    def test_warmup_outputs_nan(self) -> None:
        factor = MultiTimeframeConfirmationFactor(fast_window=5, slow_window=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_fast_above_slow_produces_positive_signal(self) -> None:
        factor = MultiTimeframeConfirmationFactor(fast_window=5, slow_window=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = MultiTimeframeConfirmationFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["close"]))
