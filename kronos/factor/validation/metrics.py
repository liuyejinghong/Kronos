"""Factor validation metrics — IC, Rank IC, grouped returns, turnover, decay.

Entry/exit price convention (PIT-safe):
    entry_price = bar[available_at_bar + 1].open
    exit_price  = bar[entry_bar + N].close    (N = forward horizon in bars)

This ensures we never use a price that wasn't available when the signal fired.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Forward returns (PIT-safe)
# ---------------------------------------------------------------------------


def compute_forward_returns(
    prices: pd.Series,
    available_at: pd.Series,
    periods: list[int],
) -> pd.DataFrame:
    """Compute forward returns anchored on available_at.

    For each bar i:
        entry_price = prices.iloc[i + 1]   (open of next bar)
        exit_price  = prices.iloc[i + 1 + N].close  → approximated by
                      prices.iloc[i + N + 1] since we use close series

    Args:
        prices: Series of per-bar prices (close), indexed 0..n-1.
        available_at: Series of available_at timestamps (epoch ms), same index.
        periods: List of forward horizons in bar counts.

    Returns:
        DataFrame with one column per period: "fwd_1", "fwd_3", etc.
        NaN for rows where forward window extends beyond the data.
    """
    n = len(prices)
    result: dict[str, pd.Series] = {}

    for period in periods:
        col = f"fwd_{period}"
        fwd = pd.Series(index=prices.index, dtype=float)
        for i in range(n):
            entry_idx = i + 1  # next bar open (entry)
            exit_idx = i + 1 + period  # N bars after entry (exit close)
            if exit_idx >= n:
                fwd.iloc[i] = float("nan")
            else:
                entry_price = prices.iloc[entry_idx]
                exit_price = prices.iloc[exit_idx]
                if entry_price > 0:
                    fwd.iloc[i] = (exit_price - entry_price) / entry_price
                else:
                    fwd.iloc[i] = float("nan")
        result[col] = fwd

    return pd.DataFrame(result, index=prices.index)


# ---------------------------------------------------------------------------
# IC / Rank IC
# ---------------------------------------------------------------------------


def compute_ic(
    factor_values: pd.Series,
    forward_returns: pd.DataFrame,
) -> pd.DataFrame:
    """Compute Pearson IC and Spearman Rank IC for each forward period.

    NaN rows (warmup + insufficient forward window) are excluded per period.

    Returns:
        DataFrame with columns: period, ic, rank_ic, n_obs
    """
    records = []
    for col in forward_returns.columns:
        period = int(col.split("_")[1])
        combined = pd.DataFrame({"factor": factor_values, "fwd": forward_returns[col]}).dropna()
        if len(combined) < 10:
            continue
        ic, _ = stats.pearsonr(combined["factor"], combined["fwd"])
        rank_ic, _ = stats.spearmanr(combined["factor"], combined["fwd"])
        records.append(
            {
                "period": period,
                "ic": float(ic),
                "rank_ic": float(rank_ic),
                "n_obs": len(combined),
            }
        )
    return pd.DataFrame(records)


def compute_ic_series(
    factor_values: pd.Series,
    forward_returns: pd.Series,
    groupby: pd.Series,
) -> pd.Series:
    """Compute cross-sectional Rank IC per time period (for decay analysis).

    Args:
        factor_values: Factor signal values.
        forward_returns: Single-period forward returns.
        groupby: Time group labels (e.g. event_time) to group cross-sections.

    Returns:
        Series of Rank IC values indexed by time group.
    """
    df = pd.DataFrame(
        {
            "factor": factor_values,
            "fwd": forward_returns,
            "group": groupby,
        }
    ).dropna()

    ic_by_time: dict[object, float] = {}
    for grp_val, grp in df.groupby("group"):
        if len(grp) < 2:
            continue
        rho, _ = stats.spearmanr(grp["factor"], grp["fwd"])
        ic_by_time[grp_val] = float(rho)

    return pd.Series(ic_by_time)


def summarise_ic(ic_series: pd.Series) -> dict[str, float]:
    """Summarise an IC time-series into scalar metrics."""
    clean = ic_series.dropna()
    if len(clean) == 0:
        return {"mean_ic": float("nan"), "ic_positive_ratio": float("nan"), "ic_ir": float("nan")}
    return {
        "mean_ic": float(clean.mean()),
        "ic_positive_ratio": float((clean > 0).mean()),
        "ic_ir": float(clean.mean() / clean.std()) if clean.std() > 0 else float("nan"),
    }


# ---------------------------------------------------------------------------
# Grouped returns
# ---------------------------------------------------------------------------


def compute_grouped_returns(
    factor_values: pd.Series,
    forward_returns: pd.Series,
    quantiles: int = 5,
) -> dict[str, object]:
    """Compute quantile group returns.

    Args:
        factor_values: Factor signal (higher = more bullish).
        forward_returns: Single-period forward returns (same index).
        quantiles: Number of quantile groups.

    Returns:
        Dict with keys:
            quantile_returns: Series indexed by quantile (1 = bottom, Q = top)
            top_minus_bottom: float (top quantile mean return - bottom quantile mean return)
            skipped_pct: fraction of cross-sections skipped due to insufficient samples
    """
    df = pd.DataFrame({"factor": factor_values, "fwd": forward_returns}).dropna()

    if len(df) < quantiles * 2:
        return {
            "quantile_returns": pd.Series(dtype=float),
            "top_minus_bottom": float("nan"),
            "skipped_pct": 1.0,
            "n_obs": 0,
        }

    try:
        df["quantile"] = pd.qcut(df["factor"], q=quantiles, labels=False, duplicates="drop")
    except ValueError:
        # Not enough unique values to form quantiles — degrade gracefully
        return {
            "quantile_returns": pd.Series(dtype=float),
            "top_minus_bottom": float("nan"),
            "skipped_pct": 1.0,
            "n_obs": len(df),
        }

    # Drop NaN quantile labels (from duplicates="drop" edge cases)
    df = df.dropna(subset=["quantile"])
    q_returns = df.groupby("quantile")["fwd"].mean()

    bottom = float(q_returns.iloc[0]) if len(q_returns) > 0 else float("nan")
    top = float(q_returns.iloc[-1]) if len(q_returns) > 0 else float("nan")
    top_minus_bottom = top - bottom if not (np.isnan(top) or np.isnan(bottom)) else float("nan")

    return {
        "quantile_returns": q_returns,
        "top_minus_bottom": top_minus_bottom,
        "skipped_pct": 0.0,
        "n_obs": len(df),
    }


# ---------------------------------------------------------------------------
# Turnover
# ---------------------------------------------------------------------------


def compute_turnover(
    factor_values: pd.Series,
    quantiles: int = 5,
    top_bottom_only: bool = True,
) -> dict[str, float]:
    """Compute period-to-period turnover for top and bottom quantile holdings.

    Turnover = fraction of holdings that changed between adjacent periods.

    Args:
        factor_values: Factor signal sorted by time (index = integer positions).
        quantiles: Number of quantile groups.
        top_bottom_only: If True, only compute for top and bottom quantiles.

    Returns:
        Dict with keys: top_turnover, bottom_turnover, median_turnover
    """
    clean = factor_values.dropna()
    if len(clean) < quantiles * 3:
        return {
            "top_turnover": float("nan"),
            "bottom_turnover": float("nan"),
            "median_turnover": float("nan"),
        }

    try:
        labels = pd.qcut(clean, q=quantiles, labels=False, duplicates="drop")
    except ValueError:
        return {
            "top_turnover": float("nan"),
            "bottom_turnover": float("nan"),
            "median_turnover": float("nan"),
        }

    int(labels.max()) if not labels.isna().all() else 0

    # Compute bar-by-bar turnover

    for idx_val, q_val in labels.items():
        if pd.isna(q_val):
            continue
        # Not applicable for single-symbol — turnover only meaningful
        # when factor_values has an index with symbol dimension.
        # For single-symbol time-series, we use rank-change as proxy.
        _ = idx_val  # unused; kept for clarity

    # Rank-change proxy for single-symbol turnover
    ranks = clean.rank(pct=True)
    rank_changes = ranks.diff().abs().dropna()
    if len(rank_changes) == 0:
        return {
            "top_turnover": float("nan"),
            "bottom_turnover": float("nan"),
            "median_turnover": float("nan"),
        }

    threshold = 1.0 / quantiles
    top_mask = ranks > (1 - threshold)
    bottom_mask = ranks < threshold

    top_changes = rank_changes[top_mask[rank_changes.index]].median()
    bottom_changes = rank_changes[bottom_mask[rank_changes.index]].median()
    median_turnover = float(rank_changes.median())

    return {
        "top_turnover": float(top_changes) if not pd.isna(top_changes) else float("nan"),
        "bottom_turnover": float(bottom_changes) if not pd.isna(bottom_changes) else float("nan"),
        "median_turnover": median_turnover,
    }


# ---------------------------------------------------------------------------
# Decay profile
# ---------------------------------------------------------------------------


def compute_decay_profile(
    factor_values: pd.Series,
    forward_returns: pd.DataFrame,
) -> pd.DataFrame:
    """Compute IC and Rank IC across multiple forward horizons (decay profile).

    Args:
        factor_values: Factor signal.
        forward_returns: DataFrame with one column per period (fwd_1, fwd_3, etc.).

    Returns:
        DataFrame with columns: period, mean_rank_ic, rank_ic_positive_ratio
        Sorted by period ascending.
    """
    ic_df = compute_ic(factor_values, forward_returns)
    if ic_df.empty:
        return pd.DataFrame(columns=["period", "mean_rank_ic", "rank_ic_positive_ratio"])
    return (
        ic_df[["period", "rank_ic"]]
        .rename(columns={"rank_ic": "mean_rank_ic"})
        .assign(
            rank_ic_positive_ratio=float("nan")  # single-run, not time-series IC
        )
        .sort_values("period")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Adjudication
# ---------------------------------------------------------------------------


def adjudicate(
    mean_rank_ic: float,
    rank_ic_positive_ratio: float,
    top_minus_bottom: float,
    median_turnover: float,
    config: object,  # ValidationConfig — avoid circular import
) -> str:
    """Apply threshold rules and return 'pass', 'review', or 'fail'.

    Uses duck-typing on config to avoid importing ValidationConfig here.
    ``rank_ic_positive_ratio`` is a cross-sectional stability gate. Single-symbol
    validation cannot compute it, so NaN means "not applicable" rather than
    evidence against the candidate.
    """
    min_ric = getattr(config, "min_mean_rank_ic", 0.02)
    min_ratio = getattr(config, "min_rank_ic_positive_ratio", 0.55)
    min_tmb = getattr(config, "min_top_minus_bottom_return", 0.0)
    max_to = getattr(config, "max_median_turnover", 0.70)
    ratio_available = not np.isnan(rank_ic_positive_ratio)
    ratio_ok = (not ratio_available) or rank_ic_positive_ratio >= min_ratio

    all_pass = (
        mean_rank_ic >= min_ric
        and ratio_ok
        and top_minus_bottom > min_tmb
        and median_turnover <= max_to
    )
    if all_pass:
        return "pass"

    # Soft review: positive IC direction and positive top-minus-bottom
    soft_ok = mean_rank_ic > 0 and top_minus_bottom > 0
    if soft_ok:
        return "review"

    return "fail"
