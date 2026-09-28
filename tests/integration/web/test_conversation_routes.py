"""Integration tests for the conversation + run API routes (P14)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.testclient import TestClient

from kronos.web import create_app

if TYPE_CHECKING:
    from pathlib import Path


def _client(tmp_path: Path) -> TestClient:
    app = create_app(project_root=tmp_path)
    return TestClient(app)


def _create_session(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/conversations")
    assert response.status_code == 201
    return response.json()


def test_create_conversation_returns_session_and_root_revision(tmp_path: Path) -> None:
    client = _client(tmp_path)

    payload = _create_session(client)

    assert payload["session_id"]
    assert payload["created_at_ms"] > 0
    assert payload["current_revision_id"]


def test_message_turn_returns_202_shape_with_task(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)

    response = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "把倍数改成 2.0"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "submitted"
    assert body["message_id"] > 0
    assert body["assistant_message_id"] > 0
    assert body["revision_id"].startswith(session["current_revision_id"])
    assert body["parent_revision_id"] == session["current_revision_id"]
    assert body["task_id"] is not None
    assert body["task_state"] == "queued"
    assert body["diff"][0]["field"] == "params.volatility_multiplier"
    assert body["echo_text"]
    assert body["clarification_question"] is None


def test_message_turn_clarification_and_refusal_shapes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)

    clarify = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "更激进一点"},
    )
    assert clarify.status_code == 202
    clarify_body = clarify.json()
    assert clarify_body["status"] == "clarification_needed"
    assert clarify_body["task_id"] is None
    assert clarify_body["clarification_question"]
    assert clarify_body["revision_id"] is None

    refused = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "帮我实盘下单"},
    )
    assert refused.status_code == 202
    refused_body = refused.json()
    assert refused_body["status"] == "refused"
    assert refused_body["task_id"] is None


def test_unknown_session_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)

    missing_message = client.post("/api/conversations/deadbeef/messages", json={"text": "你好"})
    missing_session = client.get("/api/conversations/deadbeef")

    assert missing_message.status_code == 404
    assert missing_session.status_code == 404


def test_invalid_message_payload_returns_422(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)

    empty = client.post(f"/api/conversations/{session['session_id']}/messages", json={"text": ""})
    extra = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "你好", "evil": "payload"},
    )
    wrong_type = client.post(
        f"/api/conversations/{session['session_id']}/messages", json={"text": 123}
    )

    assert empty.status_code == 422
    assert extra.status_code == 422
    assert wrong_type.status_code == 422


def test_get_conversation_returns_messages_and_revision(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)
    client.post(f"/api/conversations/{session['session_id']}/messages", json={"text": "你好"})
    client.post(f"/api/conversations/{session['session_id']}/messages", json={"text": "改用 1h"})

    response = client.get(f"/api/conversations/{session['session_id']}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["messages"]) == 4
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert body["current_revision"]["signal_timeframe"] == "1h"
    assert body["holdout_exposure_count"] == 0


def test_run_status_events_pagination_and_cancel(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)
    submitted = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "倍数改成 2.0"},
    ).json()
    task_id = submitted["task_id"]

    status = client.get(f"/api/runs/{task_id}")
    assert status.status_code == 200
    assert status.json()["state"] == "queued"
    assert status.json()["result_available"] is False

    first_page = client.get(f"/api/runs/{task_id}/events", params={"after_seq": 0})
    assert first_page.status_code == 200
    events = first_page.json()["events"]
    assert len(events) == 1
    assert events[0]["seq"] == 1

    second_page = client.get(f"/api/runs/{task_id}/events", params={"after_seq": 1})
    assert second_page.json()["events"] == []

    # Two-step cancel, step 1: queued task has no work to stop → cancelled.
    cancel = client.post(f"/api/runs/{task_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["state"] == "cancelled"

    again = client.post(f"/api/runs/{task_id}/cancel")
    assert again.status_code == 409


def test_cancel_running_task_shows_cancel_requested(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)
    submitted = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "倍数改成 2.0"},
    ).json()
    task_id = submitted["task_id"]

    # Simulate a worker claim so the task is running (service was lazily
    # created on app.state by the message POST above).
    service = client.app.state.conversation_service
    claimed = service.task_store.claim("worker-1", lease_ms=60_000)
    assert claimed.task_id == task_id

    cancel = client.post(f"/api/runs/{task_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["state"] == "cancel_requested"


def test_unknown_run_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.get("/api/runs/missing123").status_code == 404
    assert client.get("/api/runs/missing123/events").status_code == 404
    assert client.post("/api/runs/missing123/cancel").status_code == 404
    assert client.get("/api/verdicts/missing123").status_code == 404


def test_invalid_run_id_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)

    # Path-safe but regex-invalid ids are rejected by the shared validator.
    unicode_id = client.get("/api/runs/%E4%BD%A0%E5%A5%BD")  # 你好
    space_id = client.get("/api/runs/run%20id")
    assert unicode_id.status_code == 400
    assert space_id.status_code == 400


def test_verdict_endpoint_reads_published_artifact(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _create_session(client)
    submitted = client.post(
        f"/api/conversations/{session['session_id']}/messages",
        json={"text": "倍数改成 2.0"},
    ).json()
    task_id = submitted["task_id"]

    pending = client.get(f"/api/verdicts/{task_id}")
    assert pending.status_code == 404

    service = client.app.state.conversation_service
    claimed = service.task_store.claim("worker-1", lease_ms=60_000)
    service.task_store.commit_result(
        task_id,
        "worker-1",
        claimed.fencing_token,
        "succeeded",
        result={
            "verdict": {"evidence_status": "valid", "disposition": "observe"},
            "artifact_refs": {"ledger": "runs/r/execution.jsonl"},
        },
    )

    published = client.get(f"/api/verdicts/{task_id}")
    assert published.status_code == 200
    body = published.json()
    assert body["run_id"] == task_id
    assert body["state"] == "succeeded"
    assert body["verdict"]["evidence_status"] == "valid"
    assert body["artifact_refs"]["ledger"] == "runs/r/execution.jsonl"


def test_settings_routes_still_expose_glm_provider(tmp_path: Path) -> None:
    """The provider switch must keep the settings surface consistent."""
    client = _client(tmp_path)

    settings = client.get("/api/settings/llm")
    assert settings.status_code == 200
    body = settings.json()
    assert body["providers"][0]["provider"] == "glm"
    assert {m["model_id"] for m in body["available_models"]} == {"glm-4.6", "glm-4.5-air"}
    assert all(role["model_provider"] == "glm" for role in body["roles"])
