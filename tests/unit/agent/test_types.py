"""Tests for primitive Agent enum and ID contracts."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

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
    AgentModelInvocationId,
    AgentOutput,
    AgentPromptVersionId,
    AgentRole,
    AgentRoleId,
    AgentRoleKind,
    AgentRun,
    AgentRunId,
    AgentRunStatus,
    AgentTask,
    AgentTaskId,
    AgentTaskStatus,
    AgentToolInvocationId,
    ApprovalRequirement,
    ApprovalType,
    CandidateLifecycleState,
    ModelInvocationRef,
    PromptVersionRef,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def test_agent_status_enums_are_json_serializable_strings() -> None:
    payload = {
        "run_status": AgentRunStatus.RUNNING,
        "task_status": AgentTaskStatus.WAITING_APPROVAL,
        "event_level": AgentEventLevel.APPROVAL_REQUIRED,
        "event_type": AgentEventType.CANDIDATE_STATE_CHANGED,
        "error_category": AgentErrorCategory.TOOL_EXECUTION,
        "candidate_state": CandidateLifecycleState.LIVE_APPROVAL_REQUIRED,
        "approval_type": ApprovalType.LIVE_TRADING_APPLICATION,
        "role_kind": AgentRoleKind.RISK_REVIEWER,
    }

    assert json.loads(json.dumps(payload)) == {
        "run_status": "running",
        "task_status": "waiting_approval",
        "event_level": "approval_required",
        "event_type": "candidate_state_changed",
        "error_category": "tool_execution",
        "candidate_state": "live_approval_required",
        "approval_type": "live_trading_application",
        "role_kind": "risk_reviewer",
    }


def test_enum_values_are_snake_case() -> None:
    enum_classes = [
        AgentRunStatus,
        AgentTaskStatus,
        AgentEventLevel,
        AgentEventType,
        AgentErrorCategory,
        CandidateLifecycleState,
        ApprovalType,
        AgentRoleKind,
    ]

    for enum_class in enum_classes:
        for item in enum_class:
            assert _SNAKE_CASE_PATTERN.fullmatch(item.value), item.value


def test_candidate_lifecycle_covers_openspec_states() -> None:
    assert {item.value for item in CandidateLifecycleState} == {
        "material_intake",
        "migration_review",
        "hypothesis",
        "experiment_planned",
        "validating",
        "agent_analysis",
        "committee_scoring",
        "observe",
        "redesign",
        "simulate",
        "live_approval_required",
        "retired",
    }


def test_event_levels_cover_web_timeline_contract() -> None:
    assert {item.value for item in AgentEventLevel} == {
        "info",
        "decision",
        "warning",
        "approval_required",
        "error",
    }


def test_event_types_cover_agent_research_loop() -> None:
    values = {item.value for item in AgentEventType}

    assert {
        "material_intake",
        "hypothesis_generated",
        "experiment_planned",
        "tool_execution_started",
        "tool_execution_completed",
        "tool_execution_failed",
        "agent_analysis_completed",
        "committee_scoring_completed",
        "approval_requested",
        "candidate_state_changed",
    } <= values


def test_approval_types_cover_required_human_gates() -> None:
    assert {
        "prompt_activation",
        "simulation_admission",
        "live_trading_application",
    } <= {item.value for item in ApprovalType}


def test_role_kinds_cover_initial_multi_agent_committee() -> None:
    assert {
        "researcher",
        "opposition_reviewer",
        "risk_reviewer",
        "decision_reviewer",
    } <= {item.value for item in AgentRoleKind}


def test_agent_id_types_are_string_compatible() -> None:
    id_factories: list[Callable[[str], str]] = [
        AgentRunId,
        AgentTaskId,
        AgentEventId,
        AgentCandidateId,
        AgentRoleId,
        AgentPromptVersionId,
        AgentModelInvocationId,
        AgentToolInvocationId,
        AgentApprovalId,
    ]

    for factory in id_factories:
        value = factory("sample-id")
        assert value == "sample-id"
        assert isinstance(value, str)


def test_exported_enums_are_str_enum_subclasses() -> None:
    enum_classes = [
        AgentRunStatus,
        AgentTaskStatus,
        AgentEventLevel,
        AgentEventType,
        AgentErrorCategory,
        CandidateLifecycleState,
        ApprovalType,
        AgentRoleKind,
    ]

    for enum_class in enum_classes:
        assert issubclass(enum_class, StrEnum)


def test_agent_event_is_json_serializable() -> None:
    event = AgentEvent(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        event_id=AgentEventId("event-1"),
        event_type=AgentEventType.CANDIDATE_STATE_CHANGED,
        level=AgentEventLevel.DECISION,
        status=AgentTaskStatus.COMPLETED,
        message_zh="候选状态已更新。",
        candidate_id=AgentCandidateId("trend_pullback_entry"),
        artifact_paths=[
            AgentArtifactRef(
                name="agent_plan",
                path="reports/research/experiments/run-1/agent_research_plan.md",
                artifact_type="markdown_report",
                summary_zh="Agent 研究计划。",
            )
        ],
        metadata={"new_state": CandidateLifecycleState.REDESIGN},
    )

    dumped = json.loads(event.model_dump_json())

    assert dumped["run_id"] == "run-1"
    assert dumped["task_id"] == "task-1"
    assert dumped["event_id"] == "event-1"
    assert dumped["event_type"] == "candidate_state_changed"
    assert dumped["level"] == "decision"
    assert dumped["status"] == "completed"
    assert dumped["artifact_paths"][0]["path"].endswith("agent_research_plan.md")
    assert dumped["metadata"]["new_state"] == "redesign"


def test_agent_task_and_run_keep_artifact_and_error_refs() -> None:
    error = AgentErrorRef(
        error_code="tool_failed",
        message_zh="确定性工具运行失败。",
        traceback_ref="errors/run-1/tool_failed.trace",
        category=AgentErrorCategory.TOOL_EXECUTION,
        impact_zh="本轮工具失败, Agent 无法继续形成结论.",
        recoverable=True,
        user_action_zh="检查数据覆盖后重试。",
    )
    task = AgentTask(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        status=AgentTaskStatus.FAILED,
        title_zh="执行候选验证",
        candidate_id=AgentCandidateId("trend_pullback_entry"),
        lifecycle_state=CandidateLifecycleState.VALIDATING,
        error_ref=error,
    )
    run = AgentRun(
        run_id=AgentRunId("run-1"),
        status=AgentRunStatus.FAILED,
        goal_zh="验证趋势回踩候选。",
        current_task_id=AgentTaskId("task-1"),
        tasks=[task],
        error_ref=error,
    )

    assert run.tasks[0].candidate_id == "trend_pullback_entry"
    assert run.error_ref is not None
    assert run.error_ref.error_code == "tool_failed"
    assert run.error_ref.category == AgentErrorCategory.TOOL_EXECUTION
    assert run.error_ref.impact_zh == "本轮工具失败, Agent 无法继续形成结论."


def test_agent_event_rejects_missing_required_fields() -> None:
    payload: dict[str, Any] = {
        "run_id": AgentRunId("run-1"),
        "task_id": AgentTaskId("task-1"),
        "event_id": AgentEventId("event-1"),
        "event_type": AgentEventType.RUN_STARTED,
        "level": AgentEventLevel.INFO,
        "status": AgentTaskStatus.RUNNING,
    }

    try:
        AgentEvent(**payload)
    except ValidationError as exc:
        missing_fields = {
            ".".join(str(part) for part in error["loc"])
            for error in exc.errors()
            if error["type"] == "missing"
        }
        assert missing_fields == {"message_zh"}
    else:
        raise AssertionError("AgentEvent should reject missing message_zh")


def test_agent_schema_rejects_extra_fields() -> None:
    payload: dict[str, Any] = {
        "run_id": AgentRunId("run-1"),
        "status": AgentRunStatus.PENDING,
        "goal_zh": "验证新候选。",
        "unexpected": "not allowed",
    }

    try:
        AgentRun(**payload)
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "extra_forbidden"
    else:
        raise AssertionError("AgentRun should reject unknown fields")


def test_role_prompt_and_model_refs_are_traceable() -> None:
    prompt = PromptVersionRef(
        prompt_version=AgentPromptVersionId("researcher-v1"),
        role_id=AgentRoleId("researcher"),
        title_zh="研究员提示词 v1",
        prompt_hash="sha256:abc123",
        is_active=True,
    )
    role = AgentRole(
        role_id=AgentRoleId("researcher"),
        role_kind=AgentRoleKind.RESEARCHER,
        name_zh="研究员",
        prompt_version=prompt.prompt_version,
        model_provider="deepseek",
        model_name="deepseek-chat",
    )
    invocation = ModelInvocationRef(
        invocation_id=AgentModelInvocationId("model-call-1"),
        role_id=role.role_id,
        prompt_version=prompt.prompt_version,
        model_provider=role.model_provider,
        model_name=role.model_name,
        status=AgentTaskStatus.COMPLETED,
        latency_ms=1200,
    )

    assert role.prompt_version == "researcher-v1"
    assert invocation.model_provider == "deepseek"
    assert invocation.model_name == "deepseek-chat"


def test_agent_output_contains_required_decision_contract() -> None:
    evidence = AgentArtifactRef(
        name="watchlist_evidence",
        path="reports/research/experiments/run-1/watchlist_evidence_review.json",
        artifact_type="json_evidence",
    )
    approval = ApprovalRequirement(
        approval_id=AgentApprovalId("approval-1"),
        approval_type=ApprovalType.SIMULATION_ADMISSION,
        title_zh="进入模拟盘审批",
        reason_zh="候选需要人工确认后才能进入模拟盘。",
        candidate_id=AgentCandidateId("trend_pullback_entry"),
    )
    output = AgentOutput(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        role_id=AgentRoleId("decision_reviewer"),
        prompt_version=AgentPromptVersionId("decision-v1"),
        conclusion="候选可以进入模拟盘申请。",
        support_reasons=["专项证据出现多个弱正向切片。"],
        opposition_reasons=["尚无强支持切片。"],
        key_evidence=[evidence],
        max_risk="弱信号可能来自短期市场状态。",
        next_action="提交模拟盘审批。",
        approval_required=True,
        approval_requirements=[approval],
    )

    dumped = json.loads(output.model_dump_json())

    assert dumped["conclusion"] == "候选可以进入模拟盘申请。"
    assert dumped["support_reasons"]
    assert dumped["opposition_reasons"]
    assert dumped["key_evidence"][0]["path"].endswith("watchlist_evidence_review.json")
    assert dumped["approval_required"] is True
    assert dumped["approval_requirements"][0]["approval_type"] == "simulation_admission"


def test_agent_output_requires_key_evidence() -> None:
    payload: dict[str, Any] = {
        "run_id": AgentRunId("run-1"),
        "task_id": AgentTaskId("task-1"),
        "role_id": AgentRoleId("decision_reviewer"),
        "prompt_version": AgentPromptVersionId("decision-v1"),
        "conclusion": "候选可以观察。",
        "support_reasons": ["有弱正向切片。"],
        "opposition_reasons": ["证据仍不足。"],
        "key_evidence": [],
        "max_risk": "证据不足。",
        "next_action": "继续观察。",
        "approval_required": False,
    }

    try:
        AgentOutput(**payload)
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "too_short"
    else:
        raise AssertionError("AgentOutput should reject empty key_evidence")


def test_agent_output_requires_approval_details_when_flagged() -> None:
    payload: dict[str, Any] = {
        "run_id": AgentRunId("run-1"),
        "task_id": AgentTaskId("task-1"),
        "role_id": AgentRoleId("decision_reviewer"),
        "prompt_version": AgentPromptVersionId("decision-v1"),
        "conclusion": "候选申请实盘。",
        "support_reasons": ["证据通过。"],
        "opposition_reasons": ["仍有实盘滑点风险。"],
        "key_evidence": [
            AgentArtifactRef(
                name="agent_report",
                path="reports/research/experiments/run-1/agent_run_report.md",
                artifact_type="markdown_report",
            )
        ],
        "max_risk": "实盘亏损。",
        "next_action": "等待用户审批。",
        "approval_required": True,
    }

    try:
        AgentOutput(**payload)
    except ValidationError as exc:
        assert "approval_requirements must be present" in str(exc)
    else:
        raise AssertionError("AgentOutput should require approval details")
