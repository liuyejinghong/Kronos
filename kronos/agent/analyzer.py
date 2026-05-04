"""Selective Agent knowledge-base write policy."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kronos.research.knowledge_base import add_agent_decision_entry, add_failure_entry


class AgentKnowledgeWriteError(ValueError):
    """Raised when a knowledge write violates the Agent MVP policy."""


class AgentKnowledgeEntryType(StrEnum):
    """Allowed Agent memory categories."""

    RESEARCH_CONCLUSION = "research_conclusion"
    FAILURE_REASON = "failure_reason"
    CANDIDATE_STATE_CHANGE = "candidate_state_change"
    COMMITTEE_DISAGREEMENT = "committee_disagreement"
    APPROVAL_RECORD = "approval_record"


class AgentKnowledgeEntry(BaseModel):
    """Safe memory payload for selective knowledge-base writes."""

    model_config = ConfigDict(extra="forbid")

    entry_type: AgentKnowledgeEntryType
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    run_id: str | None = None
    factor_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelectiveKnowledgeWriter:
    """Write only product-level Agent memory, never raw technical logs."""

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)

    def write(self, entry: AgentKnowledgeEntry) -> int:
        """Persist one allowed Agent memory entry."""
        if entry.metadata.get("raw_log") is True:
            raise AgentKnowledgeWriteError("Raw technical logs must not enter Agent memory.")

        metadata = {
            **entry.metadata,
            "run_id": entry.run_id,
            "entry_type": entry.entry_type.value,
        }
        tags = [entry.entry_type.value, *entry.tags]
        if entry.entry_type == AgentKnowledgeEntryType.FAILURE_REASON:
            return add_failure_entry(
                title=entry.title,
                summary=entry.summary,
                factor_name=entry.factor_name,
                tags=tags,
                metadata=metadata,
                base_path=self.base_path,
            )
        return add_agent_decision_entry(
            title=entry.title,
            summary=entry.summary,
            factor_name=entry.factor_name,
            tags=tags,
            metadata=metadata,
            base_path=self.base_path,
        )
