"""Vectorised research backtest engine."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, cast

import pandas as pd

from kronos.common.errors import BacktestError
from kronos.research.backtest.costs import compute_cost, compute_funding_impact, compute_turnover
from kronos.research.backtest.metrics import build_metrics
from kronos.research.backtest.ranking import build_target_weights
from kronos.research.backtest.reporting import build_tearsheet
from kronos.research.backtest.returns import compute_asset_returns, compute_portfolio_return
from kronos.research.backtest.trades import record_rebalance_trades
from kronos.research.backtest.types import BacktestResult
from kronos.research.backtest.validators import validate_inputs
from kronos.research.backtest.weights import drift_weights, weights_to_frame

if TYPE_CHECKING:
    from kronos.research.backtest.config import BacktestConfig


class Engine:
    """Thin, vectorised research backtest engine."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def run(
        self,
        signals: pd.DataFrame,
        data: pd.DataFrame,
        *,
        run_id: str | None = None,
        git_commit: str = "unknown",
        data_snapshot_id: str = "unknown",
    ) -> BacktestResult:
        validate_inputs(signals, data, self.config)

        prepared_data = _prepare_market_data(data, self.config.universe)
        price_frame = prepared_data.pivot(index="event_time", columns="symbol", values="close").sort_index()
        funding_frame = (
            prepared_data.pivot(index="event_time", columns="symbol", values="funding_rate").sort_index()
            if "funding_rate" in prepared_data.columns
            else pd.DataFrame(index=price_frame.index, columns=price_frame.columns, dtype=float)
        )
        asset_returns = compute_asset_returns(price_frame)
        rebalance_targets = build_target_weights(_filter_rebalance_signals(signals, self.config), self.config)

        timestamps = list(price_frame.index)
        symbols = list(price_frame.columns)
        pending_targets = _schedule_targets(
            rebalance_targets, timestamps, symbols, self.config.execution_delay_bars,
        )

        active_weights = pd.Series(0.0, index=symbols, dtype=float)
        weights_rows: list[pd.DataFrame] = []
        positions_rows: list[dict[str, float | int | str]] = []
        trades_rows: list[pd.DataFrame] = []
        turnover_rows: list[dict[str, float | int]] = []
        gross_returns: list[float] = []
        net_returns: list[float] = []

        for _index, timestamp in enumerate(timestamps):
            asset_return = (
                asset_returns.loc[timestamp]
                if timestamp in asset_returns.index
                else pd.Series(0.0, index=symbols)
            )
            gross_return = compute_portfolio_return(active_weights, asset_return)
            drifted = drift_weights(active_weights, asset_return)

            target_weights = pending_targets.get(timestamp, drifted)
            turnover = compute_turnover(drifted, target_weights)
            cost = compute_cost(turnover, self.config.fee_bps, self.config.slippage_bps)
            funding_cost = 0.0
            if self.config.apply_funding and timestamp in funding_frame.index:
                funding_cost = compute_funding_impact(target_weights, funding_frame.loc[timestamp])

            net_return = gross_return - cost - funding_cost
            active_weights = target_weights

            weights_rows.append(weights_to_frame(int(timestamp), target_weights, active_weights))
            positions_rows.extend(_positions_snapshot(int(timestamp), active_weights, asset_return))
            if timestamp in pending_targets:
                trades_rows.append(
                    record_rebalance_trades(
                        int(timestamp),
                        drifted,
                        target_weights,
                        (self.config.fee_bps + self.config.slippage_bps) / 10000.0,
                    )
                )

            turnover_rows.append({
                "timestamp": int(timestamp),
                "turnover_rate": turnover,
                "cost": cost,
                "funding_cost": funding_cost,
            })
            gross_returns.append(gross_return)
            net_returns.append(net_return)

        period_returns = pd.Series(net_returns, index=timestamps, dtype=float, name="period_return")
        gross_return_series = pd.Series(gross_returns, index=timestamps, dtype=float, name="gross_return")
        equity_curve = _equity_curve(period_returns)
        weights_df = pd.concat(weights_rows, ignore_index=True) if weights_rows else pd.DataFrame()
        positions_df = pd.DataFrame(positions_rows)
        turnover_df = pd.DataFrame(turnover_rows)
        trades_df = pd.concat(trades_rows, ignore_index=True) if trades_rows else pd.DataFrame(
            columns=["timestamp", "symbol", "event", "side", "pre_weight", "post_weight", "turnover_share", "estimated_cost"]
        )
        metrics = build_metrics(period_returns, equity_curve, turnover_df, positions_df, trades_df, weights_df, self.config)
        target_weights_df = rebalance_targets.copy()
        factor_scores = signals.copy().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
        tearsheet = build_tearsheet(metrics, equity_curve, turnover_df)

        return BacktestResult(
            run_id=run_id or _run_id(signals, self.config),
            config_snapshot=self.config.model_dump(mode="json"),
            git_commit=git_commit,
            data_snapshot_id=data_snapshot_id,
            equity_curve=equity_curve,
            period_returns=period_returns,
            gross_returns=gross_return_series,
            weights=weights_df,
            target_weights=target_weights_df,
            turnover=turnover_df,
            positions=positions_df,
            trades=trades_df,
            metrics=metrics,
            factor_scores=factor_scores,
            tearsheet=tearsheet,
            config_tearsheet={"timeframe": self.config.timeframe, "mode": self.config.mode},
        )


