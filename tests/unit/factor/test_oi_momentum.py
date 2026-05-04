"""Unit tests for OIMomentumFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.derivatives import OIMomentumFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + i * 300_000 for i in range(n)],
        "available_at": [base + i * 300_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "sum_open_interest": [10_000.0 + i * 100 for i in range(n)],
    })


class TestOIMomentumFactor:
    def test_basic_metadata(self) -> None:
        factor = OIMomentumFactor()
        assert factor.family == "derivatives"
        assert factor.name == "oi_momentum"

    def test_warmup_outputs_nan(self) -> None:
        factor = OIMomentumFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_rising_oi_produces_positive_signal_after_warmup(self) -> None:
        factor = OIMomentumFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result >= 0).all()

    def test_missing_input_raises(self) -> None:
        factor = OIMomentumFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["sum_open_interest"]))
