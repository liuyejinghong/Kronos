# ruff: noqa: RUF001
"""Backtest tearsheet and replay report generation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Mapping

    from kronos.research.backtest.types import BacktestMetrics, BacktestResult


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


def build_replay_report(result: BacktestResult, *, max_trades: int = 8) -> list[str]:
    """Build a product-facing replay report from one backtest result."""
    metrics = result.metrics
    replay_trades = _key_trades(result, max_trades=max_trades)
    symbols = _result_symbols(result)

    lines = [
        f"# 关键交易重放：{result.run_id}",
        "",
        "## 一句话结论",
        "",
        "- 本报告只解释关键交易过程，不构成收益证明或实盘建议。",
        f"- 涉及币种：{', '.join(symbols) if symbols else '未记录'}",
        f"- 交易数：{metrics.trade_count}",
        f"- 总收益：{metrics.total_return:+.2%}",
        f"- 最大回撤：{metrics.max_drawdown:+.2%}",
        "",
        "## 结果概览",
        "",
        f"- Sharpe：{metrics.sharpe:.2f}",
        f"- Sortino：{metrics.sortino:.2f}",
        f"- Calmar：{metrics.calmar:.2f}",
        f"- 年化收益：{metrics.annual_return:+.2%}",
        f"- 年化波动：{metrics.annual_volatility:+.2%}",
        f"- 胜率：{metrics.win_rate:+.2%}",
        f"- 换手均值：{metrics.turnover_mean:.4f}",
        "",
        "## 关键交易重放",
        "",
    ]
    if replay_trades.empty:
        lines.append("- 当前没有可展示的关键交易。")
    else:
        lines.extend([
            "| 时间 | 币种 | 事件 | 方向 | 前权重 | 后权重 | 换手 | 估算成本 | 权益 | 回撤 | 信号 | 解释 |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ])
        for row in replay_trades.to_dict(orient="records"):
            lines.append(
                "| "
                f"{_format_timestamp(row['timestamp'])} | "
                f"{row.get('symbol', '-') } | "
                f"{_event_label(str(row.get('event', '-')))} | "
                f"{_direction_label(str(row.get('side', '-')))} | "
                f"{_format_number(row.get('pre_weight'))} | "
                f"{_format_number(row.get('post_weight'))} | "
                f"{_format_number(row.get('turnover_share'))} | "
                f"{_format_number(row.get('estimated_cost'))} | "
                f"{_format_number(row.get('equity'))} | "
                f"{_format_percent(row.get('drawdown'))} | "
                f"{_format_signal(row.get('signal_value'))} | "
                f"{_replay_explanation(row)} |"
            )

    lines.extend([
        "",
        "## 只读观察边界",
        "",
        "- 本报告只解释研究回放，不会自动下单。",
        "- 回放里的成本和滑点只是估算，不代表真实成交。",
        "- 进入更强执行层前仍然需要人工确认。",
    ])
    return lines


def write_replay_report(result: BacktestResult, path: str | Path, *, max_trades: int = 8) -> None:
    """Persist the replay report as Markdown."""
    report_path = Path(path)
    report_path.write_text("\n".join(build_replay_report(result, max_trades=max_trades)) + "\n", encoding="utf-8")


def _key_trades(result: BacktestResult, *, max_trades: int) -> pd.DataFrame:
    trades = result.trades.copy()
    if trades.empty:
        return trades

    frame = trades.copy()
    if "signal" in result.factor_scores.columns:
        signals = result.factor_scores[["timestamp", "symbol", "signal"]].rename(columns={"signal": "signal_value"})
        frame = frame.merge(signals, on=["timestamp", "symbol"], how="left")
    elif "value" in result.factor_scores.columns:
        signals = result.factor_scores[["timestamp", "symbol", "value"]].rename(columns={"value": "signal_value"})
        frame = frame.merge(signals, on=["timestamp", "symbol"], how="left")

    equity = result.equity_curve[["timestamp", "equity", "drawdown"]].drop_duplicates("timestamp")
    frame = frame.merge(equity, on="timestamp", how="left")

    sort_columns = [column for column in ("estimated_cost", "turnover_share", "timestamp") if column in frame.columns]
    ascending = [False, False, True][: len(sort_columns)]
    if sort_columns:
        frame = frame.sort_values(sort_columns, ascending=ascending)
    return frame.head(max_trades).reset_index(drop=True)


def _result_symbols(result: BacktestResult) -> list[str]:
    if "symbol" not in result.trades.columns:
        return []
    symbols = [str(symbol) for symbol in result.trades["symbol"].dropna().unique()]
    return sorted(symbols)


def _format_timestamp(value: object) -> str:
    if isinstance(value, (int, float, np.integer, np.floating)):
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
    return "-"


def _format_number(value: object) -> str:
    if isinstance(value, (int, float, np.integer, np.floating)) and pd.notna(value):
        return f"{float(value):.4f}"
    return "-"


def _format_percent(value: object) -> str:
    if isinstance(value, (int, float, np.integer, np.floating)) and pd.notna(value):
        return f"{float(value):+.2%}"
    return "-"


def _format_signal(value: object) -> str:
    if isinstance(value, (int, float, np.integer, np.floating)) and pd.notna(value):
        return f"{float(value):+.4f}"
    return "-"


def _event_label(value: str) -> str:
    return {
        "open": "开仓",
        "close": "平仓",
        "rebalance": "调仓",
    }.get(value, value or "-")


def _direction_label(value: str) -> str:
    return {
        "long": "做多",
        "short": "做空",
        "flat": "空仓",
    }.get(value, value or "-")


def _replay_explanation(row: Mapping[Any, Any]) -> str:
    event = str(row.get("event") or "-")
    side = str(row.get("side") or "-")
    signal_value = row.get("signal_value")
    pieces = [_event_label(event), _direction_label(side)]
    if isinstance(signal_value, (int, float, np.integer, np.floating)) and pd.notna(signal_value):
        if float(signal_value) > 0:
            pieces.append("偏多信号")
        elif float(signal_value) < 0:
            pieces.append("偏空信号")
        else:
            pieces.append("中性信号")
    return " / ".join(piece for piece in pieces if piece and piece != "-")
