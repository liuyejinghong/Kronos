# ruff: noqa: RUF001, RUF002 -- Chinese questions and docstring use fullwidth punctuation.
"""Unit tests for the whitelisted LLM context builder (P19 security-boundary).

Spec: 密钥与上下文外发必须受限 — LLM 上下文只含策略摘要与必要证据字段；
绝无密钥、全量原始数据或开发记忆。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from kronos.conversation.llm_client import GLMChatMessage
from kronos.conversation.llm_context import (
    MAX_QUESTION_CHARS,
    audit_context,
    build_context,
)
from kronos.strategy.spec import StrategySpec


def _verdict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "evidence_status": "valid",
        "disposition": "observe",
        "reason_codes": ["few_trades"],
        "metrics": {
            "win_rate": {"value": 0.55, "reason": "ok"},
            "profit_factor": {"value": None, "reason": "zero_trades"},
            "net_return": {"value": 0.031, "reason": "ok"},
        },
        "artifact_refs": {
            "ledger": "/Users/ethan/runs/r1/ExecutionLedger.json",
            "evidence": "state\\deep\\EvidenceBundle.json",
        },
        # Fields that must NEVER leak into the context:
        "run_id": "run-123",
        "generated_at": 1760000000000,
        "internal_notes": "owner prefers conservative sizing",
    }
    base.update(overrides)
    return base


def _user_payload(messages: list[GLMChatMessage]) -> dict[str, Any]:
    assert [m.role for m in messages] == ["system", "user"]
    return json.loads(messages[1].content)


def test_build_context_contains_only_whitelisted_fields() -> None:
    spec = StrategySpec.model_validate({})

    messages = build_context(spec=spec, verdict=_verdict(), question="现在结论如何？")
    payload = _user_payload(messages)

    assert set(payload) == {"strategy", "verdict", "artifact_basenames", "question"}
    assert set(payload["strategy"]) == {
        "variant_label_zh",
        "symbols",
        "signal_timeframe",
        "params",
        "strategy_revision_id",
    }
    assert set(payload["strategy"]["params"]) == {"atr_period", "volatility_multiplier"}
    assert isinstance(payload["strategy"]["params"]["atr_period"], int)
    assert isinstance(payload["strategy"]["params"]["volatility_multiplier"], float)
    assert set(payload["verdict"]) == {
        "evidence_status",
        "disposition",
        "reason_codes",
        "metrics",
    }
    assert payload["verdict"]["evidence_status"] == "valid"
    assert payload["verdict"]["disposition"] == "observe"
    assert payload["verdict"]["reason_codes"] == ["few_trades"]
    assert payload["question"] == "现在结论如何？"
    # Fields outside the whitelist (run_id / generated_at / internal_notes)
    # and metric reason strings never appear anywhere in the messages.
    serialized = "\n".join(message.content for message in messages)
    for banned in ("run_id", "generated_at", "internal_notes", "zero_trades", "owner prefers"):
        assert banned not in serialized
    assert audit_context(messages) == []


def test_build_context_drops_secrets_and_raw_data_from_verdict() -> None:
    poisoned = _verdict(
        api_key="sk-live-abcdef123456",
        metrics={
            "win_rate": {"value": 0.9, "reason": "ok"},
            "junk_string": {"value": "not-a-number", "reason": "x"},
        },
        bars=[[1, 2, 3, 4]] * 1000,
    )

    messages = build_context(
        spec=StrategySpec.model_validate({}), verdict=poisoned, question="解读一下"
    )
    serialized = "\n".join(message.content for message in messages)

    assert "sk-live" not in serialized
    assert "api_key" not in serialized
    assert "bars" not in serialized
    assert set(_user_payload(messages)["verdict"]["metrics"]) == {"win_rate"}
    assert audit_context(messages) == []


def test_build_context_reduces_artifact_refs_to_basenames() -> None:
    spec = StrategySpec.model_validate({})

    messages = build_context(
        spec=spec,
        verdict=_verdict(),
        question="依据是什么？",
        artifact_refs={
            "ledger": "/home/user/reports/run-1/ExecutionLedger.json",
            "evidence": "C:\\Users\\ethan\\state\\EvidenceBundle.json",
            "manifest": "snapshots/manifest-2026.json",
        },
    )
    payload = _user_payload(messages)

    assert payload["artifact_basenames"] == [
        "ExecutionLedger.json",
        "EvidenceBundle.json",
        "manifest-2026.json",
    ]
    serialized = "\n".join(message.content for message in messages)
    for banned in ("/home", "C:", "snapshots/", "\\\\"):
        assert banned not in serialized
    assert audit_context(messages) == []


def test_build_context_without_verdict_keeps_null() -> None:
    spec = StrategySpec.model_validate({})

    messages = build_context(spec=spec, verdict=None, question="有什么结论吗？")
    payload = _user_payload(messages)

    assert payload["verdict"] is None
    assert payload["artifact_basenames"] == []
    assert audit_context(messages) == []


def test_build_context_truncates_long_question() -> None:
    spec = StrategySpec.model_validate({})

    messages = build_context(spec=spec, verdict=None, question="问" * 1_000_000)
    payload = _user_payload(messages)

    assert len(payload["question"]) == MAX_QUESTION_CHARS


def test_build_context_is_deterministic() -> None:
    spec = StrategySpec.model_validate({})

    first = build_context(spec=spec, verdict=_verdict(), question="结论？")
    second = build_context(spec=spec, verdict=_verdict(), question="结论？")

    assert [(m.role, m.content) for m in first] == [(m.role, m.content) for m in second]


@pytest.mark.parametrize("question", ["", "   "])
def test_build_context_rejects_empty_question(question: str) -> None:
    spec = StrategySpec.model_validate({})

    with pytest.raises(ValueError, match="question"):
        build_context(spec=spec, verdict=None, question=question)


# ------------------------------------------------------------------- audit


def _user(content: str) -> GLMChatMessage:
    return GLMChatMessage(role="user", content=content)


def test_audit_flags_provider_key_shapes() -> None:
    violations = audit_context([_user('{"note": "sk-a1b2c3d4e5f6"}')])

    assert len(violations) == 1
    assert "secret_like_token" in violations[0]
    assert "messages[0] (user)" in violations[0]


def test_audit_flags_api_key_references() -> None:
    assert audit_context([_user("api_key = abc123")]) != []
    assert audit_context([_user("Authorization: Bearer eyJhbGciOi")]) != []
    assert audit_context([_user("export KRONOS_GLM_API_KEY=x")]) != []


def test_audit_flags_file_paths_beyond_basenames() -> None:
    for path in (
        "/Users/ethan/reports/x.json",
        "/tmp/secret.txt",
        "state/conversations.sqlite3",
        "reports/agent_runtime/r1",
        "C:\\Users\\ethan\\x.json",
    ):
        violations = audit_context([_user(path)])
        assert violations, path
        assert "file_path" in violations[0]


def test_audit_flags_dev_memory_references() -> None:
    for text in ("see MEMORY.md for context", "DECISIONS.md said", "PROGRESS_LOG entry"):
        violations = audit_context([_user(text)])
        assert violations, text
        assert "dev_memory_reference" in violations[0]


def test_audit_flags_bulk_bar_data() -> None:
    header_row = _user("timestamp,open,high,low,close\n")
    assert audit_context([header_row]) != []

    bulk = _user(", ".join(f"{index}.5" for index in range(500)))
    violations = audit_context([bulk])
    assert violations
    assert "full_bar_data_bulk" in violations[0]


def test_audit_passes_built_context_and_plain_questions() -> None:
    spec = StrategySpec.model_validate({})

    clean = build_context(spec=spec, verdict=_verdict(), question="倍数改成 2.0 会怎样？")
    assert audit_context(clean) == []
    assert audit_context([_user("普通中文问题，不含路径或密钥。")]) == []
