# ruff: noqa: RUF001
"""Minimal Agent run report writers."""

from __future__ import annotations

import json
from pathlib import Path

from kronos.agent.events import redact_secret_like_values
from kronos.agent.types import (
    AgentArtifactRef,
    AgentErrorRef,
    AgentEvent,
    AgentOutput,
    AgentRun,
    AgentTaskStatus,
)

AGENT_RUN_SUMMARY_FILENAME = "agent_run_summary.json"
AGENT_RUN_REPORT_FILENAME = "agent_run_report.md"
AGENT_ERRORS_FILENAME = "agent_errors.md"


def write_agent_run_summary(
    *,
    run: AgentRun,
    run_dir: str | Path,
    outputs: list[AgentOutput] | None = None,
    events: list[AgentEvent] | None = None,
) -> Path:
    """Write the machine-readable Agent run summary."""
    target_dir = Path(run_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / AGENT_RUN_SUMMARY_FILENAME
    payload = {
        "run": run.model_dump(mode="json"),
        "outputs": [output.model_dump(mode="json") for output in outputs or []],
        "event_count": len(events or []),
        "events": [event.model_dump(mode="json") for event in events or []],
        "artifact_paths": [artifact.model_dump(mode="json") for artifact in run.artifact_paths],
    }
    path.write_text(
        json.dumps(redact_secret_like_values(payload), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def write_agent_run_report(
    *,
    run: AgentRun,
    run_dir: str | Path,
    research_reason_zh: str,
    outputs: list[AgentOutput] | None = None,
) -> Path:
    """Write the PM-readable Agent run report."""
    target_dir = Path(run_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / AGENT_RUN_REPORT_FILENAME
    primary_output: AgentOutput | None = outputs[0] if outputs else None
    lines = [
        f"# Kronos Agent 研究报告：{run.run_id}",
        "",
        "## 第一屏",
        "",
        f"- 当前研究目标：{run.goal_zh}",
        f"- 为什么研究：{research_reason_zh}",
        f"- 关键证据：{_evidence_text(primary_output)}",
        f"- 当前结论：{primary_output.conclusion if primary_output else '尚未形成结论。'}",
        f"- 下一步动作：{primary_output.next_action if primary_output else '等待下一步任务。'}",
        f"- 是否需要审批：{_approval_text(primary_output)}",
        "",
        "## 运行状态",
        "",
        f"- Run ID：{run.run_id}",
        f"- 当前状态：{run.status.value}",
        f"- 当前任务：{run.current_task_id or '无'}",
        f"- 任务数量：{len(run.tasks)}",
        "",
        "## 产物",
        "",
    ]
    lines.extend(_artifact_lines(run, primary_output))
    path.write_text("\n".join(redact_secret_like_values(lines)) + "\n", encoding="utf-8")
    return path


def write_agent_errors(*, run: AgentRun, run_dir: str | Path) -> Path:
    """Write a user-readable Agent error report."""
    target_dir = Path(run_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / AGENT_ERRORS_FILENAME
    error_ref = run.error_ref
    failed_tasks = [task for task in run.tasks if task.status == AgentTaskStatus.FAILED]
    lines = [
        f"# Kronos Agent 错误报告：{run.run_id}",
        "",
        "## 第一屏",
        "",
        f"- 失败阶段：{failed_tasks[0].title_zh if failed_tasks else '未知阶段'}",
        f"- 错误分类：{error_ref.category.value if error_ref else 'unknown'}",
        f"- 直接影响：{_error_impact(error_ref)}",
        f"- 用户是否可处理：{'可以' if error_ref and error_ref.recoverable else '需要开发排查'}",
        f"- 下一步动作：{error_ref.user_action_zh if error_ref and error_ref.user_action_zh else '查看 traceback_ref 并定位失败原因。'}",
        f"- error_code：{error_ref.error_code if error_ref else 'unknown_error'}",
        f"- traceback_ref：{error_ref.traceback_ref if error_ref and error_ref.traceback_ref else '未提供'}",
        "",
    ]
    if failed_tasks:
        lines.extend([
            "## 失败任务",
            "",
        ])
        for task in failed_tasks:
            lines.append(f"- {task.task_id}：{task.title_zh}")
    path.write_text("\n".join(redact_secret_like_values(lines)) + "\n", encoding="utf-8")
    return path


def _evidence_text(output: AgentOutput | None) -> str:
    if output is None or not output.key_evidence:
        return "尚未产生关键证据。"
    return "；".join(
        f"{artifact.name} ({artifact.path})"
        for artifact in output.key_evidence
    )


def _approval_text(output: AgentOutput | None) -> str:
    if output is None or not output.approval_required:
        return "否"
    return "是，" + "；".join(
        f"{approval.title_zh}：{approval.reason_zh}"
        for approval in output.approval_requirements
    )


def _error_impact(error_ref: AgentErrorRef | None) -> str:
    if error_ref is None:
        return "Agent run 未能完成。"
    return error_ref.impact_zh or error_ref.message_zh


def _artifact_lines(run: AgentRun, output: AgentOutput | None) -> list[str]:
    artifacts = list(run.artifact_paths)
    if output is not None:
        artifacts.extend(output.artifact_paths)
        artifacts.extend(output.key_evidence)
    artifacts = _dedupe_artifacts(artifacts)
    if not artifacts:
        return ["- 暂无。", ""]
    lines = [
        f"- {artifact.name}：{artifact.path}"
        for artifact in artifacts
    ]
    lines.append("")
    return lines


def _dedupe_artifacts(artifacts: list[AgentArtifactRef]) -> list[AgentArtifactRef]:
    deduped: list[AgentArtifactRef] = []
    seen: set[tuple[str, str]] = set()
    for artifact in artifacts:
        key = (artifact.name, artifact.path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(artifact)
    return deduped
