"""Primitive Agent identifiers and enum contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, NewType

from pydantic import BaseModel, ConfigDict, Field, model_validator

AgentRunId = NewType("AgentRunId", str)
AgentTaskId = NewType("AgentTaskId", str)
AgentEventId = NewType("AgentEventId", str)
AgentCandidateId = NewType("AgentCandidateId", str)
AgentRoleId = NewType("AgentRoleId", str)
AgentPromptVersionId = NewType("AgentPromptVersionId", str)
AgentModelInvocationId = NewType("AgentModelInvocationId", str)
AgentToolInvocationId = NewType("AgentToolInvocationId", str)
AgentApprovalId = NewType("AgentApprovalId", str)


class AgentRunStatus(StrEnum):
    """Lifecycle status for one Agent research run."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTaskStatus(StrEnum):
    """Lifecycle status for a task inside an Agent run."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class AgentEventLevel(StrEnum):
    """User-facing severity level for Agent timeline events."""

    INFO = "info"
    DECISION = "decision"
    WARNING = "warning"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"


class AgentEventType(StrEnum):
    """Append-only event timeline event type."""

    RUN_CREATED = "run_created"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    TASK_QUEUED = "task_queued"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    MATERIAL_INTAKE = "material_intake"
    HYPOTHESIS_GENERATED = "hypothesis_generated"
    EXPERIMENT_PLANNED = "experiment_planned"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    AGENT_ANALYSIS_COMPLETED = "agent_analysis_completed"
    COMMITTEE_SCORING_COMPLETED = "committee_scoring_completed"
    CANDIDATE_STATE_CHANGED = "candidate_state_changed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    ERROR_REPORTED = "error_reported"


class AgentErrorCategory(StrEnum):
    """Stable user-facing categories for Agent failures."""

    INPUT_DATA = "input_data"
    TOOL_EXECUTION = "tool_execution"
    MODEL_PROVIDER = "model_provider"
    SECRET_CONFIGURATION = "secret_configuration"
    REPORTING = "reporting"
    WEB_API = "web_api"
    TIMELINE_RECOVERY = "timeline_recovery"
    UNKNOWN = "unknown"


class CandidateLifecycleState(StrEnum):
    """Candidate lifecycle state managed by the Agent runtime."""

    MATERIAL_INTAKE = "material_intake"
    MIGRATION_REVIEW = "migration_review"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT_PLANNED = "experiment_planned"
    VALIDATING = "validating"
    AGENT_ANALYSIS = "agent_analysis"
    COMMITTEE_SCORING = "committee_scoring"
    OBSERVE = "observe"
    REDESIGN = "redesign"
    SIMULATE = "simulate"
    LIVE_APPROVAL_REQUIRED = "live_approval_required"
    RETIRED = "retired"


class ApprovalType(StrEnum):
    """Human approval gate types for Agent decisions."""

    PROMPT_ACTIVATION = "prompt_activation"
    CANDIDATE_IMPLEMENTATION = "candidate_implementation"
    CANDIDATE_RETIREMENT = "candidate_retirement"
    SIMULATION_ADMISSION = "simulation_admission"
    PORTFOLIO_ADMISSION = "portfolio_admission"
    LIVE_TRADING_APPLICATION = "live_trading_application"


class AgentRoleKind(StrEnum):
    """Built-in Agent role categories."""

    RESEARCHER = "researcher"
    OPPOSITION_REVIEWER = "opposition_reviewer"
    RISK_REVIEWER = "risk_reviewer"
    DECISION_REVIEWER = "decision_reviewer"
    TOOL_OPERATOR = "tool_operator"


class AgentArtifactRef(BaseModel):
    """Reference to a file or persisted artifact produced by an Agent run."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    summary_zh: str | None = None


class AgentErrorRef(BaseModel):
    """Reference to an error report and developer traceback."""

    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(min_length=1)
    message_zh: str = Field(min_length=1)
    category: AgentErrorCategory = AgentErrorCategory.UNKNOWN
    impact_zh: str | None = None
    traceback_ref: str | None = None
    recoverable: bool = True
    user_action_zh: str | None = None


