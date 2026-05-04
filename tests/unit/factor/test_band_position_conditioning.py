"""Unit tests for BandPositionConditioningFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.trend import BandPositionConditioningFactor


def _make_df(n: int = 50) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "close": [100.0 + i * 0.4 for i in range(n)],
    })


class TestBandPositionConditioningFactor:
    def test_basic_metadata(self) -> None:
        factor = BandPositionConditioningFactor()
        assert factor.family == "trend_momentum"
        assert factor.name == "band_position_conditioning"

    def test_warmup_outputs_nan(self) -> None:
        factor = BandPositionConditioningFactor(lookback=10, std_window=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_uptrend_above_band_center_gives_positive_signal(self) -> None:
        factor = BandPositionConditioningFactor(lookback=10, std_window=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = BandPositionConditioningFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["close"]))
