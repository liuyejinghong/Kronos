# ruff: noqa: RUF001
"""Integration tests for CLI commands."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pyarrow as pa
from cli.main import app
from typer.testing import CliRunner

from kronos.factor.candidates import (
    CandidateFactorSpec,
    clear_candidates,
    register_candidate,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


def _register_test_candidates() -> None:
    clear_candidates()
    for i, (cid, family, title, impl) in enumerate([
        ("indicator_spread_regime", "trend_momentum", "指标 spread regime", "asi_spread"),
        ("signal_persistence_density", "trend_momentum", "信号持续性密度", "signal_persistence_density"),
        ("trend_pullback_tolerance", "trend_momentum", "趋势回撤容忍度", "trend_pullback_tolerance"),
        ("bar_close_pressure", "volatility_path", "bar 内收盘位置压力", "bar_close_pressure"),
        ("body_energy", "volatility_path", "body-energy 累积", "body_energy"),
        ("trend_pullback_entry", "mean_reversion", "趋势内回踩入场", "trend_pullback_entry"),
        ("range_chop_filter", "volatility_path", "range-chop 过滤器", "range_chop_filter"),
    ]):
        register_candidate(CandidateFactorSpec(
            cid, family, title, ("BTCUSDT",), i + 1, impl,
        ))


def _make_kline_table(symbol: str = "BTCUSDT", n: int = 10) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 60_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 60_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "open": pa.array([67000.0] * n, type=pa.float64()),
        "high": pa.array([67500.0] * n, type=pa.float64()),
        "low": pa.array([66800.0] * n, type=pa.float64()),
        "close": pa.array([67200.0] * n, type=pa.float64()),
        "volume": pa.array([100.0] * n, type=pa.float64()),
        "quote_volume": pa.array([6720000.0] * n, type=pa.float64()),
        "trade_count": pa.array([100] * n, type=pa.int64()),
        "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
        "venue": ["binance"] * n,
    })


def _make_variable_kline_table(symbol: str = "BTCUSDT", n: int = 90) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    opens = [67000.0 + i * 8.0 + (i % 7) * 3.0 for i in range(n)]
    closes = [price + ((i % 5) - 2) * 5.0 + i * 0.4 for i, price in enumerate(opens)]
    highs = [
        max(open_, close) + 12.0 + (i % 3)
        for i, (open_, close) in enumerate(zip(opens, closes, strict=True))
    ]
    lows = [
        min(open_, close) - 12.0 - (i % 4)
        for i, (open_, close) in enumerate(zip(opens, closes, strict=True))
    ]
    volumes = [100.0 + (i % 13) * 7.0 for i in range(n)]
    return pa.table({
        "event_time": pa.array([base + i * 60_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 60_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "open": pa.array(opens, type=pa.float64()),
        "high": pa.array(highs, type=pa.float64()),
        "low": pa.array(lows, type=pa.float64()),
        "close": pa.array(closes, type=pa.float64()),
        "volume": pa.array(volumes, type=pa.float64()),
        "quote_volume": pa.array(
            [close * volume for close, volume in zip(closes, volumes, strict=True)],
            type=pa.float64(),
        ),
        "trade_count": pa.array([100 + i for i in range(n)], type=pa.int64()),
        "taker_buy_volume": pa.array([volume * 0.52 for volume in volumes], type=pa.float64()),
        "venue": ["binance"] * n,
    })


def _make_funding_table(symbol: str = "BTCUSDT", n: int = 3) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 28_800_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + i * 28_800_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
        "mark_price": pa.array([67000.0] * n, type=pa.float64()),
    })


def _make_oi_table(symbol: str = "BTCUSDT", n: int = 3) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 300_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 300_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "sum_open_interest": pa.array([50000.0] * n, type=pa.float64()),
        "sum_open_interest_value": pa.array([3350000000.0] * n, type=pa.float64()),
    })


def _write_test_config(tmp_path: Path) -> Path:
    """Write a test config pointing to tmp_path for data."""
    config = tmp_path / "test.toml"
    data_path = str(tmp_path / "data")
    config.write_text(
        f'[runtime]\nmode = "dev"\nlog_level = "WARNING"\nlog_json = false\n\n'
        f'[data]\nbase_path = "{data_path}"\n'
    )
    return config


class TestDataStatusCLI:
    """Integration tests for 'kronos data status' command."""

    def test_status_no_data(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        result = runner.invoke(app, ["data", "status", "--symbols", "BTCUSDT", "--config", str(config)])
        assert result.exit_code == 0
        assert "no data" in result.stdout

    @patch("kronos.data.sync.fetch_klines")
    def test_status_with_data(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"

        mock_fetch.return_value = _make_kline_table(n=60)
        from kronos.data.sync import sync_klines
        sync_klines("BTCUSDT", base_path=data_path, since=1709251200000)

        result = runner.invoke(app, ["data", "status", "--symbols", "BTCUSDT", "--config", str(config)])
        assert result.exit_code == 0
        assert "klines_1m" in result.stdout
        assert "60" in result.stdout


class TestDataSyncCLI:
    """Integration tests for 'kronos data sync' command."""

    @patch("kronos.data.sync.fetch_open_interest")
    @patch("kronos.data.sync.fetch_funding_rates")
    @patch("kronos.data.sync.fetch_klines")
    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_success(
        self,
        mock_exchange: MagicMock,
        mock_klines: MagicMock,
        mock_funding: MagicMock,
        mock_oi: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)

        from kronos.data.loaders.exchange_info import SymbolInfo
        mock_exchange.return_value = [
            SymbolInfo(
                symbol="BTCUSDT", onboard_date=1569398400000,
                price_precision=2, quantity_precision=3,
                tick_size=0.01, step_size=0.001,
                status="TRADING", contract_type="PERPETUAL",
            ),
        ]
        mock_klines.return_value = _make_kline_table(n=10)
        mock_funding.return_value = _make_funding_table(n=3)
        mock_oi.return_value = _make_oi_table(n=3)

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "BTCUSDT",
            "--config", str(config),
        ])
        assert result.exit_code == 0
        assert "Data Sync Guide" in result.stdout
        assert "api_key_required: no" in result.stdout
        assert "Binance USDM public market data" in result.stdout
        assert "time_range: incremental" in result.stdout
        assert "Sync Summary" in result.stdout
        assert "BTCUSDT" in result.stdout

    @patch("kronos.data.sync.fetch_open_interest")
    @patch("kronos.data.sync.fetch_funding_rates")
    @patch("kronos.data.sync.fetch_klines")
    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_explains_bounded_since_range(
        self,
        mock_exchange: MagicMock,
        mock_klines: MagicMock,
        mock_funding: MagicMock,
        mock_oi: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)

        from kronos.data.loaders.exchange_info import SymbolInfo
        mock_exchange.return_value = [
            SymbolInfo(
                symbol="BTCUSDT", onboard_date=1569398400000,
                price_precision=2, quantity_precision=3,
                tick_size=0.01, step_size=0.001,
                status="TRADING", contract_type="PERPETUAL",
            ),
        ]
        mock_klines.return_value = _make_kline_table(n=10)
        mock_funding.return_value = _make_funding_table(n=3)
        mock_oi.return_value = _make_oi_table(n=3)

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "BTCUSDT",
            "--since", "2026-01-01",
            "--config", str(config),
        ])

        assert result.exit_code == 0
        assert "time_range: from 2026-01-01 UTC to latest closed records" in result.stdout

    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_invalid_symbol(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)
        mock_exchange.return_value = []  # No symbols

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "FAKECOIN",
            "--config", str(config),
        ])
        assert result.exit_code == 1

    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_network_error(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)
        mock_exchange.side_effect = Exception("Connection refused")

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "BTCUSDT",
            "--config", str(config),
        ])
        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Cannot connect" in output or "Connection refused" in output


class TestReportCLI:
    """Integration tests for 'kronos report' commands."""

    def test_report_latest_prints_latest_summary(self, tmp_path: Path) -> None:
        reports_path = tmp_path / "reports" / "research"
        latest = reports_path / "experiments" / "run-new" / "auto_run_report.md"
        latest.parent.mkdir(parents=True)
        latest.write_text(
            "\n".join([
                "# Kronos 自动研究日报",
                "",
                "## 一句话结论",
                "",
                "本轮没有策略进入模拟盘。",
                "",
                "## 数据同步",
                "",
                "- 使用本地数据",
            ]),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "report", "latest",
            "--reports-path", str(reports_path),
        ])

        assert result.exit_code == 0, result.output
        assert "Latest Kronos Report" in result.stdout
        assert f"report: {latest}" in result.stdout
        assert "本轮没有策略进入模拟盘。" in result.stdout

    def test_report_latest_fails_clearly_without_reports(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "report", "latest",
            "--reports-path", str(tmp_path / "reports" / "research"),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "No reports found" in output
        assert "kronos quickstart" in output

    def test_report_replay_prints_latest_replay_summary(self, tmp_path: Path) -> None:
        reports_path = tmp_path / "reports" / "research"
        replay = reports_path / "experiments" / "run-replay" / "backtest_replay_report.md"
        replay.parent.mkdir(parents=True)
        replay.write_text(
            "\n".join([
                "# 关键交易重放：run-replay",
                "",
                "## 一句话结论",
                "",
                "- 本报告只解释关键交易过程，不构成收益证明或实盘建议。",
                "- 涉及币种：BTCUSDT",
            ]),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "report", "replay",
            "--reports-path", str(reports_path),
        ])

        assert result.exit_code == 0, result.output
        assert "Backtest Replay Report" in result.stdout
        assert f"report: {replay}" in result.stdout
        assert "本报告只解释关键交易过程" in result.stdout

    def test_report_replay_fails_when_no_replay_exists(self, tmp_path: Path) -> None:
        reports_path = tmp_path / "reports" / "research"
        latest = reports_path / "experiments" / "run-new" / "auto_run_report.md"
        latest.parent.mkdir(parents=True)
        latest.write_text("## 一句话结论\n\n本轮没有策略进入模拟盘。\n", encoding="utf-8")

        result = runner.invoke(app, [
            "report", "replay",
            "--reports-path", str(reports_path),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "No backtest replay reports found" in output
        assert "先跑一次回放或研究工作台" in output

    def test_report_regime_prints_latest_regime_summary(self, tmp_path: Path) -> None:
        reports_path = tmp_path / "reports" / "research"
        report = reports_path / "experiments" / "run-regime" / "watchlist_evidence_report.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "\n".join([
                "# 观察名单补证据专项报告：range_chop_filter",
                "",
                "## 分市场状态证据",
                "",
                "| 切片 | 样本 | 结论 | mean_rank_ic | top_minus_bottom | 解释 |",
                "|---|---:|---|---:|---:|---|",
                "| 高波动 | 42 | 支持继续补证据 | 0.12 | 0.08 | 该切片支持继续补证据，但还不能直接进入组合层。 |",
            ]),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "report", "regime",
            "--reports-path", str(reports_path),
        ])

        assert result.exit_code == 0, result.output
        assert "Market Regime Evidence" in result.stdout
        assert "分市场状态证据" in result.stdout
        assert f"report: {report}" in result.stdout

    def test_report_observation_prints_latest_boundary_summary(self, tmp_path: Path) -> None:
        reports_path = tmp_path / "reports" / "research"
        report = reports_path / "experiments" / "run-observation" / "research_workbench_report.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "\n".join([
                "# 研究工作台报告",
                "",
                "## 模拟盘边界",
                "",
                "- 当前版本只到研究报告和 Agent 复盘，不会启动实时模拟盘。",
                "- 实时模拟盘需要 Binance 实时行情和只读 API Key，属于 v0.4.0 预留能力。",
            ]),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "report", "observation",
            "--reports-path", str(reports_path),
        ])

        assert result.exit_code == 0, result.output
        assert "Read-Only Observation Boundary" in result.stdout
        assert "模拟盘边界" in result.stdout
        assert f"report: {report}" in result.stdout

    def test_report_observation_fails_with_next_step_hint(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "report", "observation",
            "--reports-path", str(tmp_path / "reports" / "research"),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "No read-only observation reports found" in output
        assert "先跑 `kronos research workbench` 或 `kronos report replay`" in output

    def test_report_regime_fails_without_regime_report(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "report", "regime",
            "--reports-path", str(tmp_path / "reports" / "research"),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "No market-regime reports found" in output
        assert "watchlist-evidence" in output

    def test_report_observation_fails_without_observation_report(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "report", "observation",
            "--reports-path", str(tmp_path / "reports" / "research"),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "No read-only observation reports found" in output
        assert "research workbench" in output

    def test_report_observation_plan_generates_from_latest_report(self, tmp_path: Path) -> None:
        reports_path = tmp_path / "reports" / "research"
        run_dir = reports_path / "experiments" / "run-plan"
        run_dir.mkdir(parents=True)
        report = run_dir / "auto_run_report.md"
        report.write_text("# Kronos 自动研究日报\n", encoding="utf-8")
        (run_dir / "auto_run_summary.json").write_text(
            json.dumps({
                "summary": {
                    "evaluated": 1,
                    "promoted": 1,
                    "not_promoted": 0,
                    "skipped": 0,
                },
                "run_id": "run-plan",
                "symbols": ["BTCUSDT"],
                "timeframe": "15m",
                "data_coverage": [{
                    "symbol": "BTCUSDT",
                    "dataset": "klines_15m",
                    "span_days": 120.0,
                }],
                "config_snapshot": {"data_kind": "local"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "report", "observation-plan",
            "--reports-path", str(reports_path),
        ])

        plan = run_dir / "paper_observation_plan.md"
        assert result.exit_code == 0, result.output
        assert "Paper Observation Plan" in result.stdout
        assert "只读观察候选" in result.stdout
        assert f"plan: {plan}" in result.stdout
        assert plan.exists()
        assert "不会发送真实订单" in plan.read_text(encoding="utf-8")

    def test_report_observation_plan_generates_from_specified_report(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "reports" / "research" / "experiments" / "specified-plan"
        run_dir.mkdir(parents=True)
        report = run_dir / "auto_run_report.md"
        report.write_text("# Kronos 自动研究日报\n", encoding="utf-8")
        (run_dir / "auto_run_summary.json").write_text(
            json.dumps({
                "summary": {
                    "evaluated": 1,
                    "promoted": 0,
                    "not_promoted": 1,
                    "skipped": 0,
                },
                "run_id": "specified-plan",
                "symbols": ["BTCUSDT"],
                "timeframe": "15m",
                "data_coverage": [{
                    "symbol": "BTCUSDT",
                    "dataset": "klines_15m",
                    "span_days": 120.0,
                }],
                "config_snapshot": {"data_kind": "local"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["report", "observation-plan", str(report)])

        assert result.exit_code == 0, result.output
        assert "暂不观察" in result.stdout
        assert f"source_report: {report}" in result.stdout
        assert (run_dir / "paper_observation_plan.md").exists()

    def test_report_observation_plan_fails_for_missing_report_path(self, tmp_path: Path) -> None:
        missing_report = tmp_path / "missing" / "auto_run_report.md"

        result = runner.invoke(app, ["report", "observation-plan", str(missing_report)])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "Research report does not exist" in output
        assert "report latest" in output

    def test_report_observation_plan_fails_without_reports(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "report", "observation-plan",
            "--reports-path", str(tmp_path / "reports" / "research"),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "No reports found" in output
        assert "只读观察计划" in output


class TestQuickstartCLI:
    """Integration tests for 'kronos quickstart' command."""

    def test_quickstart_uses_step_labels_in_output(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)

        result = runner.invoke(app, [
            "quickstart",
            "--config", str(config),
            "--skip-data-gen",
            "--symbols", "BTCUSDT",
        ])

        assert result.exit_code == 0, result.output
        assert "第 1 步 / 检查本地数据" in result.stdout
        assert "第 2 步 / 正在注册内置策略" in result.stdout
        assert "第 3 步 / 正在运行最小研究循环" in result.stdout
        assert "接下来可以做什么" in result.stdout


class TestStrategyCLI:
    """Integration tests for 'kronos strategy' commands."""

    def setup_method(self) -> None:
        clear_candidates()

    def teardown_method(self) -> None:
        clear_candidates()

    def test_init_validate_smoke_and_register_strategy_config(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        strategies_path = tmp_path / "strategies"

        from kronos.data.seed import generate_sample_klines
        from kronos.factor.candidates import list_candidate_factors

        generate_sample_klines("BTCUSDT", base_path=data_path, days=7)

        init_result = runner.invoke(app, [
            "strategy", "init-r-breaker",
            "--id", "my_r_breaker",
            "--symbols", "BTCUSDT",
            "--timeframe", "15m",
            "--output-dir", str(strategies_path),
        ])

        strategy_path = strategies_path / "my_r_breaker.toml"
        assert init_result.exit_code == 0, init_result.output
        assert strategy_path.exists()
        assert "Strategy Config Created" in init_result.stdout
        assert "quickstart uses 1m sample data" in init_result.stdout
        assert "空跑确认信号能算出来: kronos strategy smoke-test" in init_result.stdout
        assert "进入候选池, 让 Agent 和报告能看到它: kronos strategy register" in init_result.stdout

        validate_result = runner.invoke(app, [
            "strategy", "validate",
            str(strategy_path),
        ])

        assert validate_result.exit_code == 0, validate_result.output
        assert "Strategy Config Valid" in validate_result.stdout
        assert "trading_enabled: no" in validate_result.stdout

        smoke_result = runner.invoke(app, [
            "strategy", "smoke-test",
            str(strategy_path),
            "--config", str(config),
        ])

        assert smoke_result.exit_code == 0, smoke_result.output
        assert "Strategy Smoke Test" in smoke_result.stdout
        assert "status: 通过" in smoke_result.stdout
        assert "symbols_checked: 1" in smoke_result.stdout
        assert "trading_enabled: no" in smoke_result.stdout

        register_result = runner.invoke(app, [
            "strategy", "register",
            str(strategy_path),
            "--config", str(config),
        ])

        assert register_result.exit_code == 0, register_result.output
        assert "Strategy Registered" in register_result.stdout
        assert "candidate_id: my_r_breaker" in register_result.stdout
        assert "visible_to_agent: yes" in register_result.stdout
        assert "打开 Agent 复盘这个候选: kronos agent start" in register_result.stdout

        candidates = list_candidate_factors()
        assert len(candidates) == 1
        assert candidates[0].candidate_id == "my_r_breaker"
        assert candidates[0].origin == "user_config"

    def test_strategy_draft_generates_validate_ready_toml(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "strategy", "draft",
            "--prompt", "我想做 BTCUSDT 和 ETHUSDT 的 R-breaker 日内突破, 15m 周期",
            "--id", "drafted_r_breaker",
            "--output-dir", str(tmp_path),
        ])

        strategy_path = tmp_path / "drafted_r_breaker.toml"
        assert result.exit_code == 0, result.output
        assert strategy_path.exists()
        assert "Strategy Draft" in result.stdout
        assert "status: 已生成草案" in result.stdout
        assert "draft_toml:" in result.stdout
        assert "trading_enabled: no" in result.stdout
        assert "下一步: 先把草案当作研究配置" in result.stdout
        assert "检查配置是否完整: kronos strategy validate" in result.stdout
        assert "空跑确认信号能算出来: kronos strategy smoke-test" in result.stdout
        assert "进入候选池, 让 Agent 和报告能看到它: kronos strategy register" in result.stdout

        validate_result = runner.invoke(app, [
            "strategy", "validate",
            str(strategy_path),
        ])
        assert validate_result.exit_code == 0, validate_result.output
        assert "Strategy Config Valid" in validate_result.stdout

    def test_strategy_draft_clarifies_missing_fields(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "strategy", "draft",
            "--prompt", "我想做一个日内突破策略",
            "--output-dir", str(tmp_path),
        ])

        assert result.exit_code == 0, result.output
        assert "status: 需要澄清" in result.stdout
        assert "unresolved: 品种; 周期" in result.stdout
        assert "draft_toml:" not in result.stdout
        assert not list(tmp_path.glob("*.toml"))

    def test_strategy_draft_rejects_unsupported_template(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [
            "strategy", "draft",
            "--prompt", "我想做 BTCUSDT 1h 均线金叉策略",
            "--output-dir", str(tmp_path),
        ])

        assert result.exit_code == 0, result.output
        assert "status: 当前模板不支持" in result.stdout
        assert "unsupported_reason:" in result.stdout
        assert "draft_toml:" not in result.stdout
        assert not list(tmp_path.glob("*.toml"))

    def test_strategy_draft_in_docker_prints_container_commands(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr("cli.main._in_docker", lambda: True)

        result = runner.invoke(app, [
            "strategy", "draft",
            "--prompt", "我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期",
            "--id", "docker_draft",
            "--output-dir", str(tmp_path),
        ])

        assert result.exit_code == 0, result.output
        assert "docker compose run --rm kronos uv run kronos strategy validate" in result.stdout
        assert "docker compose run --rm kronos uv run kronos strategy smoke-test" in result.stdout
        assert "docker compose run --rm kronos uv run kronos strategy register" in result.stdout

    def test_strategy_smoke_test_reports_each_symbol(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        strategies_path = tmp_path / "strategies"

        from kronos.data.seed import generate_sample_klines

        generate_sample_klines("BTCUSDT", base_path=data_path, days=7)
        strategy_path = strategies_path / "multi_symbol.toml"
        strategies_path.mkdir(parents=True, exist_ok=True)
        strategy_path.write_text(
            """