class AgentTask(BaseModel):
    """Structured task inside a single Agent run."""

    model_config = ConfigDict(extra="forbid")

    run_id: AgentRunId = Field(min_length=1)
    task_id: AgentTaskId = Field(min_length=1)
    status: AgentTaskStatus
    title_zh: str = Field(min_length=1)
    candidate_id: AgentCandidateId | None = None
    lifecycle_state: CandidateLifecycleState | None = None
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    error_ref: AgentErrorRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRun(BaseModel):
    """Structured state for one Agent research run."""

    model_config = ConfigDict(extra="forbid")

    run_id: AgentRunId = Field(min_length=1)
    status: AgentRunStatus
    goal_zh: str = Field(min_length=1)
    current_task_id: AgentTaskId | None = None
    tasks: list[AgentTask] = Field(default_factory=list)
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    error_ref: AgentErrorRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    """Append-only event timeline record for Agent runs."""

    model_config = ConfigDict(extra="forbid")

    run_id: AgentRunId = Field(min_length=1)
    task_id: AgentTaskId = Field(min_length=1)
    event_id: AgentEventId = Field(min_length=1)
    event_type: AgentEventType
    level: AgentEventLevel
    status: AgentTaskStatus
    message_zh: str = Field(min_length=1)
    candidate_id: AgentCandidateId | None = None
    role_id: AgentRoleId | None = None
    prompt_version: AgentPromptVersionId | None = None
    model_provider: str | None = None
    model_name: str | None = None
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    error_ref: AgentErrorRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptVersionRef(BaseModel):
    """Traceable prompt version reference for one Agent role."""

    model_config = ConfigDict(extra="forbid")

    prompt_version: AgentPromptVersionId = Field(min_length=1)
    role_id: AgentRoleId = Field(min_length=1)
    title_zh: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=1)
    is_active: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRole(BaseModel):
    """Configured Agent role used in one run or task."""

    model_config = ConfigDict(extra="forbid")

    role_id: AgentRoleId = Field(min_length=1)
    role_kind: AgentRoleKind
    name_zh: str = Field(min_length=1)
    enabled: bool = True
    prompt_version: AgentPromptVersionId = Field(min_length=1)
    model_provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelInvocationRef(BaseModel):
    """Traceable reference for one model invocation."""

    model_config = ConfigDict(extra="forbid")

    invocation_id: AgentModelInvocationId = Field(min_length=1)
    role_id: AgentRoleId = Field(min_length=1)
    prompt_version: AgentPromptVersionId = Field(min_length=1)
    model_provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    status: AgentTaskStatus
    latency_ms: int | None = Field(default=None, ge=0)
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    error_ref: AgentErrorRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequirement(BaseModel):
    """Human approval required before a sensitive Agent action."""

    model_config = ConfigDict(extra="forbid")

    approval_id: AgentApprovalId = Field(min_length=1)
    approval_type: ApprovalType
    title_zh: str = Field(min_length=1)
    reason_zh: str = Field(min_length=1)
    candidate_id: AgentCandidateId | None = None
    blocking: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    """Standard user-facing output contract for one Agent conclusion."""

    model_config = ConfigDict(extra="forbid")

    run_id: AgentRunId = Field(min_length=1)
    task_id: AgentTaskId = Field(min_length=1)
    role_id: AgentRoleId = Field(min_length=1)
    prompt_version: AgentPromptVersionId = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    support_reasons: list[str] = Field(min_length=1)
    opposition_reasons: list[str] = Field(min_length=1)
    key_evidence: list[AgentArtifactRef] = Field(min_length=1)
    max_risk: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    approval_required: bool
    approval_requirements: list[ApprovalRequirement] = Field(default_factory=list)
    model_invocation: ModelInvocationRef | None = None
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _approval_requirements_match_flag(self) -> AgentOutput:
        if self.approval_required and not self.approval_requirements:
            raise ValueError("approval_requirements must be present when approval_required is true")
        return self
