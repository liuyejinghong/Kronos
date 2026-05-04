"""Tests for candidate lifecycle state machine and failure convergence."""

from __future__ import annotations

from itertools import pairwise

import pytest

from kronos.agent.state_machine import (
    CandidateLifecycleError,
    CandidateLifecycleMachine,
    FailureConvergenceGuard,
    FailureEvidence,
    FailureRecommendation,
)
from kronos.agent.types import AgentCandidateId, CandidateLifecycleState


def test_candidate_lifecycle_allows_expected_research_path() -> None:
    machine = CandidateLifecycleMachine()
    candidate_id = "trend_pullback_entry"
    path = [
        CandidateLifecycleState.MATERIAL_INTAKE,
        CandidateLifecycleState.MIGRATION_REVIEW,
        CandidateLifecycleState.HYPOTHESIS,
        CandidateLifecycleState.EXPERIMENT_PLANNED,
        CandidateLifecycleState.VALIDATING,
        CandidateLifecycleState.AGENT_ANALYSIS,
        CandidateLifecycleState.COMMITTEE_SCORING,
        CandidateLifecycleState.REDESIGN,
    ]

    transitions = [
        machine.transition(
            candidate_id=candidate_id,
            from_state=from_state,
            to_state=to_state,
            reason_zh="进入下一步。",
        )
        for from_state, to_state in pairwise(path)
    ]

    assert [transition.to_state for transition in transitions] == path[1:]


def test_candidate_lifecycle_rejects_invalid_transition() -> None:
    machine = CandidateLifecycleMachine()

    with pytest.raises(CandidateLifecycleError):
        machine.transition(
            candidate_id="trend_pullback_entry",
            from_state=CandidateLifecycleState.MATERIAL_INTAKE,
            to_state=CandidateLifecycleState.VALIDATING,
            reason_zh="跳过必要步骤。",
        )


def test_committee_scoring_can_enter_terminal_states() -> None:
    machine = CandidateLifecycleMachine()

    assert machine.allowed_next_states(CandidateLifecycleState.COMMITTEE_SCORING) == {
        CandidateLifecycleState.OBSERVE,
        CandidateLifecycleState.REDESIGN,
        CandidateLifecycleState.SIMULATE,
        CandidateLifecycleState.LIVE_APPROVAL_REQUIRED,
        CandidateLifecycleState.RETIRED,
    }


def test_live_approval_required_does_not_auto_enter_live() -> None:
    machine = CandidateLifecycleMachine()

    assert machine.allowed_next_states(CandidateLifecycleState.LIVE_APPROVAL_REQUIRED) == set()


def test_failure_guard_recommends_observe_after_repeated_same_failure() -> None:
    guard = FailureConvergenceGuard()
    failures = [
        FailureEvidence(
            candidate_id=AgentCandidateId("range_chop_filter"),
            failure_class="weak_signal",
            has_new_evidence=False,
            summary_zh="第一轮弱信号。",
        ),
        FailureEvidence(
            candidate_id=AgentCandidateId("range_chop_filter"),
            failure_class="weak_signal",
            has_new_evidence=False,
            summary_zh="第二轮弱信号。",
        ),
    ]

    decision = guard.decide(failures)

    assert decision.recommendation == FailureRecommendation.OBSERVE
    assert decision.repeated_failure_count == 2


def test_failure_guard_recommends_retired_for_repeated_terminal_failure() -> None:
    guard = FailureConvergenceGuard()
    failures = [
        FailureEvidence(
            candidate_id=AgentCandidateId("legacy_factor"),
            failure_class="market_mechanism_mismatch",
            has_new_evidence=False,
            summary_zh="第一轮机制不适配。",
        ),
        FailureEvidence(
            candidate_id=AgentCandidateId("legacy_factor"),
            failure_class="market_mechanism_mismatch",
            has_new_evidence=False,
            summary_zh="第二轮机制不适配。",
        ),
    ]

    decision = guard.decide(failures)

    assert decision.recommendation == FailureRecommendation.RETIRED
    assert decision.repeated_failure_count == 2


def test_failure_guard_continues_when_new_evidence_exists() -> None:
    guard = FailureConvergenceGuard()
    failures = [
        FailureEvidence(
            candidate_id=AgentCandidateId("range_chop_filter"),
            failure_class="weak_signal",
            has_new_evidence=False,
            summary_zh="第一轮弱信号。",
        ),
        FailureEvidence(
            candidate_id=AgentCandidateId("range_chop_filter"),
            failure_class="weak_signal",
            has_new_evidence=True,
            summary_zh="第二轮新增证据。",
        ),
    ]

    decision = guard.decide(failures)

    assert decision.recommendation == FailureRecommendation.CONTINUE
