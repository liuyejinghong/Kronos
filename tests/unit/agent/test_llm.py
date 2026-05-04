"""Tests for Agent LLM provider interfaces and DeepSeek adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kronos.agent.events import read_events
from kronos.agent.llm import (
    DEEPSEEK_PROVIDER_NAME,
    DeepSeekLLMProvider,
    DeepSeekProviderConfig,
    LLMCallStatus,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    build_llm_invocation_event,
    write_llm_invocation_event,
)
from kronos.agent.secrets import LocalSecretStore
from kronos.agent.types import (
    AgentArtifactRef,
    AgentEventType,
    AgentPromptVersionId,
    AgentRoleId,
    AgentTaskStatus,
)

if TYPE_CHECKING:
    from pathlib import Path


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeHTTPClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> FakeHTTPResponse:
        self.requests.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "模型结论"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            }
        )


def _request() -> LLMRequest:
    return LLMRequest(
        role_id=AgentRoleId("researcher"),
        prompt_version=AgentPromptVersionId("researcher-prompt-v1"),
        model_provider=DEEPSEEK_PROVIDER_NAME,
        model_name="custom-agent-model",
        messages=[
            LLMMessage(role=LLMMessageRole.SYSTEM, content="你是量化研究员。"),
            LLMMessage(role=LLMMessageRole.USER, content="生成下一轮研究假设。"),
        ],
        temperature=0.2,
        max_tokens=512,
        artifact_paths=[
            AgentArtifactRef(
                name="source_summary",
                path="reports/source.json",
                artifact_type="json",
            )
        ],
    )


def test_deepseek_provider_returns_waiting_configuration_without_key(tmp_path: Path) -> None:
    provider = DeepSeekLLMProvider(
        secret_store=LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json"),
    )

    response = provider.complete(_request())
    status = provider.check_status(model_name="custom-agent-model")

    assert response.status == LLMCallStatus.WAITING_CONFIGURATION
    assert response.invocation.status == AgentTaskStatus.WAITING_APPROVAL
    assert response.invocation.error_ref is not None
    assert response.invocation.error_ref.error_code == "llm_provider_not_configured"
    assert status.status == LLMCallStatus.WAITING_CONFIGURATION
    assert status.configured is False
    assert status.masked_api_key is None


def test_deepseek_provider_uses_configured_model_and_masks_status(tmp_path: Path) -> None:
    raw_key = "sk-test-secret-123456"
    secret_store = LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json")
    secret_store.set_secret(provider=DEEPSEEK_PROVIDER_NAME, api_key=raw_key)
    fake_http = FakeHTTPClient()
    provider = DeepSeekLLMProvider(
        secret_store=secret_store,
        config=DeepSeekProviderConfig(base_url="https://api.deepseek.com", timeout_seconds=7.0),
        http_client=fake_http,
    )

    response = provider.complete(_request())
    status = provider.check_status(model_name="custom-agent-model")

    assert response.status == LLMCallStatus.COMPLETED
    assert response.content == "模型结论"
    assert response.raw_usage == {"prompt_tokens": 10, "completion_tokens": 3}
    assert fake_http.requests[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert fake_http.requests[0]["json"]["model"] == "custom-agent-model"
    assert fake_http.requests[0]["timeout"] == 7.0
    assert raw_key not in status.model_dump_json()
    assert status.masked_api_key is not None
    assert status.masked_api_key.endswith("3456")


def test_llm_invocation_event_records_trace_fields_without_secret(tmp_path: Path) -> None:
    provider = DeepSeekLLMProvider(
        secret_store=LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json"),
    )
    response = provider.complete(_request())

    event = build_llm_invocation_event(
        run_id="run-1",
        task_id="task-1",
        response=response,
    )

    assert event.event_type == AgentEventType.ERROR_REPORTED
    assert event.role_id == "researcher"
    assert event.prompt_version == "researcher-prompt-v1"
    assert event.model_provider == DEEPSEEK_PROVIDER_NAME
    assert event.model_name == "custom-agent-model"
    assert event.metadata["llm_status"] == "waiting_configuration"
    assert "api_key" not in event.model_dump_json()


def test_write_llm_invocation_event_appends_to_timeline(tmp_path: Path) -> None:
    provider = DeepSeekLLMProvider(
        secret_store=LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json"),
    )
    response = provider.complete(_request())

    write_llm_invocation_event(
        run_dir=str(tmp_path / "run-1"),
        run_id="run-1",
        task_id="task-1",
        response=response,
    )
    events = read_events(tmp_path / "run-1")

    assert len(events) == 1
    assert events[0].metadata["llm_status"] == "waiting_configuration"
