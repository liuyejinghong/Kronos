"""Integration tests for the extra v0.5.0 settings endpoints (P18).

Covers ``GET /api/settings/llm/providers/glm/probe`` (masked connectivity
probe, one bounded chat call) and ``GET /api/settings/system`` (read-only
local paths, no secrets). The probe's paid call is stubbed by replacing the
``GLMClient`` symbol inside the settings route module, so no test traffic
ever reaches the real GLM endpoint.
"""

# ruff: noqa: RUF001

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from fastapi.testclient import TestClient

from kronos.agent.secrets import LocalSecretStore
from kronos.conversation.llm_client import (
    GLMChatMessage,
    GLMChatResult,
    GLMProbeStatus,
    GLMRequestError,
    GLMUsage,
)
from kronos.web import create_app
from kronos.web.routes import settings as settings_routes

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(project_root=tmp_path))


class _StubGLMClient:
    """Offline stand-in for GLMClient, installed via ``_install_stub``."""

    last_request: ClassVar[dict[str, Any]] = {}
    raise_error: ClassVar[Exception | None] = None

    def __init__(self, *, secret_store: Any = None, **_kwargs: Any) -> None:
        self._secret_store = secret_store

    def probe(self, *, model: str | None = None) -> GLMProbeStatus:
        secret = self._secret_store.get_secret("glm") if self._secret_store else None
        configured = bool(secret)
        return GLMProbeStatus(
            provider="glm",
            configured=configured,
            masked_api_key="****1234" if configured else None,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model_name=model or "glm-4.5-air",
            message_zh="GLM（智谱）API Key 已配置。"
            if configured
            else "GLM（智谱）API Key 尚未配置。",
        )

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
        _StubGLMClient.last_request = {
            "messages": [item.content for item in messages],
            "max_tokens": max_tokens,
            "timeout_seconds": timeout_seconds,
            "model": model,
        }
        if _StubGLMClient.raise_error is not None:
            raise _StubGLMClient.raise_error
        return GLMChatResult(
            content="pong",
            model=model or "glm-4.5-air",
            usage=GLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            latency_ms=123,
        )


def _install_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubGLMClient.last_request = {}
    _StubGLMClient.raise_error = None
    monkeypatch.setattr(settings_routes, "GLMClient", _StubGLMClient)


def test_probe_without_key_reports_not_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a stored key the probe endpoint reports configured=False."""
    _install_stub(monkeypatch)
    client = _client(tmp_path)

    response = client.get("/api/settings/llm/providers/glm/probe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "glm"
    assert payload["configured"] is False
    assert payload["reachable"] is False
    assert payload["masked_api_key"] is None
    assert payload["latency_ms"] is None
    assert "尚未配置" in payload["message_zh"]
    assert _StubGLMClient.last_request == {}


def test_probe_with_key_makes_one_bounded_call_and_masks_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a key, exactly one bounded chat call runs and only masked data returns."""
    _install_stub(monkeypatch)
    store = LocalSecretStore()
    store.set_secret(provider="glm", api_key="sk-real-secret-1234")
    client = _client(tmp_path)

    response = client.get("/api/settings/llm/providers/glm/probe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["reachable"] is True
    assert payload["latency_ms"] == 123
    assert payload["masked_api_key"] == "****1234"
    assert "sk-real-secret-1234" not in response.text
    assert _StubGLMClient.last_request["max_tokens"] is not None
    assert _StubGLMClient.last_request["timeout_seconds"] is not None
    # One probe = exactly one chat message sent to the provider.
    assert len(_StubGLMClient.last_request["messages"]) == 1


def test_probe_provider_failure_is_reported_masked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider errors surface as reachable=False with a Chinese message."""
    _install_stub(monkeypatch)
    LocalSecretStore().set_secret(provider="glm", api_key="sk-real-secret-1234")
    _StubGLMClient.raise_error = GLMRequestError("GLM 请求失败：HTTP 401")
    client = _client(tmp_path)

    response = client.get("/api/settings/llm/providers/glm/probe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["reachable"] is False
    assert "HTTP 401" in payload["message_zh"]
    assert "sk-real-secret-1234" not in response.text


def test_probe_unsupported_provider_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/settings/llm/providers/deepseek/probe")

    assert response.status_code == 404


def test_system_paths_are_read_only_strings(tmp_path: Path) -> None:
    """The system endpoint returns the four local paths and no secret material."""
    client = _client(tmp_path)

    response = client.get("/api/settings/system")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "state_dir": str(tmp_path / "state"),
        "data_dir": str(tmp_path / "data"),
        "snapshots_dir": str(tmp_path / "state" / "snapshots"),
        "freqtrade_venv": str(tmp_path / ".tools" / "freqtrade-venv"),
    }
    assert "api_key" not in response.text
