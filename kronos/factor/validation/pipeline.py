"""Factor validation pipeline — orchestrates all validation metrics into a single run.

validate_factor() is the main entry point. It:
    1. Computes forward returns (PIT-safe)
    2. Computes IC / Rank IC across periods
    3. Computes grouped returns (quantile spread)
    4. Computes turnover proxy
    5. Computes decay profile
    6. Adjudicates: pass / review / fail
    7. Returns ValidationResult with all metrics

Factor status transitions live in thresholds.OUTCOME_TO_STATUS, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from kronos.factor.validation.metrics import (
    adjudicate,
    compute_decay_profile,
    compute_forward_returns,
    compute_grouped_returns,
    compute_ic,
    compute_turnover,
    summarise_ic,
)
from kronos.factor.validation.thresholds import ValidationConfig, ValidationOutcome


@dataclass
class ValidationResult:
    """Full output of a single validation run."""

    outcome: ValidationOutcome

    # IC metrics (per period)
    ic_table: pd.DataFrame  # columns: period, ic, rank_ic, n_obs

    # IC summary (single-period, for adjudication — uses periods[0] by default)
    mean_rank_ic: float
    rank_ic_positive_ratio: float  # placeholder — requires time-series IC; set NaN for single-run
    ic_ir: float

    # Grouped returns
    quantile_returns: pd.Series  # indexed by quantile
    top_minus_bottom: float

    # Turnover
    median_turnover: float
    top_turnover: float
    bottom_turnover: float

    # Decay profile
    decay: pd.DataFrame  # columns: period, mean_rank_ic, rank_ic_positive_ratio

    # Raw forward returns (for optional persistence/debug)
    forward_returns: pd.DataFrame

    # Misc
    n_obs: int = 0
    skipped_pct: float = 0.0
    config: ValidationConfig = field(default_factory=ValidationConfig)

    def to_dict(self) -> dict[str, Any]:
        """Serialise scalars + period IC table to a JSON-compatible dict."""
        ic_records = self.ic_table.to_dict(orient="records") if not self.ic_table.empty else []
        decay_records = self.decay.to_dict(orient="records") if not self.decay.empty else []
        qr: dict[str, float] = {}
        if not self.quantile_returns.empty:
            qr = {str(k): float(v) for k, v in self.quantile_returns.items()}
        return {
            "outcome": str(self.outcome),
            "mean_rank_ic": self.mean_rank_ic,
            "rank_ic_positive_ratio": self.rank_ic_positive_ratio,
            "ic_ir": self.ic_ir,
            "top_minus_bottom": self.top_minus_bottom,
            "median_turnover": self.median_turnover,
            "top_turnover": self.top_turnover,
            "bottom_turnover": self.bottom_turnover,
            "n_obs": self.n_obs,
            "skipped_pct": self.skipped_pct,
            "ic_table": ic_records,
            "decay": decay_records,
            "quantile_returns": qr,
        }


def validate_factor(
    factor_values: pd.Series,
    prices: pd.Series,
    available_at: pd.Series,
    *,
    config: ValidationConfig | None = None,
) -> ValidationResult:
    """Run the full factor validation pipeline.

    Args:
        factor_values: Factor signal series, same index as prices.
        prices: Close price series (PIT-safe), same index as factor_values.
        available_at: Epoch-ms timestamps when each bar became available.
        config: Validation configuration and thresholds (uses defaults if None).

    Returns:
        ValidationResult with all metrics and adjudication outcome.

    Note:
        forward_returns, factor_values, and prices must share the same integer
        positional index (0..n-1). NaN rows in factor_values are excluded per metric.
    """
    if config is None:
        config = ValidationConfig()

    # ------------------------------------------------------------------
    # 1. Forward returns
    # ------------------------------------------------------------------
    forward_returns = compute_forward_returns(prices, available_at, config.periods)

    # ------------------------------------------------------------------
    # 2. IC / Rank IC table (all periods)
    # ------------------------------------------------------------------
    ic_table = compute_ic(factor_values, forward_returns)

    # ------------------------------------------------------------------
    # 3. Summarise IC for the primary period (first in config.periods)
    # ------------------------------------------------------------------
    primary_period = config.periods[0]
    primary_col = f"fwd_{primary_period}"

    if not ic_table.empty and primary_period in ic_table["period"].values:
        primary_row = ic_table[ic_table["period"] == primary_period].iloc[0]
        mean_rank_ic = float(primary_row["rank_ic"])
        n_obs = int(primary_row["n_obs"])
    else:
        mean_rank_ic = float("nan")
        n_obs = 0

    # rank_ic_positive_ratio requires a time-series of cross-sectional IC.
    # For a single-symbol run there's no cross-section, so we keep NaN as a
    # "not applicable" sentinel and let adjudication skip that threshold.
    rank_ic_positive_ratio = float("nan")
    ic_ir = float("nan")

    # If we have the primary column in forward returns, build a pseudo-summary
    # using IC series over time if the factor_values index has a time dimension.
    # For the simple (single-symbol, flat index) case, we just use scalar IC.
    primary_fwd = forward_returns.get(primary_col, pd.Series(dtype=float))
    if not primary_fwd.empty:
        ic_summary = summarise_ic(pd.Series([mean_rank_ic]))
        ic_ir = ic_summary.get("ic_ir", float("nan"))

    # ------------------------------------------------------------------
    # 4. Grouped returns (primary period)
    # ------------------------------------------------------------------
    grouped = compute_grouped_returns(factor_values, primary_fwd, quantiles=config.quantiles)
    quantile_returns: pd.Series = grouped["quantile_returns"]  # type: ignore[assignment]
    top_minus_bottom: float = grouped["top_minus_bottom"]  # type: ignore[assignment]
    raw_n_obs = grouped.get("n_obs", 0)
    n_obs = n_obs or (int(raw_n_obs) if isinstance(raw_n_obs, (int, float)) else 0)
    skipped_pct: float = grouped["skipped_pct"]  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # 5. Turnover
    # ------------------------------------------------------------------
    turnover = compute_turnover(factor_values, quantiles=config.quantiles)
    median_turnover: float = turnover["median_turnover"]
    top_turnover: float = turnover["top_turnover"]
    bottom_turnover: float = turnover["bottom_turnover"]

    # ------------------------------------------------------------------
    # 6. Decay profile
    # ------------------------------------------------------------------
    decay = compute_decay_profile(factor_values, forward_returns)

    # ------------------------------------------------------------------
    # 7. Adjudicate
    # ------------------------------------------------------------------
    adj_turnover = median_turnover if not _is_nan(median_turnover) else float("inf")

    verdict_str = adjudicate(
        mean_rank_ic=mean_rank_ic if not _is_nan(mean_rank_ic) else 0.0,
        rank_ic_positive_ratio=rank_ic_positive_ratio,
        top_minus_bottom=top_minus_bottom if not _is_nan(top_minus_bottom) else 0.0,
        median_turnover=adj_turnover,
        config=config,
    )
    outcome = ValidationOutcome(verdict_str)

    return ValidationResult(
        outcome=outcome,
        ic_table=ic_table,
        mean_rank_ic=mean_rank_ic,
        rank_ic_positive_ratio=rank_ic_positive_ratio,
        ic_ir=ic_ir,
        quantile_returns=quantile_returns,
        top_minus_bottom=top_minus_bottom,
        median_turnover=median_turnover,
        top_turnover=top_turnover,
        bottom_turnover=bottom_turnover,
        decay=decay,
        forward_returns=forward_returns,
        n_obs=n_obs,
        skipped_pct=skipped_pct,
        config=config,
    )


def _is_nan(x: float) -> bool:
    """Safe NaN check for floats."""
    import math

    return math.isnan(x)
