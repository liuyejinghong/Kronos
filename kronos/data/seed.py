"""Generate synthetic market data for quickstart / smoke-test usage.

All generated data is tagged ``venue = "synthetic"`` so query consumers can
distinguish it from real Binance data.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import numpy as np
import pyarrow as pa

from kronos.common.log import get_logger
from kronos.data.schemas.candle import CANDLE_DEDUP_KEY
from kronos.data.storage.parquet_store import write_records_partitioned

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("kronos.data.seed")

_DEFAULT_SYMBOLS = ("BTCUSDT",)
_DEFAULT_DAYS = 7
_SEED = 42


def generate_sample_klines(
    symbol: str = "BTCUSDT",
    *,
    base_path: str | Path,
    days: int = _DEFAULT_DAYS,
    seed: int = _SEED,
) -> int:
    """Generate synthetic 1m kline data and write to the standard Parquet store.

    Uses a geometric Brownian motion with weak upward drift and intraday
    seasonality to produce plausible-looking but clearly synthetic bars.

    Returns:
        Number of bars written.
    """
    from pathlib import Path as _Path

    rng = np.random.default_rng(seed)
    now_ms = int(time.time() * 1000)
    n_bars = days * 24 * 60  # 1m bars for N days
    start_ms = now_ms - n_bars * 60_000

    # Drift + volatility parameters (annualized, scaled to 1-min)
    mu = 0.15  # 15% annual drift
    sigma = 0.80  # 80% annual vol
    dt = 1.0 / (365 * 24 * 60)  # 1-minute fraction of a year

    log_returns = rng.normal(
        (mu - 0.5 * sigma**2) * dt,
        sigma * np.sqrt(dt),
        size=n_bars,
    )
    # Mild intraday seasonality: slightly higher vol near UTC day open
    minute_of_day = np.arange(n_bars) % (24 * 60)
    seasonality = 1.0 + 0.15 * np.sin(2 * np.pi * minute_of_day / (24 * 60) - np.pi / 4)
    log_returns = log_returns * seasonality

    price = 90000.0 * np.exp(np.cumsum(log_returns))
    price = np.maximum(price, 1000.0)  # floor

    rows: list[dict[str, Any]] = []
    for i in range(n_bars):
        open_time = start_ms + i * 60_000
        close_time = open_time + 59_999
        open_price = price[i]
        close_price = price[i + 1] if i + 1 < n_bars else price[i] * (1 + log_returns[i])
        bar_range = abs(close_price - open_price) + abs(price[i]) * sigma * np.sqrt(dt) * 2
        high = max(open_price, close_price) + abs(rng.normal(0, bar_range * 0.3))
        low = min(open_price, close_price) - abs(rng.normal(0, bar_range * 0.3))
        low = max(low, 1.0)
        volume = abs(rng.normal(50.0, 20.0))

        rows.append({
            "event_time": open_time,
            "available_at": close_time,
            "ingested_at": now_ms,
            "symbol": symbol,
            "open": float(open_price),
            "high": float(high),
            "low": float(low),
            "close": float(close_price),
            "volume": float(volume),
            "quote_volume": float(volume * close_price),
            "trade_count": int(max(1, abs(rng.normal(500, 200)))),
            "taker_buy_volume": float(volume * abs(rng.normal(0.5, 0.15))),
            "venue": "synthetic",
        })

    table = pa.Table.from_pylist(rows)
    paths = write_records_partitioned(
        table, _Path(base_path), symbol, "klines_1m", CANDLE_DEDUP_KEY,
    )
    log.info(
        "seed.klines_generated",
        symbol=symbol,
        bars=n_bars,
        partitions=len(paths),
        venue="synthetic",
    )
    return n_bars


def has_any_data(base_path: str | Path) -> bool:
    """Check whether any curated kline data exists."""
    from pathlib import Path as _Path

    root = _Path(base_path) / "curated"
    if not root.exists():
        return False
    return any(root.rglob("*.parquet"))
