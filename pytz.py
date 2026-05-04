"""Minimal compatibility shim for tooling that imports ``pytz.UTC``.

This project uses stdlib timezone support. Some research-only third-party
packages still import ``pytz.UTC`` directly, so we expose the minimal surface
they need without adding a new dependency.
"""

from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

__version__ = "2024.2"
UTC = timezone.utc


def timezone(name: str):
    """Return a zoneinfo timezone object for the requested name."""
    if name == "UTC":
        return UTC
    return ZoneInfo(name)
