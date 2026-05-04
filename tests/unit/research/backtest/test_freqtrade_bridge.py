"""Unit tests for the Freqtrade bridge."""

from __future__ import annotations

import pandas as pd

from kronos.research.backtest import BacktestConfig, Engine
from kronos.research.backtest.freqtrade_bridge import (
    build_freqtrade_config,
    build_lookahead_analysis_command,
    compare_with_freqtrade,
    evaluate_lookahead_output,
    export_signals,
    run_cross_validation,
)


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


class TestFreqtradeBridge:
    def test_builds_lookahead_command(self, tmp_path) -> None:
        command = build_lookahead_analysis_command(
            config_path=tmp_path / "freqtrade_config.json",
            export_dir=tmp_path,
        )
        assert command[0] == "freqtrade"
        assert "lookahead-analysis" in command
        assert str(tmp_path / "freqtrade_config.json") in command
        assert str(tmp_path / "lookahead_analysis.json") in command

    def test_exports_standard_signal_file(self, tmp_path) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1))
        result = engine.run(_signals(), _market_data())

        path = export_signals(
            _signals(),
            result.target_weights,
            output_path=tmp_path / "signals.csv",
            run_id=result.run_id,
        )
        exported = pd.read_csv(path)
        assert {"timestamp", "symbol", "signal", "target_weight", "side", "rebalance_id"}.issubset(exported.columns)

    def test_builds_minimal_freqtrade_config(self) -> None:
        config = build_freqtrade_config(
            BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral"),
            universe=["BTCUSDT", "ETHUSDT"],
            since=1_700_000_000_000,
            until=1_700_100_000_000,
            signal_path="signals.csv",
        )
        assert config["timeframe"] == "1h"
        assert config["pairs"] == ["BTCUSDT", "ETHUSDT"]
        assert config["signal_path"] == "signals.csv"

    def test_cross_validation_passes_when_diffs_are_small(self) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1))
        result = engine.run(_signals(), _market_data())
        freqtrade_equity = result.equity_curve[["timestamp", "equity"]].copy()
        summary = {
            "final_equity": float(freqtrade_equity["equity"].iloc[-1]),
            "max_drawdown": result.metrics.max_drawdown,
            "sharpe": result.metrics.sharpe,
            "trade_count": result.metrics.trade_count,
        }
        verdict = compare_with_freqtrade(
            result,
            freqtrade_equity=freqtrade_equity,
            freqtrade_summary=summary,
            lookahead_clean=True,
            artifacts={"signals": "signals.csv"},
        )
        assert verdict.status == "passed"

    def test_cross_validation_fails_when_lookahead_fails(self) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1))
        result = engine.run(_signals(), _market_data())
        freqtrade_equity = result.equity_curve[["timestamp", "equity"]].copy()
        summary = {
            "final_equity": float(freqtrade_equity["equity"].iloc[-1]),
            "max_drawdown": result.metrics.max_drawdown,
            "sharpe": result.metrics.sharpe,
            "trade_count": result.metrics.trade_count,
        }
        verdict = compare_with_freqtrade(
            result,
            freqtrade_equity=freqtrade_equity,
            freqtrade_summary=summary,
            lookahead_clean=False,
            artifacts={"signals": "signals.csv"},
        )
        assert verdict.status == "failed"
        assert verdict.failure_reason == "lookahead_check_failed"

    def test_lookahead_output_marks_failure_when_violations_exist(self) -> None:
        result = evaluate_lookahead_output({"status": "passed", "violations": ["bias"]})
        assert result["passed"] is False
        assert result["status"] == "failed"

    def test_run_cross_validation_executes_standard_workflow(self, tmp_path) -> None:
        engine = Engine(BacktestConfig(timeframe="1h", rebalance_frequency="1h", mode="market_neutral", top_n=1))
        signals = _signals()
        result = engine.run(signals, _market_data())
        freqtrade_equity = result.equity_curve[["timestamp", "equity"]].copy()
        summary = {
            "final_equity": float(freqtrade_equity["equity"].iloc[-1]),
            "max_drawdown": result.metrics.max_drawdown,
            "sharpe": result.metrics.sharpe,
            "trade_count": result.metrics.trade_count,
        }

        verdict = run_cross_validation(
            result=result,
            signals=signals,
            freqtrade_equity=freqtrade_equity,
            freqtrade_summary=summary,
            output_dir=tmp_path,
            universe=["BTCUSDT", "ETHUSDT"],
            lookahead_output={"status": "passed", "violations": []},
        )

        assert verdict.status == "passed"
        assert (tmp_path / "signals.csv").exists()
        assert (tmp_path / "freqtrade_config.json").exists()
        assert "lookahead-analysis" in verdict.artifacts["lookahead_command"]
