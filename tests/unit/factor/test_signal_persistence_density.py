"""Unit tests for SignalPersistenceDensityFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.trend import SignalPersistenceDensityFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for i in range(n):
        open_ = 100.0 + i * 0.2
        rows.append({
            "event_time": base + i * 60_000,
            "available_at": base + i * 60_000,
            "symbol": "BTCUSDT",
            "open": open_,
            "close": open_ + 0.4,
        })
    return pd.DataFrame(rows)


class TestSignalPersistenceDensityFactor:
    def test_basic_metadata(self) -> None:
        factor = SignalPersistenceDensityFactor()
        assert factor.family == "trend_momentum"
        assert factor.name == "signal_persistence_density"

    def test_warmup_outputs_nan(self) -> None:
        factor = SignalPersistenceDensityFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_consistent_bullish_bodies_produce_positive_density(self) -> None:
        factor = SignalPersistenceDensityFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 0).all()

    def test_missing_input_raises(self) -> None:
        factor = SignalPersistenceDensityFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["close"]))
