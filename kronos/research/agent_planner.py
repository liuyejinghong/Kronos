# ruff: noqa: RUF001
"""Agent MVP planner for RD-Agent-style research loops."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kronos.research.experiments.artifacts import experiment_root
from kronos.research.knowledge_base import add_agent_decision_entry, add_agent_plan_entry


@dataclass(frozen=True)
class AgentHypothesis:
    """One agent-generated research hypothesis and its deterministic experiment plan."""

    hypothesis_id: str
    title_zh: str
    source_zh: str
    candidate_ids: list[str]
    rationale_zh: str
    experiment_plan_zh: list[str]
    tool_commands: list[str]
    success_gate_zh: str
    failure_gate_zh: str
    human_gate_zh: str
    priority: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title_zh": self.title_zh,
            "source_zh": self.source_zh,
            "candidate_ids": self.candidate_ids,
            "rationale_zh": self.rationale_zh,
            "experiment_plan_zh": self.experiment_plan_zh,
            "tool_commands": self.tool_commands,
            "success_gate_zh": self.success_gate_zh,
            "failure_gate_zh": self.failure_gate_zh,
            "human_gate_zh": self.human_gate_zh,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class AgentResearchPlan:
    """Agent MVP output for one next-research planning cycle."""

    run_id: str
    goal_zh: str
    source_summary_path: str
    source_run_id: str | None
    selected_candidates: list[dict[str, Any]]
    retirement_review_candidates: list[dict[str, Any]]
    hypotheses: list[AgentHypothesis]
    next_action_zh: str
    artifact_paths: dict[str, str]

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source_run_id": self.source_run_id,
            "selected_candidates": len(self.selected_candidates),
            "retirement_review_candidates": len(self.retirement_review_candidates),
            "hypotheses": len(self.hypotheses),
            "next_action_zh": self.next_action_zh,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "run_id": self.run_id,
            "goal_zh": self.goal_zh,
            "source_summary_path": self.source_summary_path,
            "source_run_id": self.source_run_id,
            "selected_candidates": self.selected_candidates,
            "retirement_review_candidates": self.retirement_review_candidates,
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
            "next_action_zh": self.next_action_zh,
            "artifact_paths": self.artifact_paths,
        }


@dataclass(frozen=True)
class AgentEvidenceDecision:
    """Agent interpretation of one deterministic evidence review."""

    candidate_id: str
    candidate_title: str
    factor_name: str
    evidence_json_path: str
    decision: str
    decision_label_zh: str
    rationale_zh: str
    next_step_zh: str
    supportive_slices: int
    weak_positive_slices: int
    history_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_title": self.candidate_title,
            "factor_name": self.factor_name,
            "evidence_json_path": self.evidence_json_path,
            "decision": self.decision,
            "decision_label_zh": self.decision_label_zh,
            "rationale_zh": self.rationale_zh,
            "next_step_zh": self.next_step_zh,
            "supportive_slices": self.supportive_slices,
            "weak_positive_slices": self.weak_positive_slices,
            "history_status": self.history_status,
        }


@dataclass(frozen=True)
class AgentEvidenceDecisionReport:
    """Agent MVP output after reading deterministic evidence results."""

    run_id: str
    evidence_json_paths: list[str]
    decisions: list[AgentEvidenceDecision]
    next_action_zh: str
    artifact_paths: dict[str, str]

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "evidence_reviews": len(self.evidence_json_paths),
            "decisions": len(self.decisions),
            "next_action_zh": self.next_action_zh,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "run_id": self.run_id,
            "evidence_json_paths": self.evidence_json_paths,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "next_action_zh": self.next_action_zh,
            "artifact_paths": self.artifact_paths,
        }


def run_research_agent_planner(
    *,
    summary_json_path: str | Path,
    output_base_path: str | Path,
    run_id: str,
    goal_zh: str,
) -> AgentResearchPlan:
    """Read the latest deterministic research result and propose the next experiments."""
    source_path = Path(summary_json_path)
    summary = json.loads(source_path.read_text(encoding="utf-8"))
    dispositions = _extract_candidate_dispositions(summary)
    selected_candidates = _select_next_candidates(dispositions)
    retirement_candidates = _retirement_review_candidates(dispositions)
    hypotheses = _build_hypotheses(
        goal_zh=goal_zh,
        selected_candidates=selected_candidates,
        retirement_candidates=retirement_candidates,
        source_summary=summary,
    )
    next_action = _next_action_text(hypotheses)
    run_root = experiment_root(output_base_path, run_id)
    json_path = run_root / "agent_research_plan.json"
    report_path = run_root / "agent_research_plan.md"
    artifact_paths = {
        "agent_plan_json": str(json_path),
        "agent_plan_report": str(report_path),
    }
    result = AgentResearchPlan(
        run_id=run_id,
        goal_zh=goal_zh,
        source_summary_path=str(source_path),
        source_run_id=_source_run_id(summary),
        selected_candidates=selected_candidates,
        retirement_review_candidates=retirement_candidates,
        hypotheses=hypotheses,
        next_action_zh=next_action,
        artifact_paths=artifact_paths,
    )
    json_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _write_agent_report(result, report_path)
    add_agent_plan_entry(
        title=f"Agent research plan: {run_id}",
        summary=next_action,
        factor_name=_primary_factor_name(selected_candidates),
        tags=[
            "agent_research_plan",
            "rd_agent_loop",
            "hypothesis_generation",
            run_id,
        ],
        metadata={
            "run_id": run_id,
            "goal_zh": goal_zh,
            "source_run_id": result.source_run_id,
            "source_summary_path": str(source_path),
            "selected_candidates": selected_candidates,
            "retirement_review_candidates": retirement_candidates,
            "hypotheses": [hypothesis.to_dict() for hypothesis in hypotheses],
            "artifact_paths": artifact_paths,
        },
        base_path=output_base_path,
    )
    return result


def run_research_agent_decision(
    *,
    evidence_json_paths: list[str | Path],
    output_base_path: str | Path,
    run_id: str,
) -> AgentEvidenceDecisionReport:
    """Read deterministic evidence reviews and turn them into Agent decisions."""
    if not evidence_json_paths:
        raise ValueError("agent decision requires at least one evidence JSON path")
    decisions = [
        _decision_from_evidence(Path(path))
        for path in evidence_json_paths
    ]
    next_action = _evidence_next_action(decisions)
    run_root = experiment_root(output_base_path, run_id)
    json_path = run_root / "agent_research_decision.json"
    report_path = run_root / "agent_research_decision.md"
    artifact_paths = {
        "agent_decision_json": str(json_path),
        "agent_decision_report": str(report_path),
    }
    result = AgentEvidenceDecisionReport(
        run_id=run_id,
        evidence_json_paths=[str(path) for path in evidence_json_paths],
        decisions=decisions,
        next_action_zh=next_action,
        artifact_paths=artifact_paths,
    )
    json_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _write_evidence_decision_report(result, report_path)
    add_agent_decision_entry(
        title=f"Agent research decision: {run_id}",
        summary=next_action,
        factor_name=_primary_decision_factor(decisions),
        tags=[
            "agent_research_decision",
            "rd_agent_loop",
            "result_reading",
            run_id,
        ],
        metadata={
            "run_id": run_id,
            "evidence_json_paths": [str(path) for path in evidence_json_paths],
            "decisions": [decision.to_dict() for decision in decisions],
            "artifact_paths": artifact_paths,
        },
        base_path=output_base_path,
    )
    return result


def _extract_candidate_dispositions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    workbench = summary.get("workbench")
    if isinstance(workbench, dict):
        dispositions = workbench.get("candidate_dispositions")
        if isinstance(dispositions, list):
            return [item for item in dispositions if isinstance(item, dict)]
    candidate_dispositions = summary.get("candidate_dispositions")
    if isinstance(candidate_dispositions, list):
        return [item for item in candidate_dispositions if isinstance(item, dict)]
    raise ValueError("agent planner requires candidate_dispositions in the research summary")


def _select_next_candidates(dispositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    watchlist = [
        _candidate_view(item)
        for item in dispositions
        if item.get("status") == "watchlist"
    ]
    watchlist.sort(key=_candidate_priority_score, reverse=True)
    if watchlist:
        return watchlist[:3]

    fallback = [
        _candidate_view(item)
        for item in dispositions
        if item.get("status") == "retirement_recommended"
    ]
    fallback.sort(key=_candidate_priority_score, reverse=True)
    return fallback[:2]


def _retirement_review_candidates(dispositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        _candidate_view(item)
        for item in dispositions
        if item.get("status") == "retirement_recommended"
    ]
    candidates.sort(key=lambda item: item["candidate_id"])
    return candidates


def _candidate_view(item: dict[str, Any]) -> dict[str, Any]:
    metrics = item.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "candidate_id": str(item.get("candidate_id") or item.get("factor_name") or ""),
        "candidate_title": str(item.get("candidate_title") or item.get("factor_name") or ""),
        "factor_name": str(item.get("factor_name") or ""),
        "status": str(item.get("status") or ""),
        "status_label_zh": str(item.get("status_label_zh") or ""),
        "recommendation_zh": str(item.get("recommendation_zh") or ""),
        "rationale_zh": str(item.get("rationale_zh") or ""),
        "metrics": metrics,
    }


def _candidate_priority_score(candidate: dict[str, Any]) -> float:
    metrics = candidate["metrics"]
    mean_rank_ic = _float_metric(metrics.get("mean_rank_ic"))
    top_minus_bottom = _float_metric(metrics.get("top_minus_bottom"))
    positive_ratio = _float_metric(metrics.get("walkforward_positive_test_window_ratio"))
    validation_bonus = 1.0 if metrics.get("validation_outcome") == "review" else 0.0
    return validation_bonus + positive_ratio + max(mean_rank_ic, 0.0) * 20 + max(top_minus_bottom, 0.0) * 5000


def _build_hypotheses(
    *,
    goal_zh: str,
    selected_candidates: list[dict[str, Any]],
    retirement_candidates: list[dict[str, Any]],
    source_summary: dict[str, Any],
) -> list[AgentHypothesis]:
    hypotheses: list[AgentHypothesis] = []
    for index, candidate in enumerate(selected_candidates, start=1):
        candidate_id = candidate["candidate_id"]
        factor_name = candidate["factor_name"] or candidate_id
        hypotheses.append(
            AgentHypothesis(
                hypothesis_id=f"H{index:02d}-{candidate_id}",
                title_zh=f"{candidate['candidate_title']} 可能只在特定市场状态下有效",
                source_zh="来自上一轮研究处置清单中的观察名单或相对最接近候选。",
                candidate_ids=[candidate_id],
                rationale_zh=(
                    f"{candidate['rationale_zh']} Agent 不应直接重复全量跑批，"
                    "而应先验证它是否是分币种、分波动或分趋势状态下的局部信号。"
                ),
                experiment_plan_zh=[
                    "先做候选专项证据复盘，按币种和市场状态拆开看支持切片。",
                    "如果专项复盘仍没有稳定支持，就进入退休评审，不继续参数微调。",
                    "如果只有局部支持，则把它改造成市场状态过滤器，而不是单独 alpha。",
                ],
                tool_commands=[
                    "kronos research watchlist-evidence "
                    f"--candidate {candidate_id} --min-history-days 90 --config configs/dev.toml",
                    "kronos research workbench "
                    f"--candidates {factor_name} --config configs/dev.toml",
                ],
                success_gate_zh="至少两个币种或两个市场状态切片出现稳定支持，且 walk-forward 不恶化。",
                failure_gate_zh="专项证据继续显示大部分切片不支持，或样本外均值为负。",
                human_gate_zh="只能提出观察/改造/退休建议，不能进入组合或实盘。",
                priority=index,
            )
        )

    if retirement_candidates:
        hypotheses.append(
            AgentHypothesis(
                hypothesis_id="H90-legacy-retirement-review",
                title_zh="旧策略候选的静态迁移大概率不成立，需要批量退休评审",
                source_zh="来自上一轮研究中多数候选建议退休的处置结果。",
                candidate_ids=[item["candidate_id"] for item in retirement_candidates],
                rationale_zh=(
                    "如果一批旧 A 股 / 期货候选在 90 天 crypto 数据下仍无法通过验证，"
                    "下一轮研究重点不应是重复跑同一批，而是确认哪些假设正式退休，"
                    "把研究资源转向 crypto-native 改造方向。"
                ),
                experiment_plan_zh=[
                    "对退休候选做产品评审：确认是正式退休、保留观察，还是需要新数据。",
                    "把正式退休原因写入知识库，避免下一轮 Agent 重复提出同类实验。",
                    "只保留有明确 crypto 机制解释的候选进入新假设池。",
                ],
                tool_commands=[
                    "kronos agent propose --summary-json <latest_auto_run_summary.json> "
                    "--goal \"旧策略候选退休评审\"",
                ],
                success_gate_zh="退休/保留/补数据三类处置被明确记录，下一轮候选池变小。",
                failure_gate_zh="没有形成处置结论，导致 Agent 下轮继续重复研究同一批弱候选。",
                human_gate_zh="退休是产品评审动作，Agent 只能提出建议，不能删除资产。",
                priority=90,
            )
        )

    if _promoted_count(source_summary) == 0:
        hypotheses.append(
            AgentHypothesis(
                hypothesis_id="H91-crypto-native-redesign",
                title_zh="下一轮应从旧策略参数微调转向 crypto-native 机制改造",
                source_zh="来自上一轮结果：无候选晋升，观察名单也只代表弱信号。",
                candidate_ids=[item["candidate_id"] for item in selected_candidates],
                rationale_zh=(
                    f"当前目标是：{_as_sentence(goal_zh)}上一轮没有任何候选进入组合或实盘，"
                    "说明 Agent 的下一步不应机械重复跑批，而应提出带有 crypto 市场机制的改造实验。"
                ),
                experiment_plan_zh=[
                    "优先围绕 funding、open interest、liquidation 或多周期确认设计新候选。",
                    "新候选必须先作为实验 proposal 进入验证，不直接替换旧候选状态。",
                    "实验仍调用确定性研究工具，结论以验证报告和 walk-forward 为准。",
                ],
                tool_commands=[
                    "kronos research workbench --config configs/dev.toml",
                    "kronos run today --skip-sync-data --config configs/dev.toml",
                ],
                success_gate_zh="新候选 proposal 有明确市场机制、数据需求、验证门槛和失败退出条件。",
                failure_gate_zh="只产生泛泛想法，不能落成可执行实验或无法被确定性工具验证。",
                human_gate_zh="新候选进入实现前需要人工确认，不自动改写已验证策略状态。",
                priority=91,
            )
        )

    return sorted(hypotheses, key=lambda hypothesis: hypothesis.priority)


def _write_agent_report(result: AgentResearchPlan, path: Path) -> None:
    lines = [
        f"# Kronos Agent 研究计划：{result.run_id}",
        "",
        "## 一句话结论",
        "",
        result.next_action_zh,
        "",
        "## 这次 Agent 做了什么",
        "",
        "- 读取上一轮确定性研究结果。",
        "- 选择下一轮最值得研究的候选或方向。",
        "- 提出研究假设。",
        "- 把假设转成可执行实验计划。",
        "- 明确成功、失败和人工确认边界。",
        "",
        "## 研究目标",
        "",
        result.goal_zh,
        "",
        "## 输入依据",
        "",
        f"- 来源批次：{result.source_run_id or '-'}",
        f"- 来源摘要：{result.source_summary_path}",
        "",
        "## Agent 选择的下一轮候选",
        "",
    ]
    if result.selected_candidates:
        for candidate in result.selected_candidates:
            lines.extend([
                f"### {candidate['candidate_title']}",
                "",
                f"- 候选 ID：{candidate['candidate_id']}",
                f"- 对应因子：{candidate['factor_name']}",
                f"- 当前状态：{candidate['status_label_zh'] or candidate['status']}",
                f"- 选择理由：{candidate['rationale_zh']}",
                "",
            ])
    else:
        lines.append("- 没有候选进入下一轮研究选择。")

    lines.extend(["", "## 下一轮研究假设与实验", ""])
    for hypothesis in result.hypotheses:
        lines.extend([
            f"### {hypothesis.hypothesis_id}：{hypothesis.title_zh}",
            "",
            f"- 来源：{hypothesis.source_zh}",
            f"- 候选：{', '.join(hypothesis.candidate_ids) if hypothesis.candidate_ids else '-'}",
            f"- 判断依据：{hypothesis.rationale_zh}",
            "- 实验计划：",
        ])
        lines.extend([f"  - {item}" for item in hypothesis.experiment_plan_zh])
        lines.append("- 可调用工具：")
        lines.extend([f"  - `{command}`" for command in hypothesis.tool_commands])
        lines.extend([
            f"- 成功标准：{hypothesis.success_gate_zh}",
            f"- 失败标准：{hypothesis.failure_gate_zh}",
            f"- 人工闸门：{hypothesis.human_gate_zh}",
            "",
        ])

    lines.extend(["## 退休评审池", ""])
    if result.retirement_review_candidates:
        for candidate in result.retirement_review_candidates:
            lines.append(
                f"- {candidate['candidate_title']}：{candidate['recommendation_zh']}"
            )
    else:
        lines.append("- 本轮没有退休评审候选。")

    lines.extend([
        "",
        "## 下一步",
        "",
        result.next_action_zh,
        "",
        "## 产物位置",
        "",
        f"- Agent 计划 JSON：{result.artifact_paths['agent_plan_json']}",
        f"- Agent 计划报告：{result.artifact_paths['agent_plan_report']}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_from_evidence(path: Path) -> AgentEvidenceDecision:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    supportive = _int_metric(summary.get("supportive_slices"))
    weak_positive = _int_metric(summary.get("weak_positive_slices"))
    history_status = str(payload.get("history_status") or summary.get("history_status") or "")
    decision, label, next_step = _classify_evidence_decision(
        history_status=history_status,
        supportive_slices=supportive,
        weak_positive_slices=weak_positive,
    )
    candidate_id = str(payload.get("candidate_id") or summary.get("candidate_id") or "")
    candidate_title = str(payload.get("candidate_title") or candidate_id)
    factor_name = str(payload.get("factor_name") or summary.get("factor_name") or candidate_id)
    return AgentEvidenceDecision(
        candidate_id=candidate_id,
        candidate_title=candidate_title,
        factor_name=factor_name,
        evidence_json_path=str(path),
        decision=decision,
        decision_label_zh=label,
        rationale_zh=_evidence_rationale(
            history_status=history_status,
            supportive_slices=supportive,
            weak_positive_slices=weak_positive,
        ),
        next_step_zh=next_step,
        supportive_slices=supportive,
        weak_positive_slices=weak_positive,
        history_status=history_status,
    )


def _classify_evidence_decision(
    *,
    history_status: str,
    supportive_slices: int,
    weak_positive_slices: int,
) -> tuple[str, str, str]:
    if history_status != "enough_history":
        return (
            "need_data",
            "补数据",
            "先补足历史数据，再允许 Agent 重新判断；当前不能退休也不能升级。",
        )
    if supportive_slices >= 2:
        return (
            "deeper_research",
            "进入深研",
            "进入更严格的 workbench / walk-forward 复验，但仍不能进入组合或实盘。",
        )
    if weak_positive_slices >= 2:
        return (
            "redesign_candidate",
            "候选改造",
            "保留为 crypto 改造候选，下一步改造成市场状态过滤器或组合条件。",
        )
    if weak_positive_slices == 1:
        return (
            "observe_only",
            "仅保留观察",
            "保留记录但不加码研究；除非出现新数据或新机制解释，否则不继续重复跑。",
        )
    return (
        "retire_candidate",
        "建议退休",
        "进入退休评审池，避免下一轮 Agent 重复提出同一方向。",
    )


def _evidence_rationale(
    *,
    history_status: str,
    supportive_slices: int,
    weak_positive_slices: int,
) -> str:
    if history_status != "enough_history":
        return "历史样本不足，当前证据不能支持升级或退休。"
    if supportive_slices >= 2:
        return f"出现 {supportive_slices} 个支持切片，可以进入更严格复验。"
    if weak_positive_slices:
        return (
            f"没有强支持切片，但有 {weak_positive_slices} 个弱正向切片，"
            "适合做候选改造或仅保留观察。"
        )
    return "没有强支持或弱正向切片，继续研究价值不足。"


def _write_evidence_decision_report(result: AgentEvidenceDecisionReport, path: Path) -> None:
    lines = [
        f"# Kronos Agent 结果读取：{result.run_id}",
        "",
        "## 一句话结论",
        "",
        result.next_action_zh,
        "",
        "## Agent 读取了什么",
        "",
    ]
    lines.extend([f"- {evidence_path}" for evidence_path in result.evidence_json_paths])
    lines.extend(["", "## 处置建议", ""])
    for decision in result.decisions:
        lines.extend([
            f"### {decision.candidate_title}",
            "",
            f"- 候选 ID：{decision.candidate_id}",
            f"- 对应因子：{decision.factor_name}",
            f"- 证据状态：{decision.history_status}",
            f"- 强支持切片：{decision.supportive_slices}",
            f"- 弱正向切片：{decision.weak_positive_slices}",
            f"- Agent 判断：{decision.decision_label_zh}",
            f"- 判断依据：{decision.rationale_zh}",
            f"- 下一步：{decision.next_step_zh}",
            f"- 证据 JSON：{decision.evidence_json_path}",
            "",
        ])
    lines.extend([
        "## 人工闸门",
        "",
        "- Agent 本报告只给研究处置建议。",
        "- 任何候选进入组合、风控或实盘前仍需人工确认。",
        "",
        "## 产物位置",
        "",
        f"- Agent 决策 JSON：{result.artifact_paths['agent_decision_json']}",
        f"- Agent 决策报告：{result.artifact_paths['agent_decision_report']}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _next_action_text(hypotheses: list[AgentHypothesis]) -> str:
    if not hypotheses:
        return "Agent 没有找到可推进的下一轮研究假设，需要先补上一轮研究结果。"
    first = hypotheses[0]
    return f"下一轮优先推进 {first.title_zh}，先做专项证据复盘，不安装定时器也不进入交易。"


def _evidence_next_action(decisions: list[AgentEvidenceDecision]) -> str:
    if not decisions:
        return "Agent 没有读取到专项证据结果。"
    redesign = [item for item in decisions if item.decision == "redesign_candidate"]
    if redesign:
        names = "、".join(item.candidate_title for item in redesign)
        return f"{names} 只适合进入候选改造，不进入组合或实盘。"
    observe = [item for item in decisions if item.decision == "observe_only"]
    if observe:
        names = "、".join(item.candidate_title for item in observe)
        return f"{names} 只保留观察，除非有新数据或新机制解释，否则不重复研究。"
    retired = [item for item in decisions if item.decision == "retire_candidate"]
    if retired:
        return "本轮专项证据没有支持切片，建议进入退休评审。"
    return "本轮专项证据需要补数据后再判断。"


def _source_run_id(summary: dict[str, Any]) -> str | None:
    run_id = summary.get("run_id")
    if isinstance(run_id, str):
        return run_id
    nested = summary.get("summary")
    if isinstance(nested, dict):
        nested_run_id = nested.get("run_id")
        if isinstance(nested_run_id, str):
            return nested_run_id
    return None


def _promoted_count(summary: dict[str, Any]) -> int:
    nested = summary.get("summary")
    if isinstance(nested, dict):
        promoted = nested.get("promoted")
        if isinstance(promoted, int):
            return promoted
    promoted = summary.get("promoted")
    return promoted if isinstance(promoted, int) else 0


def _primary_factor_name(candidates: list[dict[str, Any]]) -> str | None:
    if not candidates:
        return None
    factor_name = candidates[0].get("factor_name")
    return factor_name if isinstance(factor_name, str) and factor_name else None


def _primary_decision_factor(decisions: list[AgentEvidenceDecision]) -> str | None:
    if not decisions:
        return None
    return decisions[0].factor_name or None


def _float_metric(value: Any) -> float:
    if isinstance(value, int | float):
        metric = float(value)
        return metric if math.isfinite(metric) else 0.0
    return 0.0


def _int_metric(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0


def _as_sentence(value: str) -> str:
    text = value.strip().rstrip("。.!！?？")
    return f"{text}。" if text else ""


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
