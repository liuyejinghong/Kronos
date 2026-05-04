"""Unit tests for BodyEnergyFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.volatility import BodyEnergyFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for i in range(n):
        open_ = 100.0 + i * 0.2
        close = open_ + 0.5
        rows.append({
            "event_time": base + i * 60_000,
            "available_at": base + i * 60_000,
            "symbol": "BTCUSDT",
            "open": open_,
            "high": close + 0.3,
            "low": open_ - 0.3,
            "close": close,
        })
    return pd.DataFrame(rows)


class TestBodyEnergyFactor:
    def test_basic_metadata(self) -> None:
        factor = BodyEnergyFactor()
        assert factor.family == "volatility_path"
        assert factor.name == "body_energy"

    def test_warmup_outputs_nan(self) -> None:
        factor = BodyEnergyFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_direction_is_positive_for_consistent_bullish_bodies(self) -> None:
        factor = BodyEnergyFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = BodyEnergyFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["high"]))
