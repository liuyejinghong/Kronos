"""Unit tests for MoveDensityFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.liquidity import MoveDensityFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "volume": [100.0 + i * 2 for i in range(n)],
        "close": [100.0 + i * 0.5 for i in range(n)],
    })


class TestMoveDensityFactor:
    def test_basic_metadata(self) -> None:
        factor = MoveDensityFactor()
        assert factor.family == "volume_liquidity"
        assert factor.name == "move_density"

    def test_warmup_outputs_nan(self) -> None:
        factor = MoveDensityFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_density_is_positive(self) -> None:
        factor = MoveDensityFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = MoveDensityFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["close"]))