[strategy]
id = "multi_symbol"
name = "Multi Symbol"
kind = "r_breaker"

[universe]
symbols = ["BTCUSDT", "ETHUSDT"]
timeframe = "15m"

[params]
atr_period = 14
volatility_multiplier = 1.5
""".strip(),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "strategy", "smoke-test",
            str(strategy_path),
            "--config", str(config),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "status: 未通过" in output
        assert "symbols_checked: 2" in output
        assert "failed_symbols: ETHUSDT" in output
        assert "--- symbol: BTCUSDT ---" in output
        assert "--- symbol: ETHUSDT ---" in output

    def test_register_blocks_when_smoke_test_fails(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        strategies_path = tmp_path / "strategies"

        init_result = runner.invoke(app, [
            "strategy", "init-r-breaker",
            "--id", "blocked_r_breaker",
            "--symbols", "BTCUSDT",
            "--output-dir", str(strategies_path),
        ])
        strategy_path = strategies_path / "blocked_r_breaker.toml"
        assert init_result.exit_code == 0, init_result.output

        register_result = runner.invoke(app, [
            "strategy", "register",
            str(strategy_path),
            "--config", str(config),
        ])

        output = register_result.stdout + (register_result.stderr or "")
        assert register_result.exit_code == 1
        assert "registration: blocked" in output
        assert "本地没有" in output

    def test_strategy_missing_host_path_in_docker_shows_path_hint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("cli.main._in_docker", lambda: True)

        result = runner.invoke(app, [
            "strategy", "smoke-test",
            "/Users/ethan/.kronos/strategies/r_breaker.toml",
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "Strategy config invalid" in output
        assert "Docker path hint" in output
        assert "/root/.kronos/strategies/r_breaker.toml" in output


class TestResearchPromotionCLI:
    """Integration tests for 'kronos research promote-candidates' command."""

    def setup_method(self) -> None:
        _register_test_candidates()

    def teardown_method(self) -> None:
        clear_candidates()

    def test_promote_candidates_requires_local_data(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)

        result = runner.invoke(app, [
            "research", "promote-candidates",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--periods", "1",
            "--train-size", "12",
            "--validation-size", "6",
            "--test-size", "6",
            "--config", str(config),
        ])

        output = result.stdout + (result.stderr or "")
        assert result.exit_code == 1
        assert "Cannot run promotion batch" in output

    def test_promote_candidates_preflight_reports_ready_data(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"

        from kronos.data.storage.parquet_store import write_partition

        write_partition(
            _make_variable_kline_table(n=90),
            data_path,
            "BTCUSDT",
            "klines_1m",
            2024,
            3,
        )
        write_partition(
            _make_funding_table(n=3),
            data_path,
            "BTCUSDT",
            "funding",
            2024,
            3,
        )

        result = runner.invoke(app, [
            "research", "promote-candidates",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--timeframe", "1m",
            "--preflight-only",
            "--config", str(config),
        ])

        assert result.exit_code == 0, result.output
        assert "Promotion Preflight" in result.stdout
        assert "ready: yes" in result.stdout

    def test_promote_candidates_writes_batch_summary(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        reports_path = tmp_path / "reports"

        from kronos.data.storage.parquet_store import write_partition

        write_partition(
            _make_variable_kline_table(n=90),
            data_path,
            "BTCUSDT",
            "klines_1m",
            2024,
            3,
        )
        write_partition(
            _make_funding_table(n=3),
            data_path,
            "BTCUSDT",
            "funding",
            2024,
            3,
        )

        result = runner.invoke(app, [
            "research", "promote-candidates",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--timeframe", "1m",
            "--periods", "1",
            "--train-size", "12",
            "--validation-size", "6",
            "--test-size", "6",
            "--step-size", "6",
            "--batch-id", "test-batch",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        assert result.exit_code == 0, result.output
        assert "Promotion Batch Summary" in result.stdout
        assert "evaluated: 1" in result.stdout
        assert "artifact:" in result.stdout
        assert "report:" in result.stdout
        assert (
            reports_path
            / "experiments"
            / "test-batch"
            / "promotion_batch_summary.json"
        ).exists()
        assert (
            reports_path
            / "experiments"
            / "test-batch"
            / "promotion_batch_report.md"
        ).exists()

    def test_workbench_writes_pm_report_and_failure_groups(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        reports_path = tmp_path / "reports"

        from kronos.data.storage.parquet_store import write_partition

        write_partition(
            _make_variable_kline_table(n=90),
            data_path,
            "BTCUSDT",
            "klines_1m",
            2024,
            3,
        )
        write_partition(
            _make_funding_table(n=3),
            data_path,
            "BTCUSDT",
            "funding",
            2024,
            3,
        )

        result = runner.invoke(app, [
            "research", "workbench",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--timeframe", "1m",
            "--periods", "1",
            "--train-size", "12",
            "--validation-size", "6",
            "--test-size", "6",
            "--step-size", "6",
            "--batch-id", "test-workbench",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        pm_report = (
            reports_path
            / "experiments"
            / "test-workbench"
            / "research_workbench_report.md"
        )
        failure_groups = (
            reports_path
            / "experiments"
            / "test-workbench"
            / "failure_reason_groups.json"
        )
        candidate_dispositions = (
            reports_path
            / "experiments"
            / "test-workbench"
            / "candidate_dispositions.json"
        )
        candidate_disposition_report = (
            reports_path
            / "experiments"
            / "test-workbench"
            / "candidate_disposition_report.md"
        )
        watchlist_reviews = (
            reports_path
            / "experiments"
            / "test-workbench"
            / "watchlist_reviews.json"
        )
        watchlist_review_report = (
            reports_path
            / "experiments"
            / "test-workbench"
            / "watchlist_review_report.md"
        )

        assert result.exit_code == 0, result.output
        assert "Research Workbench Summary" in result.stdout
        assert "pm_report:" in result.stdout
        assert "candidate_dispositions:" in result.stdout
        assert "watchlist_reviews:" in result.stdout
        assert pm_report.exists()
        assert failure_groups.exists()
        assert candidate_dispositions.exists()
        assert candidate_disposition_report.exists()
        assert watchlist_reviews.exists()
        assert watchlist_review_report.exists()
        report_text = pm_report.read_text(encoding="utf-8")
        assert "一句话结论" in report_text
        assert "funding" in report_text
        assert "交易语言解读" in report_text
        assert "预测方向" in report_text
        assert "模拟盘边界" in report_text
        assert "失败原因分层" in report_text
        assert "候选处置清单" in report_text
        assert "观察名单二次复盘" in report_text

    def test_watchlist_evidence_writes_focused_report(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        reports_path = tmp_path / "reports"

        from kronos.data.storage.parquet_store import write_partition

        write_partition(
            _make_variable_kline_table(n=120),
            data_path,
            "BTCUSDT",
            "klines_1m",
            2024,
            3,
        )

        result = runner.invoke(app, [
            "research", "watchlist-evidence",
            "--symbols", "BTCUSDT",
            "--candidate", "range_chop_filter",
            "--timeframe", "1m",
            "--periods", "1",
            "--min-history-days", "0",
            "--batch-id", "test-watchlist-evidence",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        evidence_report = (
            reports_path
            / "experiments"
            / "test-watchlist-evidence"
            / "watchlist_evidence_report.md"
        )
        evidence_json = (
            reports_path
            / "experiments"
            / "test-watchlist-evidence"
            / "watchlist_evidence_review.json"
        )

        assert result.exit_code == 0, result.output
        assert "Watchlist Evidence Summary" in result.stdout
        assert "evidence_report:" in result.stdout
        assert evidence_report.exists()
        assert evidence_json.exists()
        report_text = evidence_report.read_text(encoding="utf-8")
        assert "观察名单补证据专项报告" in report_text
        assert "分币种证据" in report_text
        assert "分市场状态证据" in report_text
        assert "候选改造评估" in report_text

    def test_auto_run_writes_daily_report_and_summary(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        reports_path = tmp_path / "reports"

        from kronos.data.storage.parquet_store import write_partition

        write_partition(
            _make_variable_kline_table(n=120),
            data_path,
            "BTCUSDT",
            "klines_1m",
            2024,
            3,
        )
        write_partition(
            _make_funding_table(n=3),
            data_path,
            "BTCUSDT",
            "funding",
            2024,
            3,
        )

        result = runner.invoke(app, [
            "research", "auto-run",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--timeframe", "1m",
            "--periods", "1",
            "--train-size", "12",
            "--validation-size", "6",
            "--test-size", "6",
            "--step-size", "6",
            "--min-history-days", "0",
            "--run-id", "test-auto-run",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        auto_report = (
            reports_path
            / "experiments"
            / "test-auto-run"
            / "auto_run_report.md"
        )
        auto_summary = (
            reports_path
            / "experiments"
            / "test-auto-run"
            / "auto_run_summary.json"
        )
        workbench_report = (
            reports_path
            / "experiments"
            / "test-auto-run-workbench"
            / "research_workbench_report.md"
        )
        evidence_report = (
            reports_path
            / "experiments"
            / "test-auto-run-evidence-range_chop_filter"
            / "watchlist_evidence_report.md"
        )
        body_energy_report = (
            reports_path
            / "experiments"
            / "test-auto-run-evidence-body_energy"
            / "watchlist_evidence_report.md"
        )

        assert result.exit_code == 0, result.output
        assert "Auto Runner Summary" in result.stdout
        assert "daily_report:" in result.stdout
        assert auto_report.exists()
        assert auto_summary.exists()
        assert workbench_report.exists()
        assert evidence_report.exists()
        assert body_energy_report.exists()

        report_text = auto_report.read_text(encoding="utf-8")
        assert "Kronos 自动研究日报" in report_text
        assert "不会自动下单" in report_text
        assert "kronos report latest" in report_text
        assert "模拟盘边界" in report_text
        assert "90 天复验已完成" not in report_text
        assert "当前样本约" in report_text

        summary = json.loads(auto_summary.read_text(encoding="utf-8"))
        assert summary["summary"]["run_id"] == "test-auto-run"
        assert summary["summary"]["evidence_reviews"] == 2
        assert summary["artifact_paths"]["workbench_report"] == str(workbench_report)
        assert summary["config_snapshot"]["command"] == "research auto-run"

    def test_run_today_writes_system_status_and_wraps_auto_run(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"
        reports_path = tmp_path / "reports"

        from kronos.data.storage.parquet_store import write_partition

        write_partition(
            _make_variable_kline_table(n=120),
            data_path,
            "BTCUSDT",
            "klines_1m",
            2024,
            3,
        )
        write_partition(
            _make_funding_table(n=3),
            data_path,
            "BTCUSDT",
            "funding",
            2024,
            3,
        )

        result = runner.invoke(app, [
            "run", "today",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--timeframe", "1m",
            "--periods", "1",
            "--train-size", "12",
            "--validation-size", "6",
            "--test-size", "6",
            "--step-size", "6",
            "--min-history-days", "0",
            "--max-data-age-hours", "0",
            "--run-id", "test-kronos-run",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        status_report = (
            reports_path
            / "experiments"
            / "test-kronos-run"
            / "kronos_run_status.md"
        )
        status_json = (
            reports_path
            / "experiments"
            / "test-kronos-run"
            / "kronos_run_status.json"
        )
        auto_report = (
            reports_path
            / "experiments"
            / "test-kronos-run-research"
            / "auto_run_report.md"
        )

        assert result.exit_code == 0, result.output
        assert "Kronos Run Summary" in result.stdout
        assert "status: success" in result.stdout
        assert status_report.exists()
        assert status_json.exists()
        assert auto_report.exists()

        report_text = status_report.read_text(encoding="utf-8")
        assert "Kronos 运行状态" in report_text
        assert "整体状态" in report_text
        assert "成功" in report_text
        assert "自动研究日报" in report_text

        summary = json.loads(status_json.read_text(encoding="utf-8"))
        assert summary["summary"]["run_id"] == "test-kronos-run"
        assert summary["summary"]["status"] == "success"
        assert summary["artifact_paths"]["auto_run_report"] == str(auto_report)

    def test_run_today_writes_failure_status_when_data_is_missing(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        reports_path = tmp_path / "reports"

        result = runner.invoke(app, [
            "run", "today",
            "--symbols", "BTCUSDT",
            "--candidates", "indicator_spread_regime",
            "--timeframe", "1m",
            "--periods", "1",
            "--min-history-days", "90",
            "--run-id", "test-kronos-run-failed",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        status_report = (
            reports_path
            / "experiments"
            / "test-kronos-run-failed"
            / "kronos_run_status.md"
        )
        status_json = (
            reports_path
            / "experiments"
            / "test-kronos-run-failed"
            / "kronos_run_status.json"
        )

        assert result.exit_code == 1
        assert "status: failed" in result.stdout
        assert status_report.exists()
        assert status_json.exists()

        report_text = status_report.read_text(encoding="utf-8")
        assert "整体状态" in report_text
        assert "失败" in report_text
        assert "缺少 BTCUSDT / 1m K线数据" in report_text

        summary = json.loads(status_json.read_text(encoding="utf-8"))
        assert summary["summary"]["status"] == "failed"
        assert summary["failure_reason"].startswith("数据检查未通过")


class TestAgentCLI:
    """Integration tests for Agent MVP commands."""

    def test_agent_status_outputs_no_active_run(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        runtime_path = tmp_path / "agent_runtime"

        result = runner.invoke(app, [
            "agent", "status",
            "--runtime-path", str(runtime_path),
            "--config", str(config),
        ])

        assert result.exit_code == 0, result.output
        assert "Kronos Agent Status" in result.stdout
        assert "active: no" in result.stdout
        assert "pending_count: 0" in result.stdout
        assert "当前没有正在运行的 Agent 任务" in result.stdout

    def test_agent_status_outputs_current_run(self, tmp_path: Path) -> None:
        from kronos.agent.supervisor import AgentSupervisor

        config = _write_test_config(tmp_path)
        runtime_path = tmp_path / "agent_runtime"
        AgentSupervisor(runtime_path).start_run(
            run_id="test-agent-run",
            goal_zh="验证下一轮候选。",
            task_id="task-1",
            task_title_zh="生成研究假设",
        )

        result = runner.invoke(app, [
            "agent", "status",
            "--runtime-path", str(runtime_path),
            "--config", str(config),
        ])

        assert result.exit_code == 0, result.output
        assert "active: yes" in result.stdout
        assert "current_run: test-agent-run" in result.stdout
        assert "run_status: running" in result.stdout
        assert "current_task: task-1" in result.stdout
        assert "task_status: running" in result.stdout
        assert "last_event_type: run_started" in result.stdout

    def test_agent_propose_writes_research_plan(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        reports_path = tmp_path / "reports"
        summary_path = tmp_path / "auto_run_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": "source-run",
                    "summary": {"promoted": 0},
                    "workbench": {
                        "candidate_dispositions": [
                            {
                                "candidate_id": "multi_timeframe_confirmation",
                                "candidate_title": "Multi Timeframe Confirmation",
                                "factor_name": "multi_timeframe_confirmation",
                                "status": "watchlist",
                                "status_label_zh": "观察名单",
                                "recommendation_zh": "保留观察",
                                "rationale_zh": "基础验证出现弱信号, 但未达到晋升门槛。",
                                "metrics": {
                                    "validation_outcome": "review",
                                    "mean_rank_ic": 0.003,
                                    "top_minus_bottom": 0.00002,
                                    "walkforward_positive_test_window_ratio": 0.53,
                                },
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "agent", "propose",
            "--summary-json", str(summary_path),
            "--run-id", "test-agent-plan",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        report_path = reports_path / "experiments" / "test-agent-plan" / "agent_research_plan.md"
        plan_json_path = (
            reports_path
            / "experiments"
            / "test-agent-plan"
            / "agent_research_plan.json"
        )

        assert result.exit_code == 0, result.output
        assert "Kronos Agent Plan" in result.stdout
        assert "hypotheses:" in result.stdout
        assert report_path.exists()
        assert plan_json_path.exists()
        assert "下一轮研究假设与实验" in report_path.read_text(encoding="utf-8")

    def test_agent_conclude_writes_decision_report(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        reports_path = tmp_path / "reports"
        evidence_path = tmp_path / "watchlist_evidence_review.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "summary": {
                        "candidate_id": "multi_timeframe_confirmation",
                        "factor_name": "multi_timeframe_confirmation",
                        "history_status": "enough_history",
                        "supportive_slices": 0,
                        "weak_positive_slices": 1,
                    },
                    "candidate_id": "multi_timeframe_confirmation",
                    "candidate_title": "Multi Timeframe Confirmation",
                    "factor_name": "multi_timeframe_confirmation",
                    "history_status": "enough_history",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "agent", "conclude",
            "--evidence-json", str(evidence_path),
            "--run-id", "test-agent-decision",
            "--output-path", str(reports_path),
            "--config", str(config),
        ])

        report_path = (
            reports_path
            / "experiments"
            / "test-agent-decision"
            / "agent_research_decision.md"
        )
        decision_json_path = (
            reports_path
            / "experiments"
            / "test-agent-decision"
            / "agent_research_decision.json"
        )

        assert result.exit_code == 0, result.output
        assert "Kronos Agent Decision" in result.stdout
        assert report_path.exists()
        assert decision_json_path.exists()
        assert "处置建议" in report_path.read_text(encoding="utf-8")

    def test_agent_run_once_writes_cycle_report(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        reports_path = tmp_path / "reports"
        summary_path = tmp_path / "auto_run_summary.json"
        evidence_path = tmp_path / "watchlist_evidence_review.json"
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": "source-run",
                    "summary": {"promoted": 0},
                    "workbench": {
                        "candidate_dispositions": [
                            {
                                "candidate_id": "trend_pullback_entry",
                                "candidate_title": "Trend Pullback Entry",
                                "factor_name": "trend_pullback_entry",
                                "status": "watchlist",
                                "status_label_zh": "观察名单",
                                "recommendation_zh": "保留观察",
                                "rationale_zh": "基础验证出现弱信号, 但未达到晋升门槛。",
                                "metrics": {
                                    "validation_outcome": "review",
                                    "mean_rank_ic": 0.002,
                                    "top_minus_bottom": 0.00001,
                                    "walkforward_positive_test_window_ratio": 0.52,
                                },
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        evidence_path.write_text(
            json.dumps(
                {
                    "summary": {
                        "candidate_id": "trend_pullback_entry",
                        "factor_name": "trend_pullback_entry",
                        "history_status": "enough_history",
                        "supportive_slices": 0,
                        "weak_positive_slices": 4,
                    },
                    "candidate_id": "trend_pullback_entry",
                    "candidate_title": "Trend Pullback Entry",
                    "factor_name": "trend_pullback_entry",
                    "history_status": "enough_history",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, [
            "agent", "run-once",
            "--summary-json", str(summary_path),
            "--evidence-json", str(evidence_path),
            "--run-id", "test-agent-cycle",
            "--output-path", str(reports_path),
            "--runtime-path", str(tmp_path / "agent_runtime"),
            "--config", str(config),
        ])

        run_dir = reports_path / "experiments" / "test-agent-cycle"
        report_path = run_dir / "agent_run_report.md"
        summary_output_path = run_dir / "agent_run_summary.json"
        events_path = run_dir / "agent_events.jsonl"

        assert result.exit_code == 0, result.output
        assert "Kronos Agent Run Once" in result.stdout
        assert "status: completed" in result.stdout
        assert "tools: 2" in result.stdout
        assert report_path.exists()
        assert summary_output_path.exists()
        assert events_path.exists()
        runtime_status_path = tmp_path / "agent_runtime" / "agent_supervisor_status.json"
        assert runtime_status_path.exists()
        report_text = report_path.read_text(encoding="utf-8")
        assert "Kronos Agent 研究报告" in report_text
        assert "下一步" in report_text
