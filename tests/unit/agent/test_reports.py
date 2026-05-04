"""Tests for minimal Agent report writers."""

from __future__ import annotations

import json
from pathlib import Path

from kronos.agent.reports import (
    AGENT_ERRORS_FILENAME,
    AGENT_RUN_REPORT_FILENAME,
    AGENT_RUN_SUMMARY_FILENAME,
    write_agent_errors,
    write_agent_run_report,
    write_agent_run_summary,
)
from kronos.agent.types import (
    AgentApprovalId,
    AgentArtifactRef,
    AgentCandidateId,
    AgentErrorCategory,
    AgentErrorRef,
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
    ApprovalRequirement,
    ApprovalType,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _artifact() -> AgentArtifactRef:
    return AgentArtifactRef(
        name="evidence",
        path="reports/research/experiments/run-1/evidence.json",
        artifact_type="json_evidence",
        summary_zh="专项证据。",
    )


def _run(*, failed: bool = False) -> AgentRun:
    error = None
    status = AgentRunStatus.COMPLETED
    task_status = AgentTaskStatus.COMPLETED
    if failed:
        status = AgentRunStatus.FAILED
        task_status = AgentTaskStatus.FAILED
        error = AgentErrorRef(
            error_code="tool_failed",
            message_zh="确定性工具失败。",
            category=AgentErrorCategory.TOOL_EXECUTION,
            impact_zh="本轮 Agent 无法生成可信结论。",
            traceback_ref="errors/run-1/tool.trace",
            user_action_zh="检查数据覆盖后重试。",
        )
    task = AgentTask(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        status=task_status,
        title_zh="验证候选",
        candidate_id=AgentCandidateId("trend_pullback_entry"),
        error_ref=error,
    )
    return AgentRun(
        run_id=AgentRunId("run-1"),
        status=status,
        goal_zh="验证趋势回踩候选。",
        current_task_id=AgentTaskId("task-1"),
        tasks=[task],
        error_ref=error,
        artifact_paths=[_artifact()],
        metadata={"api_key": "super-secret-key"},
    )


def _output() -> AgentOutput:
    return AgentOutput(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        role_id=AgentRoleId("decision"),
        prompt_version=AgentPromptVersionId("decision-v1"),
        conclusion="候选继续改造。",
        support_reasons=["出现多个弱正向切片。"],
        opposition_reasons=["尚无强支持切片。"],
        key_evidence=[_artifact()],
        max_risk="弱信号可能失效。",
        next_action="进入候选改造。",
        approval_required=True,
        approval_requirements=[
            ApprovalRequirement(
                approval_id=AgentApprovalId("approval-1"),
                approval_type=ApprovalType.CANDIDATE_IMPLEMENTATION,
                title_zh="候选改造审批",
                reason_zh="需要确认是否投入开发。",
                candidate_id=AgentCandidateId("trend_pullback_entry"),
            )
        ],
    )


def _event() -> AgentEvent:
    return AgentEvent(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        event_id=AgentEventId("event-1"),
        event_type=AgentEventType.AGENT_ANALYSIS_COMPLETED,
        level=AgentEventLevel.DECISION,
        status=AgentTaskStatus.COMPLETED,
        message_zh="Agent 分析完成。",
    )


def test_write_agent_run_summary_outputs_machine_readable_json(tmp_path: Path) -> None:
    path = write_agent_run_summary(
        run=_run(),
        outputs=[_output()],
        events=[_event()],
        run_dir=tmp_path,
    )

    assert path == tmp_path / AGENT_RUN_SUMMARY_FILENAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["run"]["goal_zh"] == "验证趋势回踩候选。"
    assert payload["outputs"][0]["conclusion"] == "候选继续改造。"
    assert payload["event_count"] == 1


def test_write_agent_run_report_first_screen_is_pm_readable(tmp_path: Path) -> None:
    path = write_agent_run_report(
        run=_run(),
        outputs=[_output()],
        research_reason_zh="上一轮证据显示趋势回踩有改造价值。",
        run_dir=tmp_path,
    )

    assert path == tmp_path / AGENT_RUN_REPORT_FILENAME
    report = path.read_text(encoding="utf-8")
    assert "当前研究目标" in report
    assert "为什么研究" in report
    assert "关键证据" in report
    assert "当前结论" in report
    assert "下一步动作" in report
    assert "是否需要审批" in report


def test_write_agent_run_report_dedupes_repeated_artifacts(tmp_path: Path) -> None:
    path = write_agent_run_report(
        run=_run(),
        outputs=[_output()],
        research_reason_zh="上一轮证据显示趋势回踩有改造价值。",
        run_dir=tmp_path,
    )

    report = path.read_text(encoding="utf-8")
    expected_line = "- evidence\uff1areports/research/experiments/run-1/evidence.json"
    assert report.count(expected_line) == 1


def test_write_agent_errors_outputs_user_readable_failure_report(tmp_path: Path) -> None:
    path = write_agent_errors(run=_run(failed=True), run_dir=tmp_path)

    assert path == tmp_path / AGENT_ERRORS_FILENAME
    report = path.read_text(encoding="utf-8")
    assert "失败阶段" in report
    assert "错误分类" in report
    assert "tool_execution" in report
    assert "直接影响" in report
    assert "本轮 Agent 无法生成可信结论。" in report
    assert "用户是否可处理" in report
    assert "下一步动作" in report
    assert "tool_failed" in report


def test_reports_redact_secret_like_fields(tmp_path: Path) -> None:
    summary_path = write_agent_run_summary(run=_run(), run_dir=tmp_path)

    raw = summary_path.read_text(encoding="utf-8")
    assert "super-secret-key" not in raw
    assert "[REDACTED]" in raw


def test_agent_fixtures_are_valid_and_reusable(tmp_path: Path) -> None:
    success_run = AgentRun.model_validate_json(
        (FIXTURE_DIR / "success_agent_run.json").read_text(encoding="utf-8")
    )
    failed_run = AgentRun.model_validate_json(
        (FIXTURE_DIR / "failed_agent_run.json").read_text(encoding="utf-8")
    )
    events = [
        AgentEvent.model_validate_json(line)
        for line in (FIXTURE_DIR / "agent_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert success_run.status == AgentRunStatus.COMPLETED
    assert failed_run.status == AgentRunStatus.FAILED
    assert [event.event_id for event in events] == ["event-1", "event-2"]

    report_path = write_agent_run_report(
        run=success_run,
        outputs=[],
        research_reason_zh="验证 fixture 可被后续批次复用。",
        run_dir=tmp_path,
    )
    error_path = write_agent_errors(run=failed_run, run_dir=tmp_path)

    assert report_path.exists()
    assert error_path.exists()
