"""Unit tests for backtest metrics and tearsheet payloads."""

from __future__ import annotations

import pandas as pd

from kronos.research.backtest import BacktestConfig
from kronos.research.backtest.metrics import build_metrics
from kronos.research.backtest.reporting import build_tearsheet


def _equity_curve() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [1, 2, 3],
        "equity": [1.0, 1.1, 1.21],
        "drawdown": [0.0, 0.0, 0.0],
        "period_return": [0.0, 0.1, 0.1],
    })


def _turnover() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [1, 2, 3],
        "turnover_rate": [0.0, 0.5, 0.25],
        "cost": [0.0, 0.001, 0.0005],
        "funding_cost": [0.0, 0.0, 0.0],
    })


def _positions() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [1, 1, 2, 2],
        "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "ETHUSDT"],
        "actual_weight": [1.0, -1.0, 1.0, -1.0],
        "side": ["long", "short", "long", "short"],
        "pnl_contribution": [0.0, 0.0, 0.1, 0.05],
    })


def _weights() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [1, 1, 2, 2],
        "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "ETHUSDT"],
        "target_weight": [1.0, -1.0, 1.0, -1.0],
        "actual_weight": [1.0, -1.0, 1.0, -1.0],
    })


def _trades() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [2, 2],
        "symbol": ["BTCUSDT", "ETHUSDT"],
        "event": ["open", "open"],
        "side": ["long", "short"],
        "pre_weight": [0.0, 0.0],
        "post_weight": [1.0, -1.0],
        "turnover_share": [1.0, 1.0],
        "estimated_cost": [0.001, 0.001],
        "holding_bars": [2, 2],
    })


class TestMetrics:
    def test_builds_metrics_payload(self) -> None:
        returns = pd.Series([0.0, 0.1, 0.1], index=[1, 2, 3], dtype=float)
        metrics = build_metrics(
            returns,
            _equity_curve(),
            _turnover(),
            _positions(),
            _trades(),
            _weights(),
            BacktestConfig(timeframe="1h", rebalance_frequency="1h"),
        )

        assert metrics.total_return > 0
        assert metrics.trade_count == 2
        assert metrics.turnover_mean > 0

    def test_builds_json_compatible_tearsheet(self) -> None:
        returns = pd.Series([0.0, 0.1, 0.1], index=[1, 2, 3], dtype=float)
        metrics = build_metrics(
            returns,
            _equity_curve(),
            _turnover(),
            _positions(),
            _trades(),
            _weights(),
            BacktestConfig(timeframe="1h", rebalance_frequency="1h"),
        )
        tearsheet = build_tearsheet(metrics, _equity_curve(), _turnover())
        assert "overview" in tearsheet
        assert "risk" in tearsheet
        assert "trading" in tearsheet
