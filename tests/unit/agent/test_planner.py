"""Tests for one-cycle Agent run orchestration and selective memory writes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from kronos.agent.analyzer import (
    AgentKnowledgeEntry,
    AgentKnowledgeEntryType,
    AgentKnowledgeWriteError,
    SelectiveKnowledgeWriter,
)
from kronos.agent.events import read_events
from kronos.agent.planner import run_agent_once
from kronos.agent.types import AgentRunStatus
from kronos.research.knowledge_base import search_entries

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
                    "weak_positive_slices": 4,
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


def test_agent_run_once_writes_report_summary_and_events(tmp_path: Path) -> None:
    summary_path = tmp_path / "auto_run_summary.json"
    evidence_path = tmp_path / "watchlist_evidence_review.json"
    output_path = tmp_path / "reports" / "research"
    _summary_fixture(summary_path)
    _evidence_fixture(evidence_path)

    result = run_agent_once(
        summary_json_path=summary_path,
        evidence_json_paths=[evidence_path],
        output_base_path=output_path,
        run_id="agent-cycle-test",
        goal_zh="验证下一轮候选。",
    )

    assert result.status == AgentRunStatus.COMPLETED
    assert result.summary()["tools"] == 2
    assert result.summary()["failed_tools"] == 0
    assert "agent_run_report" in result.artifact_paths
    assert "agent_run_summary" in result.artifact_paths
    assert "agent_events" in result.artifact_paths
    assert "agent_plan_report" in result.artifact_paths
    assert "agent_decision_report" in result.artifact_paths
    assert "候选改造" in result.next_action_zh
    assert "agent_research_plan" in (
        output_path / "experiments" / "agent-cycle-test" / "agent_run_report.md"
    ).read_text(encoding="utf-8")

    run_agent_once(
        summary_json_path=summary_path,
        evidence_json_paths=[evidence_path],
        output_base_path=output_path,
        run_id="agent-cycle-test",
        goal_zh="验证下一轮候选。",
    )
    events = read_events(output_path / "experiments" / "agent-cycle-test")
    assert len(events) == 6


def test_agent_run_once_publishes_web_runtime_snapshot(tmp_path: Path) -> None:
    summary_path = tmp_path / "auto_run_summary.json"
    evidence_path = tmp_path / "watchlist_evidence_review.json"
    output_path = tmp_path / "reports" / "research"
    runtime_path = tmp_path / "reports" / "agent_runtime"
    _summary_fixture(summary_path)
    _evidence_fixture(evidence_path)

    run_agent_once(
        summary_json_path=summary_path,
        evidence_json_paths=[evidence_path],
        output_base_path=output_path,
        run_id="agent-cycle-test",
        goal_zh="验证下一轮候选。",
        runtime_path=runtime_path,
    )
    run_agent_once(
        summary_json_path=summary_path,
        evidence_json_paths=[evidence_path],
        output_base_path=output_path,
        run_id="agent-cycle-test",
        goal_zh="验证下一轮候选。",
        runtime_path=runtime_path,
    )

    status_payload = json.loads(
        (runtime_path / "agent_supervisor_status.json").read_text(encoding="utf-8")
    )
    events = read_events(runtime_path / "agent-cycle-test")

    assert status_payload["active"] is False
    assert status_payload["current_run"]["run_id"] == "agent-cycle-test"
    assert status_payload["current_task"]["status"] == "completed"
    assert len(events) == 6
    assert events[-1].event_type == "run_completed"


def test_agent_run_once_requires_evidence_and_does_not_recurse(tmp_path: Path) -> None:
    summary_path = tmp_path / "auto_run_summary.json"
    _summary_fixture(summary_path)

    with pytest.raises(ValueError):
        run_agent_once(
            summary_json_path=summary_path,
            evidence_json_paths=[],
            output_base_path=tmp_path / "reports" / "research",
            run_id="agent-cycle-test",
            goal_zh="验证下一轮候选。",
        )


def test_selective_knowledge_writer_rejects_raw_logs(tmp_path: Path) -> None:
    writer = SelectiveKnowledgeWriter(tmp_path / "reports" / "research")

    with pytest.raises(AgentKnowledgeWriteError):
        writer.write(
            AgentKnowledgeEntry(
                entry_type=AgentKnowledgeEntryType.RESEARCH_CONCLUSION,
                title="raw",
                summary="raw",
                metadata={"raw_log": True},
            )
        )


def test_selective_knowledge_writer_persists_allowed_memory(tmp_path: Path) -> None:
    base_path = tmp_path / "reports" / "research"
    writer = SelectiveKnowledgeWriter(base_path)

    entry_id = writer.write(
        AgentKnowledgeEntry(
            entry_type=AgentKnowledgeEntryType.RESEARCH_CONCLUSION,
            title="Agent conclusion",
            summary="trend_pullback_entry 进入候选改造。",
            run_id="agent-cycle-test",
            factor_name="trend_pullback_entry",
            tags=["agent"],
        )
    )
    hits = search_entries(
        "trend_pullback_entry",
        base_path=base_path,
        entry_type="agent_research_decision",
    )

    assert entry_id > 0
    assert len(hits) == 1
    assert hits[0].run_id == "agent-cycle-test"
