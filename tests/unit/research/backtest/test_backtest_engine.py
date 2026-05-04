"""Unit tests for the research backtest engine module."""

from __future__ import annotations

import pandas as pd
import pytest

from kronos.common.errors import BacktestError
from kronos.research.backtest import BacktestConfig, Engine


def _signals() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows: list[dict[str, int | float | str]] = []
    for step in range(4):
        ts = base + step * 3_600_000
        rows.append({"timestamp": ts, "symbol": "BTCUSDT", "signal": 1.0 + step})
        rows.append({"timestamp": ts, "symbol": "ETHUSDT", "signal": -1.0 - step})
    return pd.DataFrame(rows)


def _market_data() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows: list[dict[str, int | float | str]] = []
    btc_prices = [100.0, 101.0, 103.0, 104.0, 106.0]
    eth_prices = [100.0, 99.0, 97.0, 96.0, 95.0]
    for index, ts in enumerate(base + step * 3_600_000 for step in range(5)):
        rows.append({
            "event_time": ts,
            "available_at": ts,
            "symbol": "BTCUSDT",
            "open": btc_prices[index],
            "high": btc_prices[index] + 1.0,
            "low": btc_prices[index] - 1.0,
            "close": btc_prices[index],
            "volume": 100.0,
            "funding_rate": 0.0,
        })
        rows.append({
            "event_time": ts,
            "available_at": ts,
            "symbol": "ETHUSDT",
            "open": eth_prices[index],
            "high": eth_prices[index] + 1.0,
            "low": eth_prices[index] - 1.0,
            "close": eth_prices[index],
            "volume": 100.0,
            "funding_rate": 0.0,
        })
    return pd.DataFrame(rows)


class TestValidators:
    def test_rejects_missing_signal_columns(self) -> None:
        engine = Engine(BacktestConfig())
        with pytest.raises(BacktestError, match="signals missing required columns"):
            engine.run(pd.DataFrame({"symbol": ["BTCUSDT"]}), _market_data())

    def test_rejects_non_pit_signal_alignment(self) -> None:
        engine = Engine(BacktestConfig())
        bad_data = _market_data().copy()
        bad_data["available_at"] = bad_data["event_time"] + 60_000
        with pytest.raises(BacktestError, match="must align to PIT-safe market data rows"):
            engine.run(_signals(), bad_data)


class TestEngineRun:
    def test_runs_market_neutral_pipeline(self) -> None:
        engine = Engine(
            BacktestConfig(
                timeframe="1h",
                rebalance_frequency="1h",
                mode="market_neutral",
                top_n=1,
            )
        )
        result = engine.run(_signals(), _market_data())

        assert not result.equity_curve.empty
        assert not result.weights.empty
        assert not result.target_weights.empty
        assert not result.turnover.empty
        assert result.metrics.trade_count > 0
        assert set(result.weights["symbol"].unique()) == {"BTCUSDT", "ETHUSDT"}

    def test_delay_one_bar_before_weights_take_effect(self) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="long_only", top_n=1))
        result = engine.run(_signals(), _market_data())

        first_timestamp = int(result.weights["timestamp"].min())
        first_rows = result.weights[result.weights["timestamp"] == first_timestamp]
        assert (first_rows["actual_weight"] == 0.0).all()

        second_timestamp = sorted(result.weights["timestamp"].unique())[1]
        second_rows = result.weights[result.weights["timestamp"] == second_timestamp]
        assert (second_rows["actual_weight"] > 0).any()

    def test_market_neutral_weights_are_balanced(self) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1))
        result = engine.run(_signals(), _market_data())

        for timestamp, frame in result.weights.groupby("timestamp"):
            gross_long = frame[frame["actual_weight"] > 0]["actual_weight"].sum()
            gross_short = frame[frame["actual_weight"] < 0]["actual_weight"].sum()
            if timestamp == result.weights["timestamp"].min():
                continue
            assert gross_long == pytest.approx(1.0)
            assert gross_short == pytest.approx(-1.0)

    def test_long_only_never_generates_negative_weights(self) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="long_only", top_n=1))
        result = engine.run(_signals(), _market_data())
        assert (result.weights["actual_weight"] >= 0).all()

    def test_short_only_never_generates_positive_weights(self) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="short_only", top_n=1))
        result = engine.run(_signals(), _market_data())
        assert (result.weights["actual_weight"] <= 0).all()
