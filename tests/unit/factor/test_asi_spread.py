"""Unit tests for ASISpreadFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.trend import ASISpreadFactor


def _make_ohlc(n: int = 80, symbol: str = "BTCUSDT") -> pd.DataFrame:
    base_ts = 1_700_000_000_000
    base = 100.0
    rows = []
    for i in range(n):
        o = base + i * 0.1
        h = o + 1.5
        low = o - 1.0
        c = o + 0.5
        rows.append({
            "event_time": base_ts + i * 3_600_000,
            "available_at": base_ts + (i + 1) * 3_600_000,
            "symbol": symbol,
            "open": o,
            "high": h,
            "low": low,
            "close": c,
        })
    return pd.DataFrame(rows)


class TestASISpreadFactor:
    def test_name_family_version(self) -> None:
        f = ASISpreadFactor()
        assert f.name == "asi_spread"
        assert f.family == "trend_momentum"
        assert f.version == "1.0.0"

    def test_warmup_rows_are_nan(self) -> None:
        f = ASISpreadFactor(short_window=5, long_window=20)
        result = f.compute(_make_ohlc(60))
        # warmup_bars = long_window = 20 → first 19 rows are NaN
        assert result.iloc[:19].isna().all()

    def test_post_warmup_not_all_nan(self) -> None:
        f = ASISpreadFactor(short_window=5, long_window=20)
        result = f.compute(_make_ohlc(60))
        assert result.iloc[20:].notna().any()

    def test_output_length_matches_input(self) -> None:
        f = ASISpreadFactor(short_window=5, long_window=20)
        df = _make_ohlc(60)
        result = f.compute(df)
        assert len(result) == len(df)

    def test_output_index_matches_input(self) -> None:
        f = ASISpreadFactor(short_window=5, long_window=20)
        df = _make_ohlc(60)
        result = f.compute(df)
        assert result.index.equals(df.index)

    def test_missing_column_raises(self) -> None:
        f = ASISpreadFactor()
        df = _make_ohlc()
        with pytest.raises(FactorInputError):
            f.compute(df.drop(columns=["high"]))

    def test_metadata_determinism(self) -> None:
        f = ASISpreadFactor(short_window=10, long_window=30)
        assert f.metadata() == f.metadata()
        assert f.metadata() == {"short_window": 10, "long_window": 30}

    def test_reproducibility(self) -> None:
        f = ASISpreadFactor(short_window=5, long_window=20)
        df = _make_ohlc(60)
        r1 = f.compute(df)
        r2 = f.compute(df)
        pd.testing.assert_series_equal(r1, r2)

    def test_custom_windows_update_lookback(self) -> None:
        f = ASISpreadFactor(short_window=3, long_window=10)
        assert f.lookback == 10
        assert f.warmup_bars == 10
