"""Signal ranking helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pandas as pd

if TYPE_CHECKING:
    from kronos.research.backtest.config import BacktestConfig


def build_target_weights(signals: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    """Map rebalance signals to target portfolio weights."""
    ordered = signals.sort_values(["timestamp", "signal", "symbol"], ascending=[True, False, True])
    targets: list[dict[str, float | int | str]] = []

    for timestamp, group in ordered.groupby("timestamp", sort=True):
        timestamp_int = int(cast("int", timestamp))
        clean = group.dropna(subset=["signal"]).copy()
        if clean.empty:
            continue

        if config.mode == "long_only":
            selected = clean.nlargest(config.top_n, "signal")
            weight = 1.0 / len(selected)
            for _, row in selected.iterrows():
                targets.append({
                    "timestamp": timestamp_int,
                    "symbol": str(row["symbol"]),
                    "target_weight": weight,
                    "side": "long",
                })
        elif config.mode == "short_only":
            selected = clean.nsmallest(config.top_n, "signal")
            weight = -1.0 / len(selected)
            for _, row in selected.iterrows():
                targets.append({
                    "timestamp": timestamp_int,
                    "symbol": str(row["symbol"]),
                    "target_weight": weight,
                    "side": "short",
                })
        else:
            longs = clean.nlargest(config.top_n, "signal")
            shorts = clean.nsmallest(config.top_n, "signal")
            long_weight = 1.0 / len(longs) if len(longs) else 0.0
            short_weight = -1.0 / len(shorts) if len(shorts) else 0.0
            for _, row in longs.iterrows():
                targets.append({
                    "timestamp": timestamp_int,
                    "symbol": str(row["symbol"]),
                    "target_weight": long_weight,
                    "side": "long",
                })
            for _, row in shorts.iterrows():
                targets.append({
                    "timestamp": timestamp_int,
                    "symbol": str(row["symbol"]),
                    "target_weight": short_weight,
                    "side": "short",
                })

    return pd.DataFrame(targets, columns=["timestamp", "symbol", "target_weight", "side"])
