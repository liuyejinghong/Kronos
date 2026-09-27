"""Approval center routes for the local Web API."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from kronos.agent.events import write_event
from kronos.agent.types import (
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentRunId,
    AgentTaskId,
    AgentTaskStatus,
)
from kronos.web.app import get_context
from kronos.web.routes._mappers import validate_run_id
from kronos.web.schemas import ApprovalListResponse, ApprovalResolveRequest, ApprovalResolveResponse

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse)
def list_approvals() -> ApprovalListResponse:
    """Return pending approval items for the local approval center.

    No production path generates approval items yet; the list is honestly
    empty until a real approval flow is wired (audit FSR-014).
    """
    return ApprovalListResponse(items=[])


@router.post("/{approval_id}/resolve", response_model=ApprovalResolveResponse)
def resolve_approval(
    approval_id: str,
    payload: ApprovalResolveRequest,
    request: Request,
) -> ApprovalResolveResponse:
    """Record one approval decision as an append-only Agent event."""
    validate_run_id(payload.run_id)
    context = get_context(request)
    run_dir = context.runtime_path / payload.run_id
    if not run_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Agent run {payload.run_id} does not exist; refusing to record an approval for it.",
        )
    event_id = AgentEventId(f"approval-{uuid4().hex}")
    status = AgentTaskStatus.COMPLETED if payload.approved else AgentTaskStatus.CANCELLED
    event = AgentEvent(
        run_id=AgentRunId(payload.run_id),
        task_id=AgentTaskId(payload.task_id),
        event_id=event_id,
        event_type=AgentEventType.APPROVAL_RESOLVED,
        level=AgentEventLevel.DECISION,
        status=status,
        message_zh=payload.reason_zh,
        metadata={
            "approval_id": approval_id,
            "approved": payload.approved,
        },
    )
    event_path = write_event(event, run_dir=run_dir)
    return ApprovalResolveResponse(
        approval_id=approval_id,
        approved=payload.approved,
        event_id=str(event_id),
        event_path=str(event_path),
    )
