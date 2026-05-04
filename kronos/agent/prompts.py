"""Prompt version store for Agent roles."""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.types import AgentPromptVersionId, AgentRoleId


class PromptStoreError(ValueError):
    """Raised when a prompt version operation is invalid."""


class PromptVersionStatus(StrEnum):
    """Lifecycle status for one prompt version."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PromptVersionRecord(BaseModel):
    """Immutable prompt version record."""

    model_config = ConfigDict(extra="forbid")

    prompt_version: AgentPromptVersionId = Field(min_length=1)
    role_id: AgentRoleId = Field(min_length=1)
    title_zh: str = Field(min_length=1)
    content: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=1)
    status: PromptVersionStatus = PromptVersionStatus.DRAFT
    version_number: int = Field(ge=1)
    activated_by_user: bool = False


class PromptVersionStore:
    """In-memory prompt store that preserves immutable version history."""

    def __init__(self, records: list[PromptVersionRecord] | None = None) -> None:
        self._records: dict[str, list[PromptVersionRecord]] = {}
        for record in records or []:
            self._records.setdefault(str(record.role_id), []).append(record.model_copy(deep=True))

    def create_draft(
        self,
        *,
        role_id: str,
        title_zh: str,
        content: str,
    ) -> PromptVersionRecord:
        """Create a new draft prompt version without overwriting old versions."""
        version_number = self._next_version_number(role_id)
        record = PromptVersionRecord(
            prompt_version=AgentPromptVersionId(f"{role_id}-prompt-v{version_number}"),
            role_id=AgentRoleId(role_id),
            title_zh=title_zh,
            content=content,
            prompt_hash=_prompt_hash(content),
            version_number=version_number,
        )
        self._records.setdefault(role_id, []).append(record)
        return record.model_copy(deep=True)

    def update_prompt(
        self,
        *,
        role_id: str,
        title_zh: str,
        content: str,
    ) -> PromptVersionRecord:
        """Create a new draft version for a prompt edit."""
        return self.create_draft(role_id=role_id, title_zh=title_zh, content=content)

    def activate_prompt(
        self,
        *,
        role_id: str,
        prompt_version: str,
        confirmed: bool,
    ) -> PromptVersionRecord:
        """Activate a prompt version after explicit human confirmation."""
        if not confirmed:
            raise PromptStoreError("Prompt activation requires explicit confirmation.")

        records = self._records.get(role_id, [])
        target: PromptVersionRecord | None = None
        updated_records: list[PromptVersionRecord] = []
        for record in records:
            if record.prompt_version == prompt_version:
                target = record.model_copy(
                    update={
                        "status": PromptVersionStatus.ACTIVE,
                        "activated_by_user": True,
                    }
                )
                updated_records.append(target)
            elif record.status == PromptVersionStatus.ACTIVE:
                updated_records.append(record.model_copy(update={"status": PromptVersionStatus.ARCHIVED}))
            else:
                updated_records.append(record)

        if target is None:
            raise PromptStoreError(f"Unknown prompt version: {prompt_version}")
        self._records[role_id] = updated_records
        return target.model_copy(deep=True)

    def get_active_prompt(self, role_id: str) -> PromptVersionRecord | None:
        """Return the active prompt for a role, if configured."""
        for record in self._records.get(role_id, []):
            if record.status == PromptVersionStatus.ACTIVE:
                return record.model_copy(deep=True)
        return None

    def list_prompt_versions(self, role_id: str) -> list[PromptVersionRecord]:
        """Return immutable prompt history for one role."""
        return [
            record.model_copy(deep=True)
            for record in sorted(
                self._records.get(role_id, []),
                key=lambda item: item.version_number,
            )
        ]

    def _next_version_number(self, role_id: str) -> int:
        records = self._records.get(role_id, [])
        if not records:
            return 1
        return max(record.version_number for record in records) + 1


def _prompt_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
