"""Unit tests for FactorRegistry."""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd
import pytest

from kronos.common.errors import FactorRegistryError, FactorVersionError
from kronos.common.types import FactorStatus
from kronos.factor.base import BaseFactor
from kronos.factor.materialize import write_factor_partition
from kronos.factor.registry import FactorRegistry

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

class _FactorV1(BaseFactor):
    name = "test_factor"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 5
    warmup_bars = 5
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = "Test factor v1"

    def metadata(self) -> dict[str, Any]:
        return {"lookback": 5}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(5, min_periods=5).mean()


class _FactorV2(BaseFactor):
    name = "test_factor"
    family = "trend_momentum"
    version = "1.1.0"
    lookback = 10
    warmup_bars = 10
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = "Test factor v2"

    def metadata(self) -> dict[str, Any]:
        return {"lookback": 10}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(10, min_periods=10).mean()


class _OtherFactor(BaseFactor):
    name = "other_factor"
    family = "volatility_path"
    version = "1.0.0"
    lookback = 3
    warmup_bars = 3
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = "Other factor"

    def metadata(self) -> dict[str, Any]:
        return {"lookback": 3}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(3, min_periods=3).mean()


class _FundingProbeFactor(BaseFactor):
    name = "funding_probe"
    family = "derivatives"
    version = "1.0.0"
    lookback = 1
    warmup_bars = 1
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["funding_rate"]
    description = "Expose joined funding values for PIT-safe join tests"

    def metadata(self) -> dict[str, Any]:
        return {}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        return df["funding_rate"].astype(float)


