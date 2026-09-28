# ruff: noqa: RUF001 -- Chinese user-facing strings use fullwidth punctuation.
"""Lean GLM (Zhipu) client for the conversation service (package P14).

OpenAI-compatible chat completions against the documented Zhipu endpoint
``https://open.bigmodel.cn/api/paas/v4/chat/completions``
(https://docs.bigmodel.cn/cn/guide/develop/openai/introduction.md; model ids
per https://docs.bigmodel.cn/cn/guide/start/model-overview.md).

Provider ruling D-20260928-002: GLM replaces DeepSeek as the single LLM
provider; there is intentionally no second provider behind this client.

Key resolution order: explicit ``api_key`` argument > SecretStore provider
``"glm"`` > ``KRONOS_GLM_API_KEY`` environment variable (tests/dev fallback).
Without a key, :meth:`GLMClient.complete` raises the typed
:class:`GLMNotConfiguredError` and :meth:`GLMClient.probe` reports
``configured=False`` — :meth:`probe` never makes a paid network call.

Model tiers (``kronos.agent.roles``): the strong tier (``glm-4.6``) is for
research-judgment roles; the cheap tier (``glm-4.5-air``) is the default
here because the conversation LLM hook only disambiguates parameters.

Every result carries the provider ``usage`` (prompt/completion tokens) for
the budget ledger; when the provider reports no usage the flag
``GLMUsage.estimated`` is set so the ledger records its conservative
default instead of zero (never zero).

The LLM is a LATER fallback hook in the conversation pipeline: the
deterministic path (P14) never calls this client. Tests mock httpx; the
single real-endpoint smoke test is skipped unless ``KRONOS_GLM_SMOKE=1``.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Final, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.llm import GLM_DEFAULT_BASE_URL, GLM_PROVIDER_NAME
from kronos.agent.roles import GLM_CHEAP_MODEL, GLM_STRONG_MODEL
from kronos.agent.secrets import mask_secret
from kronos.common.errors import KronosError

GLM_CHAT_COMPLETIONS_PATH: Final[str] = "/chat/completions"
GLM_API_KEY_ENV: Final[str] = "KRONOS_GLM_API_KEY"

__all__ = [
    "GLM_API_KEY_ENV",
    "GLM_CHAT_COMPLETIONS_PATH",
    "GLM_CHEAP_MODEL",
    "GLM_STRONG_MODEL",
    "GLMChatMessage",
    "GLMChatResult",
    "GLMClient",
    "GLMClientError",
    "GLMNotConfiguredError",
    "GLMProbeStatus",
    "GLMRequestError",
    "GLMUsage",
]

type GLMRole = Literal["system", "user", "assistant"]

_THINKING_TAG_RE: Final[re.Pattern[str]] = re.compile(r"</think>\s*", re.DOTALL)


class GLMClientError(KronosError):
    """Base class for GLM client failures."""


class GLMNotConfiguredError(GLMClientError):
    """No API key was found in the argument, the secret store, or the env."""


class GLMRequestError(GLMClientError):
    """The provider call failed (HTTP error or malformed response payload)."""


class GLMChatMessage(BaseModel):
    """One OpenAI-compatible chat message."""

    model_config = ConfigDict(extra="forbid")

    role: GLMRole
    content: str = Field(min_length=1)


class GLMUsage(BaseModel):
    """Token usage for the budget ledger.

    ``estimated=True`` marks the case where the provider returned no usage
    block; the ledger then records its conservative default, never zero.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated: bool = False


class GLMChatResult(BaseModel):
    """One completed chat completion."""

    model_config = ConfigDict(extra="forbid")

    content: str
    model: str
    usage: GLMUsage
    latency_ms: int
    raw_usage: dict[str, Any] = Field(default_factory=dict)


