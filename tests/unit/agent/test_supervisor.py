"""Tests for the local Agent Supervisor lifecycle skeleton."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kronos.agent.events import read_events, write_event
from kronos.agent.supervisor import (
    SUPERVISOR_STATUS_FILENAME,
    AgentSupervisor,
    AgentSupervisorError,
)
from kronos.agent.types import (
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

if TYPE_CHECKING:
    from pathlib import Path


def test_supervisor_starts_run_and_exposes_status(tmp_path: Path) -> None:
    supervisor = AgentSupervisor(tmp_path)

    run = supervisor.start_run(
        run_id="run-1",
        goal_zh="验证下一轮候选。",
        task_id="task-1",
        task_title_zh="生成研究假设",
    )

    status = supervisor.get_status()
    events = read_events(tmp_path / "run-1")

    assert run.status == AgentRunStatus.RUNNING
    assert status.active is True
    assert status.current_run is not None
    assert status.current_run.run_id == "run-1"
    assert status.current_task is not None
    assert status.current_task.status == AgentTaskStatus.RUNNING
    assert status.last_event is not None
    assert status.last_event.event_type == AgentEventType.RUN_STARTED
    assert [event.event_type for event in events] == [AgentEventType.RUN_STARTED]
    assert (tmp_path / SUPERVISOR_STATUS_FILENAME).exists()


def test_supervisor_stops_current_run(tmp_path: Path) -> None:
    supervisor = AgentSupervisor(tmp_path)
    supervisor.start_run(
        run_id="run-1",
        goal_zh="验证下一轮候选。",
        task_id="task-1",
        task_title_zh="生成研究假设",
    )

    stopped_run = supervisor.stop_run(reason_zh="人工暂停。")
    status = supervisor.get_status()
    events = read_events(tmp_path / "run-1")

    assert stopped_run.status == AgentRunStatus.CANCELLED
    assert stopped_run.tasks[0].status == AgentTaskStatus.CANCELLED
    assert status.active is False
    assert status.current_run is not None
    assert status.current_run.status == AgentRunStatus.CANCELLED
    assert status.last_event is not None
    assert status.last_event.message_zh == "人工暂停。"
    assert [event.event_type for event in events] == [
        AgentEventType.RUN_STARTED,
        AgentEventType.RUN_COMPLETED,
    ]


def test_supervisor_status_can_be_reloaded_from_disk(tmp_path: Path) -> None:
    supervisor = AgentSupervisor(tmp_path)
    supervisor.start_run(
        run_id="run-1",
        goal_zh="验证下一轮候选。",
        task_id="task-1",
        task_title_zh="生成研究假设",
    )

    reloaded = AgentSupervisor(tmp_path)
    status = reloaded.get_status()

    assert status.active is True
    assert status.current_run is not None
    assert status.current_run.run_id == "run-1"
    assert status.last_event is not None
    assert status.last_event.event_type == AgentEventType.RUN_STARTED


def test_supervisor_rejects_second_active_run(tmp_path: Path) -> None:
    supervisor = AgentSupervisor(tmp_path)
    supervisor.start_run(
        run_id="run-1",
        goal_zh="验证下一轮候选。",
        task_id="task-1",
        task_title_zh="生成研究假设",
    )

    with pytest.raises(AgentSupervisorError):
        supervisor.start_run(
            run_id="run-2",
            goal_zh="验证另一个候选。",
            task_id="task-2",
            task_title_zh="重复主任务",
        )


def test_supervisor_empty_status_is_user_readable(tmp_path: Path) -> None:
    status = AgentSupervisor(tmp_path).get_status()

    assert status.active is False
    assert status.current_run is None
    assert status.current_task is None
    assert status.last_event is None
    assert status.pending_count == 0


def test_supervisor_recovers_latest_status_from_timeline_when_snapshot_is_missing(
    tmp_path: Path,
) -> None:
    write_event(
        AgentEvent(
            run_id=AgentRunId("run-1"),
            task_id=AgentTaskId("task-1"),
            event_id=AgentEventId("event-1"),
            event_type=AgentEventType.RUN_STARTED,
            level=AgentEventLevel.INFO,
            status=AgentTaskStatus.RUNNING,
            message_zh="Agent 运行已启动: 验收 Agent run",
        ),
        run_dir=tmp_path / "run-1",
    )
    write_event(
        AgentEvent(
            run_id=AgentRunId("run-1"),
            task_id=AgentTaskId("task-1"),
            event_id=AgentEventId("event-2"),
            event_type=AgentEventType.RUN_COMPLETED,
            level=AgentEventLevel.DECISION,
            status=AgentTaskStatus.COMPLETED,
            message_zh="验收完成。",
        ),
        run_dir=tmp_path / "run-1",
    )

    status = AgentSupervisor(tmp_path).get_status()

    assert status.active is False
    assert status.current_run is not None
    assert status.current_run.run_id == "run-1"
    assert status.current_run.status == AgentRunStatus.COMPLETED
    assert status.current_run.metadata["recovered_from"] == "agent_events.jsonl"
    assert status.current_task is not None
    assert status.current_task.title_zh == "从事件时间线恢复的 Agent 任务"
    assert status.last_event is not None
    assert status.last_event.event_type == AgentEventType.RUN_COMPLETED


def test_supervisor_publishes_completed_run_snapshot(tmp_path: Path) -> None:
    supervisor = AgentSupervisor(tmp_path)
    task = AgentTask(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        status=AgentTaskStatus.COMPLETED,
        title_zh="验收 Agent run",
    )
    run = AgentRun(
        run_id=AgentRunId("run-1"),
        status=AgentRunStatus.COMPLETED,
        goal_zh="完成一轮验收。",
        current_task_id=task.task_id,
        tasks=[task],
    )
    write_event(
        AgentEvent(
            run_id=AgentRunId("run-1"),
            task_id=AgentTaskId("task-1"),
            event_id=AgentEventId("event-1"),
            event_type=AgentEventType.RUN_COMPLETED,
            level=AgentEventLevel.DECISION,
            status=AgentTaskStatus.COMPLETED,
            message_zh="验收完成。",
        ),
        run_dir=tmp_path / "source-run",
    )
    source_events = read_events(tmp_path / "source-run")

    status = supervisor.publish_run_snapshot(run=run, events=source_events)
    reloaded = AgentSupervisor(tmp_path).get_status()

    assert status.active is False
    assert status.current_run is not None
    assert status.current_run.run_id == "run-1"
    assert status.current_task is not None
    assert status.current_task.status == AgentTaskStatus.COMPLETED
    assert reloaded.current_run is not None
    assert reloaded.current_run.status == AgentRunStatus.COMPLETED
    assert read_events(tmp_path / "run-1")
