"""Input validators for the research backtest engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kronos.common.errors import BacktestError

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pandas as pd

    from kronos.research.backtest.config import BacktestConfig


REQUIRED_SIGNAL_COLUMNS = {"timestamp", "symbol", "signal"}
REQUIRED_DATA_COLUMNS = {
    "event_time",
    "available_at",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def validate_signals(signals: pd.DataFrame) -> None:
    _require_columns(signals.columns, REQUIRED_SIGNAL_COLUMNS, "signals")
    if signals.empty:
        raise BacktestError("signals must not be empty")
    if signals["timestamp"].isna().any():
        raise BacktestError("signals.timestamp must not contain nulls")
    if signals["symbol"].isna().any():
        raise BacktestError("signals.symbol must not contain nulls")
    if signals["signal"].isna().any():
        raise BacktestError("signals.signal must not contain nulls")


def validate_data(data: pd.DataFrame) -> None:
    _require_columns(data.columns, REQUIRED_DATA_COLUMNS, "data")
    if data.empty:
        raise BacktestError("data must not be empty")
    if (data["available_at"] < data["event_time"]).any():
        raise BacktestError("data.available_at must be >= event_time for every row")
    sorted_data = data.sort_values(["symbol", "event_time"])
    if not sorted_data.groupby("symbol")["event_time"].apply(lambda s: s.is_monotonic_increasing).all():
        raise BacktestError("data.event_time must be monotonic increasing within each symbol")


def validate_pit_contract(signals: pd.DataFrame, data: pd.DataFrame) -> None:
    merged = signals.merge(
        data[["event_time", "available_at", "symbol"]],
        left_on=["timestamp", "symbol"],
        right_on=["available_at", "symbol"],
        how="left",
    )
    if merged["available_at"].isna().any():
        raise BacktestError("signals must align to PIT-safe market data rows by timestamp and symbol")
    if (merged["available_at"] > merged["timestamp"]).any():
        raise BacktestError("signals reference data that was not yet available at decision time")


def validate_lookahead(config: BacktestConfig) -> None:
    if config.execution_delay_bars < 1:
        raise BacktestError("lookahead violation: execution_delay_bars must be at least 1")


def validate_inputs(signals: pd.DataFrame, data: pd.DataFrame, config: BacktestConfig) -> None:
    validate_signals(signals)
    validate_data(data)
    validate_pit_contract(signals, data)
    validate_lookahead(config)


def _require_columns(columns: Iterable[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(columns))
    if missing:
        raise BacktestError(f"{label} missing required columns: {missing}")
