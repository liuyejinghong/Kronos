"""Tests for latest report discovery."""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from kronos.reporting import find_latest_report, summarize_report

if TYPE_CHECKING:
    from pathlib import Path


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
