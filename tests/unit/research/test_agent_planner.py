"""Tests for the Agent MVP research planner."""

from __future__ import annotations

import json
from pathlib import Path

from kronos.research.agent_planner import run_research_agent_decision, run_research_agent_planner
from kronos.research.knowledge_base import search_entries


def test_agent_planner_generates_next_hypotheses_and_memory(tmp_path: Path) -> None:
    summary_path = tmp_path / "auto_run_summary.json"
    summary_path.write_text(
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
                        },
                        {
                            "candidate_id": "body_energy",
                            "candidate_title": "Body Energy",
                            "factor_name": "body_energy",
                            "status": "retirement_recommended",
                            "status_label_zh": "建议退休",
                            "recommendation_zh": "建议退休为失效假设。",
                            "rationale_zh": "基础验证未通过。",
                            "metrics": {
                                "validation_outcome": "fail",
                                "mean_rank_ic": -0.01,
                                "walkforward_positive_test_window_ratio": 0.44,
                            },
                        },
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "reports" / "research"
    result = run_research_agent_planner(
        summary_json_path=summary_path,
        output_base_path=output_path,
        run_id="agent-test",
        goal_zh="把旧策略迁移成 crypto 候选。",
    )

    assert result.source_run_id == "source-run"
    assert result.selected_candidates[0]["candidate_id"] == "trend_pullback_entry"
    assert len(result.hypotheses) >= 2
    assert "定时器" in result.next_action_zh

    report_path = Path(result.artifact_paths["agent_plan_report"])
    json_path = Path(result.artifact_paths["agent_plan_json"])
    assert report_path.exists()
    assert json_path.exists()
    assert "下一轮研究假设与实验" in report_path.read_text(encoding="utf-8")

    hits = search_entries(
        "trend_pullback_entry",
        base_path=output_path,
        entry_type="agent_research_plan",
    )
    assert len(hits) == 1
    assert hits[0].run_id == "agent-test"


def test_agent_decision_reads_evidence_and_persists_decision(tmp_path: Path) -> None:
    evidence_path = tmp_path / "watchlist_evidence_review.json"
    evidence_path.write_text(
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

    output_path = tmp_path / "reports" / "research"
    result = run_research_agent_decision(
        evidence_json_paths=[evidence_path],
        output_base_path=output_path,
        run_id="agent-decision-test",
    )

    assert result.decisions[0].decision == "redesign_candidate"
    assert "候选改造" in result.next_action_zh
    assert Path(result.artifact_paths["agent_decision_report"]).exists()

    hits = search_entries(
        "trend_pullback_entry",
        base_path=output_path,
        entry_type="agent_research_decision",
    )
    assert len(hits) == 1
    assert hits[0].run_id == "agent-decision-test"
