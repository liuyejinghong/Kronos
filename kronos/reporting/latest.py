"""Find and summarize the latest product-facing Kronos report."""
# ruff: noqa: RUF001

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPORT_FILENAMES = (
    "kronos_run_status.md",
    "agent_run_report.md",
    "auto_run_report.md",
    "research_workbench_report.md",
    "agent_research_decision.md",
    "agent_research_plan.md",
    "promotion_batch_report.md",
)

PRODUCT_SECTION_HEADINGS = (
    "## 第一屏结论",
    "## 一句话结论",
    "## 当前研究目标",
    "## 产品结论",
)


@dataclass(frozen=True)
class LatestReport:
    """A discovered report and the run directory it belongs to."""

    path: Path
    run_dir: Path
    modified_at: float
    sort_timestamp: float


def find_latest_report(base_path: str | Path = "reports/research") -> LatestReport | None:
    """Return the newest product-facing report under the research reports tree."""
    base = Path(base_path)
    experiments = base / "experiments"
    if not experiments.exists():
        return None

    candidates: list[LatestReport] = []
    for filename in REPORT_FILENAMES:
        for path in experiments.glob(f"*/{filename}"):
            if path.is_file():
                stat = path.stat()
                candidates.append(
                    LatestReport(
                        path=path,
                        run_dir=path.parent,
                        modified_at=stat.st_mtime,
                        sort_timestamp=_run_sort_timestamp(path.parent, stat.st_mtime),
                    )
                )

    if not candidates:
        return None
    return max(candidates, key=lambda report: (report.sort_timestamp, str(report.path)))


def summarize_report(path: str | Path, *, max_lines: int = 18) -> list[str]:
    """Extract a compact, user-readable summary from a Markdown report."""
    report_path = Path(path)
    structured = _structured_summary(report_path)
    if structured:
        return structured[:max_lines]

    lines = report_path.read_text(encoding="utf-8").splitlines()
    section = _first_matching_section(lines, PRODUCT_SECTION_HEADINGS)
    if section:
        return section[:max_lines]

    compact = [line for line in lines if line.strip()]
    return compact[:max_lines]


def summarize_report_section(
    path: str | Path,
    *,
    headings: tuple[str, ...],
    max_lines: int = 18,
) -> list[str]:
    """Extract a specific section from a Markdown report."""
    report_path = Path(path)
    lines = report_path.read_text(encoding="utf-8").splitlines()
    section = _first_matching_section(lines, headings)
    if section:
        return section[:max_lines]
    return summarize_report(report_path, max_lines=max_lines)


def _first_matching_section(lines: list[str], headings: tuple[str, ...]) -> list[str]:
    for idx, line in enumerate(lines):
        if line.strip() not in headings:
            continue
        section: list[str] = []
        for current in lines[idx + 1 :]:
            stripped = current.strip()
            if stripped.startswith("## ") and section:
                break
            if stripped:
                section.append(stripped)
        if section:
            return section
    return []


def _structured_summary(report_path: Path) -> list[str]:
    if report_path.name != "auto_run_report.md":
        if report_path.name == "backtest_replay_report.md":
            return _replay_summary(report_path)
        return []
    summary = _read_summary(report_path.parent / "auto_run_summary.json")
    if summary is None:
        return []

    quick = _auto_run_quick_summary(summary)
    return quick if quick else []


def _replay_summary(report_path: Path) -> list[str]:
    lines = report_path.read_text(encoding="utf-8").splitlines()
    section = _first_matching_section(lines, ("## 一句话结论", "## 结果概览"))
    if section:
        return section
    compact = [line for line in lines if line.strip()]
    return compact[:18]


def _auto_run_quick_summary(payload: dict[str, Any]) -> list[str]:
    summary = _dict(payload.get("summary"))
    if not summary:
        return []

    config = _dict(payload.get("config_snapshot"))
    symbols = _string_list(payload.get("symbols"))
    timeframe = str(payload.get("timeframe") or config.get("timeframe") or "未知")
    coverage = [
        item for item in _list_of_dicts(payload.get("data_coverage"))
        if str(item.get("dataset", "")).startswith("klines_")
    ]
    max_days = _max_span_days(coverage)
    data_kind = _data_kind(payload, config)
    evaluated = _int(summary.get("evaluated"))
    promoted = _int(summary.get("promoted"))
    not_promoted = _int(summary.get("not_promoted"))
    skipped = _int(summary.get("skipped"))
    strategy_line = _strategy_line(evaluated, promoted, not_promoted, skipped)
    regime_line = _market_regime_line(payload)
    next_step = _latest_next_step(data_kind=data_kind, max_days=max_days, promoted=promoted)

    lines = [
        "本次结果",
        "数据来源: "
        + ("sample 试跑" if data_kind == "synthetic" else "本地真实/同步行情"),
        f"样本范围: {', '.join(symbols) if symbols else '未记录币种'} / {timeframe} / 约 {max_days} 天",
        f"评估对象: {strategy_line}",
        f"市场状态: {regime_line}",
        "结论: "
        + (
            f"{promoted} 个策略进入深度研究，但仍不是交易或模拟盘结论。"
            if promoted > 0
            else "当前没有策略通过验证，不建议进入组合或模拟盘。"
        ),
    ]
    if data_kind == "synthetic":
        confidence = "这是安装和流程试跑, 不能证明策略有效或无效。"
    elif max_days < 90:
        confidence = "样本不足 90 天, 只能做短样本观察, 不能称为完整复验。"
    else:
        confidence = "样本已达到 90 天级别, 可以阅读下游报告判断失败切片和改造方向。"
    lines.append(f"可信度/只读边界: {confidence}{_read_only_observation_boundary()}")
    lines.append(f"下一步: {next_step}")
    return lines


