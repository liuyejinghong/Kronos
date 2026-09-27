"""Append-only Agent event timeline writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kronos.agent.types import AgentEvent
from kronos.common.redaction import is_secret_like_key as _is_secret_like_key
from kronos.common.redaction import redact_obj

EVENT_TIMELINE_FILENAME = "agent_events.jsonl"
# Re-exported for backwards compatibility with existing imports.
REDACTED_SECRET = "[REDACTED]"
SECRET_KEY_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)


class AgentEventWriter:
    """Write and read one run's append-only Agent event timeline."""

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.events_path = self.run_dir / EVENT_TIMELINE_FILENAME

    def write_event(self, event: AgentEvent) -> Path:
        """Append an Agent event as one JSONL record."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        record = redact_secret_like_values(event.model_dump(mode="json"))
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False))
            handle.write("\n")
        return self.events_path

    def replace_events(self, events: list[AgentEvent]) -> Path:
        """Replace the run timeline with an exact event snapshot."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("w", encoding="utf-8") as handle:
            for event in events:
                record = redact_secret_like_values(event.model_dump(mode="json"))
                handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False))
                handle.write("\n")
        return self.events_path

    def read_events(self) -> list[AgentEvent]:
        """Read all events in write order, skipping corrupt lines."""
        if not self.events_path.exists():
            return []
        events: list[AgentEvent] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(AgentEvent.model_validate_json(line))
            except ValueError:
                # One corrupt line must not take down the whole timeline
                # (audit FSR-028).
                import structlog

                structlog.get_logger("kronos.agent.events").warning(
                    "events.corrupt_line_skipped", path=str(self.events_path)
                )
        return events


def write_event(event: AgentEvent, *, run_dir: str | Path) -> Path:
    """Append an Agent event to the run timeline."""
    return AgentEventWriter(run_dir).write_event(event)


def read_events(run_dir: str | Path) -> list[AgentEvent]:
    """Read Agent events from a run timeline."""
    return AgentEventWriter(run_dir).read_events()


def replace_events(events: list[AgentEvent], *, run_dir: str | Path) -> Path:
    """Replace Agent events for a Web-readable runtime snapshot."""
    return AgentEventWriter(run_dir).replace_events(events)


def redact_secret_like_values(value: Any) -> Any:
    # Delegates to the shared authority: string leaves are redacted too
    # (markdown report lines are lists of strings).
    return redact_obj(value)


def is_secret_like_key(key: str) -> bool:
    return _is_secret_like_key(key)
