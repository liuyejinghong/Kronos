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


# --- 2026-09-27 audit regression tests (FSR-005 / engine overwrite) ---


def _three_symbol_market_data() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows: list[dict[str, int | float | str]] = []
    for index, ts in enumerate(base + step * 3_600_000 for step in range(5)):
        for symbol, price in (("BTCUSDT", 100.0), ("ETHUSDT", 50.0), ("SOLUSDT", 20.0)):
            rows.append({
                "event_time": ts,
                "available_at": ts,
                "symbol": symbol,
                "open": price + index,
                "high": price + index + 1.0,
                "low": price + index - 1.0,
                "close": price + index,
                "volume": 100.0,
                "funding_rate": 0.0,
            })
    return pd.DataFrame(rows)


class TestAuditFixes:
    def test_market_neutral_small_universe_keeps_both_legs(self) -> None:
        """top_n >= universe must not collapse into a short-only book (FSR-005)."""
        base = 1_700_000_000_000
        signals = pd.DataFrame([
            {"timestamp": base, "symbol": s, "signal": v}
            for s, v in (("BTCUSDT", 2.0), ("ETHUSDT", 1.0), ("SOLUSDT", -2.0))
        ])
        engine = Engine(
            BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=20)
        )
        result = engine.run(signals, _three_symbol_market_data())

        tw = result.target_weights
        assert not tw.empty
        assert not tw.duplicated(subset=["timestamp", "symbol"]).any()
        assert tw[tw["target_weight"] > 0]["target_weight"].sum() == pytest.approx(1.0)
        assert tw[tw["target_weight"] < 0]["target_weight"].sum() == pytest.approx(-1.0)

    def test_misaligned_signal_timestamps_merge_not_overwrite(self) -> None:
        """Signals one bar apart inside one 4h bucket must both survive."""
        base = 1_700_000_000_000
        signals = pd.DataFrame([
            {"timestamp": base, "symbol": "BTCUSDT", "signal": 2.0},
            {"timestamp": base + 3_600_000, "symbol": "ETHUSDT", "signal": -2.0},
        ])
        data = _three_symbol_market_data()
        data = data[data["symbol"].isin(["BTCUSDT", "ETHUSDT"])].reset_index(drop=True)
        engine = Engine(
            BacktestConfig(timeframe="1h", rebalance_frequency="4h", mode="market_neutral", top_n=5)
        )
        result = engine.run(signals, data)

        tw = result.target_weights
        frame = tw
        btc = frame[frame["symbol"] == "BTCUSDT"]["target_weight"].sum()
        eth = frame[frame["symbol"] == "ETHUSDT"]["target_weight"].sum()
        assert btc == pytest.approx(1.0), frame
        assert eth == pytest.approx(-1.0), frame
