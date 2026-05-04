"""Unit tests for MidpointPowerFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.volatility import MidpointPowerFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for i in range(n):
        low = 100.0 + i
        high = low + 10.0
        close = high - 1.0
        rows.append({
            "event_time": base + i * 60_000,
            "available_at": base + i * 60_000,
            "symbol": "BTCUSDT",
            "high": high,
            "low": low,
            "close": close,
        })
    return pd.DataFrame(rows)


class TestMidpointPowerFactor:
    def test_basic_metadata(self) -> None:
        factor = MidpointPowerFactor()
        assert factor.family == "volatility_path"
        assert factor.name == "midpoint_power"

    def test_warmup_outputs_nan(self) -> None:
        factor = MidpointPowerFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_close_above_previous_midpoint_gives_positive_signal(self) -> None:
        factor = MidpointPowerFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = MidpointPowerFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["low"]))
