"""Shared secret redaction — the single authority for every user-facing surface.

Every surface that renders reports, memory, events, or error text to a human
must pass strings through `redact_text` (and structured objects through
`redact_obj`). Pattern sets live here so they cannot drift per-surface.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# key=value / key: value forms, quoted or bare
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|apikey|api[_-]?secret|secret|signature|token|password)"
    r"(\s*[\"']?\s*[:=]\s*)"
    r"([^\s`'\",)]+)"
)
# JSON-style "apiKey": "..."
_JSON_FORM_PATTERN = re.compile(
    r"(?i)([\"'])(apikey|api_key|api[-_]?secret|secret|token|password)\1(\s*:\s*)\1[^\1]+?\1"
)
# Authorization: Bearer <token>
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._+-]{8,}")
# Provider key prefixes (OpenAI/DeepSeek style)
_SK_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
# Long high-entropy tokens (mixed case + digit, 32+ alnum)
_LONG_SECRET_PATTERN = re.compile(
    r"\b(?=[A-Za-z0-9]{32,}\b)(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[a-z])"
    r"(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{32,}\b"
)
# Anything in a URL query string
_URL_QUERY_PATTERN = re.compile(r"(https?://[^\s?\"'`]+)\?[^\s)`\"']+")

SECRET_KEY_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)


def redact_text(value: str) -> str:
    """Return text with secret-like values masked."""
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1\2" + REDACTED, value)
    redacted = _JSON_FORM_PATTERN.sub(r"\1\2\3\1" + REDACTED + r"\1", redacted)
    redacted = _URL_QUERY_PATTERN.sub(r"\1?" + REDACTED, redacted)
    redacted = _BEARER_PATTERN.sub("Bearer " + REDACTED, redacted)
    redacted = _SK_KEY_PATTERN.sub(REDACTED, redacted)
    return _LONG_SECRET_PATTERN.sub(REDACTED, redacted)


def redact_obj(value: Any) -> Any:
    """Recursively redact structured data; string leaves go through redact_text."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and is_secret_like_key(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_obj(item)
        return redacted
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def has_secret_like_text(value: str) -> bool:
    """Return whether text contains a likely secret token."""
    return (
        _SECRET_ASSIGNMENT_PATTERN.search(value) is not None
        or _JSON_FORM_PATTERN.search(value) is not None
        or _URL_QUERY_PATTERN.search(value) is not None
        or _BEARER_PATTERN.search(value) is not None
        or _SK_KEY_PATTERN.search(value) is not None
        or _LONG_SECRET_PATTERN.search(value) is not None
    )


def is_secret_like_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS)
