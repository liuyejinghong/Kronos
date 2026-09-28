# ruff: noqa: RUF001 -- Chinese user-facing probe messages use fullwidth punctuation.
"""Settings routes for the local Web API."""

from __future__ import annotations

from typing import Final

from fastapi import APIRouter, HTTPException, Request

from kronos.agent.llm import GLM_PROVIDER_NAME, GLMLLMProvider
from kronos.agent.roles import GLM_MODELS, AgentRoleRegistry
from kronos.agent.secrets import LocalSecretStore
from kronos.conversation.llm_client import GLMChatMessage, GLMClient, GLMClientError
from kronos.web.app import get_context
from kronos.web.schemas import (
    AvailableModelResponse,
    LLMSecretUpdateRequest,
    LLMSettingsResponse,
    ProviderProbeResponse,
    ProviderReadinessResponse,
    ProviderSecretStatusResponse,
    RoleSettingsResponse,
    SystemPathsResponse,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

#: The connectivity probe sends exactly ONE chat completion request (this is
#: the paid part, surfaced to the user on the probe button label) with a
#: bounded token budget and timeout so the settings page cannot hang.
_PROBE_MAX_TOKENS: Final[int] = 256
_PROBE_TIMEOUT_SECONDS: Final[float] = 20.0


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings(request: Request) -> LLMSettingsResponse:
    """Return masked LLM provider and role settings."""
    context = get_context(request)
    secret_status = LocalSecretStore(context.secret_store_path).get_status(GLM_PROVIDER_NAME)
    roles = AgentRoleRegistry().list_roles()
    return LLMSettingsResponse(
        providers=[
            ProviderSecretStatusResponse(
                provider=secret_status.provider,
                configured=secret_status.configured,
                masked_value=secret_status.masked_value,
                storage_backend=secret_status.storage_backend,
            )
        ],
        roles=[
            RoleSettingsResponse(
                role_id=str(role.role_id),
                role_kind=role.role_kind.value,
                name_zh=role.name_zh,
                enabled=role.enabled,
                prompt_version=str(role.prompt_version),
                model_provider=role.model_provider,
                model_name=role.model_name,
            )
            for role in roles
        ],
        available_models=[
            AvailableModelResponse(
                model_id=model["id"],
                label_zh=model["label_zh"],
                label_en=model["label_en"],
            )
            for model in GLM_MODELS
        ],
    )


@router.get(
    "/llm/providers/{provider}/status",
    response_model=ProviderReadinessResponse,
)
def get_provider_status(provider: str, request: Request) -> ProviderReadinessResponse:
    """Return masked provider readiness without making a model call."""
    normalized_provider = _supported_provider(provider)

    context = get_context(request)
    status = GLMLLMProvider(secret_store=LocalSecretStore(context.secret_store_path)).check_status(
        model_name=_model_name_for_provider(normalized_provider)
    )
    return ProviderReadinessResponse(
        provider=status.provider,
        status=status.status.value,
        configured=status.configured,
        masked_api_key=status.masked_api_key,
        base_url=status.base_url,
        model_name=status.model_name,
        message_zh=status.message_zh,
    )


@router.put(
    "/llm/providers/{provider}/secret",
    response_model=ProviderSecretStatusResponse,
)
def set_provider_secret(
    provider: str,
    payload: LLMSecretUpdateRequest,
    request: Request,
) -> ProviderSecretStatusResponse:
    """Store a provider API key and return only masked status."""
    normalized_provider = _supported_provider(provider)
    context = get_context(request)
    status = LocalSecretStore(context.secret_store_path).set_secret(
        provider=normalized_provider,
        api_key=payload.api_key.get_secret_value(),
    )
    return ProviderSecretStatusResponse(
        provider=status.provider,
        configured=status.configured,
        masked_value=status.masked_value,
        storage_backend=status.storage_backend,
    )


@router.get(
    "/llm/providers/{provider}/probe",
    response_model=ProviderProbeResponse,
)
def probe_provider(provider: str, request: Request) -> ProviderProbeResponse:
    """Run one bounded connectivity probe; masked output, never echoes the key.

    Cost contract: when a key is configured this makes exactly one chat
    completion request (a tiny "ping" with a small token budget); the model's
    reply content is discarded and only reachability plus latency are
    reported. Without a key no network traffic happens at all.
    """
    normalized_provider = _supported_provider(provider)

    context = get_context(request)
    client = GLMClient(secret_store=LocalSecretStore(context.secret_store_path))
    model_name = _model_name_for_provider(normalized_provider)
    status = client.probe(model=model_name)
    if not status.configured:
        return ProviderProbeResponse(
            provider=status.provider,
            configured=False,
            masked_api_key=status.masked_api_key,
            base_url=status.base_url,
            model_name=status.model_name,
            reachable=False,
            latency_ms=None,
            message_zh="尚未配置 API Key，请先在上方保存 Key，再进行连通性测试。",
        )
    try:
        result = client.complete(
            [GLMChatMessage(role="user", content="ping")],
            model=model_name,
            max_tokens=_PROBE_MAX_TOKENS,
            timeout_seconds=_PROBE_TIMEOUT_SECONDS,
        )
    except GLMClientError as exc:
        # Typed client errors (GLMRequestError / GLMNotConfiguredError) carry
        # only HTTP status / exception type names, never the API key or the
        # raw response body.
        return ProviderProbeResponse(
            provider=status.provider,
            configured=True,
            masked_api_key=status.masked_api_key,
            base_url=status.base_url,
            model_name=status.model_name,
            reachable=False,
            latency_ms=None,
            message_zh=f"连通性测试失败：{exc}",
        )
    return ProviderProbeResponse(
        provider=status.provider,
        configured=True,
        masked_api_key=status.masked_api_key,
        base_url=status.base_url,
        model_name=result.model,
        reachable=True,
        latency_ms=result.latency_ms,
        message_zh=f"连通性测试成功：{result.model} 已正常响应（本次探测消耗了一次模型调用）。",
    )


@router.get("/system", response_model=SystemPathsResponse)
def get_system_paths(request: Request) -> SystemPathsResponse:
    """Return read-only local paths (no secrets) for the settings page."""
    context = get_context(request)
    return SystemPathsResponse(
        state_dir=str(context.state_path),
        data_dir=str(context.data_path),
        snapshots_dir=str(context.snapshots_path),
        freqtrade_venv=str(context.freqtrade_venv_path),
    )


def _model_name_for_provider(provider: str) -> str | None:
    role = next(
        (item for item in AgentRoleRegistry().list_roles() if item.model_provider == provider),
        None,
    )
    return role.model_name if role is not None else None


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower().replace("_", "-")


def _supported_provider(provider: str) -> str:
    normalized_provider = _normalize_provider(provider)
    if normalized_provider != GLM_PROVIDER_NAME:
        raise HTTPException(status_code=404, detail="Unsupported provider.")
    return normalized_provider
