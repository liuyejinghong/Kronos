"""LLM provider interface and DeepSeek OpenAI-compatible adapter."""

from __future__ import annotations

from enum import StrEnum
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.events import write_event
from kronos.agent.types import (
    AgentArtifactRef,
    AgentErrorCategory,
    AgentErrorRef,
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentModelInvocationId,
    AgentPromptVersionId,
    AgentRoleId,
    AgentRunId,
    AgentTaskId,
    AgentTaskStatus,
    ModelInvocationRef,
)

DEEPSEEK_PROVIDER_NAME = "deepseek"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"


class LLMMessageRole(StrEnum):
    """OpenAI-compatible chat message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMCallStatus(StrEnum):
    """Provider call status surfaced to Agent runtime."""

    WAITING_CONFIGURATION = "waiting_configuration"
    COMPLETED = "completed"
    FAILED = "failed"


class LLMMessage(BaseModel):
    """One OpenAI-compatible chat message."""

    model_config = ConfigDict(extra="forbid")

    role: LLMMessageRole
    content: str = Field(min_length=1)


class LLMRequest(BaseModel):
    """Provider-agnostic model invocation request."""

    model_config = ConfigDict(extra="forbid")

    role_id: AgentRoleId = Field(min_length=1)
    prompt_version: AgentPromptVersionId = Field(min_length=1)
    model_provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    messages: list[LLMMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: float | None = Field(default=None, gt=0)
    max_retries: int | None = Field(default=None, ge=0)
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Provider-agnostic model invocation response."""

    model_config = ConfigDict(extra="forbid")

    status: LLMCallStatus
    invocation: ModelInvocationRef
    content: str | None = None
    raw_usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProviderMaskedStatus(BaseModel):
    """Provider readiness status safe to expose in settings and reports."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    status: LLMCallStatus
    configured: bool
    masked_api_key: str | None = None
    base_url: str = Field(min_length=1)
    model_name: str | None = None
    message_zh: str = Field(min_length=1)


class DeepSeekProviderConfig(BaseModel):
    """DeepSeek OpenAI-compatible provider configuration."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = DEEPSEEK_DEFAULT_BASE_URL
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=0, ge=0)


class LLMProvider(Protocol):
    """Provider protocol used by Agent roles."""

    def check_status(self, *, model_name: str | None = None) -> LLMProviderMaskedStatus:
        """Return masked provider configuration status."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one non-streaming chat completion request."""


class _HttpResponse(Protocol):
    def raise_for_status(self) -> None:
        """Raise when the HTTP response is not successful."""

    def json(self) -> Any:
        """Return response JSON."""


class _HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> _HttpResponse:
        """Send an HTTP POST request."""


class _SecretStore(Protocol):
    def get_status(self, provider: str) -> Any:
        """Return provider secret status."""

    def get_secret(self, provider: str) -> str | None:
        """Return provider secret value for backend-only calls."""


