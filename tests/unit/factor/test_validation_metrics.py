"""Unit tests for factor validation metrics and pipeline.

Coverage:
    - compute_forward_returns: PIT-safe entry/exit, NaN at boundaries
    - compute_ic: Pearson + Spearman, min n_obs guard
    - compute_grouped_returns: quantile spread, graceful degradation
    - compute_turnover: rank-change proxy, NaN guard
    - compute_decay_profile: multi-period IC, sorted output
    - adjudicate: pass / review / fail thresholds
    - validate_factor: integration through full pipeline
    - ValidationResult.to_dict: JSON-serialisable scalars
    - persist_validation_result: file layout + content
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from kronos.factor.validation import (
    ValidationConfig,
    ValidationOutcome,
    persist_validation_result,
    validate_factor,
)
from kronos.factor.validation.metrics import (
    adjudicate,
    compute_decay_profile,
    compute_forward_returns,
    compute_grouped_returns,
    compute_ic,
    compute_turnover,
    summarise_ic,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prices(n: int = 50, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    raw = 100 + rng.normal(0, 1, n).cumsum()
    return pd.Series(raw, dtype=float)


def _available_at(n: int = 50) -> pd.Series:
    """Monotone epoch-ms timestamps, one per bar."""
    base = 1_700_000_000_000
    return pd.Series([base + i * 60_000 for i in range(n)], dtype=float)


def _factor(prices: pd.Series, shift: int = 1) -> pd.Series:
    """Simple momentum factor: price change over `shift` bars."""
    return prices.diff(shift).fillna(0.0)


# ---------------------------------------------------------------------------
# compute_forward_returns
# ---------------------------------------------------------------------------


class TestComputeForwardReturns:
    def test_shape(self) -> None:
        p = _prices(20)
        avail = _available_at(20)
        fwd = compute_forward_returns(p, avail, [1, 3])
        assert list(fwd.columns) == ["fwd_1", "fwd_3"]
        assert len(fwd) == 20

    def test_pit_safe_entry_exit(self) -> None:
        """Entry at bar i+1, exit at bar i+1+N — check manual calc."""
        p = pd.Series([100.0, 102.0, 105.0, 104.0, 106.0])
        avail = _available_at(5)
        fwd = compute_forward_returns(p, avail, [1])
        # bar 0: entry=p[1]=102, exit=p[2]=105 → (105-102)/102
        expected_0 = (105 - 102) / 102
        assert math.isclose(fwd["fwd_1"].iloc[0], expected_0, rel_tol=1e-9)

    def test_nan_at_tail(self) -> None:
        """Last N rows must be NaN (exit index out of bounds)."""
        p = _prices(10)
        avail = _available_at(10)
        fwd = compute_forward_returns(p, avail, [3])
        # rows where i+1+3 >= 10 → i >= 6 → last 4 rows NaN
        assert fwd["fwd_3"].iloc[-1:].isna().all()
        assert not math.isnan(float(fwd["fwd_3"].iloc[0]))

    def test_zero_entry_price_yields_nan(self) -> None:
        p = pd.Series([0.0, 100.0, 101.0])
        avail = _available_at(3)
        fwd = compute_forward_returns(p, avail, [1])
        # bar 0: entry price = p[1] = 100 (not zero), so this is valid
        # bar 1: entry price = p[2] = 101, exit = p[3] — out of bounds → NaN
        assert math.isnan(fwd["fwd_1"].iloc[1])

    def test_entry_zero_price_gives_nan(self) -> None:
        """If the entry bar has price=0, that row should be NaN."""
        p = pd.Series([100.0, 0.0, 102.0, 103.0])
        avail = _available_at(4)
        fwd = compute_forward_returns(p, avail, [1])
        # bar 0: entry=p[1]=0 → NaN
        assert math.isnan(fwd["fwd_1"].iloc[0])


# ---------------------------------------------------------------------------
# compute_ic
# ---------------------------------------------------------------------------


class TestComputeIC:
    def test_returns_dataframe_with_expected_columns(self) -> None:
        p = _prices(40)
        fwd = compute_forward_returns(p, _available_at(40), [1, 3])
        factor = _factor(p)
        ic = compute_ic(factor, fwd)
        assert set(ic.columns) == {"period", "ic", "rank_ic", "n_obs"}

    def test_strong_correlation_gives_positive_ic(self) -> None:
        """A factor that IS the return should have IC near 1."""
        n = 50
        p = _prices(n)
        fwd = compute_forward_returns(p, _available_at(n), [1])
        # Factor = forward return itself (perfect predictor)
        perfect_factor = fwd["fwd_1"].fillna(0.0)
        ic = compute_ic(perfect_factor, fwd[["fwd_1"]])
        assert not ic.empty
        assert ic["rank_ic"].iloc[0] > 0.9

    def test_random_factor_ic_near_zero(self) -> None:
        rng = np.random.default_rng(42)
        n = 200
        p = pd.Series(100 + rng.normal(0, 1, n).cumsum())
        fwd = compute_forward_returns(p, _available_at(n), [1])
        random_factor = pd.Series(rng.normal(0, 1, n))
        ic = compute_ic(random_factor, fwd)
        # IC should be small in absolute value (within ±0.3 for n=200)
        assert abs(float(ic["rank_ic"].iloc[0])) < 0.3

    def test_min_obs_guard(self) -> None:
        """Fewer than 10 valid obs → period omitted from output."""
        p = _prices(5)
        fwd = compute_forward_returns(p, _available_at(5), [1])
        factor = _factor(p)
        ic = compute_ic(factor, fwd)
        assert ic.empty


# ---------------------------------------------------------------------------
# compute_grouped_returns
# ---------------------------------------------------------------------------


class TestComputeGroupedReturns:
    def test_basic_structure(self) -> None:
        n = 100
        p = _prices(n)
        fwd = compute_forward_returns(p, _available_at(n), [1])
        factor = _factor(p)
        result = compute_grouped_returns(factor, fwd["fwd_1"].dropna(), quantiles=5)
        assert isinstance(result["quantile_returns"], pd.Series)
        assert isinstance(result["top_minus_bottom"], float)

    def test_positive_factor_positive_spread(self) -> None:
        """Monotone factor should give top-minus-bottom > 0."""
        n = 200
        rng = np.random.default_rng(1)
        signal = pd.Series(np.arange(n, dtype=float))  # perfectly ranked
        # Create returns that correlate with signal
        noise = pd.Series(rng.normal(0, 0.001, n))
        returns = signal / signal.max() * 0.01 + noise
        result = compute_grouped_returns(signal, returns, quantiles=5)
        assert result["top_minus_bottom"] > 0

    def test_small_sample_degrades_gracefully(self) -> None:
        factor = pd.Series([1.0, 2.0])
        fwd = pd.Series([0.01, 0.02])
        result = compute_grouped_returns(factor, fwd, quantiles=5)
        assert math.isnan(result["top_minus_bottom"])  # type: ignore[arg-type]
        assert result["skipped_pct"] == 1.0

    def test_constant_factor_degrades_gracefully(self) -> None:
        factor = pd.Series([1.0] * 30)
        fwd = pd.Series(np.random.default_rng(0).normal(0, 0.01, 30))
        result = compute_grouped_returns(factor, fwd, quantiles=5)
        # All same value → qcut fails → graceful NaN
        assert math.isnan(result["top_minus_bottom"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# compute_turnover
# ---------------------------------------------------------------------------


class TestComputeTurnover:
    def test_returns_expected_keys(self) -> None:
        factor = _factor(_prices(50))
        result = compute_turnover(factor)
        assert "top_turnover" in result
        assert "bottom_turnover" in result
        assert "median_turnover" in result

    def test_small_sample_returns_nan(self) -> None:
        factor = pd.Series([1.0, 2.0])
        result = compute_turnover(factor, quantiles=5)
        assert math.isnan(result["top_turnover"])
        assert math.isnan(result["bottom_turnover"])
        assert math.isnan(result["median_turnover"])

    def test_constant_factor_returns_nan(self) -> None:
        factor = pd.Series([5.0] * 100)
        result = compute_turnover(factor, quantiles=5)
        assert math.isnan(result["top_turnover"]) or math.isnan(result["median_turnover"])

    def test_turnover_in_zero_one_range(self) -> None:
        """Rank-change proxy should produce [0, 1] values for typical factors."""
        factor = _factor(_prices(100, seed=7))
        result = compute_turnover(factor, quantiles=5)
        if not math.isnan(result["median_turnover"]):
            assert 0.0 <= result["median_turnover"] <= 1.0


# ---------------------------------------------------------------------------
# summarise_ic
# ---------------------------------------------------------------------------


class TestSummariseIC:
    def test_empty_series_returns_nan(self) -> None:
        s = summarise_ic(pd.Series(dtype=float))
        assert math.isnan(s["mean_ic"])
        assert math.isnan(s["ic_ir"])

    def test_all_positive_ic(self) -> None:
        s = summarise_ic(pd.Series([0.05, 0.07, 0.04]))
        assert s["ic_positive_ratio"] == 1.0
        assert s["mean_ic"] > 0

    def test_mixed_ic(self) -> None:
        s = summarise_ic(pd.Series([0.1, -0.05, 0.03]))
        assert 0 < s["ic_positive_ratio"] < 1.0


# ---------------------------------------------------------------------------
# compute_decay_profile
# ---------------------------------------------------------------------------


class TestComputeDecayProfile:
    def test_sorted_by_period(self) -> None:
        n = 100
        p = _prices(n)
        fwd = compute_forward_returns(p, _available_at(n), [1, 3, 5])
        factor = _factor(p)
        decay = compute_decay_profile(factor, fwd)
        if not decay.empty:
            assert list(decay["period"]) == sorted(decay["period"].tolist())

    def test_columns_present(self) -> None:
        n = 100
        p = _prices(n)
        fwd = compute_forward_returns(p, _available_at(n), [1, 3])
        factor = _factor(p)
        decay = compute_decay_profile(factor, fwd)
        if not decay.empty:
            assert "period" in decay.columns
            assert "mean_rank_ic" in decay.columns


# ---------------------------------------------------------------------------
# adjudicate
# ---------------------------------------------------------------------------


class TestAdjudicate:
    def _config(self) -> ValidationConfig:
        return ValidationConfig()

    def test_all_pass(self) -> None:
        cfg = self._config()
        result = adjudicate(
            mean_rank_ic=0.05,
            rank_ic_positive_ratio=0.60,
            top_minus_bottom=0.01,
            median_turnover=0.30,
            config=cfg,
        )
        assert result == "pass"

    def test_low_ic_fails(self) -> None:
        cfg = self._config()
        result = adjudicate(
            mean_rank_ic=-0.01,
            rank_ic_positive_ratio=0.40,
            top_minus_bottom=-0.005,
            median_turnover=0.30,
            config=cfg,
        )
        assert result == "fail"

    def test_borderline_review(self) -> None:
        """Positive IC direction but below threshold → review."""
        cfg = self._config()
        result = adjudicate(
            mean_rank_ic=0.01,    # below min 0.02
            rank_ic_positive_ratio=0.50,  # below min 0.55
            top_minus_bottom=0.005,  # above 0
            median_turnover=0.40,
            config=cfg,
        )
        assert result == "review"

    def test_high_turnover_blocks_pass(self) -> None:
        cfg = self._config()
        result = adjudicate(
            mean_rank_ic=0.05,
            rank_ic_positive_ratio=0.65,
            top_minus_bottom=0.01,
            median_turnover=0.90,  # above max 0.70
            config=cfg,
        )
        # All other metrics pass, but turnover fails → review or fail depending on direction
        assert result in {"review", "fail"}


# ---------------------------------------------------------------------------
# validate_factor (integration)
# ---------------------------------------------------------------------------


class TestValidateFactor:
    def test_returns_validation_result(self) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        assert isinstance(result.outcome, ValidationOutcome)
        assert result.outcome in {ValidationOutcome.PASS, ValidationOutcome.REVIEW, ValidationOutcome.FAIL}

    def test_to_dict_json_serialisable(self) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        d = result.to_dict()
        # Should be JSON-serialisable (no NaN, no non-serialisable types)
        serialised = json.dumps(d)
        parsed = json.loads(serialised)
        assert parsed["outcome"] in {"pass", "review", "fail"}

    def test_perfect_predictor_passes(self) -> None:
        """Factor = forward return (shifted) → should at least be 'review' or 'pass'."""
        n = 100
        p = _prices(n, seed=5)
        avail = _available_at(n)
        fwd = compute_forward_returns(p, avail, [1])
        factor = fwd["fwd_1"].fillna(0.0)
        result = validate_factor(factor, p, avail, config=ValidationConfig(periods=[1]))
        assert result.outcome in {ValidationOutcome.PASS, ValidationOutcome.REVIEW}

    def test_random_factor_outcome_is_valid_enum(self) -> None:
        rng = np.random.default_rng(99)
        n = 100
        p = pd.Series(100 + rng.normal(0, 1, n).cumsum())
        avail = _available_at(n)
        factor = pd.Series(rng.normal(0, 1, n))
        result = validate_factor(factor, p, avail)
        assert result.outcome in {ValidationOutcome.PASS, ValidationOutcome.REVIEW, ValidationOutcome.FAIL}

    def test_custom_config_applied(self) -> None:
        """Custom config with high thresholds → likely fail for random factor."""
        rng = np.random.default_rng(77)
        n = 100
        p = pd.Series(100 + rng.normal(0, 1, n).cumsum())
        avail = _available_at(n)
        factor = pd.Series(rng.normal(0, 1, n))
        strict_config = ValidationConfig(
            min_mean_rank_ic=0.99,       # impossible to meet
            min_rank_ic_positive_ratio=0.99,
            min_top_minus_bottom_return=0.99,
            max_median_turnover=0.001,
        )
        result = validate_factor(factor, p, avail, config=strict_config)
        assert result.outcome in {ValidationOutcome.REVIEW, ValidationOutcome.FAIL}


# ---------------------------------------------------------------------------
# persist_validation_result
# ---------------------------------------------------------------------------


class TestPersistValidationResult:
    def test_creates_expected_files(self, tmp_path) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        run_dir = persist_validation_result(
            result,
            "test_factor",
            base_dir=tmp_path,
            run_id="run001",
            factor_version="1.0.0",
        )

        assert (run_dir / "metrics.json").exists()
        assert (run_dir / "outcome.txt").exists()
        assert run_dir == tmp_path / "test_factor" / "1.0.0"

    def test_metrics_json_content(self, tmp_path) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        run_dir = persist_validation_result(
            result,
            "test_factor",
            base_dir=tmp_path,
            run_id="run002",
            factor_version="1.0.0",
        )

        content = json.loads((run_dir / "metrics.json").read_text())
        assert "outcome" in content
        assert content["outcome"] in {"pass", "review", "fail"}

    def test_outcome_txt_matches_result(self, tmp_path) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        run_dir = persist_validation_result(
            result,
            "test_factor",
            base_dir=tmp_path,
            run_id="run003",
            factor_version="1.0.0",
        )

        txt = (run_dir / "outcome.txt").read_text().strip()
        assert txt == str(result.outcome)

    def test_auto_run_id_creates_dir(self, tmp_path) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        run_dir = persist_validation_result(result, "factor_x", base_dir=tmp_path)
        assert run_dir.exists()
        assert run_dir == tmp_path / "factor_x" / "unversioned"

    def test_default_base_dir_matches_spec(self, monkeypatch, tmp_path) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)

        monkeypatch.chdir(tmp_path)
        run_dir = persist_validation_result(
            result,
            "factor_x",
            run_id="run004",
            factor_version="1.0.0",
        )

        assert run_dir.resolve() == (
            tmp_path / "reports" / "factor_validation" / "factor_x" / "1.0.0"
        ).resolve()
        assert (run_dir / "metrics.json").exists()

    def test_metrics_json_includes_report_metadata(self, tmp_path) -> None:
        n = 80
        p = _prices(n)
        avail = _available_at(n)
        factor = _factor(p)
        result = validate_factor(factor, p, avail)
        run_dir = persist_validation_result(
            result,
            "factor_x",
            base_dir=tmp_path,
            run_id="run005",
            factor_version="1.2.0",
            timeframe="1h",
            universe=["BTCUSDT", "ETHUSDT"],
        )

        content = json.loads((run_dir / "metrics.json").read_text())
        metadata = content["report_metadata"]

        assert metadata["factor_name"] == "factor_x"
        assert metadata["factor_version"] == "1.2.0"
        assert metadata["run_id"] == "run005"
        assert metadata["report_path_segment"] == "1.2.0"
        assert metadata["timeframe"] == "1h"
        assert metadata["universe"] == ["BTCUSDT", "ETHUSDT"]
        assert metadata["thresholds"]["min_mean_rank_ic"] == result.config.min_mean_rank_ic
        assert metadata["periods"] == [1, 3, 5]
        assert metadata["quantiles"] == 5
