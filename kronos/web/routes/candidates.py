"""Candidate pool routes for the local Web API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from kronos.agent.types import CandidateLifecycleState
from kronos.factor.candidates import CandidateFactorSpec, list_candidate_factors
from kronos.web.schemas import CandidateDetailResponse, CandidateListItemResponse

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("", response_model=list[CandidateListItemResponse])
def list_candidates() -> list[CandidateListItemResponse]:
    """Return the current candidate pool for the Web workbench."""
    return [_candidate_item(spec) for spec in list_candidate_factors()]


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
def get_candidate(candidate_id: str) -> CandidateDetailResponse:
    """Return one candidate detail payload."""
    spec = next(
        (item for item in list_candidate_factors() if item.candidate_id == candidate_id),
        None,
    )
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown candidate: {candidate_id}")
    item = _candidate_item(spec)
    return CandidateDetailResponse(
        **item.model_dump(),
        source_strategies=list(spec.source_strategies),
        artifact_paths=[],
        next_action_zh="等待 Agent 选择是否进入下一轮研究。",
    )


def _candidate_item(spec: CandidateFactorSpec) -> CandidateListItemResponse:
    lifecycle_state = _candidate_lifecycle_state(spec)
    return CandidateListItemResponse(
        candidate_id=spec.candidate_id,
        title_zh=spec.title,
        family=spec.family,
        origin=spec.origin,
        migration_rank=spec.migration_rank,
        implementation_name=spec.implementation_name,
        lifecycle_state=lifecycle_state,
        status_label_zh=_status_label(lifecycle_state),
    )


def _candidate_lifecycle_state(spec: CandidateFactorSpec) -> CandidateLifecycleState | None:
    if spec.lifecycle_state is not None:
        return spec.lifecycle_state
    if spec.initial_status == "candidate":
        return CandidateLifecycleState.MIGRATION_REVIEW
    try:
        return CandidateLifecycleState(spec.initial_status)
    except ValueError:
        return None


def _status_label(state: CandidateLifecycleState | None) -> str:
    if state is None:
        return "未知"
    labels = {
        CandidateLifecycleState.MATERIAL_INTAKE: "材料进入",
        CandidateLifecycleState.MIGRATION_REVIEW: "迁移审查",
        CandidateLifecycleState.HYPOTHESIS: "假设生成",
        CandidateLifecycleState.EXPERIMENT_PLANNED: "实验计划",
        CandidateLifecycleState.VALIDATING: "验证中",
        CandidateLifecycleState.AGENT_ANALYSIS: "Agent 分析",
        CandidateLifecycleState.COMMITTEE_SCORING: "投委会评分",
        CandidateLifecycleState.OBSERVE: "观察",
        CandidateLifecycleState.REDESIGN: "候选改造",
        CandidateLifecycleState.SIMULATE: "模拟盘",
        CandidateLifecycleState.LIVE_APPROVAL_REQUIRED: "待实盘审批",
        CandidateLifecycleState.RETIRED: "淘汰",
    }
    return labels[state]
