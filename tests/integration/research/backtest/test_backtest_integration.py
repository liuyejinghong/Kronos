"""Integration tests for the research backtest module."""

from __future__ import annotations

import time

import pandas as pd
import pyarrow as pa
import pytest

from kronos.data.storage.parquet_store import write_partition
from kronos.data.storage.query import load_universe
from kronos.factor.implementations.trend import CMOMomentumFactor
from kronos.factor.registry import FactorRegistry
from kronos.research.backtest import BacktestConfig, Engine
from kronos.research.backtest.freqtrade_bridge import run_cross_validation


def _write_symbol_data(tmp_path, symbol: str, base_price: float) -> None:
    base = 1_709_251_200_000
    now = int(time.time() * 1000)
    event_times = [base + i * 60_000 for i in range(360)]
    table = pa.table({
        "event_time": pa.array(event_times, type=pa.int64()),
        "available_at": pa.array(event_times, type=pa.int64()),
        "ingested_at": pa.array([now] * len(event_times), type=pa.int64()),
        "symbol": [symbol] * len(event_times),
        "open": pa.array([base_price + i * 0.1 for i in range(len(event_times))], type=pa.float64()),
        "high": pa.array([base_price + i * 0.1 + 0.5 for i in range(len(event_times))], type=pa.float64()),
        "low": pa.array([base_price + i * 0.1 - 0.5 for i in range(len(event_times))], type=pa.float64()),
        "close": pa.array([base_price + i * 0.1 + 0.2 for i in range(len(event_times))], type=pa.float64()),
        "volume": pa.array([100.0] * len(event_times), type=pa.float64()),
    })
    write_partition(table, tmp_path, symbol, "klines_1m", 2024, 3)


