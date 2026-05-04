"""Mapping helpers from Agent domain models to Web API schemas."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import HTTPException

from kronos.web.schemas import (
    AgentEventResponse,
    AgentRunStatusResponse,
    AgentTaskStatusResponse,
    ArtifactRefResponse,
)

if TYPE_CHECKING:
    from kronos.agent.types import AgentArtifactRef, AgentEvent, AgentRun, AgentTask

_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:@(){}+-]*$")


def validate_run_id(run_id: str) -> str:
    """Validate run_id is safe for filesystem path construction.

    Rejects values containing path traversal characters (``..``, ``/``, ``\\``)
    or other unsafe patterns. Returns the validated run_id unchanged.
    """
    if not run_id or not run_id.strip():
        raise HTTPException(status_code=400, detail="run_id must not be empty")
    if not _RUN_ID_PATTERN.match(run_id):
        raise HTTPException(status_code=400, detail=f"Invalid run_id: {run_id}")
    return run_id


def artifact_response(artifact: AgentArtifactRef) -> ArtifactRefResponse:
    """Convert an Agent artifact ref to a Web response."""
    return ArtifactRefResponse(
        name=artifact.name,
        path=artifact.path,
        artifact_type=artifact.artifact_type,
        summary_zh=artifact.summary_zh,
    )


def event_response(event: AgentEvent) -> AgentEventResponse:
    """Convert an Agent event to a Web timeline item."""
    return AgentEventResponse(
        run_id=str(event.run_id),
        task_id=str(event.task_id),
        event_id=str(event.event_id),
        event_type=event.event_type,
        level=event.level,
        status=event.status,
        message_zh=event.message_zh,
        candidate_id=str(event.candidate_id) if event.candidate_id is not None else None,
        role_id=str(event.role_id) if event.role_id is not None else None,
        prompt_version=str(event.prompt_version) if event.prompt_version is not None else None,
        model_provider=event.model_provider,
        model_name=event.model_name,
        artifact_paths=[artifact_response(artifact) for artifact in event.artifact_paths],
    )


def run_response(run: AgentRun) -> AgentRunStatusResponse:
    """Convert an Agent run to a Web status item."""
    return AgentRunStatusResponse(
        run_id=str(run.run_id),
        status=run.status,
        goal_zh=run.goal_zh,
        current_task_id=str(run.current_task_id) if run.current_task_id is not None else None,
        artifact_paths=[artifact_response(artifact) for artifact in run.artifact_paths],
    )


def task_response(task: AgentTask) -> AgentTaskStatusResponse:
    """Convert an Agent task to a Web status item."""
    return AgentTaskStatusResponse(
        task_id=str(task.task_id),
        status=task.status,
        title_zh=task.title_zh,
        candidate_id=str(task.candidate_id) if task.candidate_id is not None else None,
        lifecycle_state=task.lifecycle_state,
    )
