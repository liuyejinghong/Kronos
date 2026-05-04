"""Unit tests for the research knowledge base."""

from __future__ import annotations

from datetime import UTC, datetime

from kronos.research.experiments.schema import build_run_record
from kronos.research.knowledge_base import (
    add_agent_plan_entry,
    add_candidate_disposition_entry,
    add_experiment_entry,
    add_failure_entry,
    add_watchlist_evidence_entry,
    add_watchlist_review_entry,
    init_knowledge_base,
    search_entries,
)


class TestKnowledgeBase:
    def test_init_creates_sqlite_store(self, tmp_path) -> None:
        db_path = init_knowledge_base(base_path=tmp_path)
        assert db_path.exists()

    def test_add_experiment_entry_and_search(self, tmp_path) -> None:
        record = build_run_record(
            module="backtest",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            factors=["cmo_momentum"],
            universe=["BTCUSDT"],
            split_dates={"train": "2024-01-01/2024-02-01"},
            results={"sharpe": 1.2, "total_return": 0.1},
            artifact_paths={"metrics": "experiments/run/metrics.json"},
            run_id="run-1",
            now=datetime(2026, 4, 11, 18, 0, 0, tzinfo=UTC),
        )
        add_experiment_entry(record, base_path=tmp_path)
        hits = search_entries("cmo_momentum", base_path=tmp_path)
        assert len(hits) == 1
        assert hits[0].run_id == "run-1"

    def test_add_failure_entry_and_filter_by_type(self, tmp_path) -> None:
        add_failure_entry(
            title="Funding drag failure",
            summary="candidate failed because funding drag overwhelmed gross alpha",
            factor_name="funding_regime",
            tags=["failure", "funding"],
            metadata={"run_id": "run-failure"},
            base_path=tmp_path,
        )
        hits = search_entries("funding", base_path=tmp_path, entry_type="failure_reason")
        assert len(hits) == 1
        assert hits[0].factor_name == "funding_regime"

    def test_add_candidate_disposition_entry(self, tmp_path) -> None:
        add_candidate_disposition_entry(
            title="Candidate disposition: range_chop_filter",
            summary="watchlist candidate, review before retirement",
            factor_name="range_chop_filter",
            tags=["candidate_disposition", "watchlist"],
            metadata={"run_id": "run-disposition", "score": float("nan")},
            base_path=tmp_path,
        )

        hits = search_entries(
            "range_chop_filter",
            base_path=tmp_path,
            entry_type="candidate_disposition",
        )

        assert len(hits) == 1
        assert hits[0].run_id == "run-disposition"
        assert "NaN" not in hits[0].metadata_json

    def test_add_watchlist_review_entry(self, tmp_path) -> None:
        add_watchlist_review_entry(
            title="Watchlist review: body energy",
            summary="保留观察并补长历史证据",
            factor_name="body_energy",
            tags=["watchlist_review", "extend_evidence"],
            metadata={"run_id": "run-2", "score": float("inf")},
            base_path=tmp_path,
        )

        hits = search_entries("body", base_path=tmp_path, entry_type="watchlist_review")

        assert len(hits) == 1
        assert hits[0].factor_name == "body_energy"
        assert "Infinity" not in hits[0].metadata_json

    def test_add_watchlist_evidence_entry(self, tmp_path) -> None:
        add_watchlist_evidence_entry(
            title="Watchlist evidence: range chop",
            summary="需要更长历史确认",
            factor_name="range_chop_filter",
            tags=["watchlist_evidence", "range_chop_filter"],
            metadata={"batch_id": "evidence-1", "score": float("nan")},
            base_path=tmp_path,
        )

        hits = search_entries(
            "range",
            base_path=tmp_path,
            entry_type="watchlist_evidence",
        )

        assert len(hits) == 1
        assert hits[0].run_id == "evidence-1"
        assert "NaN" not in hits[0].metadata_json

    def test_agent_plan_entry_replaces_same_run_id(self, tmp_path) -> None:
        add_agent_plan_entry(
            title="Agent research plan: agent-rerun",
            summary="obsolete plan for agent rerun candidate",
            factor_name="trend_pullback_entry",
            tags=["agent_research_plan", "agent_rerun_candidate"],
            metadata={"run_id": "agent-rerun"},
            base_path=tmp_path,
        )
        add_agent_plan_entry(
            title="Agent research plan: agent-rerun",
            summary="current plan for agent rerun candidate",
            factor_name="trend_pullback_entry",
            tags=["agent_research_plan", "agent_rerun_candidate"],
            metadata={"run_id": "agent-rerun"},
            base_path=tmp_path,
        )

        hits = search_entries(
            "agent_rerun_candidate",
            base_path=tmp_path,
            entry_type="agent_research_plan",
        )

        assert len(hits) == 1
        assert hits[0].summary == "current plan for agent rerun candidate"
