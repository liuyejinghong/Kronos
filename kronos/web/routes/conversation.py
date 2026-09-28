"""Conversation + run API routes (package P14, release doc section 4.7).

Endpoints:
- ``POST /api/conversations``                     → create session (201)
- ``POST /api/conversations/{id}/messages``       → 202-shaped turn result
- ``GET  /api/conversations/{id}``                → session + messages + revision
- ``GET  /api/runs/{task_id}``                    → task status (TaskStore read)
- ``GET  /api/runs/{task_id}/events?after_seq=``  → incremental event poll
- ``POST /api/runs/{task_id}/cancel``             → two-step cancel (step 1)
- ``GET  /api/verdicts/{run_id}``                 → verdict artifact by ref

Message submission persists first and returns the 202-shaped result with
message/revision/task ids; the browser polls the run endpoints from there.
The service is lazily created once per app from ``WebAppContext.state_path``
(same pattern as the settings routes' lazy stores) and shared across
requests so the SQLite connections stay open.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from kronos.conversation.service import (
    ConversationService,
    MessageResult,
    SessionDetail,
    SessionNotFoundError,
)
from kronos.research.verdict.contracts import TaskEvent  # noqa: TC001  (response model)
from kronos.runtime.tasks import TaskNotFoundError, TaskStateError
from kronos.web.app import get_context
from kronos.web.routes._mappers import validate_run_id

router = APIRouter(tags=["conversation"])


# ----------------------------------------------------------------- schemas


class ConversationCreatedResponse(BaseModel):
    """Result of creating one conversation session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    created_at_ms: int
    current_revision_id: str


class MessageRequest(BaseModel):
    """One user utterance (strict: unknown fields rejected)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)


class RunStatusResponse(BaseModel):
    """Task status projection for the conversation UI."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    kind: str
    state: str
    stage: str
    attempt: int
    error_ref: str | None = None
    created_at: int
    updated_at: int
    result_available: bool


class RunEventsResponse(BaseModel):
    """Incremental event page for one task (``?after_seq=`` polling)."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    events: list[TaskEvent]


class VerdictResponse(BaseModel):
    """Published verdict artifact for one run (read-only)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    state: str
    verdict: dict[str, Any]
    artifact_refs: dict[str, str]


# ------------------------------------------------------------ service access


def get_conversation_service(request: Request) -> ConversationService:
    """Return the app-wide conversation service, creating it on first use."""
    service = getattr(request.app.state, "conversation_service", None)
    if service is None:
        context = get_context(request)
        service = ConversationService(context.state_path)
        request.app.state.conversation_service = service
    return service


# ------------------------------------------------------------------- routes


@router.post("/api/conversations", response_model=ConversationCreatedResponse, status_code=201)
def create_conversation(request: Request) -> ConversationCreatedResponse:
    service = get_conversation_service(request)
    session = service.create_session()
    return ConversationCreatedResponse(
        session_id=session.session_id,
        created_at_ms=session.created_at_ms,
        current_revision_id=session.current_revision_id,
    )


@router.post(
    "/api/conversations/{session_id}/messages",
    response_model=MessageResult,
    status_code=202,
)
def send_message(session_id: str, payload: MessageRequest, request: Request) -> MessageResult:
    validate_run_id(session_id)  # same safe-id pattern as run ids
    service = get_conversation_service(request)
    try:
        return service.send_message(session_id, payload.text)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/conversations/{session_id}", response_model=SessionDetail)
def get_conversation(session_id: str, request: Request) -> SessionDetail:
    validate_run_id(session_id)
    service = get_conversation_service(request)
    try:
        return service.get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/runs/{task_id}", response_model=RunStatusResponse)
def get_run(task_id: str, request: Request) -> RunStatusResponse:
    validate_run_id(task_id)
    service = get_conversation_service(request)
    try:
        task = service.task_store.get(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunStatusResponse(
        task_id=task.task_id,
        kind=task.kind,
        state=task.state,
        stage=task.stage,
        attempt=task.attempt,
        error_ref=task.error_ref,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result_available=service.task_store.get_result(task_id) is not None,
    )


@router.get("/api/runs/{task_id}/events", response_model=RunEventsResponse)
def get_run_events(
    task_id: str,
    request: Request,
    after_seq: int = Query(default=0, ge=0),
) -> RunEventsResponse:
    validate_run_id(task_id)
    service = get_conversation_service(request)
    try:
        service.task_store.get(task_id)  # existence check → 404
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    events = service.task_store.events(task_id, after_seq=after_seq)
    return RunEventsResponse(task_id=task_id, events=events)


@router.post("/api/runs/{task_id}/cancel", response_model=RunStatusResponse)
def cancel_run(task_id: str, request: Request) -> RunStatusResponse:
    """First step of the two-step cancel (worker confirms the stop later)."""
    validate_run_id(task_id)
    service = get_conversation_service(request)
    try:
        task = service.task_store.request_cancel(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RunStatusResponse(
        task_id=task.task_id,
        kind=task.kind,
        state=task.state,
        stage=task.stage,
        attempt=task.attempt,
        error_ref=task.error_ref,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result_available=service.task_store.get_result(task_id) is not None,
    )


@router.get("/api/verdicts/{run_id}", response_model=VerdictResponse)
def get_verdict(run_id: str, request: Request) -> VerdictResponse:
    validate_run_id(run_id)
    service = get_conversation_service(request)
    try:
        task = service.task_store.get(run_id)
        result = service.task_store.get_result(run_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result is None or "verdict" not in result:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id} has no published verdict (state={task.state})",
        )
    verdict = result["verdict"]
    artifact_raw = result.get("artifact_refs")
    artifact_refs = (
        {str(key): str(value) for key, value in artifact_raw.items()}
        if isinstance(artifact_raw, dict)
        else {}
    )
    return VerdictResponse(
        run_id=run_id, state=task.state, verdict=verdict, artifact_refs=artifact_refs
    )
