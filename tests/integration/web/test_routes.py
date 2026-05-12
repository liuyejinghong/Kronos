"""Route tests for the local Kronos Agent Web API."""
# ruff: noqa: RUF001

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from kronos.agent.events import write_event
from kronos.agent.supervisor import AgentSupervisor
from kronos.agent.types import (
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentRunId,
    AgentTaskId,
    AgentTaskStatus,
)
from kronos.web import create_app


def _client(tmp_path: Path) -> TestClient:
    app = create_app(project_root=tmp_path)
    return TestClient(app)


def _copy_memory_docs(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[3]
    for relative_path in [
        "MEMORY.md",
        "DECISIONS.md",
        "TODO.md",
        "docs/PROJECT_STATUS.md",
        "docs/ROADMAP.md",
        "docs/PRODUCT_CONTROL_PANEL.md",
        "docs/agent-harness/PROGRESS_LOG.md",
    ]:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative_path, target)


def test_agent_status_returns_current_supervisor_status(tmp_path: Path) -> None:
    runtime_path = tmp_path / "reports" / "agent_runtime"
    AgentSupervisor(runtime_path).start_run(
        run_id="web-agent-run",
        goal_zh="验证 Web API 状态。",
        task_id="task-1",
        task_title_zh="启动 Agent",
    )
    client = _client(tmp_path)

    response = client.get("/api/agent/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is True
    assert payload["current_run"]["run_id"] == "web-agent-run"
    assert payload["current_task"]["task_id"] == "task-1"
    assert payload["last_event"]["event_type"] == "run_started"


def test_candidate_pool_and_detail_routes(tmp_path: Path) -> None:
    from kronos.factor.candidates import CandidateFactorSpec, clear_candidates, register_candidate

    clear_candidates()
    register_candidate(CandidateFactorSpec(
        "test_strategy", "trend_momentum", "测试策略", ("BTCUSDT", "ETHUSDT"), 1,
        "test_impl",
    ))
    register_candidate(CandidateFactorSpec(
        "test_strategy_2", "volatility_path", "测试策略2", ("SOLUSDT",), 2,
    ))

    client = _client(tmp_path)

    list_response = client.get("/api/candidates")
    detail_response = client.get("/api/candidates/test_strategy")

    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["candidate_id"] == "test_strategy"
    assert detail["implementation_name"] == "test_impl"
    assert detail["source_strategies"]

    clear_candidates()


def test_event_timeline_and_sse_routes(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "research" / "experiments" / "web-run"
    write_event(
        AgentEvent(
            run_id=AgentRunId("web-run"),
            task_id=AgentTaskId("task-1"),
            event_id=AgentEventId("event-1"),
            event_type=AgentEventType.TOOL_EXECUTION_COMPLETED,
            level=AgentEventLevel.DECISION,
            status=AgentTaskStatus.COMPLETED,
            message_zh="工具执行完成。",
        ),
        run_dir=run_dir,
    )
    client = _client(tmp_path)

    list_response = client.get("/api/agent/events", params={"run_id": "web-run"})
    stream_response = client.get("/api/agent/events/stream", params={"run_id": "web-run"})

    assert list_response.status_code == 200
    assert list_response.json()[0]["message_zh"] == "工具执行完成。"
    assert stream_response.status_code == 200
    assert "text/event-stream" in stream_response.headers["content-type"]
    assert "tool_execution_completed" in stream_response.text


def test_agent_run_summary_route_returns_pm_brief(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "research" / "experiments" / "web-run"
    run_dir.mkdir(parents=True)
    (run_dir / "agent_run_summary.json").write_text(
        json.dumps(
            {
                "run": {
                    "run_id": "web-run",
                    "status": "completed",
                    "goal_zh": "验证 Web 汇总。",
                    "artifact_paths": [],
                },
                "outputs": [
                    {
                        "conclusion": "进入候选改造。",
                        "next_action": "先做 crypto-native 改造。",
                        "max_risk": "证据仍不足。",
                        "approval_required": False,
                        "support_reasons": ["有弱正向证据。"],
                        "opposition_reasons": ["不能直接实盘。"],
                        "key_evidence": [
                            {
                                "name": "report",
                                "path": "reports/research/example.md",
                                "artifact_type": "md",
                                "summary_zh": None,
                            }
                        ],
                    }
                ],
                "event_count": 6,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = _client(tmp_path)

    response = client.get("/api/agent/runs/web-run/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "web-run"
    assert payload["goal_zh"] == "验证 Web 汇总。"
    assert payload["next_action_zh"] == "先做 crypto-native 改造。"
    assert payload["evidence_count"] == 1
    assert payload["event_count"] == 6


def test_agent_run_report_route_returns_readable_markdown(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "research" / "experiments" / "web-run"
    run_dir.mkdir(parents=True)
    (run_dir / "agent_run_report.md").write_text(
        "# Web Run Agent 报告\n\n本轮结论: 进入候选改造。\n",
        encoding="utf-8",
    )
    client = _client(tmp_path)

    response = client.get("/api/agent/runs/web-run/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "web-run"
    assert payload["title_zh"] == "Web Run Agent 报告"
    assert "进入候选改造" in payload["content_md"]


def test_agent_memory_summary_route_returns_acceptance_first_state(tmp_path: Path) -> None:
    _copy_memory_docs(tmp_path)
    client = _client(tmp_path)

    response = client.get("/api/agent/memory/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["current_version"] == "0.4.10"
    assert payload["state"]["next_version"] == "0.4.11"
    assert "Agent 记忆与交接控制台" in payload["state"]["current_acceptance_target_zh"]
    assert "产品 review" in payload["state"]["next_action_zh"]
    assert "还没有成功证据" not in payload["state"]["latest_successful_run_zh"]
    assert "20260509T134805Z-paper" in payload["state"]["latest_successful_run_zh"]
    assert payload["handoff"]["prompt_md"].startswith("# Kronos Agent Handoff")
    assert payload["check"]["blocking_count"] == 0


def test_agent_memory_check_route_flags_missing_docs(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/agent/memory/check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocking"
    assert payload["blocking_count"] >= 1


def test_paper_status_route_returns_not_started_without_run(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/paper/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_started"
    assert payload["environment"] == "testnet"
    assert payload["run_id"] is None
    assert payload["latest_orders"] == []
    assert "preflight" in payload["next_action_zh"]


def test_paper_status_route_returns_latest_run_evidence(tmp_path: Path) -> None:
    paper_dir = tmp_path / "reports" / "paper"
    run_dir = paper_dir / "web-paper-run"
    run_dir.mkdir(parents=True)
    status_payload = {
        "run_id": "web-paper-run",
        "status": "completed",
        "environment": "testnet",
        "run_dir": str(run_dir),
        "report_path": str(run_dir / "paper_report.md"),
        "symbol": "BTCUSDT",
        "side": "BUY",
        "testnet_only": True,
    }
    (paper_dir / "current_status.json").write_text(
        json.dumps(status_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "paper_orders.jsonl").write_text(
        json.dumps(
            {
                "order_id": "testnet-order-1",
                "client_order_id": "kronos-web-paper-run",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 0.001,
                "status": "FILLED",
                "environment": "testnet",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "paper_fills.jsonl").write_text(
        json.dumps(
            {
                "order_id": "testnet-order-1",
                "trade_id": "trade-1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "price": 50000.0,
                "quantity": 0.001,
                "commission": 0.01,
                "commission_asset": "USDT",
                "fill_time": "2026-05-09T00:00:00+00:00",
                "environment": "testnet",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "paper_report.md").write_text(
        "# Binance 测试网模拟盘报告\n\n- 测试网订单 ID：testnet-order-1\n",
        encoding="utf-8",
    )
    client = _client(tmp_path)

    status_response = client.get("/api/paper/status")
    report_response = client.get("/api/paper/runs/web-paper-run/report")

    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "completed"
    assert status["run_id"] == "web-paper-run"
    assert status["report_available"] is True
    assert status["latest_orders"][0]["order_id"] == "testnet-order-1"
    assert status["latest_fills"][0]["trade_id"] == "trade-1"
    assert "实盘" in status["next_action_zh"]
    assert report_response.status_code == 200
    assert report_response.json()["title_zh"] == "Binance 测试网模拟盘报告"


def test_paper_run_report_route_redacts_secret_like_markdown(tmp_path: Path) -> None:
    paper_dir = tmp_path / "reports" / "paper"
    run_dir = paper_dir / "failed-paper-run"
    run_dir.mkdir(parents=True)
    (run_dir / "paper_report.md").write_text(
        (
            "# Binance 测试网模拟盘报告\n\n"
            "- 错误：api_secret=super-secret signature=abc123 token=token123\n"
            "- URL：https://testnet.binance.vision/api/v3/order?signature=abc123&token=token123\n"
        ),
        encoding="utf-8",
    )
    client = _client(tmp_path)

    response = client.get("/api/paper/runs/failed-paper-run/report")

    assert response.status_code == 200
    raw = response.text
    payload = response.json()
    assert payload["title_zh"] == "Binance 测试网模拟盘报告"
    assert "api_secret=<redacted>" in payload["content_md"]
    assert "signature=<redacted>" in payload["content_md"]
    assert "token=<redacted>" in payload["content_md"]
    assert "https://testnet.binance.vision/api/v3/order?<redacted>" in payload["content_md"]
    assert "super-secret" not in raw
    assert "abc123" not in raw
    assert "token123" not in raw


def test_paper_status_route_returns_failed_state_without_secret_leak(tmp_path: Path) -> None:
    paper_dir = tmp_path / "reports" / "paper"
    run_dir = paper_dir / "failed-paper-run"
    run_dir.mkdir(parents=True)
    (paper_dir / "current_status.json").write_text(
        json.dumps(
            {
                "run_id": "failed-paper-run",
                "status": "failed",
                "environment": "testnet",
                "run_dir": str(run_dir),
                "failure_reason": "api_key=sk-real-secret-1234 Binance 测试网连接失败",
                "testnet_only": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "paper_errors.jsonl").write_text(
        json.dumps(
            {
                "run_id": "failed-paper-run",
                "environment": "testnet",
                "reason": "api_secret=super-secret signature=abc123 token=token123",
                "created_at": "2026-05-09T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    client = _client(tmp_path)

    response = client.get("/api/paper/status")

    assert response.status_code == 200
    raw = response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["latest_errors"][0]["reason"] == (
        "api_secret=<redacted> signature=<redacted> token=<redacted>"
    )
    assert "sk-real-secret-1234" not in raw
    assert "super-secret" not in raw
    assert "abc123" not in raw


def test_paper_status_route_redacts_failure_reason_without_error_ledger(tmp_path: Path) -> None:
    paper_dir = tmp_path / "reports" / "paper"
    run_dir = paper_dir / "failed-paper-run"
    run_dir.mkdir(parents=True)
    (paper_dir / "current_status.json").write_text(
        json.dumps(
            {
                "run_id": "failed-paper-run",
                "status": "failed",
                "environment": "testnet",
                "run_dir": str(run_dir),
                "failure_reason": "api_key=sk-real-secret-1234 Binance 测试网连接失败",
                "testnet_only": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = _client(tmp_path)

    response = client.get("/api/paper/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_errors"][0]["reason"] == (
        "api_key=<redacted> Binance 测试网连接失败"
    )
    assert "sk-real-secret-1234" not in response.text


def test_llm_settings_masks_provider_secret(tmp_path: Path) -> None:
    client = _client(tmp_path)

    set_response = client.put(
        "/api/settings/llm/providers/deepseek/secret",
        json={"api_key": "sk-real-secret-1234"},
    )
    settings_response = client.get("/api/settings/llm")

    assert set_response.status_code == 200
    assert set_response.json()["configured"] is True
    assert "sk-real-secret-1234" not in set_response.text
    assert settings_response.status_code == 200
    assert "sk-real-secret-1234" not in settings_response.text
    assert settings_response.json()["providers"][0]["masked_value"].endswith("1234")


def test_llm_provider_status_is_masked_and_local_only(tmp_path: Path) -> None:
    client = _client(tmp_path)

    missing_response = client.get("/api/settings/llm/providers/deepseek/status")
    client.put(
        "/api/settings/llm/providers/deepseek/secret",
        json={"api_key": "sk-real-secret-5678"},
    )
    configured_response = client.get("/api/settings/llm/providers/deepseek/status")

    assert missing_response.status_code == 200
    assert missing_response.json()["configured"] is False
    assert missing_response.json()["status"] == "waiting_configuration"
    assert configured_response.status_code == 200
    assert configured_response.json()["configured"] is True
    assert configured_response.json()["status"] == "completed"
    assert configured_response.json()["masked_api_key"].endswith("5678")
    assert "sk-real-secret-5678" not in configured_response.text
    assert configured_response.json()["model_name"] == "deepseek-v4-pro"


def test_llm_secret_rejects_unsupported_provider(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put(
        "/api/settings/llm/providers/unknown-provider/secret",
        json={"api_key": "sk-should-not-write"},
    )

    assert response.status_code == 404
    assert not (tmp_path / ".kronos-secrets" / "agent_secrets.json").exists()


def test_material_import_writes_local_append_only_record(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/materials",
        json={
            "title_zh": "趋势回踩复盘",
            "content": "这里是一段用户导入的研究材料。",
            "source_type": "user_note",
            "candidate_id": "trend_pullback_entry",
            "tags": ["manual"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["material_id"].startswith("material-")
    material_store = tmp_path / "reports" / "agent_materials" / "materials.jsonl"
    raw = material_store.read_text(encoding="utf-8")
    assert "这里是一段用户导入的研究材料。" in raw


def test_approvals_route_returns_empty_pending_list(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/approvals")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_approval_resolve_records_agent_event(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/approvals/approval-1/resolve",
        json={
            "run_id": "approval-run",
            "task_id": "task-1",
            "approved": True,
            "reason_zh": "同意进入下一步模拟验证。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_id"] == "approval-1"
    events_path = tmp_path / "reports" / "agent_runtime" / "approval-run" / "agent_events.jsonl"
    raw = events_path.read_text(encoding="utf-8")
    assert "approval_resolved" in raw
    assert "同意进入下一步模拟验证。" in raw
