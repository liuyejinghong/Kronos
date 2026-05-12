"""Redaction helpers for repository memory files."""

from __future__ import annotations

import re

_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|apikey|api[_-]?secret|secret|signature|token|password)"
    r"(\s*[:=]\s*)"
    r"([^\s`'\",)]+)"
)
_LONG_SECRET_PATTERN = re.compile(
    r"\b(?=[A-Za-z0-9]{32,}\b)(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[a-z])"
    r"(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{32,}\b"
)
_URL_QUERY_PATTERN = re.compile(r"(https?://[^\s?]+)\?[^\s)`]+")


def redact_text(value: str) -> str:
    """Return text with secret-like values masked."""
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1\2[REDACTED]", value)
    redacted = _URL_QUERY_PATTERN.sub(r"\1?[REDACTED]", redacted)
    return _LONG_SECRET_PATTERN.sub("[REDACTED]", redacted)


def has_secret_like_text(value: str) -> bool:
    """Return whether text contains a likely secret token."""
    if _SECRET_ASSIGNMENT_PATTERN.search(value):
        return True
    if _URL_QUERY_PATTERN.search(value):
        return True
    return _LONG_SECRET_PATTERN.search(value) is not None
