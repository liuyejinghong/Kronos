"""Conversation service for the v0.5.0 strategy-verdict loop (package P14).

Deterministic-first conversation pipeline: session/message persistence,
intent parsing (:mod:`kronos.conversation.intents`), strategy revision
lineage, budget-reserved task submission, and the whitelisted server-side
tool registry. The GLM client (:mod:`kronos.conversation.llm_client`) is a
later fallback hook for ambiguous-parameter clarification and is never on
the deterministic path.
"""

from __future__ import annotations

from kronos.conversation.intents import (
    ATR_PARAM,
    MULTIPLIER_PARAM,
    ParsedIntent,
    PendingAdjustment,
    parse_intent,
)
from kronos.conversation.llm_client import (
    GLMChatMessage,
    GLMChatResult,
    GLMClient,
    GLMClientError,
    GLMNotConfiguredError,
    GLMProbeStatus,
    GLMRequestError,
    GLMUsage,
)
from kronos.conversation.service import (
    ConversationError,
    ConversationService,
    MessageRecord,
    MessageResult,
    RevisionDiffEntry,
    SessionDetail,
    SessionInfo,
    SessionNotFoundError,
    ToolAccessError,
)

__all__ = [
    "ATR_PARAM",
    "MULTIPLIER_PARAM",
    "ConversationError",
    "ConversationService",
    "GLMChatMessage",
    "GLMChatResult",
    "GLMClient",
    "GLMClientError",
    "GLMNotConfiguredError",
    "GLMProbeStatus",
    "GLMRequestError",
    "GLMUsage",
    "MessageRecord",
    "MessageResult",
    "ParsedIntent",
    "PendingAdjustment",
    "RevisionDiffEntry",
    "SessionDetail",
    "SessionInfo",
    "SessionNotFoundError",
    "ToolAccessError",
    "parse_intent",
]
