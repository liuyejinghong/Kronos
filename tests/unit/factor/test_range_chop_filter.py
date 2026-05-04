"""Unit tests for RangeChopFilterFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.volatility import RangeChopFilterFactor


def _make_df(n: int = 40) -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for i in range(n):
        low = 100.0 + i * 0.1
        high = low + 4.0
        close = low + 0.2 + (i % 2) * 0.1
        rows.append({
            "event_time": base + i * 60_000,
            "available_at": base + i * 60_000,
            "symbol": "BTCUSDT",
            "high": high,
            "low": low,
            "close": close,
        })
    return pd.DataFrame(rows)


class TestRangeChopFilterFactor:
    def test_basic_metadata(self) -> None:
        factor = RangeChopFilterFactor()
        assert factor.family == "volatility_path"
        assert factor.name == "range_chop_filter"

    def test_warmup_outputs_nan(self) -> None:
        factor = RangeChopFilterFactor(lookback=10)
        result = factor.compute(_make_df())
        assert result.iloc[:9].isna().all()

    def test_choppy_path_gives_large_positive_filter_value(self) -> None:
        factor = RangeChopFilterFactor(lookback=10)
        result = factor.compute(_make_df()).dropna()
        assert (result > 1.0).all()

    def test_missing_input_raises(self) -> None:
        factor = RangeChopFilterFactor()
        with pytest.raises(FactorInputError):
            factor.compute(_make_df().drop(columns=["high"]))
