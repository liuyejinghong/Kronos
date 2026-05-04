"""Unit tests for CMOMomentumFactor."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.factor.implementations.trend import CMOMomentumFactor


def _make_df(n: int = 50, symbol: str = "BTCUSDT") -> pd.DataFrame:
    base_ts = 1_700_000_000_000
    prices = [100.0 + i * 0.5 for i in range(n)]  # monotonically increasing
    return pd.DataFrame({
        "event_time": [base_ts + i * 60_000 for i in range(n)],
        "available_at": [base_ts + (i + 1) * 60_000 for i in range(n)],
        "symbol": [symbol] * n,
        "close": prices,
    })


class TestCMOMomentumFactor:
    def test_name_family_version(self) -> None:
        f = CMOMomentumFactor()
        assert f.name == "cmo_momentum"
        assert f.family == "trend_momentum"
        assert f.version == "1.0.0"

    def test_warmup_rows_are_nan(self) -> None:
        f = CMOMomentumFactor(lookback=20)
        result = f.compute(_make_df(50))
        assert result.iloc[:19].isna().all()

    def test_post_warmup_not_nan(self) -> None:
        f = CMOMomentumFactor(lookback=20)
        result = f.compute(_make_df(50))
        assert result.iloc[20:].notna().all()

    def test_output_length_matches_input(self) -> None:
        f = CMOMomentumFactor(lookback=20)
        df = _make_df(40)
        result = f.compute(df)
        assert len(result) == len(df)

    def test_output_index_matches_input(self) -> None:
        f = CMOMomentumFactor(lookback=20)
        df = _make_df(40)
        result = f.compute(df)
        assert result.index.equals(df.index)

    def test_monotone_up_gives_positive_cmo(self) -> None:
        f = CMOMomentumFactor(lookback=10)
        # Strictly increasing prices → sum_up > 0, sum_down = 0 → CMO = 100
        df = _make_df(30)
        result = f.compute(df)
        valid = result.dropna()
        assert (valid > 0).all(), "monotone up prices should yield positive CMO"

    def test_flat_prices_give_nan_or_zero(self) -> None:
        f = CMOMomentumFactor(lookback=10)
        base_ts = 1_700_000_000_000
        df = pd.DataFrame({
            "event_time": [base_ts + i * 60_000 for i in range(30)],
            "available_at": [base_ts + (i + 1) * 60_000 for i in range(30)],
            "symbol": ["BTCUSDT"] * 30,
            "close": [100.0] * 30,  # flat
        })
        result = f.compute(df)
        valid = result.dropna()
        # Flat prices → delta = 0 → sum_up = sum_down = 0 → NaN (not zero)
        assert valid.isna().all() or (valid == 0).all()

    def test_range_within_minus_100_to_100(self) -> None:
        f = CMOMomentumFactor(lookback=10)
        df = _make_df(50)
        result = f.compute(df)
        valid = result.dropna()
        assert (valid >= -100).all() and (valid <= 100).all()

    def test_missing_column_raises(self) -> None:
        f = CMOMomentumFactor()
        df = _make_df()
        with pytest.raises(FactorInputError):
            f.compute(df.drop(columns=["close"]))

    def test_metadata_determinism(self) -> None:
        f = CMOMomentumFactor(lookback=15)
        assert f.metadata() == f.metadata()
        assert f.metadata()["lookback"] == 15

    def test_reproducibility(self) -> None:
        f = CMOMomentumFactor(lookback=20)
        df = _make_df(40)
        r1 = f.compute(df)
        r2 = f.compute(df)
        pd.testing.assert_series_equal(r1, r2)

    def test_direction_higher_is_bullish(self) -> None:
        f = CMOMomentumFactor(lookback=10)
        # Test with alternating prices that form a clear up/down signal
        n = 30
        base_ts = 1_700_000_000_000
        # Rising then falling
        prices_up = [100.0 + i for i in range(n)]
        prices_dn = [100.0 + (n - i) for i in range(n)]
        df_up = pd.DataFrame({
            "event_time": [base_ts + i * 60_000 for i in range(n)],
            "available_at": [base_ts + (i + 1) * 60_000 for i in range(n)],
            "symbol": ["BTCUSDT"] * n,
            "close": prices_up,
        })
        df_dn = df_up.copy()
        df_dn["close"] = prices_dn
        result_up = f.compute(df_up).dropna()
        result_dn = f.compute(df_dn).dropna()
        assert result_up.mean() > result_dn.mean(), "rising price should give higher CMO"
