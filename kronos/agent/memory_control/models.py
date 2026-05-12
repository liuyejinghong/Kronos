"""Data contracts for the Agent Memory Control surface."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MemoryCheckSeverity(StrEnum):
    """Severity for memory drift and safety checks."""

    PASSED = "passed"
    WARNING = "warning"
    BLOCKING = "blocking"


class MemorySourceRef(BaseModel):
    """A repository file used as a fact source."""

    model_config = ConfigDict(extra="forbid")

    path: str
    label_zh: str
    exists: bool = True


class MemorySummaryItem(BaseModel):
    """One PM-readable memory summary with source traceability."""

    model_config = ConfigDict(extra="forbid")

    title_zh: str
    body_zh: str
    source_paths: list[str] = Field(default_factory=list)


class AgentMemoryState(BaseModel):
    """Current state shown at the top of the memory dashboard."""

    model_config = ConfigDict(extra="forbid")

    current_version: str
    next_version: str
    current_acceptance_target_zh: str
    latest_successful_run_zh: str
    product_boundary_zh: str
    highest_priority_zh: str
    next_action_zh: str
    source_paths: list[str] = Field(default_factory=list)


class MemoryCheckItem(BaseModel):
    """One check result for drift, index, or secret safety."""

    model_config = ConfigDict(extra="forbid")

    check_id: str
    severity: MemoryCheckSeverity
    title_zh: str
    detail_zh: str
    source_paths: list[str] = Field(default_factory=list)
    suggestion_zh: str | None = None


class MemoryCheckSummary(BaseModel):
    """Aggregated check result counts."""

    model_config = ConfigDict(extra="forbid")

    status: MemoryCheckSeverity
    passed_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    blocking_count: int = Field(ge=0)
    items: list[MemoryCheckItem] = Field(default_factory=list)


class AgentHandoffPack(BaseModel):
    """Copyable prompt for a new Agent session."""

    model_config = ConfigDict(extra="forbid")

    title_zh: str
    prompt_md: str
    source_paths: list[str] = Field(default_factory=list)


class AgentMemoryDashboard(BaseModel):
    """Complete read-only Agent memory dashboard payload."""

    model_config = ConfigDict(extra="forbid")

    state: AgentMemoryState
    decisions: list[MemorySummaryItem] = Field(default_factory=list)
    lessons: list[MemorySummaryItem] = Field(default_factory=list)
    sources: list[MemorySourceRef] = Field(default_factory=list)
    handoff: AgentHandoffPack
    check: MemoryCheckSummary
