"""Backtest metrics calculations."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd

from kronos.research.backtest.types import BacktestMetrics

if TYPE_CHECKING:
    from kronos.research.backtest.config import BacktestConfig


def build_metrics(
    period_returns: pd.Series,
    equity_curve: pd.DataFrame,
    turnover: pd.DataFrame,
    positions: pd.DataFrame,
    trades: pd.DataFrame,
    weights: pd.DataFrame,
    config: BacktestConfig,
) -> BacktestMetrics:
    returns = period_returns.fillna(0.0)
    periods_per_year = config.resolved_periods_per_year()
    total_return = float(equity_curve["equity"].iloc[-1] - 1.0) if not equity_curve.empty else 0.0
    annual_return = _annual_return(equity_curve["equity"], periods_per_year)
    annual_volatility = float(returns.std(ddof=0) * math.sqrt(periods_per_year)) if len(returns) else 0.0
    sharpe = _safe_ratio(float(returns.mean()) * math.sqrt(periods_per_year), returns.std(ddof=0))
    downside = returns[returns < 0]
    sortino = _safe_ratio(float(returns.mean()) * math.sqrt(periods_per_year), downside.std(ddof=0))
    max_drawdown = float(equity_curve["drawdown"].min()) if not equity_curve.empty else 0.0
    calmar = _safe_ratio(annual_return, abs(max_drawdown))
    drawdown_duration = _drawdown_duration(equity_curve["drawdown"]) if not equity_curve.empty else 0
    win_rate = float((returns > 0).mean()) if len(returns) else 0.0
    gross_profit = float(returns[returns > 0].sum())
    gross_loss = float(abs(returns[returns < 0].sum()))
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")
    trade_count = len(trades)
    avg_holding_bars = _avg_holding_bars(trades)
    turnover_mean = float(turnover["turnover_rate"].mean()) if not turnover.empty else 0.0
    annual_turnover = turnover_mean * periods_per_year
    active_counts = positions.groupby("timestamp")["actual_weight"].apply(lambda s: (s.abs() > 0).sum())
    average_active_positions = float(active_counts.mean()) if len(active_counts) else 0.0
    max_active_positions = int(active_counts.max()) if len(active_counts) else 0
    var_95 = float(returns.quantile(0.05)) if len(returns) else 0.0
    cvar_95 = float(returns[returns <= var_95].mean()) if len(returns) else 0.0
    worst_period = float(returns.min()) if len(returns) else 0.0
    worst_consecutive_window = _worst_consecutive_window(returns, config.worst_period_window)
    long_weights = weights["actual_weight"].clip(lower=0)
    short_weights = weights["actual_weight"].clip(upper=0)
    long_gross_exposure = float(long_weights.mean()) if len(long_weights) else 0.0
    short_gross_exposure = float(short_weights.abs().mean()) if len(short_weights) else 0.0
    long_period_returns = _side_contribution(weights, positions, "long")
    short_period_returns = _side_contribution(weights, positions, "short")
    long_net_contribution = float(long_period_returns.sum()) if len(long_period_returns) else 0.0
    short_net_contribution = float(short_period_returns.sum()) if len(short_period_returns) else 0.0
    long_hit_ratio = float((long_period_returns > 0).mean()) if len(long_period_returns) else 0.0
    short_hit_ratio = float((short_period_returns > 0).mean()) if len(short_period_returns) else 0.0
    long_short_ratio = long_gross_exposure / short_gross_exposure if short_gross_exposure else float("inf")

    return BacktestMetrics(
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_drawdown,
        drawdown_duration=drawdown_duration,
        total_return=total_return,
        annual_return=annual_return,
        annual_volatility=annual_volatility,
        win_rate=win_rate,
        profit_factor=profit_factor,
        trade_count=trade_count,
        avg_holding_bars=avg_holding_bars,
        turnover_mean=turnover_mean,
        annual_turnover=annual_turnover,
        average_active_positions=average_active_positions,
        max_active_positions=max_active_positions,
        var_95=var_95,
        cvar_95=cvar_95,
        worst_period=worst_period,
        worst_consecutive_window=worst_consecutive_window,
        long_gross_exposure=long_gross_exposure,
        short_gross_exposure=short_gross_exposure,
        long_net_contribution=long_net_contribution,
        short_net_contribution=short_net_contribution,
        long_hit_ratio=long_hit_ratio,
        short_hit_ratio=short_hit_ratio,
        long_short_ratio=long_short_ratio,
    )


def _annual_return(equity: pd.Series, periods_per_year: int) -> float:
    if equity.empty:
        return 0.0
    final = float(equity.iloc[-1])
    n_periods = max(len(equity) - 1, 1)
    if final <= 0:
        return -1.0
    exponent = periods_per_year / n_periods
    try:
        return float(math.exp(math.log(final) * exponent) - 1.0)
    except OverflowError:
        return float("inf")


def _safe_ratio(numerator: float, denominator: float | None) -> float:
    if denominator is None or denominator == 0 or math.isnan(denominator):
        return 0.0
    return float(numerator / denominator)


def _drawdown_duration(drawdown: pd.Series) -> int:
    current = 0
    longest = 0
    for value in drawdown:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _avg_holding_bars(trades: pd.DataFrame) -> float:
    if trades.empty or "holding_bars" not in trades.columns:
        return 0.0
    completed = trades[trades["holding_bars"].notna()]
    return float(completed["holding_bars"].mean()) if not completed.empty else 0.0


def _worst_consecutive_window(returns: pd.Series, window: int) -> float:
    if returns.empty:
        return 0.0
    rolling = returns.rolling(window, min_periods=1).sum()
    return float(rolling.min())


def _side_contribution(weights: pd.DataFrame, positions: pd.DataFrame, side: str) -> pd.Series:
    if positions.empty:
        return pd.Series(dtype=float)
    if side == "long":
        subset = positions[positions["actual_weight"] > 0]
    else:
        subset = positions[positions["actual_weight"] < 0]
    if subset.empty:
        return pd.Series(dtype=float)
    return subset.groupby("timestamp")["pnl_contribution"].sum().sort_index()
