"""Unit tests for experiment management."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from kronos.factor.diagnostics import analyze_signal_diagnostics
from kronos.factor.validation.pipeline import ValidationResult
from kronos.factor.validation.thresholds import ValidationConfig, ValidationOutcome
from kronos.research.backtest.types import BacktestMetrics, BacktestResult
from kronos.research.experiments import (
    append_run_record,
    build_run_record,
    compare_runs,
    compute_config_hash,
    generate_run_id,
    query_runs,
    rebuild_ledger_index,
    record_backtest_run,
    record_signal_diagnostics_run,
    record_validation_run,
    record_walkforward_run,
    write_backtest_artifacts,
    write_signal_diagnostics_artifacts,
    write_validation_artifacts,
    write_walkforward_artifacts,
)
from kronos.research.walkforward import run_walkforward_validation


def _backtest_result(run_id: str = "20260410T100000Z-abc1234") -> BacktestResult:
    return BacktestResult(
        run_id=run_id,
        config_snapshot={"timeframe": "1h", "mode": "market_neutral"},
        git_commit="abc123",
        data_snapshot_id="snapshot-1",
        equity_curve=pd.DataFrame({"timestamp": [1, 2], "equity": [1.0, 1.1], "drawdown": [0.0, 0.0]}),
        period_returns=pd.Series([0.0, 0.1], index=[1, 2], dtype=float),
        gross_returns=pd.Series([0.0, 0.101], index=[1, 2], dtype=float),
        weights=pd.DataFrame({"timestamp": [1], "symbol": ["BTCUSDT"], "target_weight": [1.0], "actual_weight": [1.0]}),
        target_weights=pd.DataFrame({"timestamp": [1], "symbol": ["BTCUSDT"], "target_weight": [1.0], "side": ["long"]}),
        turnover=pd.DataFrame({"timestamp": [1], "turnover_rate": [1.0], "cost": [0.001], "funding_cost": [0.0]}),
        positions=pd.DataFrame({"timestamp": [1], "symbol": ["BTCUSDT"], "actual_weight": [1.0], "side": ["long"], "pnl_contribution": [0.1]}),
        trades=pd.DataFrame({"timestamp": [1], "symbol": ["BTCUSDT"], "event": ["open"], "side": ["long"], "pre_weight": [0.0], "post_weight": [1.0], "turnover_share": [1.0], "estimated_cost": [0.001]}),
        metrics=BacktestMetrics(
            sharpe=1.0,
            sortino=1.0,
            calmar=1.0,
            max_drawdown=0.0,
            drawdown_duration=0,
            total_return=0.1,
            annual_return=0.1,
            annual_volatility=0.2,
            win_rate=1.0,
            profit_factor=2.0,
            trade_count=1,
            avg_holding_bars=1.0,
            turnover_mean=1.0,
            annual_turnover=365.0,
            average_active_positions=1.0,
            max_active_positions=1,
            var_95=-0.01,
            cvar_95=-0.01,
            worst_period=0.0,
            worst_consecutive_window=0.0,
            long_gross_exposure=1.0,
            short_gross_exposure=0.0,
            long_net_contribution=0.1,
            short_net_contribution=0.0,
            long_hit_ratio=1.0,
            short_hit_ratio=0.0,
            long_short_ratio=float("inf"),
        ),
        factor_scores=pd.DataFrame({"timestamp": [1], "symbol": ["BTCUSDT"], "signal": [1.0]}),
        tearsheet={"overview": {"total_return": 0.1}},
        config_tearsheet={"timeframe": "1h"},
    )


def _validation_result() -> ValidationResult:
    return ValidationResult(
        outcome=ValidationOutcome.PASS,
        ic_table=pd.DataFrame([{"period": 1, "ic": 0.1, "rank_ic": 0.2, "n_obs": 10}]),
        mean_rank_ic=0.2,
        rank_ic_positive_ratio=0.7,
        ic_ir=1.0,
        quantile_returns=pd.Series({1: -0.01, 2: 0.01}, dtype=float),
        top_minus_bottom=0.02,
        median_turnover=0.3,
        top_turnover=0.2,
        bottom_turnover=0.4,
        decay=pd.DataFrame([{"period": 1, "mean_rank_ic": 0.2, "rank_ic_positive_ratio": 0.7}]),
        forward_returns=pd.DataFrame({"fwd_1": [0.01, 0.02]}),
        n_obs=10,
        skipped_pct=0.0,
        config=ValidationConfig(periods=[1, 3], quantiles=2),
    )


def _diagnostic_signals() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for step in range(12):
        timestamp = base + step * 3_600_000
        rows.append({"timestamp": timestamp, "symbol": "BTCUSDT", "signal": 1.0 + step, "factor_name": "momentum"})
        rows.append({"timestamp": timestamp, "symbol": "ETHUSDT", "signal": -1.0 - step, "factor_name": "momentum"})
        rows.append({"timestamp": timestamp, "symbol": "SOLUSDT", "signal": 0.5 + step * 0.2, "factor_name": "momentum"})
    return pd.DataFrame(rows)


def _diagnostic_prices() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for step in range(16):
        timestamp = base + step * 3_600_000
        rows.extend([
            {"available_at": timestamp, "symbol": "BTCUSDT", "close": 100 + step, "volume": 300 - step, "funding_rate": 0.0001},
            {"available_at": timestamp, "symbol": "ETHUSDT", "close": 200 - step * 0.4, "volume": 150 + step, "funding_rate": -0.0001},
            {"available_at": timestamp, "symbol": "SOLUSDT", "close": 50 + step * 0.3, "volume": 120 + step * 0.5, "funding_rate": 0.00005},
        ])
    return pd.DataFrame(rows)


def _walkforward_result():
    return run_walkforward_validation(
        timestamps=list(range(12)),
        parameter_grid=[{"speed": 1}, {"speed": 2}],
        evaluator=lambda window, params: {
            "train_score": float(params["speed"]) + 1.0,
            "validation_score": float(params["speed"]),
            "test_score": float(params["speed"]) - 0.2,
        },
        train_size=4,
        validation_size=2,
        test_size=2,
        step_size=2,
        leak_audit={"status": "passed", "reason": None},
    )


class TestRunIdAndSchema:
    def test_generate_run_id_is_unique_with_same_second(self) -> None:
        now = datetime(2026, 4, 10, 10, 0, 0, tzinfo=UTC)
        left = generate_run_id({"seed": "a"}, now=now)
        right = generate_run_id({"seed": "b"}, now=now)
        assert left != right
        assert left.startswith("20260410T100000Z-")

    def test_build_run_record_requires_reproducibility_triplet(self) -> None:
        try:
            build_run_record(
                module="backtest",
                git_commit="",
                data_snapshot_id="snapshot-1",
                config_snapshot={"a": 1},
                factors=["f1"],
                universe=["BTCUSDT"],
                split_dates={},
                results={"sharpe": 1.0},
                artifact_paths={"metrics": "metrics.json"},
            )
        except ValueError as exc:
            assert "git_commit" in str(exc)
        else:
            raise AssertionError("expected validation failure for missing git_commit")

    def test_compute_config_hash_is_stable(self) -> None:
        left = compute_config_hash({"b": 2, "a": 1})
        right = compute_config_hash({"a": 1, "b": 2})
        assert left == right


class TestLedgerAndQuery:
    def test_append_only_jsonl_and_duckdb_rebuild(self, tmp_path) -> None:
        record = build_run_record(
            module="backtest",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            factors=["cmo_momentum"],
            universe=["BTCUSDT"],
            split_dates={"train": "2024-01-01/2024-02-01"},
            results={"sharpe": 1.2, "total_return": 0.1},
            artifact_paths={"metrics": "experiments/run/metrics.json"},
            run_id="run-1",
            now=datetime(2026, 4, 10, 10, 0, 0, tzinfo=UTC),
        )
        append_run_record(record, base_path=tmp_path)
        rebuild_ledger_index(base_path=tmp_path)

        rows = query_runs(base_path=tmp_path, git_commit="abc123")
        assert len(rows) == 1
        assert rows.iloc[0]["run_id"] == "run-1"

    def test_compare_runs_returns_traceable_projection(self, tmp_path) -> None:
        for idx, sharpe in enumerate([1.2, 0.8], start=1):
            record = build_run_record(
                module="backtest",
                git_commit=f"commit-{idx}",
                data_snapshot_id="snapshot-1",
                config_snapshot={"timeframe": "1h", "mode": "market_neutral"},
                factors=["cmo_momentum"],
                universe=["BTCUSDT"],
                split_dates={"train": "2024-01-01/2024-02-01"},
                results={"sharpe": sharpe, "total_return": 0.1 * idx},
                artifact_paths={"metrics": f"experiments/run-{idx}/metrics.json"},
                run_id=f"run-{idx}",
                now=datetime(2026, 4, 10, 10, 0, idx, tzinfo=UTC),
            )
            append_run_record(record, base_path=tmp_path)

        compared = compare_runs(base_path=tmp_path, factors=["cmo_momentum"], universe=["BTCUSDT"])
        assert len(compared) == 2
        assert set(compared.columns) == {
            "run_id",
            "git_commit",
            "data_snapshot_id",
            "config_hash",
            "results",
            "artifact_paths",
        }


class TestArtifacts:
    def test_write_backtest_artifacts_uses_standard_paths(self, tmp_path) -> None:
        result = _backtest_result()
        paths = write_backtest_artifacts(result, base_path=tmp_path)
        assert paths["metrics"].endswith("/experiments/20260410T100000Z-abc1234/metrics.json")
        assert paths["config_snapshot"].endswith("/config_snapshot.toml")
        assert paths["equity"].endswith("/equity.parquet")
        assert paths["trades"].endswith("/trades.parquet")

    def test_write_validation_artifacts_uses_standard_paths(self, tmp_path) -> None:
        paths = write_validation_artifacts(
            result=_validation_result(),
            factor_name="cmo_momentum",
            factor_version="1.0.0",
            base_path=tmp_path,
            run_id="20260410T101500Z-fff1111",
            timeframe="1h",
            universe=["BTCUSDT"],
        )
        assert paths["metrics"].endswith("/experiments/20260410T101500Z-fff1111/metrics.json")
        assert paths["config_snapshot"].endswith("/config_snapshot.toml")
        assert paths["report_dir"].endswith(
            "/experiments/20260410T101500Z-fff1111/reports/cmo_momentum/1.0.0"
        )
        report_payload = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
        assert report_payload["report_metadata"]["run_id"] == "20260410T101500Z-fff1111"

    def test_write_signal_diagnostics_artifacts_uses_standard_paths(self, tmp_path) -> None:
        diagnostics = analyze_signal_diagnostics(_diagnostic_signals(), _diagnostic_prices(), periods=[1, 3])
        paths = write_signal_diagnostics_artifacts(
            result=diagnostics,
            signal_name="momentum_bundle",
            base_path=tmp_path,
            run_id="20260410T111500Z-ddd2222",
            config_snapshot={"periods": [1, 3]},
        )
        assert paths["metrics"].endswith("/experiments/20260410T111500Z-ddd2222/metrics.json")
        assert paths["config_snapshot"].endswith("/config_snapshot.toml")
        payload = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
        assert payload["signal_name"] == "momentum_bundle"

    def test_write_walkforward_artifacts_uses_standard_paths(self, tmp_path) -> None:
        paths = write_walkforward_artifacts(
            result=_walkforward_result(),
            signal_name="wf_bundle",
            base_path=tmp_path,
            run_id="20260411T090000Z-wf11111",
            config_snapshot={"train_size": 4, "validation_size": 2, "test_size": 2},
        )
        assert paths["metrics"].endswith("/experiments/20260411T090000Z-wf11111/metrics.json")
        assert paths["config_snapshot"].endswith("/config_snapshot.toml")
        payload = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
        assert payload["signal_name"] == "wf_bundle"


class TestWorkflow:
    def test_record_backtest_run_writes_ledger_entry(self, tmp_path) -> None:
        run_id = record_backtest_run(
            _backtest_result(),
            base_path=str(tmp_path),
            factors=["cmo_momentum"],
            universe=["BTCUSDT"],
            split_dates={"train": "2024-01-01/2024-02-01"},
        )
        records = query_runs(base_path=tmp_path, git_commit="abc123")
        assert run_id == "20260410T100000Z-abc1234"
        assert len(records) == 1
        assert records.iloc[0]["module"] == "backtest"

    def test_record_validation_run_writes_ledger_entry(self, tmp_path) -> None:
        run_id = record_validation_run(
            result=_validation_result(),
            factor_name="cmo_momentum",
            factor_version="1.0.0",
            base_path=str(tmp_path),
            run_id="20260410T101500Z-fff1111",
            git_commit="def456",
            data_snapshot_id="snapshot-2",
            config_snapshot={"periods": [1, 3], "quantiles": 2},
            universe=["BTCUSDT"],
            split_dates={"validation": "2024-02-01/2024-03-01"},
            timeframe="1h",
        )
        records = query_runs(base_path=tmp_path, git_commit="def456")
        assert run_id == "20260410T101500Z-fff1111"
        assert len(records) == 1
        assert records.iloc[0]["module"] == "factor_validation"

    def test_record_signal_diagnostics_run_writes_ledger_entry(self, tmp_path) -> None:
        diagnostics = analyze_signal_diagnostics(_diagnostic_signals(), _diagnostic_prices(), periods=[1, 3])
        run_id = record_signal_diagnostics_run(
            result=diagnostics,
            signal_name="momentum_bundle",
            base_path=str(tmp_path),
            run_id="20260410T111500Z-ddd2222",
            git_commit="ghi789",
            data_snapshot_id="snapshot-3",
            config_snapshot={"periods": [1, 3]},
            factors=["momentum_bundle"],
            universe=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            split_dates={"diagnostics": "2024-01-01/2024-03-01"},
        )
        records = query_runs(base_path=tmp_path, git_commit="ghi789")
        assert run_id == "20260410T111500Z-ddd2222"
        assert len(records) == 1
        assert records.iloc[0]["module"] == "signal_diagnostics"

    def test_record_walkforward_run_writes_ledger_entry(self, tmp_path) -> None:
        run_id = record_walkforward_run(
            result=_walkforward_result(),
            signal_name="wf_bundle",
            base_path=str(tmp_path),
            run_id="20260411T090000Z-wf11111",
            git_commit="walk123",
            data_snapshot_id="snapshot-4",
            config_snapshot={"train_size": 4, "validation_size": 2, "test_size": 2},
            factors=["wf_bundle"],
            universe=["BTCUSDT", "ETHUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
        )
        records = query_runs(base_path=tmp_path, git_commit="walk123")
        assert run_id == "20260411T090000Z-wf11111"
        assert len(records) == 1
        assert records.iloc[0]["module"] == "walkforward"
