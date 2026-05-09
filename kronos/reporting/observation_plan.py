"""Generate read-only paper observation plans from existing research reports."""
# ruff: noqa: RUF001
# The generated Markdown is Chinese product copy; full-width punctuation is intentional.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ObservationPlan:
    """A generated read-only observation plan artifact."""

    path: Path
    source_report: Path
    verdict: str
    status: str
    next_step: str

    def summary_lines(self) -> list[str]:
        return [
            "只读观察计划",
            f"状态: {self.status}",
            f"判断: {self.verdict}",
            f"下一步: {self.next_step}",
            f"plan: {self.path}",
            f"source_report: {self.source_report}",
        ]


def generate_observation_plan(
    report_path: str | Path,
    *,
    output_path: str | Path | None = None,
    latency_bars: int = 1,
    slippage_bps: float = 5.0,
) -> ObservationPlan:
    """Generate a read-only observation plan from a research report."""
    source_report = Path(report_path)
    if not source_report.is_file():
        raise FileNotFoundError(f"Research report does not exist: {source_report}")

    run_dir = source_report.parent
    summary = _read_summary(run_dir / "auto_run_summary.json")
    summary_path = run_dir / "auto_run_summary.json" if summary is not None else None
    context = _extract_context(source_report, summary)
    verdict = _eligibility_verdict(context)
    plan_path = Path(output_path) if output_path is not None else run_dir / "paper_observation_plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = plan_path.with_suffix(".json")
    plan_path.write_text(
        _render_plan(
            source_report=source_report,
            context=context,
            verdict=verdict,
            latency_bars=latency_bars,
            slippage_bps=slippage_bps,
        ),
        encoding="utf-8",
    )
    _write_plan_metadata(
        metadata_path,
        source_report=source_report,
        summary_path=summary_path,
        context=context,
        verdict=verdict,
        latency_bars=latency_bars,
        slippage_bps=slippage_bps,
    )
    return ObservationPlan(
        path=plan_path,
        source_report=source_report,
        verdict=verdict["verdict"],
        status=verdict["status"],
        next_step=verdict["next_step"],
    )


def _extract_context(source_report: Path, summary: dict[str, Any] | None) -> dict[str, Any]:
    if summary is None:
        return {
            "data_kind": "unknown",
            "symbols": [],
            "timeframe": "未知",
            "span_days": 0.0,
            "evaluated": 0,
            "promoted": 0,
            "not_promoted": 0,
            "skipped": 0,
            "source_type": source_report.name,
        }

    summary_block = _dict(summary.get("summary"))
    config = _dict(summary.get("config_snapshot"))
    coverage = [
        item for item in _list_of_dicts(summary.get("data_coverage"))
        if str(item.get("dataset", "")).startswith("klines_")
    ]
    return {
        "data_kind": _data_kind(summary, config),
        "symbols": _string_list(summary.get("symbols")),
        "timeframe": str(summary.get("timeframe") or config.get("timeframe") or "未知"),
        "span_days": _max_span_days(coverage),
        "evaluated": _int(summary_block.get("evaluated")),
        "promoted": _int(summary_block.get("promoted")),
        "not_promoted": _int(summary_block.get("not_promoted")),
        "skipped": _int(summary_block.get("skipped")),
        "source_type": source_report.name,
    }


def _eligibility_verdict(context: dict[str, Any]) -> dict[str, str]:
    data_kind = str(context["data_kind"])
    span_days = float(context["span_days"])
    promoted = int(context["promoted"])
    evaluated = int(context["evaluated"])

    if data_kind == "synthetic":
        return {
            "status": "不建议观察",
            "verdict": "这只是 sample 流程试跑，只能证明安装和研究链路能跑通。",
            "next_step": "先同步真实行情，再重新验证。",
        }
    if span_days <= 0:
        return {
            "status": "证据不足",
            "verdict": "当前报告没有记录有效样本范围，不能判断是否适合进入只读观察。",
            "next_step": "先重跑研究报告，确认数据来源和样本范围。",
        }
    if span_days and span_days < 90:
        return {
            "status": "先补数据",
            "verdict": "当前样本不足 90 天，只适合短样本排查，不适合进入只读观察。",
            "next_step": "补足更长历史后重跑研究报告。",
        }
    if evaluated <= 0:
        return {
            "status": "证据不足",
            "verdict": "当前报告没有完成策略评估，不能生成观察建议。",
            "next_step": "先运行 quickstart 或 research workbench 形成可读结论。",
        }
    if promoted <= 0:
        return {
            "status": "暂不观察",
            "verdict": "当前没有策略通过验证，不建议进入模拟盘或只读观察。",
            "next_step": "阅读失败原因，决定改造、保留研究或淘汰。",
        }
    return {
        "status": "只读观察候选",
        "verdict": "存在通过验证的策略，可以列入只读观察候选，但这仍不是模拟盘运行或实盘建议。",
        "next_step": "先人工确认观察假设，再进入后续实时模拟盘实现。",
    }


