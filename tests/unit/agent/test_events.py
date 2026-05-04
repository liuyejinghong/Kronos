"""Tests for the append-only Agent event timeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kronos.agent.events import (
    EVENT_TIMELINE_FILENAME,
    REDACTED_SECRET,
    read_events,
    replace_events,
    write_event,
)
from kronos.agent.types import (
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentRunId,
    AgentTaskId,
    AgentTaskStatus,
)

if TYPE_CHECKING:
    from pathlib import Path


def _event(event_id: str, message: str, *, secret: str | None = None) -> AgentEvent:
    metadata = {"sequence": event_id}
    if secret is not None:
        metadata["api_key"] = secret
    return AgentEvent(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        event_id=AgentEventId(event_id),
        event_type=AgentEventType.TASK_STARTED,
        level=AgentEventLevel.INFO,
        status=AgentTaskStatus.RUNNING,
        message_zh=message,
        metadata=metadata,
    )


def test_write_event_appends_jsonl_records(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"

    path = write_event(_event("event-1", "任务开始。"), run_dir=run_dir)
    write_event(_event("event-2", "任务继续。"), run_dir=run_dir)

    assert path == run_dir / EVENT_TIMELINE_FILENAME
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 2

    events = read_events(run_dir)
    assert [event.event_id for event in events] == ["event-1", "event-2"]
    assert [event.message_zh for event in events] == ["任务开始。", "任务继续。"]


def test_read_events_returns_empty_list_for_missing_timeline(tmp_path: Path) -> None:
    assert read_events(tmp_path / "missing-run") == []


def test_write_event_redacts_secret_like_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    write_event(_event("event-1", "带密钥字段。", secret="super-secret-key"), run_dir=run_dir)

    raw = (run_dir / EVENT_TIMELINE_FILENAME).read_text(encoding="utf-8")
    assert "super-secret-key" not in raw
    assert REDACTED_SECRET in raw

    events = read_events(run_dir)
    assert events[0].metadata["api_key"] == REDACTED_SECRET


def test_replace_events_overwrites_stale_runtime_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    write_event(_event("event-1", "旧事件。"), run_dir=run_dir)

    path = replace_events([_event("event-2", "新事件。")], run_dir=run_dir)

    assert path == run_dir / EVENT_TIMELINE_FILENAME
    events = read_events(run_dir)
    assert [event.event_id for event in events] == ["event-2"]
