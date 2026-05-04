"""Single-main-task research queue for the Agent runtime."""

from __future__ import annotations

from collections import deque

from kronos.agent.types import AgentTask, AgentTaskStatus

MAIN_TASK_ACTIVE_STATUSES = {
    AgentTaskStatus.RUNNING,
    AgentTaskStatus.WAITING_APPROVAL,
}


class AgentResearchQueue:
    """Small in-memory queue that prevents multiple main tasks from running."""

    def __init__(self) -> None:
        self._pending: deque[AgentTask] = deque()
        self._active_task: AgentTask | None = None

    @property
    def pending_count(self) -> int:
        """Return how many tasks are waiting behind the current main task."""
        return len(self._pending)

    @property
    def active_task(self) -> AgentTask | None:
        """Return the current main task if one is active."""
        return self._active_task

    def submit(self, task: AgentTask) -> AgentTask:
        """Start a task when no main task is active, otherwise queue it."""
        if self._is_main_task_active():
            queued_task = task.model_copy(update={"status": AgentTaskStatus.QUEUED})
            self._pending.append(queued_task)
            return queued_task

        running_task = task.model_copy(update={"status": AgentTaskStatus.RUNNING})
        self._active_task = running_task
        return running_task

    def finish_active(self, status: AgentTaskStatus = AgentTaskStatus.COMPLETED) -> AgentTask:
        """Finish the current main task."""
        if self._active_task is None:
            raise RuntimeError("No active Agent task to finish.")
        finished_task = self._active_task.model_copy(update={"status": status})
        self._active_task = finished_task
        return finished_task

    def start_next(self) -> AgentTask | None:
        """Start the next pending task after the current task has finished."""
        if self._is_main_task_active():
            return None
        if not self._pending:
            self._active_task = None
            return None
        next_task = self._pending.popleft().model_copy(update={"status": AgentTaskStatus.RUNNING})
        self._active_task = next_task
        return next_task

    def _is_main_task_active(self) -> bool:
        return (
            self._active_task is not None
            and self._active_task.status in MAIN_TASK_ACTIVE_STATUSES
        )