class TestBacktestIntegration:
    def test_engine_runs_on_loaded_pit_safe_data(self, tmp_path) -> None:
        _write_symbol_data(tmp_path, "BTCUSDT", 100.0)
        _write_symbol_data(tmp_path, "ETHUSDT", 200.0)

        data = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1h")
        timestamps = sorted(data["available_at"].unique())[:4]
        signals = pd.DataFrame({
            "timestamp": timestamps * 2,
            "symbol": ["BTCUSDT"] * 4 + ["ETHUSDT"] * 4,
            "signal": [1.0, 1.2, 1.3, 1.4, -1.0, -1.1, -1.2, -1.3],
        }).sort_values(["timestamp", "symbol"]).reset_index(drop=True)

        result = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1)).run(
            signals,
            data,
        )

        assert not result.equity_curve.empty
        assert not result.trades.empty

    def test_factor_scores_can_feed_backtest_engine(self, tmp_path) -> None:
        _write_symbol_data(tmp_path, "BTCUSDT", 100.0)
        _write_symbol_data(tmp_path, "ETHUSDT", 200.0)

        data = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1h")
        registry = FactorRegistry()
        registry.register(CMOMomentumFactor(lookback=2), set_default=True)
        scores = registry.compute_all(data, factor_names=["cmo_momentum"])
        signals = scores[["available_at", "symbol", "value"]].rename(
            columns={"available_at": "timestamp", "value": "signal"}
        )
        signals = signals.dropna().reset_index(drop=True)

        result = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1)).run(
            signals,
            data,
        )

        assert not result.factor_scores.empty
        assert result.metrics.trade_count >= 0

    def test_signal_at_t_only_affects_t_plus_1(self, tmp_path) -> None:
        _write_symbol_data(tmp_path, "BTCUSDT", 100.0)
        _write_symbol_data(tmp_path, "ETHUSDT", 200.0)

        data = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1h")
        timestamps = sorted(data["available_at"].unique())[:4]
        signals = pd.DataFrame({
            "timestamp": timestamps * 2,
            "symbol": ["BTCUSDT"] * 4 + ["ETHUSDT"] * 4,
            "signal": [1.0, 1.2, 1.3, 1.4, -1.0, -1.1, -1.2, -1.3],
        }).sort_values(["timestamp", "symbol"]).reset_index(drop=True)

        result = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1)).run(
            signals,
            data,
        )

        timestamps_out = sorted(result.weights["timestamp"].unique())
        first_weights = result.weights[result.weights["timestamp"] == timestamps_out[0]]
        second_weights = result.weights[result.weights["timestamp"] == timestamps_out[1]]
        assert (first_weights["actual_weight"] == 0.0).all()
        assert (second_weights["actual_weight"] != 0.0).any()

    def test_three_modes_hold_expected_weight_constraints(self, tmp_path) -> None:
        _write_symbol_data(tmp_path, "BTCUSDT", 100.0)
        _write_symbol_data(tmp_path, "ETHUSDT", 200.0)
        data = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1h")
        timestamps = sorted(data["available_at"].unique())[:4]
        signals = pd.DataFrame({
            "timestamp": timestamps * 2,
            "symbol": ["BTCUSDT"] * 4 + ["ETHUSDT"] * 4,
            "signal": [1.0, 1.2, 1.3, 1.4, -1.0, -1.1, -1.2, -1.3],
        }).sort_values(["timestamp", "symbol"]).reset_index(drop=True)

        long_only = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="long_only", top_n=1)).run(
            signals,
            data,
        )
        short_only = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="short_only", top_n=1)).run(
            signals,
            data,
        )
        market_neutral = Engine(
            BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1)
        ).run(signals, data)

        assert (long_only.weights["actual_weight"] >= 0).all()
        assert (short_only.weights["actual_weight"] <= 0).all()
        rebalance_timestamps = sorted(market_neutral.target_weights["timestamp"].unique())
        effective_timestamps = set(sorted(market_neutral.weights["timestamp"].unique())[1:1 + len(rebalance_timestamps)])
        for timestamp, frame in market_neutral.weights.groupby("timestamp"):
            if timestamp not in effective_timestamps:
                continue
            assert frame[frame["actual_weight"] > 0]["actual_weight"].sum() == pytest.approx(1.0)
            assert frame[frame["actual_weight"] < 0]["actual_weight"].sum() == pytest.approx(-1.0)

    def test_bridge_reports_passed_and_failed_in_integration_flow(self, tmp_path) -> None:
        _write_symbol_data(tmp_path, "BTCUSDT", 100.0)
        _write_symbol_data(tmp_path, "ETHUSDT", 200.0)
        data = load_universe(["BTCUSDT", "ETHUSDT"], base_path=tmp_path, timeframe="1h")
        timestamps = sorted(data["available_at"].unique())[:4]
        signals = pd.DataFrame({
            "timestamp": timestamps * 2,
            "symbol": ["BTCUSDT"] * 4 + ["ETHUSDT"] * 4,
            "signal": [1.0, 1.2, 1.3, 1.4, -1.0, -1.1, -1.2, -1.3],
        }).sort_values(["timestamp", "symbol"]).reset_index(drop=True)

        result = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1)).run(
            signals,
            data,
        )
        freqtrade_equity = result.equity_curve[["timestamp", "equity"]].copy()
        summary = {
            "final_equity": float(freqtrade_equity["equity"].iloc[-1]),
            "max_drawdown": result.metrics.max_drawdown,
            "sharpe": result.metrics.sharpe,
            "trade_count": result.metrics.trade_count,
        }

        passed = run_cross_validation(
            result=result,
            signals=signals,
            freqtrade_equity=freqtrade_equity,
            freqtrade_summary=summary,
            output_dir=tmp_path / "passed",
            universe=["BTCUSDT", "ETHUSDT"],
            lookahead_output={"status": "passed", "violations": []},
        )
        failed = run_cross_validation(
            result=result,
            signals=signals,
            freqtrade_equity=freqtrade_equity,
            freqtrade_summary=summary,
            output_dir=tmp_path / "failed",
            universe=["BTCUSDT", "ETHUSDT"],
            lookahead_output={"status": "failed", "violations": ["bias"]},
        )

        assert passed.status == "passed"
        assert failed.status == "failed"
        assert failed.failure_reason == "lookahead_check_failed"