def _prepare_market_data(data: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    prepared = data.copy()
    if universe:
        prepared = prepared[prepared["symbol"].isin(universe)]
    prepared = prepared.sort_values(["event_time", "symbol"]).reset_index(drop=True)
    if prepared.empty:
        raise BacktestError("market data is empty after applying universe filter")
    return prepared


def _filter_rebalance_signals(signals: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    freq_map = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
    interval = freq_map[config.rebalance_frequency]
    rebalance_bucket = signals["timestamp"] // interval
    filtered = signals.copy()
    filtered["rebalance_bucket"] = rebalance_bucket
    filtered = filtered.sort_values(["rebalance_bucket", "timestamp", "symbol"])
    filtered = filtered.groupby(["rebalance_bucket", "symbol"], as_index=False).tail(1)
    return filtered.drop(columns=["rebalance_bucket"]).reset_index(drop=True)


def _schedule_targets(
    targets: pd.DataFrame, timestamps: list[int], symbols: list[str], delay_bars: int = 1,
) -> dict[int, pd.Series]:
    scheduled: dict[int, pd.Series] = {}
    if targets.empty:
        return scheduled

    for timestamp, group in targets.groupby("timestamp", sort=True):
        timestamp_int = int(cast("int", timestamp))
        start_idx = next(
            (idx for idx, ts in enumerate(timestamps) if ts > timestamp_int), None,
        )
        if start_idx is None:
            continue
        next_index = start_idx + delay_bars - 1
        if next_index >= len(timestamps):
            continue
        effective_ts = timestamps[next_index]
        weights = pd.Series(0.0, index=symbols, dtype=float)
        for _, row in group.iterrows():
            weights[str(row["symbol"])] = float(row["target_weight"])
        scheduled[effective_ts] = weights
    return scheduled


def _equity_curve(period_returns: pd.Series) -> pd.DataFrame:
    equity = (1.0 + period_returns.fillna(0.0)).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return pd.DataFrame({
        "timestamp": equity.index.astype("int64"),
        "equity": equity.values,
        "drawdown": drawdown.values,
        "period_return": period_returns.values,
    })


def _positions_snapshot(timestamp: int, weights: pd.Series, asset_returns: pd.Series) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for symbol, weight in weights.items():
        rows.append({
            "timestamp": timestamp,
            "symbol": str(symbol),
            "actual_weight": float(weight),
            "side": "long" if weight > 0 else ("short" if weight < 0 else "flat"),
            "pnl_contribution": float(weight * asset_returns.get(symbol, 0.0)),
        })
    return rows


def _run_id(signals: pd.DataFrame, config: BacktestConfig) -> str:
    base = f"{int(signals['timestamp'].min())}-{int(signals['timestamp'].max())}-{config.mode}"
    suffix = hashlib.sha1(json.dumps(config.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:8]
    return f"{base}-{suffix}"
