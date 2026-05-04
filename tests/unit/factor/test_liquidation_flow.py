"""Unit tests for LiquidationFlowFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.derivatives import LiquidationFlowFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + i * 60_000 for i in range(n)],
        "available_at": [base + i * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "long_liquidation_volume": [10.0 + i * 0.2 for i in range(n)],
        "short_liquidation_volume": [20.0 + i * 0.4 for i in range(n)],
    })


class TestLiquidationFlowFactor:
    def test_basic_metadata(self) -> None:
        factor = LiquidationFlowFactor()
        assert factor.family == "derivatives"
        assert factor.name == "liquidation_flow"

    def test_warmup_outputs_nan(self) -> None:
        factor = LiquidationFlowFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_short_liquidation_pressure_gives_positive_signal(self) -> None:
        factor = LiquidationFlowFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = LiquidationFlowFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["short_liquidation_volume"]))
