"""Trade ledger generation."""

from __future__ import annotations

import pandas as pd


def record_rebalance_trades(
    timestamp: int,
    previous: pd.Series,
    target: pd.Series,
    cost_rate: float,
) -> pd.DataFrame:
    symbols = sorted(set(previous.index).union(target.index))
    rows: list[dict[str, float | int | str]] = []
    for symbol in symbols:
        pre = float(previous.get(symbol, 0.0))
        post = float(target.get(symbol, 0.0))
        delta = post - pre
        if delta == 0:
            continue
        event = "rebalance"
        if pre == 0 and post != 0:
            event = "open"
        elif pre != 0 and post == 0:
            event = "close"

        rows.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "event": event,
            "side": "long" if post > 0 else ("short" if post < 0 else "flat"),
            "pre_weight": pre,
            "post_weight": post,
            "turnover_share": abs(delta),
            "estimated_cost": abs(delta) * cost_rate,
        })
    return pd.DataFrame(rows)
