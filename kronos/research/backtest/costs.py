"""Trading cost helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def compute_turnover(previous: pd.Series, target: pd.Series) -> float:
    symbols = sorted(set(previous.index).union(target.index))
    prev = previous.reindex(symbols).fillna(0.0)
    tgt = target.reindex(symbols).fillna(0.0)
    return float((tgt - prev).abs().sum())


def compute_cost(turnover: float, fee_bps: float, slippage_bps: float) -> float:
    return turnover * (fee_bps + slippage_bps) / 10000.0


def compute_funding_impact(weights: pd.Series, funding_rates: pd.Series | None) -> float:
    if funding_rates is None or funding_rates.empty or weights.empty:
        return 0.0
    aligned = funding_rates.reindex(weights.index).fillna(0.0)
    return float((weights * aligned).sum())
