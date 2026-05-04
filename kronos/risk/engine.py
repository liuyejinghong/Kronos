"""Rule-based risk engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kronos.common.types import Constraints, Level, TargetPortfolio
from kronos.notify.formatter import format_event

if TYPE_CHECKING:
    from kronos.common.types import Notifier


@dataclass(frozen=True)
class RiskConfig:
    """Minimal Phase 3 risk configuration."""

    max_leverage_hard_limit: float = 2.0
    single_asset_hard_cap: float = 0.5
    drawdown_reduce_threshold: float = -0.10
    drawdown_stop_threshold: float = -0.20
    drawdown_reduce_scale: float = 0.5
    funding_cost_budget: float = 0.01
    liquidity_floor: float = 100.0
    illiquid_scale: float = 0.5


@dataclass(frozen=True)
class RiskVerdict:
    """Structured risk review result."""

    status: str
    target_portfolio: TargetPortfolio
    reasons: list[str]
    metrics: dict[str, float]
    notification_level: str | None = None


def review_target_portfolio(
    target: TargetPortfolio,
    *,
    constraints: Constraints,
    config: RiskConfig,
    current_drawdown: float = 0.0,
    expected_funding_cost: float = 0.0,
    liquidity: dict[str, float] | None = None,
    factor_flags: dict[str, bool] | None = None,
    strategy_flags: dict[str, bool] | None = None,
) -> RiskVerdict:
    """Review and potentially scale or reject a target portfolio."""
    positions = dict(target.positions)
    reasons: list[str] = []
    metrics = {
        "gross_leverage": sum(abs(weight) for weight in positions.values()),
        "max_single_weight": max((abs(weight) for weight in positions.values()), default=0.0),
        "current_drawdown": current_drawdown,
        "expected_funding_cost": expected_funding_cost,
    }

    if factor_flags and any(flag is False for flag in factor_flags.values()):
        positions = {symbol: weight * 0.5 for symbol, weight in positions.items()}
        reasons.append("factor_level_degrade")

    if strategy_flags and any(flag is False for flag in strategy_flags.values()):
        positions = {symbol: weight * 0.5 for symbol, weight in positions.items()}
        reasons.append("strategy_level_degrade")

    positions, leverage_reason = _apply_hard_limits(positions, constraints, config)
    if leverage_reason:
        reasons.append(leverage_reason)

    positions, drawdown_reason, notification = _apply_drawdown_controls(positions, current_drawdown, config)
    if drawdown_reason:
        reasons.append(drawdown_reason)
        level = notification
    else:
        level = None

    positions, funding_reason = _apply_funding_budget(positions, expected_funding_cost, config)
    if funding_reason:
        reasons.append(funding_reason)

    positions, liquidity_reason = _apply_liquidity_scaling(positions, liquidity or {}, config)
    if liquidity_reason:
        reasons.append(liquidity_reason)

    status = "approved" if not reasons else ("rejected" if "drawdown_circuit_breaker" in reasons else "scaled")
    reviewed = TargetPortfolio(
        timestamp=target.timestamp,
        positions=positions,
        metadata={**target.metadata, "risk_reasons": reasons},
    )
    metrics["gross_leverage"] = sum(abs(weight) for weight in positions.values())
    metrics["max_single_weight"] = max((abs(weight) for weight in positions.values()), default=0.0)
    return RiskVerdict(
        status=status,
        target_portfolio=reviewed,
        reasons=reasons,
        metrics=metrics,
        notification_level=level,
    )


def emit_risk_notification(verdict: RiskVerdict, notifier: Notifier) -> None:
    """Send a structured notification for a meaningful risk verdict."""
    if verdict.notification_level is None:
        return
    level = Level(verdict.notification_level.lower())
    event = format_event(
        level=level,
        event_type="risk_verdict",
        title=f"Risk verdict: {verdict.status}",
        body=", ".join(verdict.reasons) if verdict.reasons else "risk review completed",
        data=verdict.metrics,
    )
    notifier.send(level, event["title"], event["body"], event["data"])


def _apply_hard_limits(
    positions: dict[str, float],
    constraints: Constraints,
    config: RiskConfig,
) -> tuple[dict[str, float], str | None]:
    adjusted = {
        symbol: max(-config.single_asset_hard_cap, min(config.single_asset_hard_cap, weight))
        for symbol, weight in positions.items()
    }
    gross = sum(abs(weight) for weight in adjusted.values())
    reason: str | None = None
    if gross > config.max_leverage_hard_limit and gross > 0:
        scale = config.max_leverage_hard_limit / gross
        adjusted = {symbol: weight * scale for symbol, weight in adjusted.items()}
        reason = "account_level_hard_limit"
    if any(abs(weight) > constraints.max_single_weight for weight in adjusted.values()):
        adjusted = {
            symbol: max(-constraints.max_single_weight, min(constraints.max_single_weight, weight))
            for symbol, weight in adjusted.items()
        }
        reason = (
            "account_level_hard_limit_and_position_cap"
            if reason else "portfolio_level_position_cap"
        )
    return adjusted, reason


def _apply_drawdown_controls(
    positions: dict[str, float],
    current_drawdown: float,
    config: RiskConfig,
) -> tuple[dict[str, float], str | None, str | None]:
    if current_drawdown <= config.drawdown_stop_threshold:
        return dict.fromkeys(positions, 0.0), "drawdown_circuit_breaker", "CRITICAL"
    if current_drawdown <= config.drawdown_reduce_threshold:
        return (
            {symbol: weight * config.drawdown_reduce_scale for symbol, weight in positions.items()},
            "drawdown_de_risk",
            "WARNING",
        )
    return positions, None, None


def _apply_funding_budget(
    positions: dict[str, float],
    expected_funding_cost: float,
    config: RiskConfig,
) -> tuple[dict[str, float], str | None]:
    if expected_funding_cost <= config.funding_cost_budget:
        return positions, None
    scale = config.funding_cost_budget / expected_funding_cost
    return {symbol: weight * scale for symbol, weight in positions.items()}, "funding_budget_scale"


def _apply_liquidity_scaling(
    positions: dict[str, float],
    liquidity: dict[str, float],
    config: RiskConfig,
) -> tuple[dict[str, float], str | None]:
    adjusted = dict(positions)
    changed = False
    for symbol, weight in adjusted.items():
        if liquidity.get(symbol, config.liquidity_floor) < config.liquidity_floor:
            adjusted[symbol] = weight * config.illiquid_scale
            changed = True
    return adjusted, "liquidity_scale" if changed else None
