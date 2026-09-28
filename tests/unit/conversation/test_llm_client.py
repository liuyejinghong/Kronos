# ruff: noqa: RUF001 -- Chinese user-facing strings use fullwidth punctuation.
"""Unit tests for the GLM (Zhipu) conversation client — no real network.

The one optional real-endpoint smoke test (D-20260928-002 acceptance) is
skipped unless ``KRONOS_GLM_SMOKE=1`` AND a key is available via
``KRONOS_GLM_API_KEY`` or the secret store.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from kronos.agent.roles import GLM_CHEAP_MODEL, GLM_STRONG_MODEL
from kronos.agent.secrets import LocalSecretStore
from kronos.conversation.llm_client import (
    GLM_CHAT_COMPLETIONS_PATH,
    GLMChatMessage,
    GLMClient,
    GLMNotConfiguredError,
    GLMRequestError,
)

if TYPE_CHECKING:
    from pathlib import Path


class FakeResponse:
    def __init__(self, payload: dict[str, Any], *, status_error: bool = False) -> None:
        self.payload = payload
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error:
            request = httpx.Request("POST", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
            response = httpx.Response(status_code=401, request=request)
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeHttpClient:
    """Minimal httpx.Client stand-in recording every request."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        status_error: bool = False,
        transport_error: Exception | None = None,
    ) -> None:
        self.requests: list[dict[str, Any]] = []
        self.payload = payload if payload is not None else _provider_payload()
        self.status_error = status_error
        self.transport_error = transport_error

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self.transport_error is not None:
            raise self.transport_error
        return FakeResponse(self.payload, status_error=self.status_error)


def _provider_payload() -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": "解析结果"}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
    }


def _messages() -> list[GLMChatMessage]:
    return [GLMChatMessage(role="user", content="把「改成 2」解析成参数。")]


def _client(http: FakeHttpClient, **kwargs: Any) -> GLMClient:
    defaults: dict[str, Any] = {"api_key": "test-key", "timeout_seconds": 5.0}
    defaults.update(kwargs)
    return GLMClient(http_client=http, **defaults)


def test_complete_posts_openai_compatible_body_and_returns_content() -> None:
    http = FakeHttpClient()
    client = _client(http)

    result = client.complete(
        _messages(),
        system="你是意图澄清器。",
        temperature=0.1,
        max_tokens=256,
        timeout_seconds=3.0,
        model=GLM_STRONG_MODEL,
    )

    assert result.content == "解析结果"
    assert result.model == GLM_STRONG_MODEL
    assert http.requests[0]["url"] == (
        f"https://open.bigmodel.cn/api/paas/v4{GLM_CHAT_COMPLETIONS_PATH}"
    )
    body = http.requests[0]["json"]
    assert body["model"] == GLM_STRONG_MODEL
    assert body["stream"] is False
    assert body["temperature"] == 0.1
    assert body["max_tokens"] == 256
    assert body["messages"][0] == {"role": "system", "content": "你是意图澄清器。"}
    assert body["messages"][1] == {"role": "user", "content": "把「改成 2」解析成参数。"}
    assert http.requests[0]["timeout"] == 3.0
    assert http.requests[0]["headers"]["Authorization"] == "Bearer test-key"


def test_complete_returns_provider_usage_for_budget_ledger() -> None:
    result = _client(FakeHttpClient()).complete(_messages())

    assert result.usage.prompt_tokens == 120
    assert result.usage.completion_tokens == 30
    assert result.usage.total_tokens == 150
    assert result.usage.estimated is False
    assert result.raw_usage["total_tokens"] == 150


def test_missing_provider_usage_is_marked_estimated_never_zero() -> None:
    payload = {"choices": [{"message": {"content": "ok"}}]}
    result = _client(FakeHttpClient(payload)).complete(_messages())

    assert result.usage.prompt_tokens is None
    assert result.usage.completion_tokens is None
    assert result.usage.estimated is True


def test_reasoning_content_fallback_extracts_answer() -> None:
    payload = {
        "choices": [{"message": {"content": "", "reasoning_content": "思考…</think> 最终答案"}}]
    }
    result = _client(FakeHttpClient(payload)).complete(_messages())
    assert result.content == "最终答案"


def test_missing_key_raises_typed_not_configured_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KRONOS_GLM_API_KEY", raising=False)
    client = GLMClient(
        secret_store=LocalSecretStore(tmp_path / "secrets.json"),
        http_client=FakeHttpClient(),
    )

    with pytest.raises(GLMNotConfiguredError):
        client.complete(_messages())


