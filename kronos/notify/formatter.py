"""Notification event formatting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kronos.common.types import Level


def format_event(
    *,
    level: Level,
    event_type: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured notification payload."""
    return {
        "level": str(level),
        "event_type": event_type,
        "title": title,
        "body": body,
        "data": data or {},
    }
