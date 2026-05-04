"""Portfolio construction workflow helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kronos.portfolio.allocator import construct
from kronos.risk import RiskConfig, RiskVerdict, review_target_portfolio

if TYPE_CHECKING:
    import pandas as pd

    from kronos.common.types import Constraints


def construct_with_risk_review(
    scores: pd.DataFrame,
    current_positions: dict[str, float],
    constraints: Constraints,
    *,
    risk_config: RiskConfig,
    current_drawdown: float = 0.0,
    expected_funding_cost: float = 0.0,
    liquidity: dict[str, float] | None = None,
    factor_flags: dict[str, bool] | None = None,
    strategy_flags: dict[str, bool] | None = None,
) -> RiskVerdict:
    """Construct a target portfolio then immediately run risk review."""
    target = construct(scores, current_positions, constraints)
    return review_target_portfolio(
        target,
        constraints=constraints,
        config=risk_config,
        current_drawdown=current_drawdown,
        expected_funding_cost=expected_funding_cost,
        liquidity=liquidity,
        factor_flags=factor_flags,
        strategy_flags=strategy_flags,
    )
