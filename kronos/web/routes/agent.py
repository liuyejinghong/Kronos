"""Agent status routes for the local Web API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request

from kronos.agent.supervisor import AgentSupervisor
from kronos.web.app import WebAppContext, get_context
from kronos.web.routes._mappers import event_response, run_response, task_response, validate_run_id
from kronos.web.schemas import (
    AgentRunBriefResponse,
    AgentRunReportResponse,
    AgentStatusResponse,
    ArtifactRefResponse,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])

if TYPE_CHECKING:
    from pathlib import Path


@router.get("/status", response_model=AgentStatusResponse)
def get_agent_status(request: Request) -> AgentStatusResponse:
    """Return the current local Agent runtime status."""
    context = get_context(request)
    status = AgentSupervisor(context.runtime_path).get_status()
    return AgentStatusResponse(
        active=status.active,
        pending_count=status.pending_count,
        current_run=run_response(status.current_run) if status.current_run is not None else None,
        current_task=(
            task_response(status.current_task) if status.current_task is not None else None
        ),
        last_event=event_response(status.last_event) if status.last_event is not None else None,
    )


@router.get("/runs/{run_id}/summary", response_model=AgentRunBriefResponse)
def get_agent_run_summary(run_id: str, request: Request) -> AgentRunBriefResponse:
    """Return the PM-facing summary for one Agent run."""
    validate_run_id(run_id)
    summary_path = _resolve_summary_path(get_context(request), run_id)
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return _run_brief(payload, report_path=str(summary_path.with_name("agent_run_report.md")))


@router.get("/runs/{run_id}/report", response_model=AgentRunReportResponse)
def get_agent_run_report(run_id: str, request: Request) -> AgentRunReportResponse:
    """Return the readable Markdown report for one Agent run."""
    validate_run_id(run_id)
    report_path = _resolve_report_path(get_context(request), run_id)
    content = report_path.read_text(encoding="utf-8")
    return AgentRunReportResponse(
        run_id=run_id,
        title_zh=_report_title(content),
        report_path=str(report_path),
        content_md=content,
    )


def _resolve_summary_path(context: WebAppContext, run_id: str) -> Path:
    candidate_paths = [
        context.runtime_path / run_id / "agent_run_summary.json",
        context.research_path / "experiments" / run_id / "agent_run_summary.json",
    ]
    for summary_path in candidate_paths:
        if summary_path.exists():
            return summary_path
    raise HTTPException(status_code=404, detail=f"No Agent summary found for run: {run_id}")


def _resolve_report_path(context: WebAppContext, run_id: str) -> Path:
    candidate_paths = [
        context.runtime_path / run_id / "agent_run_report.md",
        context.research_path / "experiments" / run_id / "agent_run_report.md",
    ]
    for report_path in candidate_paths:
        if report_path.exists():
            return report_path
    raise HTTPException(status_code=404, detail=f"No Agent report found for run: {run_id}")


def _run_brief(payload: dict[str, Any], *, report_path: str) -> AgentRunBriefResponse:
    run_payload = _dict_payload(payload.get("run"))
    outputs = payload.get("outputs")
    first_output = _dict_payload(outputs[0] if isinstance(outputs, list) and outputs else {})
    artifacts = _artifact_responses(
        first_output.get("key_evidence") or run_payload.get("artifact_paths") or []
    )
    conclusion = str(first_output.get("conclusion") or "本轮还没有形成最终结论。")
    next_action = str(first_output.get("next_action") or conclusion)
    return AgentRunBriefResponse(
        run_id=str(run_payload.get("run_id") or ""),
        status=str(run_payload.get("status") or ""),
        goal_zh=str(run_payload.get("goal_zh") or ""),
        conclusion_zh=conclusion,
        next_action_zh=next_action,
        max_risk_zh=(
            str(first_output["max_risk"])
            if isinstance(first_output.get("max_risk"), str)
            else None
        ),
        approval_required=bool(first_output.get("approval_required") or False),
        support_reasons=_string_list(first_output.get("support_reasons")),
        opposition_reasons=_string_list(first_output.get("opposition_reasons")),
        evidence_count=len(artifacts),
        event_count=int(payload.get("event_count") or 0),
        artifact_paths=artifacts,
        report_path=report_path,
    )


def _report_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or "Agent 研究报告"
    return "Agent 研究报告"


def _dict_payload(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _artifact_responses(value: Any) -> list[ArtifactRefResponse]:
    if not isinstance(value, list):
        return []
    artifacts: list[ArtifactRefResponse] = []
    for item in value:
        if isinstance(item, dict):
            artifacts.append(ArtifactRefResponse.model_validate(item))
    return artifacts
