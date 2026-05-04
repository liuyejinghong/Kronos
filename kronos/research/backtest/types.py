"""Backtest result schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True)
class BacktestMetrics:
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    drawdown_duration: int
    total_return: float
    annual_return: float
    annual_volatility: float
    win_rate: float
    profit_factor: float
    trade_count: int
    avg_holding_bars: float
    turnover_mean: float
    annual_turnover: float
    average_active_positions: float
    max_active_positions: int
    var_95: float
    cvar_95: float
    worst_period: float
    worst_consecutive_window: float
    long_gross_exposure: float
    short_gross_exposure: float
    long_net_contribution: float
    short_net_contribution: float
    long_hit_ratio: float
    short_hit_ratio: float
    long_short_ratio: float


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    config_snapshot: dict[str, Any]
    git_commit: str
    data_snapshot_id: str
    equity_curve: pd.DataFrame
    period_returns: pd.Series
    gross_returns: pd.Series
    weights: pd.DataFrame
    target_weights: pd.DataFrame
    turnover: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    metrics: BacktestMetrics
    factor_scores: pd.DataFrame
    tearsheet: dict[str, Any]
    config_tearsheet: dict[str, Any]
    tearsheet_path: str | None = None


@dataclass(frozen=True)
class CrossValidationResult:
    status: str
    kronos_summary: dict[str, Any]
    freqtrade_summary: dict[str, Any]
    equity_diff_metrics: dict[str, float]
    thresholds: dict[str, Any]
    lookahead_check_status: str
    artifacts: dict[str, str]
    failure_reason: str | None = None
