"""Portfolio weight utilities."""

from __future__ import annotations

import pandas as pd


def weights_to_frame(timestamp: int, target: pd.Series, actual: pd.Series) -> pd.DataFrame:
    symbols = sorted(set(target.index).union(actual.index))
    return pd.DataFrame({
        "timestamp": [timestamp] * len(symbols),
        "symbol": symbols,
        "target_weight": [float(target.get(symbol, 0.0)) for symbol in symbols],
        "actual_weight": [float(actual.get(symbol, 0.0)) for symbol in symbols],
    })


def drift_weights(weights: pd.Series, asset_returns: pd.Series) -> pd.Series:
    if weights.empty:
        return weights
    aligned_returns = asset_returns.reindex(weights.index).fillna(0.0)
    gross_return = float((weights * aligned_returns).sum())
    denominator = 1.0 + gross_return
    if denominator <= 0:
        return weights * 0.0
    return (weights * (1.0 + aligned_returns)) / denominator
