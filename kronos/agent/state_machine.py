"""Candidate lifecycle transitions and failure convergence guard."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.types import AgentCandidateId, CandidateLifecycleState


class CandidateLifecycleError(ValueError):
    """Raised when a candidate lifecycle transition is not allowed."""


TERMINAL_STATES = {
    CandidateLifecycleState.OBSERVE,
    CandidateLifecycleState.REDESIGN,
    CandidateLifecycleState.SIMULATE,
    CandidateLifecycleState.LIVE_APPROVAL_REQUIRED,
    CandidateLifecycleState.RETIRED,
}

ALLOWED_TRANSITIONS: dict[CandidateLifecycleState, set[CandidateLifecycleState]] = {
    CandidateLifecycleState.MATERIAL_INTAKE: {CandidateLifecycleState.MIGRATION_REVIEW},
    CandidateLifecycleState.MIGRATION_REVIEW: {CandidateLifecycleState.HYPOTHESIS},
    CandidateLifecycleState.HYPOTHESIS: {CandidateLifecycleState.EXPERIMENT_PLANNED},
    CandidateLifecycleState.EXPERIMENT_PLANNED: {CandidateLifecycleState.VALIDATING},
    CandidateLifecycleState.VALIDATING: {CandidateLifecycleState.AGENT_ANALYSIS},
    CandidateLifecycleState.AGENT_ANALYSIS: {CandidateLifecycleState.COMMITTEE_SCORING},
    CandidateLifecycleState.COMMITTEE_SCORING: TERMINAL_STATES,
    CandidateLifecycleState.OBSERVE: set(),
    CandidateLifecycleState.REDESIGN: set(),
    CandidateLifecycleState.SIMULATE: set(),
    CandidateLifecycleState.LIVE_APPROVAL_REQUIRED: set(),
    CandidateLifecycleState.RETIRED: set(),
}


class CandidateLifecycleTransition(BaseModel):
    """One accepted candidate lifecycle transition."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: AgentCandidateId = Field(min_length=1)
    from_state: CandidateLifecycleState
    to_state: CandidateLifecycleState
    reason_zh: str = Field(min_length=1)


class CandidateLifecycleMachine:
    """Validate candidate lifecycle movement through the Agent research loop."""

    def allowed_next_states(
        self,
        state: CandidateLifecycleState,
    ) -> set[CandidateLifecycleState]:
        """Return the allowed next states for a lifecycle state."""
        return set(ALLOWED_TRANSITIONS[state])

    def transition(
        self,
        *,
        candidate_id: str,
        from_state: CandidateLifecycleState,
        to_state: CandidateLifecycleState,
        reason_zh: str,
    ) -> CandidateLifecycleTransition:
        """Validate and record one candidate lifecycle transition."""
        if to_state not in ALLOWED_TRANSITIONS[from_state]:
            raise CandidateLifecycleError(
                f"Invalid candidate lifecycle transition: {from_state.value} -> {to_state.value}"
            )
        return CandidateLifecycleTransition(
            candidate_id=AgentCandidateId(candidate_id),
            from_state=from_state,
            to_state=to_state,
            reason_zh=reason_zh,
        )


class FailureRecommendation(StrEnum):
    """Recommended candidate disposition after repeated failures."""

    CONTINUE = "continue"
    OBSERVE = "observe"
    RETIRED = "retired"


class FailureEvidence(BaseModel):
    """One Agent failure observation used for convergence control."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: AgentCandidateId = Field(min_length=1)
    failure_class: str = Field(min_length=1)
    has_new_evidence: bool = False
    summary_zh: str = Field(min_length=1)


class FailureConvergenceDecision(BaseModel):
    """Failure convergence recommendation for one candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: AgentCandidateId = Field(min_length=1)
    recommendation: FailureRecommendation
    repeated_failure_count: int = Field(ge=0)
    failure_class: str | None = None
    reason_zh: str


class FailureConvergenceGuard:
    """Stop the Agent from repeatedly chasing the same unsupported direction."""

    def __init__(
        self,
        *,
        observe_threshold: int = 2,
        retired_threshold: int = 3,
        retirement_failure_classes: set[str] | None = None,
    ) -> None:
        self.observe_threshold = observe_threshold
        self.retired_threshold = retired_threshold
        self.retirement_failure_classes = retirement_failure_classes or {
            "market_mechanism_mismatch",
            "migration_invalid",
        }

    def decide(self, failures: list[FailureEvidence]) -> FailureConvergenceDecision:
        """Return observe/retired when the same failure repeats without new evidence."""
        if not failures:
            return FailureConvergenceDecision(
                candidate_id=AgentCandidateId("unknown"),
                recommendation=FailureRecommendation.CONTINUE,
                repeated_failure_count=0,
                reason_zh="暂无失败记录, 继续观察。",
            )

        latest = failures[-1]
        repeated_count = self._latest_same_class_count(failures)
        has_new_evidence = any(item.has_new_evidence for item in failures[-repeated_count:])
        recommendation = FailureRecommendation.CONTINUE
        reason_zh = "仍有新证据或失败次数不足, 继续验证。"

        if repeated_count >= self.retired_threshold and not has_new_evidence:
            recommendation = FailureRecommendation.RETIRED
            reason_zh = "连续多轮同类失败且没有新证据, 建议进入退休。"
        elif (
            repeated_count >= self.observe_threshold
            and not has_new_evidence
            and latest.failure_class in self.retirement_failure_classes
        ):
            recommendation = FailureRecommendation.RETIRED
            reason_zh = "连续两轮关键同类失败且没有新证据, 建议退休。"
        elif repeated_count >= self.observe_threshold and not has_new_evidence:
            recommendation = FailureRecommendation.OBSERVE
            reason_zh = "连续两轮同类失败且没有新证据, 建议转入观察。"

        return FailureConvergenceDecision(
            candidate_id=latest.candidate_id,
            recommendation=recommendation,
            repeated_failure_count=repeated_count,
            failure_class=latest.failure_class,
            reason_zh=reason_zh,
        )

    def _latest_same_class_count(self, failures: list[FailureEvidence]) -> int:
        latest_class = failures[-1].failure_class
        count = 0
        for failure in reversed(failures):
            if failure.failure_class != latest_class:
                break
            count += 1
        return count
