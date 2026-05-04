"""One-cycle Agent run orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.events import EVENT_TIMELINE_FILENAME, read_events, write_event
from kronos.agent.reports import (
    AGENT_ERRORS_FILENAME,
    AGENT_RUN_REPORT_FILENAME,
    AGENT_RUN_SUMMARY_FILENAME,
    write_agent_errors,
    write_agent_run_report,
    write_agent_run_summary,
)
from kronos.agent.supervisor import AgentSupervisor
from kronos.agent.tools import (
    AgentToolExecutionRecord,
    AgentToolExecutor,
    agent_conclude_tool,
    agent_propose_tool,
)
from kronos.agent.types import (
    AgentArtifactRef,
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentOutput,
    AgentPromptVersionId,
    AgentRoleId,
    AgentRun,
    AgentRunId,
    AgentRunStatus,
    AgentTask,
    AgentTaskId,
    AgentTaskStatus,
)
from kronos.research.experiments.artifacts import experiment_root


class AgentRunOnceResult(BaseModel):
    """Summary for one non-recursive Agent research cycle."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: AgentRunStatus
    next_action_zh: str = Field(min_length=1)
    tool_records: list[AgentToolExecutionRecord] = Field(default_factory=list)
    artifact_paths: dict[str, str] = Field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """Return a compact CLI-friendly summary."""
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "tools": len(self.tool_records),
            "failed_tools": sum(
                record.status == AgentTaskStatus.FAILED
                for record in self.tool_records
            ),
            "next_action_zh": self.next_action_zh,
        }


def run_agent_once(
    *,
    summary_json_path: str | Path,
    evidence_json_paths: list[str | Path],
    output_base_path: str | Path,
    run_id: str,
    goal_zh: str,
    runtime_path: str | Path | None = None,
) -> AgentRunOnceResult:
    """Run one bounded Agent cycle and stop at a next-action decision."""
    if not evidence_json_paths:
        raise ValueError("agent run-once requires at least one evidence JSON path")

    output_base = Path(output_base_path)
    run_dir = experiment_root(output_base, run_id)
    _reset_run_once_artifacts(run_dir)
    task_id = AgentTaskId("agent-cycle")
    task = AgentTask(
        run_id=AgentRunId(run_id),
        task_id=task_id,
        status=AgentTaskStatus.RUNNING,
        title_zh="执行一轮 Agent 研究闭环",
    )
    started_run = AgentRun(
        run_id=AgentRunId(run_id),
        status=AgentRunStatus.RUNNING,
        goal_zh=goal_zh,
        current_task_id=task_id,
        tasks=[task],
    )
    write_event(
        _run_event(
            run=started_run,
            task=task,
            event_type=AgentEventType.RUN_STARTED,
            level=AgentEventLevel.INFO,
            status=AgentTaskStatus.RUNNING,
            message_zh="Agent 验收运行已启动。",
        ),
        run_dir=run_dir,
    )
    executor = AgentToolExecutor(run_dir=run_dir, run_id=run_id, task_id=str(task_id))
    records: list[AgentToolExecutionRecord] = []

    records.append(
        executor.execute(
            tool_name="agent_propose",
            payload={
                "summary_json_path": str(summary_json_path),
                "output_base_path": str(output_base),
                "run_id": f"{run_id}-plan",
                "goal_zh": goal_zh,
            },
            handler=agent_propose_tool,
        )
    )
    records.append(
        executor.execute(
            tool_name="agent_conclude",
            payload={
                "evidence_json_paths": [str(path) for path in evidence_json_paths],
                "output_base_path": str(output_base),
                "run_id": f"{run_id}-decision",
            },
            handler=agent_conclude_tool,
        )
    )

    failed_record = next(
        (record for record in records if record.status == AgentTaskStatus.FAILED),
        None,
    )
    final_task_status = AgentTaskStatus.FAILED if failed_record is not None else AgentTaskStatus.COMPLETED
    final_run_status = AgentRunStatus.FAILED if failed_record is not None else AgentRunStatus.COMPLETED
    artifacts = _collect_artifacts(records)
    run = AgentRun(
        run_id=AgentRunId(run_id),
        status=final_run_status,
        goal_zh=goal_zh,
        current_task_id=task_id,
        tasks=[task.model_copy(update={"status": final_task_status})],
        artifact_paths=artifacts,
        error_ref=failed_record.error_ref if failed_record is not None else None,
    )
    write_event(
        _run_event(
            run=run,
            task=run.tasks[0],
            event_type=(
                AgentEventType.RUN_FAILED
                if final_run_status == AgentRunStatus.FAILED
                else AgentEventType.RUN_COMPLETED
            ),
            level=(
                AgentEventLevel.ERROR
                if final_run_status == AgentRunStatus.FAILED
                else AgentEventLevel.DECISION
            ),
            status=final_task_status,
            message_zh=(
                "Agent 验收运行失败, 已生成错误报告。"
                if final_run_status == AgentRunStatus.FAILED
                else "Agent 验收运行已完成, 等待人工复核下一步。"
            ),
            artifact_paths=artifacts,
        ),
        run_dir=run_dir,
    )
    events = read_events(run_dir)
    outputs = [] if failed_record is not None else [_agent_output(run_id, artifacts, records)]
    summary_path = write_agent_run_summary(
        run=run,
        outputs=outputs,
        events=events,
        run_dir=run_dir,
    )
    report_path = write_agent_run_report(
        run=run,
        outputs=outputs,
        research_reason_zh="把 Agent 计划、确定性工具执行和结果读取串成一轮可审计闭环。",
        run_dir=run_dir,
    )
    artifact_paths = {
        "agent_run_summary": str(summary_path),
        "agent_run_report": str(report_path),
        "agent_events": str(run_dir / "agent_events.jsonl"),
    }
    if failed_record is not None:
        artifact_paths["agent_errors"] = str(write_agent_errors(run=run, run_dir=run_dir))

    for artifact in artifacts:
        artifact_paths[artifact.name] = artifact.path

    if runtime_path is not None:
        AgentSupervisor(runtime_path).publish_run_snapshot(run=run, events=events)

    return AgentRunOnceResult(
        run_id=run_id,
        status=final_run_status,
        next_action_zh=_next_action(records, failed_record),
        tool_records=records,
        artifact_paths=artifact_paths,
    )


