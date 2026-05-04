"""Local Agent Supervisor lifecycle skeleton."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.events import EVENT_TIMELINE_FILENAME, read_events, replace_events, write_event
from kronos.agent.types import (
    AgentArtifactRef,
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentRun,
    AgentRunId,
    AgentRunStatus,
    AgentTask,
    AgentTaskId,
    AgentTaskStatus,
)

SUPERVISOR_STATUS_FILENAME = "agent_supervisor_status.json"


class AgentSupervisorError(RuntimeError):
    """Raised when the local supervisor receives an invalid lifecycle action."""


class AgentSupervisorStatus(BaseModel):
    """PM-facing current Agent runtime status snapshot."""

    model_config = ConfigDict(extra="forbid")

    active: bool = False
    current_run: AgentRun | None = None
    current_task: AgentTask | None = None
    last_event: AgentEvent | None = None
    pending_count: int = Field(default=0, ge=0)


class AgentSupervisor:
    """In-process Agent Supervisor with a small persisted status snapshot."""

    def __init__(self, run_root: str | Path) -> None:
        self.run_root = Path(run_root)
        self.status_path = self.run_root / SUPERVISOR_STATUS_FILENAME
        self._status = self._load_status()

    def start_run(
        self,
        *,
        run_id: str,
        goal_zh: str,
        task_id: str,
        task_title_zh: str,
    ) -> AgentRun:
        """Create and start one Agent run."""
        if self._status.active:
            active_run = self._status.current_run
            raise AgentSupervisorError(
                f"Agent run already active: {active_run.run_id if active_run else 'unknown'}"
            )

        typed_run_id = AgentRunId(run_id)
        typed_task_id = AgentTaskId(task_id)
        task = AgentTask(
            run_id=typed_run_id,
            task_id=typed_task_id,
            status=AgentTaskStatus.RUNNING,
            title_zh=task_title_zh,
        )
        run = AgentRun(
            run_id=typed_run_id,
            status=AgentRunStatus.RUNNING,
            goal_zh=goal_zh,
            current_task_id=typed_task_id,
            tasks=[task],
        )
        event = self._event(
            run=run,
            task=task,
            event_type=AgentEventType.RUN_STARTED,
            level=AgentEventLevel.INFO,
            status=AgentTaskStatus.RUNNING,
            message_zh=f"Agent 运行已启动: {task_title_zh}",
        )
        self._write_event(event)
        self._status = AgentSupervisorStatus(
            active=True,
            current_run=run,
            current_task=task,
            last_event=event,
            pending_count=0,
        )
        self._save_status()
        return run

    def stop_run(self, *, reason_zh: str = "用户停止 Agent 运行。") -> AgentRun:
        """Stop the current Agent run and persist a stopped status snapshot."""
        if self._status.current_run is None:
            raise AgentSupervisorError("No Agent run is active.")

        run = self._status.current_run
        task = self._status.current_task
        stopped_task: AgentTask | None = None
        if task is not None:
            stopped_task = task.model_copy(update={"status": AgentTaskStatus.CANCELLED})

        stopped_tasks = [
            stopped_task if task_item.task_id == stopped_task.task_id else task_item
            for task_item in run.tasks
        ] if stopped_task is not None else run.tasks

        stopped_run = run.model_copy(
            update={
                "status": AgentRunStatus.CANCELLED,
                "tasks": stopped_tasks,
            }
        )
        event_task = stopped_task or AgentTask(
            run_id=stopped_run.run_id,
            task_id=AgentTaskId("supervisor"),
            status=AgentTaskStatus.CANCELLED,
            title_zh="停止 Agent 运行",
        )
        event = self._event(
            run=stopped_run,
            task=event_task,
            event_type=AgentEventType.RUN_COMPLETED,
            level=AgentEventLevel.WARNING,
            status=AgentTaskStatus.CANCELLED,
            message_zh=reason_zh,
        )
        self._write_event(event)
        self._status = AgentSupervisorStatus(
            active=False,
            current_run=stopped_run,
            current_task=stopped_task,
            last_event=event,
            pending_count=self._status.pending_count,
        )
        self._save_status()
        return stopped_run

    def publish_run_snapshot(
        self,
        *,
        run: AgentRun,
        events: list[AgentEvent],
        pending_count: int = 0,
    ) -> AgentSupervisorStatus:
        """Publish a completed or waiting run as the latest Web-readable snapshot."""
        if events:
            replace_events(events, run_dir=self._run_dir(run.run_id))

        active = run.status in {
            AgentRunStatus.PENDING,
            AgentRunStatus.RUNNING,
            AgentRunStatus.WAITING_APPROVAL,
        }
        self._status = AgentSupervisorStatus(
            active=active,
            current_run=run,
            current_task=_current_task(run),
            last_event=events[-1] if events else None,
            pending_count=pending_count,
        )
        self._save_status()
        return self._status

    def get_status(self) -> AgentSupervisorStatus:
        """Return the latest supervisor status snapshot."""
        return self._status

    def _run_dir(self, run_id: AgentRunId) -> Path:
        return self.run_root / str(run_id)

    def _write_event(self, event: AgentEvent) -> None:
        write_event(event, run_dir=self._run_dir(event.run_id))

    def _event(
        self,
        *,
        run: AgentRun,
        task: AgentTask,
        event_type: AgentEventType,
        level: AgentEventLevel,
        status: AgentTaskStatus,
        message_zh: str,
    ) -> AgentEvent:
        return AgentEvent(
            run_id=run.run_id,
            task_id=task.task_id,
            event_id=AgentEventId(f"event-{uuid4().hex}"),
            event_type=event_type,
            level=level,
            status=status,
            message_zh=message_zh,
        )

    def _load_status(self) -> AgentSupervisorStatus:
        if not self.status_path.exists():
            return self._recover_status_from_events()
        status = AgentSupervisorStatus.model_validate_json(
            self.status_path.read_text(encoding="utf-8")
        )
        if status.current_run is None:
            return status
        events = read_events(self._run_dir(status.current_run.run_id))
        if events:
            status = status.model_copy(update={"last_event": events[-1]})
        return status

    def _recover_status_from_events(self) -> AgentSupervisorStatus:
        events = self._latest_events()
        if not events:
            return AgentSupervisorStatus()
        last_event = events[-1]
        task = AgentTask(
            run_id=last_event.run_id,
            task_id=last_event.task_id,
            status=last_event.status,
            title_zh="从事件时间线恢复的 Agent 任务",
            candidate_id=last_event.candidate_id,
            artifact_paths=_artifact_paths_from_events(events),
            error_ref=last_event.error_ref,
        )
        run = AgentRun(
            run_id=last_event.run_id,
            status=_run_status_from_event(last_event),
            goal_zh=_goal_from_events(events),
            current_task_id=last_event.task_id,
            tasks=[task],
            artifact_paths=task.artifact_paths,
            error_ref=last_event.error_ref,
            metadata={"recovered_from": "agent_events.jsonl"},
        )
        return AgentSupervisorStatus(
            active=_is_active_run_status(run.status),
            current_run=run,
            current_task=task,
            last_event=last_event,
            pending_count=0,
        )

    def _latest_events(self) -> list[AgentEvent]:
        if not self.run_root.exists():
            return []
        event_dirs = [
            child
            for child in self.run_root.iterdir()
            if child.is_dir() and read_events(child)
        ]
        if not event_dirs:
            return []
        latest_dir = max(
            event_dirs,
            key=lambda child: (child / EVENT_TIMELINE_FILENAME).stat().st_mtime,
        )
        return read_events(latest_dir)

    def _save_status(self) -> None:
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(
            json.dumps(
                self._status.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )


def _current_task(run: AgentRun) -> AgentTask | None:
    if run.current_task_id is None:
        return None
    return next(
        (task for task in run.tasks if task.task_id == run.current_task_id),
        None,
    )


def _is_active_run_status(status: AgentRunStatus) -> bool:
    return status in {
        AgentRunStatus.PENDING,
        AgentRunStatus.RUNNING,
        AgentRunStatus.WAITING_APPROVAL,
    }


def _run_status_from_event(event: AgentEvent) -> AgentRunStatus:
    if event.status == AgentTaskStatus.CANCELLED:
        return AgentRunStatus.CANCELLED
    if event.event_type == AgentEventType.RUN_COMPLETED:
        return AgentRunStatus.COMPLETED
    if event.event_type in {
        AgentEventType.RUN_FAILED,
        AgentEventType.TASK_FAILED,
        AgentEventType.TOOL_EXECUTION_FAILED,
    } or event.status == AgentTaskStatus.FAILED:
        return AgentRunStatus.FAILED
    if event.status == AgentTaskStatus.WAITING_APPROVAL:
        return AgentRunStatus.WAITING_APPROVAL
    return AgentRunStatus.RUNNING


def _goal_from_events(events: list[AgentEvent]) -> str:
    started = next(
        (event for event in events if event.event_type == AgentEventType.RUN_STARTED),
        None,
    )
    if started is not None:
        return f"从事件时间线恢复: {started.message_zh}"
    return "从事件时间线恢复的 Agent run。"


def _artifact_paths_from_events(events: list[AgentEvent]) -> list[AgentArtifactRef]:
    artifacts: list[AgentArtifactRef] = []
    seen: set[str] = set()
    for event in events:
        for artifact in event.artifact_paths:
            if artifact.path in seen:
                continue
            seen.add(artifact.path)
            artifacts.append(artifact)
    return artifacts
