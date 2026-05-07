"""Tests for latest report discovery."""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING

import kronos.reporting.latest as latest
from kronos.reporting import find_latest_report, summarize_report

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_find_latest_report_prefers_newest_product_report(tmp_path: Path) -> None:
    reports = tmp_path / "reports" / "research" / "experiments"
    older = reports / "run-a" / "auto_run_report.md"
    newer = reports / "run-b" / "research_workbench_report.md"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_text("# A\n", encoding="utf-8")
    newer.write_text("# B\n", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 20, now - 20))
    os.utime(newer, (now, now))

    report = find_latest_report(tmp_path / "reports" / "research")

    assert report is not None
    assert report.path == newer
    assert report.run_dir == newer.parent


def test_find_latest_report_prefers_summary_time_over_touched_file(tmp_path: Path) -> None:
    reports = tmp_path / "reports" / "research" / "experiments"
    older = reports / "20260501T000000Z-old" / "agent_run_report.md"
    newer = reports / "20260502T000000Z-new" / "auto_run_report.md"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_text("# Old\n", encoding="utf-8")
    newer.write_text("# New\n", encoding="utf-8")
    (older.parent / "agent_run_summary.json").write_text(
        '{"run": {"run_id": "20260501T000000Z-old"}, "started_at": "2026-05-01T00:00:00Z"}',
        encoding="utf-8",
    )
    (newer.parent / "auto_run_summary.json").write_text(
        '{"run_id": "20260502T000000Z-new", "started_at": "2026-05-02T00:00:00Z"}',
        encoding="utf-8",
    )
    now = time.time()
    os.utime(older, (now, now))
    os.utime(newer, (now - 60, now - 60))

    report = find_latest_report(tmp_path / "reports" / "research")

    assert report is not None
    assert report.path == newer


def test_find_latest_report_returns_none_without_reports(tmp_path: Path) -> None:
    assert find_latest_report(tmp_path / "reports" / "research") is None


def test_summarize_report_extracts_first_product_section(tmp_path: Path) -> None:
    report = tmp_path / "auto_run_report.md"
    report.write_text(
        "\n".join([
            "# 报告",
            "",
            "## 一句话结论",
            "",
            "本轮没有策略进入模拟盘。",
            "",
            "## 数据检查",
            "",
            "- BTCUSDT 可用",
        ]),
        encoding="utf-8",
    )

    summary = summarize_report(report)

    assert summary == ["本轮没有策略进入模拟盘。"]


def test_summarize_report_prefers_auto_run_summary_first_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(latest, "_in_docker", lambda: False)
    run_dir = tmp_path / "20260506T000000Z-quickstart"
    run_dir.mkdir()
    report = run_dir / "auto_run_report.md"
    report.write_text(
        "\n".join([
            "# Kronos 自动研究日报",
            "",
            "## 一句话结论",
            "",
            "本次自动研究已完成工作台和观察名单补证据。",
        ]),
        encoding="utf-8",
    )
    (run_dir / "auto_run_summary.json").write_text(
        json.dumps({
            "summary": {
                "run_id": "20260506T000000Z-quickstart",
                "evaluated": 1,
                "promoted": 0,
                "not_promoted": 1,
                "skipped": 0,
            },
            "run_id": "20260506T000000Z-quickstart",
            "symbols": ["BTCUSDT"],
            "timeframe": "1m",
            "data_coverage": [{
                "symbol": "BTCUSDT",
                "dataset": "klines_1m",
                "dataset_label": "1m K线",
                "span_days": 7.0,
                "bars": 10080,
            }],
            "config_snapshot": {
                "command": "quickstart",
                "data_kind": "synthetic",
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = summarize_report(report, max_lines=8)

    joined = "\n".join(summary)
    assert "本次结果" in joined
    assert "数据来源: sample 流程试跑" in joined
    assert "样本范围: BTCUSDT / 1m K线 / 约 7.0 天" in joined
    assert "评估对象: 1 个已评估, 0 个通过, 1 个未通过." in joined
    assert "可信度: 这只是安装和流程试跑, 不能证明策略有效或无效。" in joined
    assert "1 个已评估" in joined
    assert "0 个通过" in joined
    assert "1 个未通过" in joined
    assert "kronos data sync" in joined


def test_summarize_report_uses_docker_command_for_docker_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(latest, "_in_docker", lambda: True)
    run_dir = tmp_path / "20260506T000000Z-quickstart"
    run_dir.mkdir()
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
            "run_id": "20260506T000000Z-quickstart",
            "symbols": ["BTCUSDT"],
            "timeframe": "1m",
            "data_coverage": [{
                "symbol": "BTCUSDT",
                "dataset": "klines_1m",
                "span_days": 7.0,
            }],
            "config_snapshot": {"data_kind": "synthetic"},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = summarize_report(report, max_lines=8)

    assert any(
        "docker compose run --rm kronos uv run kronos data sync" in line
        for line in summary
    )
