"""Settings routes for the local Web API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from kronos.agent.llm import DEEPSEEK_PROVIDER_NAME, DeepSeekLLMProvider
from kronos.agent.roles import DEEPSEEK_MODELS, AgentRoleRegistry
from kronos.agent.secrets import LocalSecretStore
from kronos.web.app import get_context
from kronos.web.schemas import (
    AvailableModelResponse,
    LLMSecretUpdateRequest,
    LLMSettingsResponse,
    ProviderReadinessResponse,
    ProviderSecretStatusResponse,
    RoleSettingsResponse,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings(request: Request) -> LLMSettingsResponse:
    """Return masked LLM provider and role settings."""
    context = get_context(request)
    secret_status = LocalSecretStore(context.secret_store_path).get_status("deepseek")
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
            for model in DEEPSEEK_MODELS
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
    status = DeepSeekLLMProvider(
        secret_store=LocalSecretStore(context.secret_store_path)
    ).check_status(model_name=_model_name_for_provider(normalized_provider))
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


def _model_name_for_provider(provider: str) -> str | None:
    role = next(
        (
            item
            for item in AgentRoleRegistry().list_roles()
            if item.model_provider == provider
        ),
        None,
    )
    return role.model_name if role is not None else None


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower().replace("_", "-")


def _supported_provider(provider: str) -> str:
    normalized_provider = _normalize_provider(provider)
    if normalized_provider != DEEPSEEK_PROVIDER_NAME:
        raise HTTPException(status_code=404, detail="Unsupported provider.")
    return normalized_provider
