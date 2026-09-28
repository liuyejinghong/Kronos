"""Unit tests for ConversationService (P14): revisions, tasks, budget, tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from kronos.conversation.service import (
    ConversationService,
    SessionNotFoundError,
    ToolAccessError,
)
from kronos.runtime.budget import BudgetExhausted, BudgetLedger, BudgetLimits, BudgetPlan
from kronos.runtime.tasks import TaskStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def svc(tmp_path: Path) -> ConversationService:
    service = ConversationService(tmp_path / "state")
    yield service
    service.close()


def _adjust(service: ConversationService, session_id: str, text: str) -> Any:
    return service.send_message(session_id, text)


def test_create_session_seeds_root_revision(svc: ConversationService) -> None:
    session = svc.create_session()

    revision = svc.current_revision(session.session_id)
    assert session.current_revision_id == revision.strategy_revision_id
    assert revision.parent_revision_id is None
    assert revision.symbols == ["BTCUSDT"]
    assert revision.signal_timeframe == "15m"


def test_unknown_session_raises_typed_error(svc: ConversationService) -> None:
    with pytest.raises(SessionNotFoundError):
        svc.send_message("missing", "你好")
    with pytest.raises(SessionNotFoundError):
        svc.get_session("missing")
    with pytest.raises(SessionNotFoundError):
        svc.mark_holdout_exposed("missing")


def test_adjust_creates_child_revision_diff_and_task(svc: ConversationService) -> None:
    session = svc.create_session()
    parent = svc.current_revision(session.session_id)

    result = svc.send_message(session.session_id, "把倍数改成 2.0")

    assert result.status == "submitted"
    assert result.parent_revision_id == parent.strategy_revision_id
    assert result.revision_id != result.parent_revision_id
    assert result.task_id is not None
    assert result.task_state == "queued"
    assert [(d.field, d.old, d.new) for d in result.diff] == [
        ("params.volatility_multiplier", "1", "2")
    ]
    child = svc.current_revision(session.session_id)
    assert child.strategy_revision_id == result.revision_id
    assert child.parent_revision_id == parent.strategy_revision_id
    assert child.params.volatility_multiplier == 2.0
    # task payload carries spec + session refs + budget binding
    payload = svc.task_store.get_payload(result.task_id)
    assert payload["session_id"] == session.session_id
    assert payload["spec_hash"] == child.spec_hash
    assert payload["budget_reservation_id"].startswith("eval-")
    assert payload["spec_content"]["params"]["volatility_multiplier"] == 2.0
    assert payload["snapshot_policy"] == "window_90_complete_utc_days"


def test_switch_symbol_creates_child_revision(svc: ConversationService) -> None:
    session = svc.create_session()
    parent = svc.current_revision(session.session_id)

    result = svc.send_message(session.session_id, "换成ETHUSDT")

    assert result.status == "submitted"
    child = svc.current_revision(session.session_id)
    assert child.symbols == ["ETHUSDT"]
    assert child.parent_revision_id == parent.strategy_revision_id
    assert result.diff[0].field == "symbols"
    assert result.diff[0].new == "ETHUSDT"


def test_switch_timeframe_creates_child_revision(svc: ConversationService) -> None:
    session = svc.create_session()

    result = svc.send_message(session.session_id, "改用 1h")

    assert result.status == "submitted"
    child = svc.current_revision(session.session_id)
    assert child.signal_timeframe == "1h"
    assert result.diff[0].field == "signal_timeframe"


def test_revision_chain_accumulates_lineage(svc: ConversationService) -> None:
    session = svc.create_session()
    first = svc.send_message(session.session_id, "倍数改成 2.0")
    second = svc.send_message(session.session_id, "ATR 改成 30")

    assert second.parent_revision_id == first.revision_id
    assert second.revision_id == f"{first.revision_id}-" + second.revision_id.split("-")[-1]


def test_idempotent_resubmit_reuses_same_task(svc: ConversationService) -> None:
    session = svc.create_session()
    first = svc.send_message(session.session_id, "倍数改成 2.0")

    detail = svc.get_session(session.session_id)
    tool_result = svc.invoke_tool(
        "evaluate_strategy",
        {"session_id": session.session_id, "spec": detail.current_revision},
    )

    assert tool_result["task_id"] == first.task_id


def test_clarification_then_value_merges_to_adjustment(svc: ConversationService) -> None:
    session = svc.create_session()

    bare = svc.send_message(session.session_id, "改成 2")
    assert bare.status == "clarification_needed"
    assert bare.clarification_question is not None
    assert bare.task_id is None

    named = svc.send_message(session.session_id, "倍数")
    assert named.status == "submitted"
    assert svc.current_revision(session.session_id).params.volatility_multiplier == 2.0


def test_clarification_creates_no_task(svc: ConversationService) -> None:
    session = svc.create_session()
    before = len(svc.task_store.list_tasks())

    result = svc.send_message(session.session_id, "更激进一点")

    assert result.status == "clarification_needed"
    assert len(svc.task_store.list_tasks()) == before


def test_out_of_scope_refusal_creates_no_task(svc: ConversationService) -> None:
    session = svc.create_session()
    before = len(svc.task_store.list_tasks())

    result = svc.send_message(session.session_id, "把实盘打开")

    assert result.status == "refused"
    assert result.task_id is None
    assert len(svc.task_store.list_tasks()) == before
    assert "实盘" in svc.list_messages(session.session_id)[-1].content


def test_evidence_question_reads_verdict_without_new_task(svc: ConversationService) -> None:
    session = svc.create_session()
    adjust = svc.send_message(session.session_id, "倍数改成 2.0")
    task_id = adjust.task_id
    assert task_id is not None
    before = len(svc.task_store.list_tasks())

    missing = svc.send_message(session.session_id, "为什么不如持有")
    assert missing.status == "answered"
    assert missing.verdict_refs == []
    assert missing.task_id is None

    claimed = svc.task_store.claim("worker-1", lease_ms=60_000)
    assert claimed.task_id == task_id
    svc.task_store.commit_result(
        task_id,
        "worker-1",
        claimed.fencing_token,
        "succeeded",
        result={
            "verdict": {
                "evidence_status": "limited",
                "disposition": "observe",
                "reason_codes": ["below_min_trades"],
            },
            "artifact_refs": {"ledger": "runs/r/execution.jsonl"},
        },
    )

    answered = svc.send_message(session.session_id, "为什么不如持有")
    assert answered.status == "answered"
    assert answered.task_id is None
    assert len(svc.task_store.list_tasks()) == before
    assert "reason_code=below_min_trades" in answered.verdict_refs
    assert "ledger=runs/r/execution.jsonl" in answered.verdict_refs


def test_ask_verdict_defaults_to_read_only_answer(svc: ConversationService) -> None:
    session = svc.create_session()
    before = len(svc.task_store.list_tasks())

    result = svc.send_message(session.session_id, "现在结论如何")

    assert result.status == "answered"
    assert result.task_id is None
    assert len(svc.task_store.list_tasks()) == before


def test_budget_exhaustion_blocks_submission(tmp_path: Path) -> None:
    state = tmp_path / "state2"
    tasks = TaskStore(state / "runtime.sqlite3")
    ledger = BudgetLedger(state / "budget.sqlite3", limits=BudgetLimits(backtests_per_round=0))
    service = ConversationService(state, task_store=tasks, budget_ledger=ledger)
    try:
        session = service.create_session()
        result = service.send_message(session.session_id, "倍数改成 2.0")

        assert result.status == "budget_exhausted"
        assert result.task_id is None
        assert result.diff  # the intended diff is still echoed
        assert len(tasks.list_tasks()) == 0
        # lineage did not advance: retrying after a budget raise works
        current = service.current_revision(session.session_id)
        assert current.params.volatility_multiplier == 1.0
    finally:
        service.close()


def test_budget_reservation_is_recorded_in_ledger(svc: ConversationService) -> None:
    session = svc.create_session()
    result = svc.send_message(session.session_id, "倍数改成 2.0")
    assert result.task_id is not None

    usage = svc.budget_ledger.round_usage(f"conv-{session.session_id}")
    assert usage.backtests.reserved == 1.0


def test_budget_exhausted_exception_type_is_exposed(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "b.sqlite3", limits=BudgetLimits(backtests_per_round=0))
    with pytest.raises(BudgetExhausted):
        ledger.reserve("r1", BudgetPlan(backtests=1), reservation_id="res-1")


def test_mark_holdout_exposed_counts_monotonically(svc: ConversationService) -> None:
    session = svc.create_session()
    assert svc.mark_holdout_exposed(session.session_id) == 1
    assert svc.mark_holdout_exposed(session.session_id) == 2
    detail = svc.get_session(session.session_id)
    assert detail.holdout_exposure_count == 2


def test_get_session_returns_message_history(svc: ConversationService) -> None:
    session = svc.create_session()
    svc.send_message(session.session_id, "你好")
    svc.send_message(session.session_id, "倍数改成 2.0")

    detail = svc.get_session(session.session_id)
    roles = [m.role for m in detail.messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert detail.messages[0].content == "你好"
    assert detail.messages[-1].status == "submitted"


# ------------------------------------------------------------------- tools


def test_tool_whitelist_rejects_unknown_names(svc: ConversationService) -> None:
    session = svc.create_session()
    with pytest.raises(ToolAccessError, match="whitelist"):
        svc.invoke_tool("run_shell", {"session_id": session.session_id, "cmd": "rm -rf /"})


def test_tool_ensure_data_submits_task_with_strict_validation(svc: ConversationService) -> None:
    session = svc.create_session()
    result = svc.invoke_tool("ensure_data", {"session_id": session.session_id, "symbol": "btcusdt"})
    assert result["symbol"] == "BTCUSDT"
    assert result["state"] == "queued"
    task = svc.task_store.get(result["task_id"])
    assert task.kind == "ensure_data"

    with pytest.raises(ToolAccessError):
        svc.invoke_tool("ensure_data", {"session_id": session.session_id, "symbol": "!!"})
    with pytest.raises(ToolAccessError):
        svc.invoke_tool(
            "ensure_data", {"session_id": session.session_id, "symbol": "BTCUSDT", "evil": 1}
        )
    with pytest.raises(ToolAccessError):
        svc.invoke_tool(
            "ensure_data",
            {"session_id": session.session_id, "symbol": "BTCUSDT", "timeframe": "4h"},
        )
    with pytest.raises(SessionNotFoundError):
        svc.invoke_tool("ensure_data", {"session_id": "missing", "symbol": "BTCUSDT"})


def test_tool_evaluate_strategy_validates_spec_strictly(svc: ConversationService) -> None:
    session = svc.create_session()
    bad_spec = {"template_version": "other_template"}
    with pytest.raises(ToolAccessError) as excinfo:
        svc.invoke_tool(
            "evaluate_strategy",
            {"session_id": session.session_id, "spec": bad_spec, "extra": 1},
        )
    assert "unknown payload keys" in str(excinfo.value)


def test_tool_compare_runs_and_read_evidence_are_read_only(svc: ConversationService) -> None:
    session = svc.create_session()
    adjust = svc.send_message(session.session_id, "倍数改成 2.0")
    task_id = adjust.task_id
    assert task_id is not None

    read = svc.invoke_tool("read_evidence", {"run_id": task_id})
    assert read["state"] == "queued"
    assert read["result"] is None

    compare = svc.invoke_tool("compare_runs", {"run_id_a": task_id, "run_id_b": task_id})
    assert compare["a"]["task_id"] == task_id

    from kronos.runtime.tasks import TaskNotFoundError

    with pytest.raises(TaskNotFoundError):
        svc.invoke_tool("read_evidence", {"run_id": "missing-run"})


# --------------------------------------------------------- sqlite persistence


def test_sessions_persist_across_service_restart(tmp_path: Path) -> None:
    state = tmp_path / "state3"
    service = ConversationService(state)
    session = service.create_session()
    result = service.send_message(session.session_id, "倍数改成 2.0")
    service.close()

    reopened = ConversationService(state)
    try:
        detail = reopened.get_session(session.session_id)
        assert detail.current_revision["params"]["volatility_multiplier"] == 2.0
        assert [m.role for m in detail.messages] == ["user", "assistant"]
        assert detail.messages[1].status == "submitted"
        task = reopened.task_store.get(result.task_id)
        assert task.state == "queued"
    finally:
        reopened.close()