@pytest.fixture
def reg() -> FactorRegistry:
    return FactorRegistry()


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_success(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        assert ("test_factor", "1.0.0") in reg._factors

    def test_register_duplicate_raises(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        with pytest.raises(FactorRegistryError, match="duplicate factor version"):
            reg.register(_FactorV1())

    def test_register_different_versions_ok(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        reg.register(_FactorV2())
        assert ("test_factor", "1.0.0") in reg._factors
        assert ("test_factor", "1.1.0") in reg._factors

    def test_initial_status_is_draft(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        assert reg._status[("test_factor", "1.0.0")] == FactorStatus.DRAFT

    def test_register_set_default(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        assert reg._defaults.get("test_factor") == "1.0.0"


# ---------------------------------------------------------------------------
# set_default() / get()
# ---------------------------------------------------------------------------

class TestGetAndSetDefault:
    def test_get_explicit_version(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        f = reg.get("test_factor", version="1.0.0")
        assert f.version == "1.0.0"

    def test_get_default_version(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        reg.set_default("test_factor", "1.0.0")
        f = reg.get("test_factor")
        assert f.version == "1.0.0"

    def test_get_no_default_raises(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        with pytest.raises(FactorVersionError, match="No default version"):
            reg.get("test_factor")

    def test_get_unknown_factor_raises(self, reg: FactorRegistry) -> None:
        with pytest.raises(FactorVersionError):
            reg.get("nonexistent")

    def test_get_wrong_version_raises(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        with pytest.raises(FactorVersionError):
            reg.get("test_factor", version="9.9.9")

    def test_set_default_unregistered_raises(self, reg: FactorRegistry) -> None:
        with pytest.raises(FactorVersionError, match="Cannot set default"):
            reg.set_default("test_factor", "1.0.0")

    def test_set_default_wrong_version_raises(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        with pytest.raises(FactorVersionError, match="Cannot set default"):
            reg.set_default("test_factor", "9.9.9")


# ---------------------------------------------------------------------------
# list_factors()
# ---------------------------------------------------------------------------

class TestListFactors:
    def test_list_empty(self, reg: FactorRegistry) -> None:
        assert reg.list_factors() == []

    def test_list_shows_all_versions(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        reg.register(_FactorV2())
        summaries = reg.list_factors()
        versions = {s["version"] for s in summaries}
        assert versions == {"1.0.0", "1.1.0"}

    def test_list_contains_required_keys(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        summary = reg.list_factors()[0]
        for key in ("name", "version", "family", "status", "is_default"):
            assert key in summary

    def test_list_marks_default(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        reg.register(_FactorV2())
        summaries = {s["version"]: s for s in reg.list_factors()}
        assert summaries["1.0.0"]["is_default"] is True
        assert summaries["1.1.0"]["is_default"] is False

    def test_list_validated_factors_only_returns_validated_entries(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        reg.register(_OtherFactor(), set_default=True)
        reg.update_status("test_factor", "1.0.0", FactorStatus.VALIDATED)

        summaries = reg.list_validated_factors()

        assert len(summaries) == 1
        assert summaries[0]["name"] == "test_factor"


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_registered_factor(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        s = reg.status("test_factor", version="1.0.0")
        assert s["name"] == "test_factor"
        assert s["registered"] is True
        assert s["status"] == FactorStatus.DRAFT
        assert s["validation_status"] == FactorStatus.DRAFT
        assert s["latest_materialized_at"] is None
        assert s["cache_coverage"] is None

    def test_status_unknown_factor_raises(self, reg: FactorRegistry) -> None:
        with pytest.raises(FactorVersionError):
            reg.status("nonexistent")

    def test_update_status(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1())
        reg.update_status("test_factor", "1.0.0", FactorStatus.CANDIDATE)
        s = reg.status("test_factor", version="1.0.0")
        assert s["status"] == FactorStatus.CANDIDATE

    def test_status_reports_cache_coverage(self, reg: FactorRegistry, tmp_path) -> None:
        reg.register(_FactorV1())

        march = pd.DataFrame({
            "event_time": [1_709_251_200_000 + i * 3_600_000 for i in range(3)],
            "available_at": [1_709_254_800_000 + i * 3_600_000 for i in range(3)],
            "symbol": ["BTCUSDT"] * 3,
            "value": [1.0, 2.0, 3.0],
        })
        april = pd.DataFrame({
            "event_time": [1_711_929_600_000 + i * 14_400_000 for i in range(2)],
            "available_at": [1_711_944_000_000 + i * 14_400_000 for i in range(2)],
            "symbol": ["ETHUSDT"] * 2,
            "value": [4.0, 5.0],
        })

        write_factor_partition(
            march,
            tmp_path,
            "test_factor",
            "1.0.0",
            "1h",
            "BTCUSDT",
            {"lookback": 5},
            1_700_000_000_000,
        )
        write_factor_partition(
            april,
            tmp_path,
            "test_factor",
            "1.0.0",
            "4h",
            "ETHUSDT",
            {"lookback": 5},
            1_700_000_000_000,
        )

        s = reg.status("test_factor", version="1.0.0", base_path=tmp_path)
        coverage = s["cache_coverage"]

        assert isinstance(s["latest_materialized_at"], int)
        assert coverage is not None
        assert coverage["timeframes"] == ["1h", "4h"]
        assert coverage["symbols"] == ["BTCUSDT", "ETHUSDT"]
        assert coverage["min_event_time"] == int(march["event_time"].min())
        assert coverage["max_event_time"] == int(april["event_time"].max())
        assert coverage["bar_count"] == 5
        assert coverage["partition_count"] == 2

    def test_promote_validated_requires_dual_gate(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        reg.update_status("test_factor", "1.0.0", FactorStatus.CANDIDATE)

        reg.promote_validated(
            "test_factor",
            "1.0.0",
            validation_passed=True,
            walkforward_passed=True,
        )

        status = reg.status("test_factor", version="1.0.0")
        assert status["status"] == FactorStatus.VALIDATED


# ---------------------------------------------------------------------------
# compute_all()
# ---------------------------------------------------------------------------

def _make_df(n: int = 30, symbol: str = "BTCUSDT") -> pd.DataFrame:
    base_ts = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base_ts + i * 60_000 for i in range(n)],
        "available_at": [base_ts + (i + 1) * 60_000 for i in range(n)],
        "symbol": [symbol] * n,
        "close": [100.0 + i * 0.1 for i in range(n)],
    })


class TestComputeAll:
    def test_single_factor_returns_long_table(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        df = _make_df(30)
        result = reg.compute_all(df)
        assert set(result.columns) >= {
            "event_time", "available_at", "symbol",
            "factor_name", "factor_version", "family", "value", "score",
        }

    def test_factor_name_in_output(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        result = reg.compute_all(_make_df(30))
        assert (result["factor_name"] == "test_factor").all()

    def test_value_preserves_warmup_nan(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        result = reg.compute_all(_make_df(30))
        # First warmup_bars - 1 = 4 rows must have NaN value
        head = result.sort_values("event_time").head(4)
        assert head["value"].isna().all()

    def test_score_is_nan_for_single_symbol(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        result = reg.compute_all(_make_df(30))
        assert result["score"].isna().all()

    def test_multi_symbol_score_filled(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        df = pd.concat([_make_df(30, "BTCUSDT"), _make_df(30, "ETHUSDT")], ignore_index=True)
        result = reg.compute_all(df)
        # After warmup, at least some cross-symbol scores should be filled
        valid_rows = result[result["value"].notna()]
        assert valid_rows["score"].notna().any()

    def test_empty_df_returns_empty(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        result = reg.compute_all(pd.DataFrame(columns=["event_time", "available_at", "symbol", "close"]))
        assert result.empty

    def test_factor_names_filter(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        reg.register(_OtherFactor(), set_default=True)
        result = reg.compute_all(_make_df(30), factor_names=["test_factor"])
        assert set(result["factor_name"].unique()) == {"test_factor"}

    def test_low_frequency_join_uses_available_at_without_future_leak(self, reg: FactorRegistry) -> None:
        reg.register(_FundingProbeFactor(), set_default=True)
        df = pd.DataFrame({
            "event_time": [1_000, 2_000, 3_000],
            "available_at": [10_000, 20_000, 30_000],
            "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT"],
        })
        low_freq_data = {
            "funding_rate": pd.DataFrame({
                "available_at": [5_000, 25_000, 35_000],
                "funding_rate": [0.1, 0.9, 1.2],
            })
        }

        result = reg.compute_all(df, factor_names=["funding_probe"], low_freq_data=low_freq_data)

        assert result["value"].tolist() == [0.1, 0.1, 0.9]

    def test_compute_validated_only_uses_validated_default_factors(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)
        reg.register(_OtherFactor(), set_default=True)
        reg.update_status("test_factor", "1.0.0", FactorStatus.VALIDATED)

        result = reg.compute_validated(_make_df(30))

        assert set(result["factor_name"].unique()) == {"test_factor"}

    def test_compute_validated_returns_empty_when_none_validated(self, reg: FactorRegistry) -> None:
        reg.register(_FactorV1(), set_default=True)

        result = reg.compute_validated(_make_df(30))

        assert result.empty
