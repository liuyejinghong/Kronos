"""Unit tests for the risk engine."""

from __future__ import annotations

from kronos.common.types import Constraints, TargetPortfolio
from kronos.risk import RiskConfig, review_target_portfolio


def _target() -> TargetPortfolio:
    return TargetPortfolio(
        timestamp=1,
        positions={"BTCUSDT": 0.8, "ETHUSDT": -0.7, "SOLUSDT": 0.3},
        metadata={"sources": ["mom"]},
    )


class TestRiskEngine:
    def test_hard_limits_scale_excess_leverage(self) -> None:
        verdict = review_target_portfolio(
            _target(),
            constraints=Constraints(max_leverage=1.0, max_single_weight=0.4),
            config=RiskConfig(max_leverage_hard_limit=1.0, single_asset_hard_cap=0.4),
        )
        assert verdict.status == "scaled"
        assert verdict.metrics["gross_leverage"] <= 1.0 + 1e-9

    def test_drawdown_circuit_breaker_rejects_portfolio(self) -> None:
        verdict = review_target_portfolio(
            _target(),
            constraints=Constraints(),
            config=RiskConfig(drawdown_stop_threshold=-0.2),
            current_drawdown=-0.25,
        )
        assert verdict.status == "rejected"
        assert all(weight == 0.0 for weight in verdict.target_portfolio.positions.values())
        assert verdict.notification_level == "CRITICAL"

    def test_funding_budget_scales_positions(self) -> None:
        verdict = review_target_portfolio(
            _target(),
            constraints=Constraints(),
            config=RiskConfig(funding_cost_budget=0.01),
            expected_funding_cost=0.02,
        )
        assert verdict.status == "scaled"
        assert "funding_budget_scale" in verdict.reasons

    def test_low_liquidity_scales_specific_assets(self) -> None:
        baseline = review_target_portfolio(
            _target(),
            constraints=Constraints(),
            config=RiskConfig(liquidity_floor=100.0, illiquid_scale=1.0),
            liquidity={"BTCUSDT": 200.0, "ETHUSDT": 200.0, "SOLUSDT": 200.0},
        )
        verdict = review_target_portfolio(
            _target(),
            constraints=Constraints(),
            config=RiskConfig(liquidity_floor=100.0, illiquid_scale=0.25),
            liquidity={"BTCUSDT": 50.0, "ETHUSDT": 200.0, "SOLUSDT": 80.0},
        )
        assert verdict.target_portfolio.positions["BTCUSDT"] < baseline.target_portfolio.positions["BTCUSDT"]
        assert verdict.target_portfolio.positions["ETHUSDT"] == baseline.target_portfolio.positions["ETHUSDT"]
        assert "liquidity_scale" in verdict.reasons
