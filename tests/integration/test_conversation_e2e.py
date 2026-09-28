"""Conversation E2E happy path with a fake engine (P20, planning doc 7.4).

Full loop through the REAL ConversationService / TaskStore / BudgetLedger on
real SQLite files in tmp, with the backtest engine replaced by a fake handler
that writes a verdict artifact and returns the publishable result:

session -> 把倍数改成 2.0 (diff echo + 202-shaped task submission) -> fake
engine completes the task -> evidence question answered from the published
verdict -> one more revision switch (换 ETHUSDT) -> lineage chain correct.

No LLM anywhere: every turn is deterministic (no GLM key in the environment),
per the conversation-web spec (对话是主入口且意图有界 / 证据问答不触发计算).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from kronos.conversation.intents import parse_intent
from kronos.conversation.service import ConversationService
from kronos.runtime.worker import Worker

if TYPE_CHECKING:
    from pathlib import Path


def _verdict_writer(state_dir: Path):
    """Fake evaluate_strategy engine: deterministic verdict per spec hash."""

    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        run_dir = state_dir / "runs" / str(payload["spec_hash"][:16])
        run_dir.mkdir(parents=True, exist_ok=True)
        verdict_path = run_dir / "verdict.json"
        verdict = {
            "evidence_status": "valid",
            "disposition": "observe",
            "reason_codes": [f"spec_hash={str(payload['spec_hash'])[:12]}"],
            "symbols": payload["spec_content"]["symbols"],
            "volatility_multiplier": payload["spec_content"]["params"]["volatility_multiplier"],
        }
        verdict_path.write_text(json.dumps(verdict, sort_keys=True), encoding="utf-8")
        return {
            "verdict": verdict,
            "artifact_refs": {"verdict_json": str(verdict_path)},
        }

    return handler


def _run_engine(service: ConversationService, state_dir: Path) -> dict[str, Any]:
    """Complete exactly one queued task through the real worker loop."""
    worker = Worker(
        service.task_store, {"evaluate_strategy": _verdict_writer(state_dir)}, heartbeat_s=0
    )
    done = worker.run_once()
    assert done is not None
    result = service.task_store.get_result(done.task_id)
    assert result is not None
    return result


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ConversationService, Path]:
    monkeypatch.delenv("KRONOS_GLM_API_KEY", raising=False)
    state = tmp_path / "state"
    service = ConversationService(state)
    yield service, state
    service.close()


def test_full_conversation_loop_with_fake_engine(
    env: tuple[ConversationService, Path],
) -> None:
    service, state = env

    # Every user utterance in this loop resolves deterministically (no model).
    for text in ("把倍数改成 2.0", "为什么不如持有", "换成ETHUSDT"):
        assert parse_intent(text).confidence == "deterministic"

    # ---- 1. session rooted at the default revision --------------------------
    session = service.create_session()
    sid = session.session_id
    root = service.current_revision(sid)
    assert root.parent_revision_id is None
    assert root.symbols == ["BTCUSDT"] and root.params.volatility_multiplier == 1.0

    # ---- 2. explicit adjustment: diff echo + 202-shaped task submission -----
    adjust = service.send_message(sid, "把倍数改成 2.0")
    assert adjust.status == "submitted"
    assert adjust.message_id > 0 and adjust.assistant_message_id > 0
    assert adjust.task_state == "queued"  # accepted (202), not yet executed
    assert adjust.parent_revision_id == root.strategy_revision_id
    assert [(d.field, d.old, d.new) for d in adjust.diff] == [
        ("params.volatility_multiplier", "1", "2")
    ]
    assert "volatility_multiplier" in adjust.echo_text
    assistant_msg = service.list_messages(sid)[-1]
    assert assistant_msg.role == "assistant"
    assert "已创建修订" in assistant_msg.content and "评估任务已提交" in assistant_msg.content
    payload = service.task_store.get_payload(adjust.task_id)
    assert payload["session_id"] == sid
    assert payload["spec_content"]["params"]["volatility_multiplier"] == 2.0

    # ---- 3. fake engine completes the task synchronously --------------------
    result1 = _run_engine(service, state)
    assert result1["verdict"]["evidence_status"] == "valid"
    assert service.task_store.get(adjust.task_id).state == "succeeded"

    # ---- 4. evidence question answered from the published verdict -----------
    # (and never starting a new backtest — 证据问答不触发计算)
    tasks_before = len(service.task_store.list_tasks())
    evidence = service.send_message(sid, "为什么不如持有")
    assert evidence.status == "answered"
    assert evidence.task_id is None
    assert len(service.task_store.list_tasks()) == tasks_before
    revision1_hash = service.current_revision(sid).spec_hash
    assert evidence.verdict_refs == [
        f"verdict_json={result1['artifact_refs']['verdict_json']}",
        f"reason_code=spec_hash={revision1_hash[:12]}",
    ]
    evidence_msg = service.list_messages(sid)[-1]
    assert f"spec_hash={revision1_hash[:12]}" in evidence_msg.content
    assert adjust.task_id is not None and adjust.task_id in evidence_msg.content

    # ---- 5. one more revision switch (换 ETHUSDT) ----------------------------
    switch = service.send_message(sid, "换成ETHUSDT")
    assert switch.status == "submitted"
    assert switch.parent_revision_id == adjust.revision_id
    assert [(d.field, d.old, d.new) for d in switch.diff] == [("symbols", "BTCUSDT", "ETHUSDT")]
    result2 = _run_engine(service, state)

    # ---- 6. lineage chain correct -------------------------------------------
    revision2 = service.current_revision(sid)
    assert revision2.symbols == ["ETHUSDT"]
    assert revision2.params.volatility_multiplier == 2.0
    assert revision2.parent_revision_id == adjust.revision_id
    assert adjust.parent_revision_id == root.strategy_revision_id
    # Revision ids chain: child id = <parent_id>-<suffix of own content hash>.
    assert switch.revision_id == f"{adjust.revision_id}-" + switch.revision_id.split("-")[-1]
    detail = service.get_session(sid)
    assert detail.current_revision["symbols"] == ["ETHUSDT"]
    assert detail.current_revision["strategy_revision_id"] == switch.revision_id

    # ---- 7. the evidence path serves the verdict of the CURRENT revision ----
    evidence2 = service.send_message(sid, "为什么不如持有")
    assert switch.task_id is not None
    assert switch.task_id in service.list_messages(sid)[-1].content
    assert f"verdict_json={result2['artifact_refs']['verdict_json']}" in evidence2.verdict_refs
    assert result2["verdict"]["symbols"] == ["ETHUSDT"]

    # ---- 8. full message history --------------------------------------------
    roles = [m.role for m in detail.messages]
    statuses = [m.status for m in detail.messages if m.role == "assistant"]
    assert roles == ["user", "assistant"] * 3
    assert statuses == ["submitted", "answered", "submitted"]
    assert detail.messages[1].intent_kind == "adjust_param"
    assert detail.messages[3].intent_kind == "evidence_question"
    assert detail.messages[5].intent_kind == "switch_symbol"

    # ---- 9. budget reservations accumulated, nothing else consumed ----------
    usage = service.budget_ledger.round_usage(f"conv-{sid}")
    assert usage.backtests.reserved == 2.0
    assert usage.llm_calls.used == 0.0 and usage.tokens_round.used == 0.0
