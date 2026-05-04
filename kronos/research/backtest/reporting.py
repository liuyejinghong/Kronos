"""Backtest tearsheet payload generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from kronos.research.backtest.types import BacktestMetrics


def build_tearsheet(metrics: BacktestMetrics, equity_curve: pd.DataFrame, turnover: pd.DataFrame) -> dict[str, object]:
    monthly = {}
    if not equity_curve.empty:
        temp = equity_curve.copy()
        temp["month"] = pd.to_datetime(temp["timestamp"], unit="ms", utc=True).dt.strftime("%Y-%m")
        monthly = temp.groupby("month")["period_return"].sum().to_dict()

    return {
        "overview": {
            "total_return": metrics.total_return,
            "annual_return": metrics.annual_return,
            "sharpe": metrics.sharpe,
            "sortino": metrics.sortino,
            "calmar": metrics.calmar,
            "max_drawdown": metrics.max_drawdown,
        },
        "risk": {
            "annual_volatility": metrics.annual_volatility,
            "var_95": metrics.var_95,
            "cvar_95": metrics.cvar_95,
            "worst_period": metrics.worst_period,
            "worst_consecutive_window": metrics.worst_consecutive_window,
        },
        "holding": {
            "average_active_positions": metrics.average_active_positions,
            "max_active_positions": metrics.max_active_positions,
            "long_gross_exposure": metrics.long_gross_exposure,
            "short_gross_exposure": metrics.short_gross_exposure,
        },
        "trading": {
            "trade_count": metrics.trade_count,
            "turnover_mean": metrics.turnover_mean,
            "annual_turnover": metrics.annual_turnover,
            "estimated_total_cost": float(turnover["cost"].sum()) if not turnover.empty else 0.0,
        },
        "monthly_returns": monthly,
    }
