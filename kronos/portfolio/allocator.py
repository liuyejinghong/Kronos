"""Rule-based portfolio construction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from kronos.common.types import Constraints, TargetPortfolio
from kronos.portfolio.mixing import mix_scores

if TYPE_CHECKING:
    import pandas as pd


def construct(
    scores: pd.DataFrame,
    current_positions: dict[str, float],
    constraints: Constraints,
) -> TargetPortfolio:
    """Construct a constrained target portfolio from Layer 2 scores."""
    mixed_scores, mixing_metadata = mix_scores(scores)
    if mixed_scores.empty:
        timestamp = int(scores["event_time"].max()) if "event_time" in scores.columns and not scores.empty else 0
        return TargetPortfolio(timestamp=timestamp, positions=current_positions.copy(), metadata={"reason": "no_scores"})

    latest_timestamp = int(mixed_scores["event_time"].max())
    latest = mixed_scores[mixed_scores["event_time"] == latest_timestamp].copy()
    latest = latest.dropna(subset=["score"])
    if latest.empty:
        return TargetPortfolio(timestamp=latest_timestamp, positions=current_positions.copy(), metadata={"reason": "no_latest_scores"})

    weights = _build_rule_based_weights(latest, constraints)
    positions = _apply_constraints(weights, latest, constraints)
    metadata: dict[str, Any] = {
        "sources": mixing_metadata["sources"],
        "strategy_weights": mixing_metadata["strategy_weights"],
        "constraint_version": "v1",
        "current_positions": current_positions,
        "rebalance_decision": "rule_based",
        "max_leverage": constraints.max_leverage,
        "max_long_exposure": constraints.max_long_exposure,
        "max_short_exposure": constraints.max_short_exposure,
        "target_volatility": constraints.target_volatility,
        "rebalance_frequency_ms": scores.attrs.get("rebalance_frequency_ms"),
        "decay_hint": scores.attrs.get("decay_hint"),
    }
    return TargetPortfolio(timestamp=latest_timestamp, positions=positions, metadata=metadata)


def _build_rule_based_weights(latest_scores: pd.DataFrame, constraints: Constraints) -> dict[str, float]:
    ranked = latest_scores.sort_values("score", ascending=False).reset_index(drop=True)
    positive = ranked[ranked["score"] > 0]
    negative = ranked[ranked["score"] < 0]

    positions: dict[str, float] = {}
    if not positive.empty:
        long_weight = 1.0 / len(positive)
        for _, row in positive.iterrows():
            positions[str(row["symbol"])] = long_weight
    if not negative.empty:
        short_weight = -1.0 / len(negative)
        for _, row in negative.iterrows():
            positions[str(row["symbol"])] = short_weight

    if not positions:
        return {}
    return positions


def _apply_constraints(
    weights: dict[str, float],
    latest_scores: pd.DataFrame,
    constraints: Constraints,
) -> dict[str, float]:
    volatility_scaled = _apply_volatility_target(weights, latest_scores, constraints)
    capped = {
        symbol: max(-constraints.max_single_weight, min(constraints.max_single_weight, weight))
        for symbol, weight in volatility_scaled.items()
    }
    capped = _apply_exposure_caps(capped, constraints)
    gross = sum(abs(weight) for weight in capped.values())
    if gross > constraints.max_leverage and gross > 0:
        scale = constraints.max_leverage / gross
        capped = {symbol: weight * scale for symbol, weight in capped.items()}
    return capped


def _apply_volatility_target(
    weights: dict[str, float],
    latest_scores: pd.DataFrame,
    constraints: Constraints,
) -> dict[str, float]:
    if constraints.target_volatility is None:
        return weights
    vol_column = "asset_volatility" if "asset_volatility" in latest_scores.columns else "volatility"
    if vol_column not in latest_scores.columns:
        return weights

    latest = latest_scores.set_index("symbol")
    adjusted: dict[str, float] = {}
    for symbol, weight in weights.items():
        volatility = (
            float(cast("float", latest.loc[symbol, vol_column]))
            if symbol in latest.index
            else 1.0
        )
        adjusted[symbol] = weight / max(volatility, 1e-12)

    return _renormalize_books(adjusted)


def _apply_exposure_caps(weights: dict[str, float], constraints: Constraints) -> dict[str, float]:
    long_book = {symbol: weight for symbol, weight in weights.items() if weight > 0}
    short_book = {symbol: weight for symbol, weight in weights.items() if weight < 0}

    long_sum = sum(long_book.values())
    short_sum = abs(sum(short_book.values()))

    if long_sum > constraints.max_long_exposure and long_sum > 0:
        scale = constraints.max_long_exposure / long_sum
        long_book = {symbol: weight * scale for symbol, weight in long_book.items()}
    if short_sum > constraints.max_short_exposure and short_sum > 0:
        scale = constraints.max_short_exposure / short_sum
        short_book = {symbol: weight * scale for symbol, weight in short_book.items()}

    return {**long_book, **short_book}


def _renormalize_books(weights: dict[str, float]) -> dict[str, float]:
    long_book = {symbol: weight for symbol, weight in weights.items() if weight > 0}
    short_book = {symbol: weight for symbol, weight in weights.items() if weight < 0}

    long_sum = sum(long_book.values())
    short_sum = abs(sum(short_book.values()))

    if long_sum > 0:
        long_book = {symbol: weight / long_sum for symbol, weight in long_book.items()}
    if short_sum > 0:
        short_book = {symbol: weight / short_sum for symbol, weight in short_book.items()}

    return {**long_book, **short_book}