def _reset_run_once_artifacts(run_dir: Path) -> None:
    for filename in (
        EVENT_TIMELINE_FILENAME,
        AGENT_RUN_SUMMARY_FILENAME,
        AGENT_RUN_REPORT_FILENAME,
        AGENT_ERRORS_FILENAME,
    ):
        (run_dir / filename).unlink(missing_ok=True)


def _collect_artifacts(records: list[AgentToolExecutionRecord]) -> list[AgentArtifactRef]:
    artifacts: list[AgentArtifactRef] = []
    seen: set[str] = set()
    for record in records:
        for artifact in record.artifact_paths:
            if artifact.path not in seen:
                artifacts.append(artifact)
                seen.add(artifact.path)
    return artifacts


def _agent_output(
    run_id: str,
    artifacts: list[AgentArtifactRef],
    records: list[AgentToolExecutionRecord],
) -> AgentOutput:
    final_record = records[-1]
    next_action = str(final_record.output_summary.get("next_action_zh") or "等待人工复核。")
    return AgentOutput(
        run_id=AgentRunId(run_id),
        task_id=AgentTaskId("agent-cycle"),
        role_id=AgentRoleId("decision_reviewer"),
        prompt_version=AgentPromptVersionId("decision-reviewer-prompt-v1"),
        conclusion=next_action,
        support_reasons=["已完成 Agent plan 和 Agent decision 两个确定性工具步骤。"],
        opposition_reasons=["本轮只是研究闭环, 不自动进入组合或实盘。"],
        key_evidence=artifacts,
        max_risk="输入证据仍来自本地 fixture 或已有研究产物, 需要后续真实批次验收。",
        next_action=next_action,
        approval_required=False,
        artifact_paths=artifacts,
    )


def _next_action(
    records: list[AgentToolExecutionRecord],
    failed_record: AgentToolExecutionRecord | None,
) -> str:
    if failed_record is not None:
        return f"工具执行失败: {failed_record.tool_name}, 需要查看错误报告。"
    final_summary = records[-1].output_summary if records else {}
    next_action = final_summary.get("next_action_zh")
    if isinstance(next_action, str) and next_action:
        return next_action
    return "本轮 Agent 研究闭环已完成, 等待人工复核后进入下一步。"


def _run_event(
    *,
    run: AgentRun,
    task: AgentTask,
    event_type: AgentEventType,
    level: AgentEventLevel,
    status: AgentTaskStatus,
    message_zh: str,
    artifact_paths: list[AgentArtifactRef] | None = None,
) -> AgentEvent:
    return AgentEvent(
        run_id=run.run_id,
        task_id=task.task_id,
        event_id=AgentEventId(f"event-{uuid4().hex}"),
        event_type=event_type,
        level=level,
        status=status,
        message_zh=message_zh,
        artifact_paths=artifact_paths or [],
    )