class DeepSeekLLMProvider:
    """DeepSeek adapter using the OpenAI-compatible chat completions contract."""

    def __init__(
        self,
        *,
        secret_store: _SecretStore,
        config: DeepSeekProviderConfig | None = None,
        http_client: _HttpClient | None = None,
    ) -> None:
        self.secret_store = secret_store
        self.config = config or DeepSeekProviderConfig()
        self.http_client = http_client or httpx.Client()

    def check_status(self, *, model_name: str | None = None) -> LLMProviderMaskedStatus:
        """Return masked DeepSeek configuration status without making a paid call."""
        secret_status = self.secret_store.get_status(DEEPSEEK_PROVIDER_NAME)
        configured = secret_status.configured
        return LLMProviderMaskedStatus(
            provider=DEEPSEEK_PROVIDER_NAME,
            status=LLMCallStatus.COMPLETED if configured else LLMCallStatus.WAITING_CONFIGURATION,
            configured=configured,
            masked_api_key=secret_status.masked_value,
            base_url=self.config.base_url,
            model_name=model_name,
            message_zh="DeepSeek API Key 已配置。" if configured else "DeepSeek API Key 尚未配置。",
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one non-streaming DeepSeek chat completion request."""
        api_key = self.secret_store.get_secret(DEEPSEEK_PROVIDER_NAME)
        started_at = perf_counter()
        if api_key is None:
            return self._response(
                request=request,
                status=LLMCallStatus.WAITING_CONFIGURATION,
                started_at=started_at,
                error_ref=AgentErrorRef(
                    error_code="llm_provider_not_configured",
                    message_zh="DeepSeek API Key 尚未配置。",
                    category=AgentErrorCategory.SECRET_CONFIGURATION,
                    impact_zh="需要模型参与的 Agent 角色会停在待配置状态.",
                    recoverable=True,
                    user_action_zh="在设置页配置 API Key 后重试。",
                ),
                metadata={"provider_status": LLMCallStatus.WAITING_CONFIGURATION.value},
            )

        body = _request_body(request)
        timeout_seconds = request.timeout_seconds or self.config.timeout_seconds
        max_retries = request.max_retries if request.max_retries is not None else self.config.max_retries
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = self.http_client.post(
                    _chat_completions_url(self.config.base_url),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                content = _extract_content(payload)
                return self._response(
                    request=request,
                    status=LLMCallStatus.COMPLETED,
                    started_at=started_at,
                    content=content,
                    raw_usage=_extract_usage(payload),
                    metadata={"attempts": attempt + 1},
                )
            except (httpx.HTTPError, LookupError, TypeError, ValueError) as exc:
                last_error = exc

        return self._response(
            request=request,
            status=LLMCallStatus.FAILED,
            started_at=started_at,
            error_ref=AgentErrorRef(
                error_code="llm_provider_call_failed",
                message_zh="DeepSeek 模型调用失败。",
                category=AgentErrorCategory.MODEL_PROVIDER,
                impact_zh="本轮模型分析无法完成, 不能进入后续 Agent 评分.",
                recoverable=True,
                user_action_zh="检查网络、模型配置和 API Key 后重试。",
            ),
            metadata={"error_type": type(last_error).__name__ if last_error else "unknown"},
        )

    def _response(
        self,
        *,
        request: LLMRequest,
        status: LLMCallStatus,
        started_at: float,
        content: str | None = None,
        raw_usage: dict[str, Any] | None = None,
        error_ref: AgentErrorRef | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        latency_ms = int((perf_counter() - started_at) * 1000)
        invocation = ModelInvocationRef(
            invocation_id=AgentModelInvocationId(f"model-invocation-{uuid4().hex}"),
            role_id=request.role_id,
            prompt_version=request.prompt_version,
            model_provider=request.model_provider,
            model_name=request.model_name,
            status=_agent_task_status(status),
            latency_ms=latency_ms,
            artifact_paths=request.artifact_paths,
            error_ref=error_ref,
            metadata=metadata or {},
        )
        return LLMResponse(
            status=status,
            invocation=invocation,
            content=content,
            raw_usage=raw_usage or {},
            metadata=metadata or {},
        )


def build_llm_invocation_event(
    *,
    run_id: str,
    task_id: str,
    response: LLMResponse,
) -> AgentEvent:
    """Build a secret-free event timeline record for one model invocation."""
    status = response.status
    level = AgentEventLevel.INFO
    event_type = AgentEventType.AGENT_ANALYSIS_COMPLETED
    message_zh = "LLM 调用完成。"
    if status == LLMCallStatus.WAITING_CONFIGURATION:
        level = AgentEventLevel.WARNING
        event_type = AgentEventType.ERROR_REPORTED
        message_zh = "LLM provider 待配置。"
    elif status == LLMCallStatus.FAILED:
        level = AgentEventLevel.ERROR
        event_type = AgentEventType.ERROR_REPORTED
        message_zh = "LLM 调用失败。"

    invocation = response.invocation
    return AgentEvent(
        run_id=AgentRunId(run_id),
        task_id=AgentTaskId(task_id),
        event_id=AgentEventId(f"event-{uuid4().hex}"),
        event_type=event_type,
        level=level,
        status=invocation.status,
        message_zh=message_zh,
        role_id=invocation.role_id,
        prompt_version=invocation.prompt_version,
        model_provider=invocation.model_provider,
        model_name=invocation.model_name,
        artifact_paths=invocation.artifact_paths,
        error_ref=invocation.error_ref,
        metadata={
            "invocation_id": invocation.invocation_id,
            "llm_status": status.value,
            "latency_ms": invocation.latency_ms,
            "usage": response.raw_usage,
        },
    )


def write_llm_invocation_event(
    *,
    run_dir: str,
    run_id: str,
    task_id: str,
    response: LLMResponse,
) -> None:
    """Append one LLM invocation event to an Agent event timeline."""
    write_event(
        build_llm_invocation_event(run_id=run_id, task_id=task_id, response=response),
        run_dir=run_dir,
    )


def _request_body(request: LLMRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": request.model_name,
        "messages": [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
        ],
        "stream": False,
    }
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.max_tokens is not None:
        body["max_tokens"] = request.max_tokens
    return body


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _extract_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise TypeError("LLM response payload must be an object.")
    choices = payload["choices"]
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response choices must be a non-empty list.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise TypeError("LLM response choice must be an object.")
    message = first_choice["message"]
    if not isinstance(message, dict):
        raise TypeError("LLM response message must be an object.")
    content = message.get("content", "")
    if isinstance(content, str) and content:
        return content
    # Fallback: reasoning models (e.g. DeepSeek-V4-Pro) put output in reasoning_content
    reasoning = message.get("reasoning_content", "")
    if isinstance(reasoning, str) and reasoning:
        return reasoning
    raise ValueError("LLM response content and reasoning_content are both empty.")


def _extract_usage(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
        return dict(payload["usage"])
    return {}


def _agent_task_status(status: LLMCallStatus) -> AgentTaskStatus:
    if status == LLMCallStatus.COMPLETED:
        return AgentTaskStatus.COMPLETED
    if status == LLMCallStatus.WAITING_CONFIGURATION:
        return AgentTaskStatus.WAITING_APPROVAL
    return AgentTaskStatus.FAILED
