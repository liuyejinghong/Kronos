"""Unit tests for Factor Protocol, BaseFactor, and FactorMeta."""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd
import pytest

from kronos.common.errors import FactorInputError
from kronos.common.types import Factor
from kronos.factor.base import BaseFactor
from kronos.factor.schemas import FactorMeta

# ---------------------------------------------------------------------------
# Minimal concrete factor for testing
# ---------------------------------------------------------------------------

class _MinimalFactor(BaseFactor):
    name = "minimal"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 5
    warmup_bars = 5
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = "Minimal test factor"

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(self.lookback, min_periods=self.lookback).mean()


def _make_df(n: int = 30) -> pd.DataFrame:
    base_ts = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base_ts + i * 60_000 for i in range(n)],
        "available_at": [base_ts + (i + 1) * 60_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "open": [100.0 + i for i in range(n)],
        "high": [105.0 + i for i in range(n)],
        "low": [95.0 + i for i in range(n)],
        "close": [102.0 + i for i in range(n)],
        "volume": [1000.0] * n,
    })


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

class TestFactorProtocol:
    def test_basefactor_satisfies_factor_protocol(self) -> None:
        f = _MinimalFactor()
        assert isinstance(f, Factor)

    def test_factor_meta_all_fields_present(self) -> None:
        f = _MinimalFactor()
        meta = f.meta
        assert meta.name == "minimal"
        assert meta.family.value == "trend_momentum"
        assert meta.version == "1.0.0"
        assert meta.lookback == 5
        assert meta.warmup_bars == 5
        assert meta.required_columns == ["close"]

    def test_missing_class_attrs_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="missing required attributes"):
            class _BadFactor(BaseFactor):  # type: ignore[abstract]
                # Missing all required attrs
                def metadata(self) -> dict[str, Any]:
                    return {}
                def _compute(self, df: pd.DataFrame) -> pd.Series:
                    return pd.Series(dtype=float)

    def test_invalid_family_raises(self) -> None:
        with pytest.raises(ValueError):
            class _BadFamily(BaseFactor):
                name = "bad"
                family = "not_a_real_family"
                version = "1.0.0"
                lookback = 5
                warmup_bars = 5
                universe = "crypto_perp"
                required_columns: ClassVar[list[str]] = ["close"]
                description = "bad"

                def metadata(self) -> dict[str, Any]:
                    return {}
                def _compute(self, df: pd.DataFrame) -> pd.Series:
                    return pd.Series(dtype=float)

            # FactorMeta validation happens via meta property
            meta = _BadFamily().meta
            assert meta is not None


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_missing_required_column_raises(self) -> None:
        f = _MinimalFactor()
        df = _make_df()
        df = df.drop(columns=["close"])
        with pytest.raises(FactorInputError, match="close"):
            f.compute(df)

    def test_missing_mandatory_column_raises(self) -> None:
        f = _MinimalFactor()
        df = _make_df()
        df = df.drop(columns=["symbol"])
        with pytest.raises(FactorInputError, match="symbol"):
            f.compute(df)

    def test_valid_input_passes(self) -> None:
        f = _MinimalFactor()
        result = f.compute(_make_df())
        assert result is not None


# ---------------------------------------------------------------------------
# Warmup / NaN behaviour
# ---------------------------------------------------------------------------

class TestWarmup:
    def test_warmup_rows_are_nan(self) -> None:
        f = _MinimalFactor()  # lookback=5, warmup_bars=5
        result = f.compute(_make_df(30))
        # First warmup_bars - 1 = 4 rows must be NaN
        assert result.iloc[:4].isna().all()

    def test_post_warmup_rows_not_nan(self) -> None:
        f = _MinimalFactor()
        result = f.compute(_make_df(30))
        assert result.iloc[5:].notna().all()

    def test_output_length_matches_input(self) -> None:
        f = _MinimalFactor()
        df = _make_df(20)
        result = f.compute(df)
        assert len(result) == len(df)

    def test_output_index_matches_input(self) -> None:
        f = _MinimalFactor()
        df = _make_df(20)
        result = f.compute(df)
        assert result.index.equals(df.index)

    def test_warmup_not_filled_with_zero(self) -> None:
        f = _MinimalFactor()
        result = f.compute(_make_df(10))
        assert not (result.iloc[:4] == 0).any()

    def test_warmup_not_filled_with_prev_value(self) -> None:
        f = _MinimalFactor()
        result = f.compute(_make_df(10))
        assert result.iloc[:4].isna().all(), "warmup must be NaN, not forward-filled"


# ---------------------------------------------------------------------------
# metadata() determinism
# ---------------------------------------------------------------------------

class TestMetadataDeterminism:
    def test_metadata_same_params_returns_identical_dict(self) -> None:
        f = _MinimalFactor()
        m1 = f.metadata()
        m2 = f.metadata()
        assert m1 == m2

    def test_metadata_contains_computation_params(self) -> None:
        f = _MinimalFactor()
        meta = f.metadata()
        assert "lookback" in meta

    def test_different_params_different_metadata(self) -> None:
        from kronos.factor.implementations.trend import CMOMomentumFactor
        f1 = CMOMomentumFactor(lookback=10)
        f2 = CMOMomentumFactor(lookback=20)
        assert f1.metadata() != f2.metadata()


# ---------------------------------------------------------------------------
# FactorMeta Pydantic validation
# ---------------------------------------------------------------------------

class TestFactorMeta:
    def test_valid_meta(self) -> None:
        m = FactorMeta(
            name="test",
            family="trend_momentum",
            version="1.0.0",
            lookback=10,
            warmup_bars=10,
            universe="crypto_perp",
            required_columns=["close"],
            description="test",
        )
        assert m.name == "test"

    def test_lookback_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="lookback must be"):
            FactorMeta(
                name="t", family="trend_momentum", version="1.0.0",
                lookback=0, warmup_bars=0, universe="u",
                required_columns=[], description="d",
            )

    def test_warmup_less_than_lookback_raises(self) -> None:
        with pytest.raises(ValueError, match="warmup_bars"):
            FactorMeta(
                name="t", family="trend_momentum", version="1.0.0",
                lookback=20, warmup_bars=10, universe="u",
                required_columns=[], description="d",
            )

    def test_empty_version_raises(self) -> None:
        with pytest.raises(ValueError, match="version"):
            FactorMeta(
                name="t", family="trend_momentum", version="  ",
                lookback=10, warmup_bars=10, universe="u",
                required_columns=[], description="d",
            )
