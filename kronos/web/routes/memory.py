"""Agent Memory Control routes for the local Web API."""

from __future__ import annotations

from fastapi import APIRouter, Request

from kronos.agent.memory_control import build_memory_dashboard, run_drift_check
from kronos.agent.memory_control.handoff import build_handoff_pack
from kronos.agent.memory_control.models import (
    AgentHandoffPack,
    AgentMemoryDashboard,
    MemoryCheckSummary,
    MemorySummaryItem,
)
from kronos.agent.memory_control.readers import (
    build_current_state,
    extract_decisions,
    extract_lessons,
    load_memory_files,
)
from kronos.web.app import get_context

router = APIRouter(prefix="/api/agent/memory", tags=["agent-memory"])


@router.get("/summary", response_model=AgentMemoryDashboard)
def get_memory_summary(request: Request) -> AgentMemoryDashboard:
    """Return the full read-only Agent memory dashboard."""
    context = get_context(request)
    return build_memory_dashboard(context.project_root)


@router.get("/decisions", response_model=list[MemorySummaryItem])
def get_memory_decisions(request: Request) -> list[MemorySummaryItem]:
    """Return recent decisions and lessons for the Agent memory dashboard."""
    context = get_context(request)
    files = load_memory_files(context.project_root)
    return [*extract_decisions(files), *extract_lessons(files)]


@router.get("/handoff", response_model=AgentHandoffPack)
def get_memory_handoff(request: Request) -> AgentHandoffPack:
    """Return a copyable handoff prompt for a new Agent session."""
    context = get_context(request)
    files = load_memory_files(context.project_root)
    state = build_current_state(files)
    decisions = extract_decisions(files)
    lessons = extract_lessons(files)
    return build_handoff_pack(
        context.project_root,
        state=state,
        decisions=decisions,
        lessons=lessons,
    )


@router.get("/check", response_model=MemoryCheckSummary)
def get_memory_check(request: Request) -> MemoryCheckSummary:
    """Return rule-based memory drift and safety checks."""
    context = get_context(request)
    return run_drift_check(context.project_root)
