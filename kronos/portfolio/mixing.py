"""Strategy-level score mixing helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def mix_scores(scores: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Combine multi-strategy score rows into a single per-symbol score view."""
    frame = scores.copy()
    score_column = "score" if "score" in frame.columns else "value"
    frame = frame.dropna(subset=[score_column, "symbol", "event_time"])
    if frame.empty:
        return frame, {"strategy_weights": {}, "sources": []}

    strategy_weights: dict[str, float] = {}
    if "strategy_id" in frame.columns:
        strategies = sorted(frame["strategy_id"].dropna().astype(str).unique())
        if strategies:
            weight = 1.0 / len(strategies)
            strategy_weights = dict.fromkeys(strategies, weight)
            frame["_strategy_weight"] = frame["strategy_id"].astype(str).map(strategy_weights).fillna(weight)
            frame["_weighted_score"] = frame[score_column] * frame["_strategy_weight"]
            grouped = _aggregate_score_frame(frame, "_weighted_score")
        else:
            grouped = _aggregate_score_frame(frame, score_column)
    else:
        grouped = _aggregate_score_frame(frame, score_column)

    metadata = {
        "strategy_weights": strategy_weights,
        "sources": sorted(frame["factor_name"].dropna().astype(str).unique()) if "factor_name" in frame.columns else [],
    }
    return grouped.sort_values(["event_time", "symbol"]).reset_index(drop=True), metadata


def _aggregate_score_frame(frame: pd.DataFrame, score_column: str) -> pd.DataFrame:
    aggregations: dict[str, tuple[str, str]] = {"score": (score_column, "mean")}
    if "asset_volatility" in frame.columns:
        aggregations["asset_volatility"] = ("asset_volatility", "mean")
    if "volatility" in frame.columns:
        aggregations["volatility"] = ("volatility", "mean")
    return frame.groupby(["event_time", "symbol"], as_index=False).agg(**aggregations)