class GLMProbeStatus(BaseModel):
    """Masked provider readiness for the settings UI (no network call)."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    configured: bool
    masked_api_key: str | None = None
    base_url: str
    model_name: str
    message_zh: str


class _HttpResponse(Protocol):
    def raise_for_status(self) -> None:
        """Raise when the HTTP response is not successful."""

    def json(self) -> Any:
        """Return the response JSON."""


class _HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> _HttpResponse:
        """Send one HTTP POST request."""


class _SecretStoreLike(Protocol):
    def get_secret(self, provider: str) -> str | None:
        """Return the raw provider API key."""


class GLMClient:
    """Minimal OpenAI-compatible adapter for the Zhipu GLM endpoint."""

    def __init__(
        self,
        *,
        secret_store: _SecretStoreLike | None = None,
        api_key: str | None = None,
        model: str = GLM_CHEAP_MODEL,
        strong_model: str = GLM_STRONG_MODEL,
        base_url: str = GLM_DEFAULT_BASE_URL,
        timeout_seconds: float = 60.0,
        max_retries: int = 0,
        http_client: _HttpClient | None = None,
    ) -> None:
        self.secret_store = secret_store
        self._explicit_api_key = api_key
        self.model = model
        self.strong_model = strong_model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.http_client = http_client or httpx.Client()

    # ------------------------------------------------------------------ api

    def complete(
        self,
        messages: list[GLMChatMessage],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
        model: str | None = None,
    ) -> GLMChatResult:
        """Run one non-streaming chat completion; typed errors on failure.

        ``system`` is prepended as a system message when given. Provider or
        network failures raise :class:`GLMRequestError`; a missing key raises
        :class:`GLMNotConfiguredError` before any network traffic.
        """
        api_key = self._resolve_api_key()
        if api_key is None:
            raise GLMNotConfiguredError(
                "GLM（智谱）API Key 尚未配置：请通过 SecretStore（provider 'glm'）或 "
                f"环境变量 {GLM_API_KEY_ENV} 提供。"
            )
        payload_messages = [
            {"role": "system", "content": system},
            *[{"role": message.role, "content": message.content} for message in messages],
        ]
        body: dict[str, Any] = {
            "model": model or self.model,
            "messages": payload_messages,
            "stream": False,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.http_client.post(
                    f"{self.base_url}{GLM_CHAT_COMPLETIONS_PATH}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=timeout,
                )
                response.raise_for_status()
                content, usage, raw_usage = _parse_response(response.json())
                latency_ms = int((time.perf_counter() - started) * 1000)
                return GLMChatResult(
                    content=content,
                    model=body["model"],
                    usage=usage,
                    latency_ms=latency_ms,
                    raw_usage=raw_usage,
                )
            except httpx.HTTPStatusError as exc:
                # Deterministic HTTP failure (auth, bad request, rate limit):
                # retrying cannot fix it, so it surfaces immediately.
                raise GLMRequestError(f"GLM 请求失败：HTTP {exc.response.status_code}") from exc
            except GLMRequestError:
                raise
            except httpx.HTTPError as exc:
                # Transport-level failure: bounded retry, then typed error.
                last_error = exc
                if attempt >= self.max_retries:
                    raise GLMRequestError(f"GLM 请求失败：{type(exc).__name__}") from exc
        raise GLMRequestError(  # pragma: no cover - loop always returns or raises
            f"GLM 请求失败：{type(last_error).__name__ if last_error else 'unknown'}"
        )

    def probe(self, *, model: str | None = None) -> GLMProbeStatus:
        """Return masked readiness for the settings UI; never calls the API."""
        api_key = self._resolve_api_key()
        configured = api_key is not None
        return GLMProbeStatus(
            provider=GLM_PROVIDER_NAME,
            configured=configured,
            masked_api_key=mask_secret(api_key) if api_key is not None else None,
            base_url=self.base_url,
            model_name=model or self.model,
            message_zh="GLM（智谱）API Key 已配置。"
            if configured
            else "GLM（智谱）API Key 尚未配置。",
        )

    # ------------------------------------------------------------- internals

    def _resolve_api_key(self) -> str | None:
        if self._explicit_api_key:
            return self._explicit_api_key
        if self.secret_store is not None:
            stored = self.secret_store.get_secret(GLM_PROVIDER_NAME)
            if stored:
                return stored
        env_key = os.environ.get(GLM_API_KEY_ENV)
        return env_key or None


def _parse_response(payload: Any) -> tuple[str, GLMUsage, dict[str, Any]]:
    """Extract ``(content, usage, raw_usage)``; typed error on bad payloads."""
    if not isinstance(payload, dict):
        raise GLMRequestError("GLM 响应必须是 JSON 对象。")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GLMRequestError("GLM 响应缺少 choices。")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        raise GLMRequestError("GLM 响应 choice 缺少 message。")
    content = message.get("content")
    if not isinstance(content, str) or not content:
        # Reasoning variants may put the answer into reasoning_content after a
        # thinking block; strip a trailing </think> marker if present.
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            reasoning = _THINKING_TAG_RE.split(reasoning)[-1].strip()
            if reasoning:
                content = reasoning
    if not isinstance(content, str) or not content:
        raise GLMRequestError("GLM 响应 content 为空。")

    raw_usage: dict[str, Any] = {}
    raw_usage_value = payload.get("usage")
    if isinstance(raw_usage_value, dict):
        raw_usage = dict(raw_usage_value)
    usage = GLMUsage(
        prompt_tokens=_int_or_none(raw_usage.get("prompt_tokens")),
        completion_tokens=_int_or_none(raw_usage.get("completion_tokens")),
        total_tokens=_int_or_none(raw_usage.get("total_tokens")),
        estimated=not raw_usage,
    )
    return content, usage, raw_usage


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return None
