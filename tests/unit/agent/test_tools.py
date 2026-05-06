"""Tests for deterministic Agent tool registry and executor."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from kronos.agent.events import REDACTED_SECRET, read_events
from kronos.agent.tools import (
    AgentToolError,
    AgentToolExecutionResult,
    AgentToolExecutor,
    AgentToolRegistry,
    agent_conclude_tool,
    agent_propose_tool,
    existing_artifact_tool,
)
from kronos.agent.types import AgentErrorCategory, AgentEventType, AgentTaskStatus

if TYPE_CHECKING:
    from pathlib import Path


def _summary_fixture(path: Path) -> None:
    path.write_text(
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


def _evidence_fixture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "candidate_id": "trend_pullback_entry",
                    "factor_name": "trend_pullback_entry",
                    "history_status": "enough_history",
                    "supportive_slices": 0,
                    "weak_positive_slices": 3,
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


def test_default_tool_registry_is_whitelist_with_schema_metadata() -> None:
    registry = AgentToolRegistry()
    tools = registry.list_tools()

    assert {tool.name for tool in tools} == {
        "agent_propose",
        "research_workbench",
        "watchlist_evidence",
        "agent_conclude",
    }
    assert all(tool.purpose_zh for tool in tools)
    assert all(tool.input_schema for tool in tools)
    assert all(tool.output_schema for tool in tools)


def test_tool_registry_rejects_unlisted_tool() -> None:
    registry = AgentToolRegistry()

    with pytest.raises(AgentToolError):
        registry.get_tool("shell")


def test_tool_executor_records_success_and_events(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    executor = AgentToolExecutor(run_dir=run_dir, run_id="run-1", task_id="task-1")

    def handler(payload: dict[str, Any]) -> AgentToolExecutionResult:
        return AgentToolExecutionResult(
            output_summary={"ok": True, "seen": payload["artifact_paths"]["report"]},
            artifact_paths=[],
        )

    record = executor.execute(
        tool_name="watchlist_evidence",
        payload={"artifact_paths": {"report": "evidence.md"}, "api_key": "secret"},
        handler=handler,
    )
    events = read_events(run_dir)

    assert record.status == AgentTaskStatus.COMPLETED
    assert record.input_summary["api_key"] == REDACTED_SECRET
    assert record.output_summary["ok"] is True
    assert [event.event_type for event in events] == [
        AgentEventType.TOOL_EXECUTION_STARTED,
        AgentEventType.TOOL_EXECUTION_COMPLETED,
    ]
    assert "secret" not in (run_dir / "agent_events.jsonl").read_text(encoding="utf-8")


def test_tool_executor_rejects_missing_required_payload_without_handler(tmp_path: Path) -> None:
    executor = AgentToolExecutor(run_dir=tmp_path / "run-1", run_id="run-1", task_id="task-1")
    called = False

    def handler(_: dict[str, Any]) -> AgentToolExecutionResult:
        nonlocal called
        called = True
        return AgentToolExecutionResult()

    record = executor.execute(tool_name="watchlist_evidence", payload={}, handler=handler)

    assert called is False
    assert record.status == AgentTaskStatus.FAILED
    assert record.error_ref is not None
    assert record.error_ref.error_code == "agent_tool_input_invalid"
    assert "artifact_paths" in (record.error_ref.user_action_zh or "")


def test_tool_executor_records_failure_without_raising(tmp_path: Path) -> None:
    executor = AgentToolExecutor(run_dir=tmp_path / "run-1", run_id="run-1", task_id="task-1")

    def handler(_: dict[str, Any]) -> AgentToolExecutionResult:
        raise ValueError("bad input")

    record = executor.execute(
        tool_name="watchlist_evidence",
        payload={"artifact_paths": {"report": "evidence.md"}},
        handler=handler,
    )

    assert record.status == AgentTaskStatus.FAILED
    assert record.error_ref is not None
    assert record.error_ref.error_code == "agent_tool_failed"
    assert record.error_ref.category == AgentErrorCategory.TOOL_EXECUTION
    assert record.error_ref.impact_zh == "本轮 Agent 无法形成可靠结论, 已停止在错误报告."


def test_agent_propose_and_conclude_tools_wrap_existing_research_artifacts(tmp_path: Path) -> None:
    summary_path = tmp_path / "auto_run_summary.json"
    evidence_path = tmp_path / "watchlist_evidence_review.json"
    output_path = tmp_path / "reports" / "research"
    _summary_fixture(summary_path)
    _evidence_fixture(evidence_path)

    plan = agent_propose_tool({
        "summary_json_path": str(summary_path),
        "output_base_path": str(output_path),
        "run_id": "agent-plan",
        "goal_zh": "验证下一轮候选。",
    })
    decision = agent_conclude_tool({
        "evidence_json_paths": [str(evidence_path)],
        "output_base_path": str(output_path),
        "run_id": "agent-decision",
    })

    assert plan.output_summary["hypotheses"] >= 1
    assert {artifact.name for artifact in plan.artifact_paths} == {
        "agent_plan_json",
        "agent_plan_report",
    }
    assert decision.output_summary["decisions"] == 1
    assert {artifact.name for artifact in decision.artifact_paths} == {
        "agent_decision_json",
        "agent_decision_report",
    }


def test_existing_artifact_tool_wraps_workbench_or_evidence_outputs() -> None:
    result = existing_artifact_tool({
        "artifact_paths": {
            "workbench_summary": "reports/workbench.json",
            "evidence_report": "reports/evidence.md",
        },
    })

    assert result.output_summary["wrapped_artifacts"] == 2
    assert [artifact.name for artifact in result.artifact_paths] == [
        "workbench_summary",
        "evidence_report",
    ]