def _market_regime_line(payload: dict[str, Any]) -> str:
    regime_summaries: list[str] = []
    for review in _list_of_dicts(payload.get("evidence_reviews")):
        for slice_ in _list_of_dicts(review.get("regime_slices")):
            label = str(slice_.get("label_zh") or slice_.get("slice_id") or "").strip()
            interpretation = str(slice_.get("interpretation_zh") or "").strip()
            if not label:
                continue
            outcome = _regime_outcome_zh(str(slice_.get("outcome") or ""))
            detail = interpretation if interpretation else outcome
            regime_summaries.append(f"{label}: {detail}")

    if regime_summaries:
        return "；".join(regime_summaries[:4])
    return "本轮没有生成分市场状态证据，不能把汇总结论外推到牛市、熊市、震荡市或高波动环境。"


def _regime_outcome_zh(outcome: str) -> str:
    return {
        "supportive": "支持继续补证据，但还不能直接进入组合层",
        "weak_positive": "只有局部弱信号，只适合保留观察或状态过滤评估",
        "insufficient": "样本或有效分组不足，不能形成判断",
        "unsupported": "当前切片不支持继续升级",
    }.get(outcome, "需要打开分段报告确认")


def _read_only_observation_boundary() -> str:
    return (
        "当前只到研究报告，不会启动模拟盘、实盘或真实订单；进入只读观察前仍需定义"
        "虚拟订单、延迟、滑点和人工闸门。"
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _max_span_days(coverage: list[dict[str, Any]]) -> float:
    spans: list[float] = []
    for row in coverage:
        value = row.get("span_days")
        if isinstance(value, int | float):
            spans.append(float(value))
    return round(max(spans), 2) if spans else 0.0


def _data_kind(payload: dict[str, Any], config: dict[str, Any]) -> str:
    explicit = config.get("data_kind")
    if explicit in {"synthetic", "local", "synced"}:
        return str(explicit)
    snapshot = str(config.get("data_snapshot_id") or payload.get("data_snapshot_id") or "")
    run_id = str(payload.get("run_id") or "")
    if "sample" in snapshot or "synthetic" in snapshot or "quickstart" in run_id:
        return "synthetic"
    return "local"


def _strategy_line(evaluated: int, promoted: int, not_promoted: int, skipped: int) -> str:
    parts = [f"{evaluated} 个已评估", f"{promoted} 个通过"]
    if not_promoted:
        parts.append(f"{not_promoted} 个未通过")
    if skipped:
        parts.append(f"{skipped} 个跳过")
    return ", ".join(parts) + "."


def _latest_next_step(*, data_kind: str, max_days: float, promoted: int) -> str:
    if data_kind == "synthetic":
        command = "kronos data sync --symbols BTCUSDT --since 2026-01-01"
        if _in_docker():
            command = f"docker compose run --rm kronos uv run {command}"
        return f"先运行 `{command}` 同步真实行情，再重新验证。"
    if promoted > 0:
        return "打开完整报告查看晋升证据，再决定是否继续深度研究。"
    if max_days < 90:
        return "补足更长历史后重跑，不要先基于短样本调参。"
    return "阅读完整报告中的失败原因，再决定改造、保留观察或退休。"


def _in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("KRONOS_DOCKER") == "1"


def _run_sort_timestamp(run_dir: Path, fallback: float) -> float:
    summary = _read_summary(run_dir / "agent_run_summary.json")
    if summary is None:
        summary = _read_summary(run_dir / "auto_run_summary.json")

    if summary is not None:
        timestamp = _summary_timestamp(summary)
        if timestamp is not None:
            return timestamp
        run_id = _summary_run_id(summary) or run_dir.name
    else:
        run_id = run_dir.name

    timestamp = _timestamp_from_run_id(run_id)
    return timestamp if timestamp is not None else fallback


def _read_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _summary_timestamp(summary: dict[str, Any]) -> float | None:
    for key in ("finished_at", "completed_at", "started_at"):
        value = summary.get(key)
        if isinstance(value, str):
            timestamp = _parse_iso_timestamp(value)
            if timestamp is not None:
                return timestamp
    run = summary.get("run")
    if isinstance(run, dict):
        for key in ("finished_at", "completed_at", "started_at"):
            value = run.get(key)
            if isinstance(value, str):
                timestamp = _parse_iso_timestamp(value)
                if timestamp is not None:
                    return timestamp
    return None


def _summary_run_id(summary: dict[str, Any]) -> str | None:
    run_id = summary.get("run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    run = summary.get("run")
    if isinstance(run, dict):
        nested = run.get("run_id")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _parse_iso_timestamp(value: str) -> float | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def _timestamp_from_run_id(run_id: str) -> float | None:
    for candidate in (run_id[:15], run_id[:8]):
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
            try:
                return datetime.strptime(candidate, fmt).timestamp()
            except ValueError:
                continue
    return None
