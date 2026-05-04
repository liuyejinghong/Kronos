"""Return calculation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def compute_asset_returns(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Compute close-to-close asset returns indexed by destination timestamp."""
    returns = price_frame.sort_index().pct_change().fillna(0.0)
    return returns


def compute_portfolio_return(weights: pd.Series, asset_returns: pd.Series) -> float:
    if weights.empty:
        return 0.0
    aligned = asset_returns.reindex(weights.index).fillna(0.0)
    return float((weights * aligned).sum())
