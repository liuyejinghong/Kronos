"""Tests for the Agent research queue."""

from __future__ import annotations

import pytest

from kronos.agent.queue import AgentResearchQueue
from kronos.agent.types import AgentRunId, AgentTask, AgentTaskId, AgentTaskStatus


def _task(task_id: str) -> AgentTask:
    return AgentTask(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId(task_id),
        status=AgentTaskStatus.PENDING,
        title_zh=f"任务 {task_id}",
    )


def test_queue_starts_first_task_and_queues_second_task() -> None:
    queue = AgentResearchQueue()

    first = queue.submit(_task("task-1"))
    second = queue.submit(_task("task-2"))

    assert first.status == AgentTaskStatus.RUNNING
    assert second.status == AgentTaskStatus.QUEUED
    assert queue.active_task == first
    assert queue.pending_count == 1


def test_queue_starts_next_pending_after_current_finishes() -> None:
    queue = AgentResearchQueue()
    queue.submit(_task("task-1"))
    queue.submit(_task("task-2"))

    finished = queue.finish_active()
    next_task = queue.start_next()

    assert finished.status == AgentTaskStatus.COMPLETED
    assert next_task is not None
    assert next_task.task_id == "task-2"
    assert next_task.status == AgentTaskStatus.RUNNING
    assert queue.pending_count == 0


def test_queue_does_not_start_next_while_main_task_is_running() -> None:
    queue = AgentResearchQueue()
    queue.submit(_task("task-1"))
    queue.submit(_task("task-2"))

    assert queue.start_next() is None
    assert queue.pending_count == 1


def test_queue_requires_active_task_before_finish() -> None:
    queue = AgentResearchQueue()

    with pytest.raises(RuntimeError):
        queue.finish_active()
