"""Unit tests for VolumeDroughtFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.liquidity import VolumeDroughtFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "volume": [200.0 - i for i in range(n)],
    })


class TestVolumeDroughtFactor:
    def test_basic_metadata(self) -> None:
        factor = VolumeDroughtFactor()
        assert factor.family == "volume_liquidity"
        assert factor.name == "volume_drought"

    def test_warmup_outputs_nan(self) -> None:
        factor = VolumeDroughtFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_declining_volume_produces_positive_signal(self) -> None:
        factor = VolumeDroughtFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = VolumeDroughtFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["volume"]))
