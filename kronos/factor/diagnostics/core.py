"""Core signal diagnostics computations."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class SignalDiagnosticsResult:
    """Structured diagnostics output for a signal or factor bundle."""

    ic_timeseries: pd.DataFrame
    grouped_returns: dict[str, dict[str, object]]
    turnover: dict[str, float]
    decay: pd.DataFrame
    correlation_matrix: pd.DataFrame
    funding_drag: dict[str, float]
    liquidity_filter: dict[str, float]
    regime_split: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ic_timeseries": self.ic_timeseries.to_dict(orient="records"),
            "grouped_returns": {
                key: {
                    **value,
                    "quantile_returns": cast("pd.Series", value["quantile_returns"]).to_dict()
                    if "quantile_returns" in value
                    else {},
                }
                for key, value in self.grouped_returns.items()
            },
            "turnover": self.turnover,
            "decay": self.decay.to_dict(orient="records"),
            "correlation_matrix": self.correlation_matrix.to_dict(),
            "funding_drag": self.funding_drag,
            "liquidity_filter": self.liquidity_filter,
            "regime_split": self.regime_split,
            "metadata": self.metadata,
            "artifacts": self.artifacts,
        }


def analyze_signal_diagnostics(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    periods: Sequence[int] = (1, 3, 5),
    quantile_buckets: Sequence[int] = (5, 10),
    rolling_window: int = 20,
) -> SignalDiagnosticsResult:
    """Run the core signal diagnostics suite."""
    prepared_signals = _prepare_signals(signals)
    prepared_prices = _prepare_prices(prices)
    forward_returns = _build_forward_returns(prepared_prices, periods)

    ic_timeseries = _compute_ic_timeseries(prepared_signals, forward_returns, rolling_window)
    grouped_returns = {
        f"q{quantiles}": _compute_grouped_returns(prepared_signals, forward_returns, quantiles)
        for quantiles in quantile_buckets
    }
    turnover = _compute_turnover(prepared_signals, quantiles=quantile_buckets[0])
    decay = _compute_decay(ic_timeseries)
    correlation_matrix = _compute_correlation_matrix(prepared_signals)
    funding_drag = _compute_funding_drag(prepared_signals, prepared_prices)
    liquidity_filter = _compute_liquidity_filter(prepared_signals, forward_returns, prepared_prices)
    regime_split = _compute_regime_split(prepared_signals, forward_returns, prepared_prices)

    metadata = {
        "periods": list(periods),
        "quantile_buckets": list(quantile_buckets),
        "rolling_window": rolling_window,
        "signal_count": len(prepared_signals),
        "asset_count": int(prepared_signals["symbol"].nunique()),
    }
    return SignalDiagnosticsResult(
        ic_timeseries=ic_timeseries,
        grouped_returns=grouped_returns,
        turnover=turnover,
        decay=decay,
        correlation_matrix=correlation_matrix,
        funding_drag=funding_drag,
        liquidity_filter=liquidity_filter,
        regime_split=regime_split,
        metadata=metadata,
    )


def _prepare_signals(signals: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "symbol", "signal"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"signals missing required columns: {sorted(missing)}")
    prepared = signals.copy()
    prepared["timestamp"] = prepared["timestamp"].astype("int64")
    prepared["signal"] = prepared["signal"].astype(float)
    return prepared.sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "close"}
    if "timestamp" not in prices.columns and "available_at" not in prices.columns:
        raise ValueError("prices must contain either 'timestamp' or 'available_at'")
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"prices missing required columns: {sorted(missing)}")
    prepared = prices.copy()
    time_column = "timestamp" if "timestamp" in prepared.columns else "available_at"
    prepared["timestamp"] = prepared[time_column].astype("int64")
    prepared["close"] = prepared["close"].astype(float)
    if "volume" in prepared.columns:
        prepared["volume"] = prepared["volume"].astype(float)
    if "funding_rate" in prepared.columns:
        prepared["funding_rate"] = prepared["funding_rate"].astype(float)
    return prepared.sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _build_forward_returns(prices: pd.DataFrame, periods: Sequence[int]) -> pd.DataFrame:
    base = prices[["timestamp", "symbol", "close"]].copy()
    outputs = []
    for period in periods:
        frame = base.copy()
        frame[f"fwd_{period}"] = frame.groupby("symbol")["close"].shift(-period) / frame["close"] - 1.0
        outputs.append(frame[["timestamp", "symbol", f"fwd_{period}"]])

    merged = outputs[0]
    for frame in outputs[1:]:
        merged = merged.merge(frame, on=["timestamp", "symbol"], how="outer")
    return merged


def _compute_ic_timeseries(signals: pd.DataFrame, forward_returns: pd.DataFrame, rolling_window: int) -> pd.DataFrame:
    merged = signals.merge(forward_returns, on=["timestamp", "symbol"], how="left")
    rows: list[dict[str, float | int]] = []
    periods = [int(column.split("_")[1]) for column in forward_returns.columns if column.startswith("fwd_")]
    for period in periods:
        col = f"fwd_{period}"
        for timestamp, group in merged.groupby("timestamp", sort=True):
            group = group.dropna(subset=["signal", col])
            if len(group) < 2:
                continue
            ic = float(group["signal"].corr(group[col], method="pearson"))
            rank_ic = float(group["signal"].corr(group[col], method="spearman"))
            rows.append({
                "timestamp": cast("int", timestamp),
                "period": period,
                "ic": ic,
                "rank_ic": rank_ic,
            })

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.sort_values(["period", "timestamp"]).reset_index(drop=True)
    result["rolling_rank_ic_mean"] = (
        result.groupby("period")["rank_ic"].transform(lambda s: s.rolling(rolling_window, min_periods=1).mean())
    )
    result["rolling_rank_ic_std"] = (
        result.groupby("period")["rank_ic"].transform(lambda s: s.rolling(rolling_window, min_periods=1).std(ddof=0))
    )
    denom = result["rolling_rank_ic_std"].replace(0.0, np.nan)
    result["icir"] = result["rolling_rank_ic_mean"] / denom
    result["positive_ratio"] = (
        result.groupby("period")["rank_ic"].transform(lambda s: (s > 0).rolling(rolling_window, min_periods=1).mean())
    )
    return result


def _compute_grouped_returns(
    signals: pd.DataFrame,
    forward_returns: pd.DataFrame,
    quantiles: int,
) -> dict[str, object]:
    merged = signals.merge(forward_returns, on=["timestamp", "symbol"], how="left")
    period = int(next(col.split("_")[1] for col in forward_returns.columns if col.startswith("fwd_")))
    target_col = f"fwd_{period}"
    grouped_rows = []
    skipped = 0
    for _timestamp, group in merged.groupby("timestamp", sort=True):
        group = group.dropna(subset=["signal", target_col])
        if len(group) < quantiles:
            skipped += 1
            continue
        try:
            labels = pd.qcut(group["signal"], q=quantiles, labels=False, duplicates="drop")
        except ValueError:
            skipped += 1
            continue
        group = group.assign(quantile=labels + 1)
        grouped_rows.append(group[["timestamp", "quantile", target_col]])

    if not grouped_rows:
        return {
            "quantile_returns": pd.Series(dtype=float),
            "top_minus_bottom": float("nan"),
            "monotonic": False,
            "skipped_timestamps": skipped,
        }

    frame = pd.concat(grouped_rows, ignore_index=True)
    quantile_returns = frame.groupby("quantile")[target_col].mean().sort_index()
    monotonic = bool(quantile_returns.is_monotonic_increasing)
    top_minus_bottom = float(quantile_returns.iloc[-1] - quantile_returns.iloc[0])
    return {
        "quantile_returns": quantile_returns,
        "top_minus_bottom": top_minus_bottom,
        "monotonic": monotonic,
        "skipped_timestamps": skipped,
    }


def _compute_turnover(signals: pd.DataFrame, quantiles: int) -> dict[str, float]:
    memberships: dict[int, dict[str, set[str]]] = {}
    for timestamp, group in signals.groupby("timestamp", sort=True):
        if len(group) < quantiles:
            continue
        labels = pd.qcut(group["signal"], q=quantiles, labels=False, duplicates="drop")
        top_group = set(group.loc[labels == labels.max(), "symbol"])
        bottom_group = set(group.loc[labels == labels.min(), "symbol"])
        memberships[cast("int", timestamp)] = {"top": top_group, "bottom": bottom_group}

    top_turnover: list[float] = []
    bottom_turnover: list[float] = []
    timestamps = sorted(memberships)
    for prev_ts, curr_ts in pairwise(timestamps):
        prev = memberships[prev_ts]
        curr = memberships[curr_ts]
        if prev["top"]:
            top_turnover.append(len(curr["top"] - prev["top"]) / len(prev["top"]))
        if prev["bottom"]:
            bottom_turnover.append(len(curr["bottom"] - prev["bottom"]) / len(prev["bottom"]))

    def _mean(values: list[float]) -> float:
        return float(np.mean(values)) if values else float("nan")

    return {
        "top_turnover": _mean(top_turnover),
        "bottom_turnover": _mean(bottom_turnover),
        "median_turnover": _mean(top_turnover + bottom_turnover),
    }


def _compute_decay(ic_timeseries: pd.DataFrame) -> pd.DataFrame:
    if ic_timeseries.empty:
        return pd.DataFrame(columns=["period", "mean_rank_ic", "icir", "positive_ratio"])
    return (
        ic_timeseries.groupby("period", as_index=False)
        .agg(
            mean_rank_ic=("rank_ic", "mean"),
            icir=("icir", "mean"),
            positive_ratio=("positive_ratio", "mean"),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )


def _compute_correlation_matrix(signals: pd.DataFrame) -> pd.DataFrame:
    if "factor_name" not in signals.columns:
        series = signals.set_index(["timestamp", "symbol"])["signal"]
        return pd.DataFrame({"signal": series}).corr()
    pivot = signals.pivot_table(
        index=["timestamp", "symbol"],
        columns="factor_name",
        values="signal",
        aggfunc="last",
    )
    return pivot.corr()


def _compute_funding_drag(signals: pd.DataFrame, prices: pd.DataFrame) -> dict[str, float]:
    if "funding_rate" not in prices.columns:
        return {"mean_drag": float("nan"), "positive_ratio": float("nan")}
    merged = signals.merge(
        prices[["timestamp", "symbol", "funding_rate"]],
        on=["timestamp", "symbol"],
        how="left",
    ).dropna(subset=["funding_rate"])
    if merged.empty:
        return {"mean_drag": float("nan"), "positive_ratio": float("nan")}
    drag = np.sign(merged["signal"]) * merged["funding_rate"]
    return {
        "mean_drag": float(drag.mean()),
        "positive_ratio": float((drag > 0).mean()),
    }


def _compute_liquidity_filter(
    signals: pd.DataFrame,
    forward_returns: pd.DataFrame,
    prices: pd.DataFrame,
) -> dict[str, float]:
    if "volume" not in prices.columns:
        return {"high_liquidity_rank_ic": float("nan"), "low_liquidity_rank_ic": float("nan")}
    period = int(next(col.split("_")[1] for col in forward_returns.columns if col.startswith("fwd_")))
    target_col = f"fwd_{period}"
    merged = (
        signals.merge(forward_returns, on=["timestamp", "symbol"], how="left")
        .merge(prices[["timestamp", "symbol", "volume"]], on=["timestamp", "symbol"], how="left")
        .dropna(subset=["signal", target_col, "volume"])
    )
    if merged.empty:
        return {"high_liquidity_rank_ic": float("nan"), "low_liquidity_rank_ic": float("nan")}

    ranks = []
    for _, group in merged.groupby("timestamp", sort=True):
        threshold = group["volume"].median()
        high = group[group["volume"] >= threshold]
        low = group[group["volume"] < threshold]
        high_ic = float(high["signal"].corr(high[target_col], method="spearman")) if len(high) >= 2 else float("nan")
        low_ic = float(low["signal"].corr(low[target_col], method="spearman")) if len(low) >= 2 else float("nan")
        ranks.append((high_ic, low_ic))

    high_values = [value for value, _ in ranks if not np.isnan(value)]
    low_values = [value for _, value in ranks if not np.isnan(value)]
    return {
        "high_liquidity_rank_ic": float(np.mean(high_values)) if high_values else float("nan"),
        "low_liquidity_rank_ic": float(np.mean(low_values)) if low_values else float("nan"),
    }


def _compute_regime_split(
    signals: pd.DataFrame,
    forward_returns: pd.DataFrame,
    prices: pd.DataFrame,
) -> dict[str, float]:
    period = int(next(col.split("_")[1] for col in forward_returns.columns if col.startswith("fwd_")))
    target_col = f"fwd_{period}"
    price_returns = prices.copy()
    price_returns["bar_return"] = price_returns.groupby("symbol")["close"].pct_change().fillna(0.0)
    merged = (
        signals.merge(forward_returns, on=["timestamp", "symbol"], how="left")
        .merge(price_returns[["timestamp", "symbol", "bar_return"]], on=["timestamp", "symbol"], how="left")
        .dropna(subset=["signal", target_col, "bar_return"])
    )
    if merged.empty:
        return {"high_vol_rank_ic": float("nan"), "low_vol_rank_ic": float("nan")}

    regime_scores = merged.groupby("timestamp")["bar_return"].apply(lambda s: s.abs().median())
    threshold = regime_scores.median()
    merged = merged.merge(regime_scores.rename("regime_score"), on="timestamp", how="left")
    high = merged[merged["regime_score"] >= threshold]
    low = merged[merged["regime_score"] < threshold]

    def _rank_ic(frame: pd.DataFrame) -> float:
        if frame.empty:
            return float("nan")
        values = []
        for _, group in frame.groupby("timestamp", sort=True):
            if len(group) < 2:
                continue
            values.append(float(group["signal"].corr(group[target_col], method="spearman")))
        return float(np.mean(values)) if values else float("nan")

    return {
        "high_vol_rank_ic": _rank_ic(high),
        "low_vol_rank_ic": _rank_ic(low),
    }