def _render_plan(
    *,
    source_report: Path,
    context: dict[str, Any],
    verdict: dict[str, str],
    latency_bars: int,
    slippage_bps: float,
) -> str:
    symbols = ", ".join(context["symbols"]) if context["symbols"] else "未记录"
    lines = [
        "# 只读观察计划",
        "",
        "## 第一屏结论",
        "",
        f"- 状态：{verdict['status']}",
        f"- 判断：{verdict['verdict']}",
        f"- 下一步：{verdict['next_step']}",
        "- 边界：这是观察计划，不是模拟盘运行，不会发送真实订单。",
        "",
        "## 来源报告",
        "",
        f"- 报告：{source_report}",
        f"- 报告类型：{context['source_type']}",
        "",
        "## 观察对象",
        "",
        f"- 品种：{symbols}",
        f"- 周期：{context['timeframe']}",
        f"- 样本范围：约 {context['span_days']} 天",
        f"- 数据来源：{_data_kind_label(str(context['data_kind']))}",
        f"- 评估结果：{context['evaluated']} 个已评估, {context['promoted']} 个通过, "
        f"{context['not_promoted']} 个未通过, {context['skipped']} 个跳过",
        "",
        "## 虚拟订单假设",
        "",
        "- 当前不会连接交易所，不会发送真实订单。",
        "- 未来如果进入观察态，所有成交都必须标记为虚拟成交。",
        f"- 默认延迟：信号出现后等待 {latency_bars} 根 bar 再记录虚拟成交。",
        f"- 默认滑点：按 {slippage_bps:g} bps 记录成本假设。",
        "- 默认资金：不计算真实保证金占用，不代表真实账户可承受风险。",
        "",
        "## 人工闸门",
        "",
        "- 进入实时模拟盘前，需要人工确认观察对象、样本范围、虚拟成交规则和风险边界。",
        "- 只读观察结果即使未来表现较好，也不能自动升级到实盘。",
        "- 任何实盘动作必须重新经过人工审批和更强执行层验证。",
        "",
        "## 现在不应该做什么",
        "",
        "- 不要把这份计划当成收益证明。",
        "- 不要把 sample 或短样本结果当成策略有效性结论。",
        "- 不要把只读观察计划理解成已经启动模拟盘。",
    ]
    return "\n".join(lines) + "\n"


def _write_plan_metadata(
    path: Path,
    *,
    source_report: Path,
    summary_path: Path | None,
    context: dict[str, Any],
    verdict: dict[str, str],
    latency_bars: int,
    slippage_bps: float,
) -> None:
    payload = {
        "artifact_type": "kronos.paper_observation_plan",
        "schema_version": 1,
        "status": verdict["status"],
        "verdict": verdict["verdict"],
        "next_step": verdict["next_step"],
        "eligible_for_testnet_paper": verdict["status"] == "只读观察候选",
        "source_report": str(source_report),
        "source_report_sha256": _sha256_file(source_report),
        "summary_path": str(summary_path) if summary_path is not None else None,
        "summary_sha256": _sha256_file(summary_path) if summary_path is not None else None,
        "data_kind": context["data_kind"],
        "symbols": context["symbols"],
        "timeframe": context["timeframe"],
        "span_days": context["span_days"],
        "evaluated": context["evaluated"],
        "promoted": context["promoted"],
        "not_promoted": context["not_promoted"],
        "skipped": context["skipped"],
        "latency_bars": latency_bars,
        "slippage_bps": slippage_bps,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_file(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _data_kind_label(value: str) -> str:
    return {
        "synthetic": "sample 试跑",
        "local": "本地行情",
        "synced": "已同步行情",
        "unknown": "未记录",
    }.get(value, value)


def _read_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


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
