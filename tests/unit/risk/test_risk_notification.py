"""Unit tests for risk notifications and portfolio-risk workflow."""

from __future__ import annotations

import pandas as pd

from kronos.common.types import Constraints, TargetPortfolio
from kronos.notify import MemoryNotifier
from kronos.portfolio import construct_with_risk_review
from kronos.risk import RiskConfig, emit_risk_notification, review_target_portfolio


def _target() -> TargetPortfolio:
    return TargetPortfolio(timestamp=1, positions={"BTCUSDT": 0.8, "ETHUSDT": -0.7}, metadata={})


def _scores() -> pd.DataFrame:
    return pd.DataFrame({
        "event_time": [1, 1],
        "symbol": ["BTCUSDT", "ETHUSDT"],
        "factor_name": ["mom", "mom"],
        "score": [0.8, -0.7],
    })


class TestRiskNotification:
    def test_emit_risk_notification_sends_warning(self) -> None:
        verdict = review_target_portfolio(
            _target(),
            constraints=Constraints(),
            config=RiskConfig(drawdown_reduce_threshold=-0.1),
            current_drawdown=-0.15,
        )
        notifier = MemoryNotifier()
        emit_risk_notification(verdict, notifier)
        assert notifier.sent[0]["level"] == "warning"

    def test_construct_with_risk_review_returns_verdict(self) -> None:
        verdict = construct_with_risk_review(
            _scores(),
            current_positions={},
            constraints=Constraints(),
            risk_config=RiskConfig(),
            expected_funding_cost=0.02,
        )
        assert verdict.status in {"approved", "scaled", "rejected"}
