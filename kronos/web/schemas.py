"""Pydantic schemas for the local Kronos Agent Web API."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from kronos.agent.types import (
    AgentEventLevel,  # noqa: TC001
    AgentEventType,  # noqa: TC001
    AgentRunStatus,  # noqa: TC001
    AgentTaskStatus,  # noqa: TC001
    ApprovalType,  # noqa: TC001
    CandidateLifecycleState,  # noqa: TC001
)


class HealthResponse(BaseModel):
    """Health status for the local Web API."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    service: str = "kronos-web-api"


class ArtifactRefResponse(BaseModel):
    """Safe artifact reference returned to Web clients."""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    artifact_type: str
    summary_zh: str | None = None


class AgentTaskStatusResponse(BaseModel):
    """Current task snapshot for the Agent status panel."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: AgentTaskStatus
    title_zh: str
    candidate_id: str | None = None
    lifecycle_state: CandidateLifecycleState | None = None


class AgentRunStatusResponse(BaseModel):
    """Current run snapshot for the Agent status panel."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: AgentRunStatus
    goal_zh: str
    current_task_id: str | None = None
    artifact_paths: list[ArtifactRefResponse] = Field(default_factory=list)


class AgentEventResponse(BaseModel):
    """Timeline event returned to the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    event_id: str
    event_type: AgentEventType
    level: AgentEventLevel
    status: AgentTaskStatus
    message_zh: str
    candidate_id: str | None = None
    role_id: str | None = None
    prompt_version: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    artifact_paths: list[ArtifactRefResponse] = Field(default_factory=list)


class AgentStatusResponse(BaseModel):
    """PM-facing Agent runtime status for the Web first screen."""

    model_config = ConfigDict(extra="forbid")

    active: bool
    pending_count: int = Field(ge=0)
    current_run: AgentRunStatusResponse | None = None
    current_task: AgentTaskStatusResponse | None = None
    last_event: AgentEventResponse | None = None


class AgentRunBriefResponse(BaseModel):
    """PM-facing summary extracted from one Agent run summary artifact."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: str
    goal_zh: str
    conclusion_zh: str
    next_action_zh: str
    max_risk_zh: str | None = None
    approval_required: bool = False
    support_reasons: list[str] = Field(default_factory=list)
    opposition_reasons: list[str] = Field(default_factory=list)
    evidence_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    artifact_paths: list[ArtifactRefResponse] = Field(default_factory=list)
    report_path: str | None = None


class AgentRunReportResponse(BaseModel):
    """Readable report payload for the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    title_zh: str
    report_path: str
    content_md: str


class PaperOrderResponse(BaseModel):
    """Safe testnet order evidence for the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = None
    client_order_id: str | None = None
    symbol: str
    side: str
    order_type: str | None = None
    quantity: float | None = None
    status: str
    environment: str = "testnet"
    created_at: str | None = None


class PaperFillResponse(BaseModel):
    """Safe testnet fill evidence for the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = None
    trade_id: str | None = None
    symbol: str
    side: str
    price: float | None = None
    quantity: float | None = None
    commission: float | None = None
    commission_asset: str | None = None
    fill_time: str | None = None
    environment: str = "testnet"


class PaperErrorResponse(BaseModel):
    """Safe testnet error evidence for the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    environment: str = "testnet"
    reason: str
    created_at: str | None = None


class PaperStatusResponse(BaseModel):
    """PM-facing testnet paper status for the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    status: str
    environment: str = "testnet"
    run_id: str | None = None
    updated_at: str | None = None
    message_zh: str
    next_action_zh: str
    run_dir: str | None = None
    report_path: str | None = None
    report_available: bool = False
    truncated: bool = False
    latest_orders: list[PaperOrderResponse] = Field(default_factory=list)
    latest_fills: list[PaperFillResponse] = Field(default_factory=list)
    latest_errors: list[PaperErrorResponse] = Field(default_factory=list)


class PaperRunReportResponse(BaseModel):
    """Readable testnet paper report payload for the Web workbench."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    title_zh: str
    report_path: str
    content_md: str


class CandidateListItemResponse(BaseModel):
    """Candidate row for the candidate pool table."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    title_zh: str
    family: str
    origin: str
    migration_rank: int
    implementation_name: str | None = None
    lifecycle_state: CandidateLifecycleState | None = None
    status_label_zh: str


class CandidateDetailResponse(CandidateListItemResponse):
    """Candidate detail payload for Web drilldown."""

    source_strategies: list[str] = Field(default_factory=list)
    artifact_paths: list[ArtifactRefResponse] = Field(default_factory=list)
    next_action_zh: str


class RoleSettingsResponse(BaseModel):
    """Agent role configuration safe for Web display."""

    model_config = ConfigDict(extra="forbid")

    role_id: str
    role_kind: str
    name_zh: str
    enabled: bool
    prompt_version: str
    model_provider: str
    model_name: str


class ProviderSecretStatusResponse(BaseModel):
    """Masked provider credential status."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    configured: bool
    masked_value: str | None = None
    storage_backend: str


class ProviderReadinessResponse(BaseModel):
    """Masked provider readiness status for Web settings."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    status: str
    configured: bool
    masked_api_key: str | None = None
    base_url: str
    model_name: str | None = None
    message_zh: str


class AvailableModelResponse(BaseModel):
    """One available LLM model entry."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    label_zh: str
    label_en: str


class LLMSettingsResponse(BaseModel):
    """LLM settings overview for the local settings page."""

    model_config = ConfigDict(extra="forbid")

    providers: list[ProviderSecretStatusResponse] = Field(default_factory=list)
    roles: list[RoleSettingsResponse] = Field(default_factory=list)
    available_models: list[AvailableModelResponse] = Field(default_factory=list)


class LLMSecretUpdateRequest(BaseModel):
    """Backend-only secret update request."""

    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr


class MaterialSourceType(StrEnum):
    """Supported material source classes for the MVP material pool."""

    LEGACY_STRATEGY = "legacy_strategy"
    CANDIDATE_NOTE = "candidate_note"
    FAILURE_RECORD = "failure_record"
    SIMULATION_LOG = "simulation_log"
    USER_NOTE = "user_note"


class MaterialImportRequest(BaseModel):
    """Material import request from the local workbench."""

    model_config = ConfigDict(extra="forbid")

    title_zh: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_type: MaterialSourceType = MaterialSourceType.USER_NOTE
    candidate_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class MaterialImportResponse(BaseModel):
    """Stored material reference returned to Web clients."""

    model_config = ConfigDict(extra="forbid")

    material_id: str
    title_zh: str
    source_type: MaterialSourceType
    candidate_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    stored_at: datetime


class ApprovalItemResponse(BaseModel):
    """Approval item for the approval center."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    approval_type: ApprovalType
    title_zh: str
    reason_zh: str
    candidate_id: str | None = None
    blocking: bool = True
    status: str = "pending"


class ApprovalListResponse(BaseModel):
    """Approval center payload."""

    model_config = ConfigDict(extra="forbid")

    items: list[ApprovalItemResponse] = Field(default_factory=list)


class ApprovalResolveRequest(BaseModel):
    """Approval resolution request recorded to the Agent event timeline."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    approved: bool
    reason_zh: str = Field(min_length=1)


class ApprovalResolveResponse(BaseModel):
    """Approval resolution event reference."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    approved: bool
    event_id: str
    event_path: str
