"""Redaction helpers for repository memory files.

Delegates to the shared authority in `kronos.common.redaction` so pattern
sets cannot drift between the memory console and other surfaces.
"""

from __future__ import annotations

from kronos.common.redaction import has_secret_like_text, redact_text

__all__ = ["has_secret_like_text", "redact_text"]
