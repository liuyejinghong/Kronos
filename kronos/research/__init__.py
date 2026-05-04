"""Research-layer orchestration helpers."""

from __future__ import annotations

from kronos.research.agent_planner import (
    AgentEvidenceDecision,
    AgentEvidenceDecisionReport,
    AgentHypothesis,
    AgentResearchPlan,
    run_research_agent_decision,
    run_research_agent_planner,
)
from kronos.research.auto_runner import AutoRunCycleResult, run_auto_research_cycle
from kronos.research.promotion import (
    CandidatePromotionBatchResult,
    PromotionCriteria,
    PromotionDecision,
    evaluate_factor_promotion,
    run_candidate_promotion_batch,
    run_factor_promotion_workflow,
    run_market_data_promotion_batch,
)
from kronos.research.watchlist_evidence import (
    EvidenceSlice,
    EvidenceSliceType,
    WatchlistEvidenceReviewResult,
    run_watchlist_evidence_review,
)
from kronos.research.workbench import (
    CandidateDisposition,
    CandidateDispositionStatus,
    FailureReasonCategory,
    FailureReasonGroup,
    ResearchWorkbenchResult,
    WatchlistReview,
    WatchlistReviewAction,
    build_candidate_dispositions,
    build_watchlist_reviews,
    group_failure_reasons,
    run_research_workbench,
)

__all__ = [
    "AgentEvidenceDecision",
    "AgentEvidenceDecisionReport",
    "AgentHypothesis",
    "AgentResearchPlan",
    "AutoRunCycleResult",
    "CandidateDisposition",
    "CandidateDispositionStatus",
    "CandidatePromotionBatchResult",
    "EvidenceSlice",
    "EvidenceSliceType",
    "FailureReasonCategory",
    "FailureReasonGroup",
    "PromotionCriteria",
    "PromotionDecision",
    "ResearchWorkbenchResult",
    "WatchlistEvidenceReviewResult",
    "WatchlistReview",
    "WatchlistReviewAction",
    "build_candidate_dispositions",
    "build_watchlist_reviews",
    "evaluate_factor_promotion",
    "group_failure_reasons",
    "run_auto_research_cycle",
    "run_candidate_promotion_batch",
    "run_factor_promotion_workflow",
    "run_market_data_promotion_batch",
    "run_research_agent_decision",
    "run_research_agent_planner",
    "run_research_workbench",
    "run_watchlist_evidence_review",
]
