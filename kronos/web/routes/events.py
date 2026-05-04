"""Agent event timeline routes for the local Web API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from kronos.agent.events import EVENT_TIMELINE_FILENAME, read_events
from kronos.web.app import WebAppContext, get_context
from kronos.web.routes._mappers import event_response, validate_run_id
from kronos.web.schemas import AgentEventResponse

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

router = APIRouter(prefix="/api/agent/events", tags=["events"])


@router.get("", response_model=list[AgentEventResponse])
def list_agent_events(
    request: Request,
    run_id: str = Query(..., min_length=1),
) -> list[AgentEventResponse]:
    """Return a rebuilt event timeline for one Agent run."""
    run_dir = _resolve_run_dir(get_context(request), run_id)
    return [event_response(event) for event in read_events(run_dir)]


@router.get("/stream")
def stream_agent_events(
    request: Request,
    run_id: str = Query(..., min_length=1),
) -> StreamingResponse:
    """Stream the existing Agent event timeline as Server-Sent Events."""
    run_dir = _resolve_run_dir(get_context(request), run_id)
    return StreamingResponse(
        _event_stream(run_dir),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _event_stream(run_dir: Path) -> Iterator[str]:
    for event in read_events(run_dir):
        payload = event_response(event).model_dump(mode="json")
        yield f"event: {event.event_type.value}\n"
        yield f"data: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"


def _resolve_run_dir(context: WebAppContext, run_id: str) -> Path:
    validate_run_id(run_id)
    candidate_dirs = [
        context.runtime_path / run_id,
        context.research_path / "experiments" / run_id,
    ]
    for run_dir in candidate_dirs:
        if (run_dir / EVENT_TIMELINE_FILENAME).exists():
            return run_dir
    raise HTTPException(status_code=404, detail=f"No Agent events found for run: {run_id}")