def test_api_key_resolved_from_secret_store_provider_glm(tmp_path: Path) -> None:
    store = LocalSecretStore(tmp_path / "secrets.json")
    store.set_secret(provider="glm", api_key="stored-key-123456")
    http = FakeHttpClient()
    client = GLMClient(secret_store=store, http_client=http)

    result = client.complete(_messages())

    assert result.content == "解析结果"
    assert http.requests[0]["headers"]["Authorization"] == "Bearer stored-key-123456"


def test_env_key_used_when_store_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KRONOS_GLM_API_KEY", "env-key-654321")
    http = FakeHttpClient()
    client = GLMClient(
        secret_store=LocalSecretStore(tmp_path / "secrets.json"),
        http_client=http,
    )

    client.complete(_messages())

    assert http.requests[0]["headers"]["Authorization"] == "Bearer env-key-654321"


def test_explicit_key_wins_over_store_and_env(tmp_path: Path) -> None:
    store = LocalSecretStore(tmp_path / "secrets.json")
    store.set_secret(provider="glm", api_key="stored-key")
    http = FakeHttpClient()
    client = GLMClient(secret_store=store, api_key="explicit-key", http_client=http)

    client.complete(_messages())

    assert http.requests[0]["headers"]["Authorization"] == "Bearer explicit-key"


def test_http_status_error_raises_typed_request_error() -> None:
    client = _client(FakeHttpClient(status_error=True))

    with pytest.raises(GLMRequestError, match="401"):
        client.complete(_messages())


def test_transport_error_raises_typed_request_error() -> None:
    http = FakeHttpClient(transport_error=httpx.ConnectError("refused"))
    client = _client(http)

    with pytest.raises(GLMRequestError):
        client.complete(_messages())


def test_transport_error_bounded_retry_then_typed_error() -> None:
    http = FakeHttpClient(transport_error=httpx.ConnectError("refused"))
    client = GLMClient(api_key="k", max_retries=2, http_client=http)

    with pytest.raises(GLMRequestError):
        client.complete(_messages())

    assert len(http.requests) == 3  # 1 initial + 2 retries, no unbounded loop


def test_malformed_payload_raises_typed_request_error() -> None:
    client = _client(FakeHttpClient({"choices": []}))

    with pytest.raises(GLMRequestError):
        client.complete(_messages())


def test_empty_content_raises_typed_request_error() -> None:
    payload = {"choices": [{"message": {"content": ""}}]}
    client = _client(FakeHttpClient(payload))

    with pytest.raises(GLMRequestError):
        client.complete(_messages())


def test_probe_reports_masked_status_without_network(tmp_path: Path) -> None:
    http = FakeHttpClient()
    missing = GLMClient(secret_store=LocalSecretStore(tmp_path / "missing.json"), http_client=http)
    store = LocalSecretStore(tmp_path / "configured.json")
    store.set_secret(provider="glm", api_key="zmbr-key-987654")
    configured = GLMClient(secret_store=store, http_client=http)

    missing_status = missing.probe()
    configured_status = configured.probe(model=GLM_STRONG_MODEL)

    assert missing_status.configured is False
    assert missing_status.masked_api_key is None
    assert configured_status.configured is True
    assert configured_status.masked_api_key is not None
    assert configured_status.masked_api_key.endswith("654")
    assert configured_status.model_name == GLM_STRONG_MODEL
    assert configured_status.provider == "glm"
    assert len(http.requests) == 0  # probe never calls the provider


def test_default_model_is_the_cheap_tier() -> None:
    http = FakeHttpClient()
    _client(http).complete(_messages())
    assert http.requests[0]["json"]["model"] == GLM_CHEAP_MODEL


@pytest.mark.skipif(
    os.environ.get("KRONOS_GLM_SMOKE") != "1"
    or not (os.environ.get("KRONOS_GLM_API_KEY") or LocalSecretStore().get_secret("glm")),
    reason="real GLM endpoint smoke test; enable with KRONOS_GLM_SMOKE=1 and a key",
)
def test_real_glm_endpoint_smoke() -> None:
    """One real call against open.bigmodel.cn (counts against the budget)."""
    client = GLMClient(model=GLM_CHEAP_MODEL, timeout_seconds=30.0)
    result = client.complete(
        [GLMChatMessage(role="user", content="回复两个字：正常")],
        max_tokens=16,
        temperature=0.0,
    )
    assert result.content
    assert result.usage.total_tokens is None or result.usage.total_tokens > 0
