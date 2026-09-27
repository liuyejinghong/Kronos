"""Tests for the Agent Memory Control file-backed harness."""
# ruff: noqa: RUF001

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from kronos.agent.memory_control import (
    build_handoff_pack,
    build_memory_dashboard,
    run_drift_check,
)
from kronos.agent.memory_control.readers import (
    build_current_state,
    extract_decisions,
    load_memory_files,
)
from kronos.agent.memory_control.redaction import redact_text


def test_memory_dashboard_reads_first_screen_state_from_repo_docs(tmp_path: Path) -> None:
    root = _write_memory_repo(tmp_path)

    dashboard = build_memory_dashboard(root)

    assert dashboard.state.current_version == "0.4.10"
    assert dashboard.state.next_version == "0.4.11"
    assert "Agent 记忆与交接控制台" in dashboard.state.current_acceptance_target_zh
    assert "产品 review" in dashboard.state.next_action_zh
    assert "还没有成功证据" not in dashboard.state.latest_successful_run_zh
    assert "20260509T134805Z-paper" in dashboard.state.latest_successful_run_zh
    assert dashboard.decisions[0].source_paths == ["DECISIONS.md"]
    assert dashboard.handoff.prompt_md.startswith("# Kronos Agent Handoff")


def test_drift_check_flags_missing_required_file(tmp_path: Path) -> None:
    root = _write_memory_repo(tmp_path)
    (root / "MEMORY.md").unlink()

    result = run_drift_check(root)

    assert result.status == "blocking"
    missing = next(item for item in result.items if item.check_id == "required-file:MEMORY.md")
    assert missing.severity == "blocking"
    assert "文件缺失" in missing.detail_zh


def test_drift_check_flags_missing_release_index(tmp_path: Path) -> None:
    root = _write_memory_repo(tmp_path)
    (root / "docs" / "ROADMAP.md").write_text("路线图暂未索引 v0.4.10。\n", encoding="utf-8")

    result = run_drift_check(root)

    index_item = next(
        item for item in result.items if item.check_id == "v0410-index:docs/ROADMAP.md"
    )
    assert index_item.severity == "warning"
    assert "缺少索引" in index_item.detail_zh


def test_secret_like_values_are_redacted_in_handoff(tmp_path: Path) -> None:
    root = _write_memory_repo(tmp_path)
    secret = "api_key=Abcd1234Abcd1234Abcd1234Abcd1234"
    (root / "MEMORY.md").write_text(
        (root / "MEMORY.md").read_text(encoding="utf-8") + f"\n- {secret}\n",
        encoding="utf-8",
    )
    files = load_memory_files(root)
    state = build_current_state(files)
    decisions = extract_decisions(files)

    handoff = build_handoff_pack(root, state=state, decisions=decisions, lessons=[])
    check = run_drift_check(root)

    assert "Abcd1234Abcd1234Abcd1234Abcd1234" not in handoff.prompt_md
    assert "[REDACTED]" in redact_text(secret)
    assert any(item.check_id == "secret-scan:MEMORY.md" and item.severity == "warning" for item in check.items)



_MEMORY_FILES = {
    "MEMORY.md": """# Kronos Persistent Memory

## Boot Protocol

- Read AGENTS.md first, then this file.

## Current Kronos State

- v0.4.10 acceptance follows the real testnet run `20260509T134805Z-paper`.

## Durable Operating Lessons

- Literal UX evidence matters.

## Memory Write Triggers

- Update after meaningful state changes.

## Verification Loop

- Run the relevant local check before claiming completion.
""",
    "DECISIONS.md": """# Kronos Decision Log

## D-20260509-006 - Plan Agent Memory Control for v0.4.10 after testnet Web status

Status: accepted

Decision: Agent Memory Control ships after v0.4.9, read-only first.

Rejected: auto-overwrite long-term memory | unsafe without human gates.
""",
    "TODO.md": """# Kronos TODO

> 更新：2026-05-11 | 版本：0.4.10 | 下一版本：0.4.11
> 状态：`done` 已完成 · `todo` 待办 · `wip` 进行中

## v0.4.10 已完成

> 产品目标：Agent 记忆与交接控制台。

| # | 事项 | 索引 |
|---|------|------|
| 90 | `done` 记忆控制台 | `docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md` + `openspec/changes/p4-agent-memory-control` |
""",
    "docs/PROJECT_STATUS.md": """# Kronos Project Status

当前版本：0.4.10 | 下一版本：0.4.11

v0.4.10 已完成 **Agent 记忆与交接控制台**。上一条真实 testnet E2E 为 `20260509T134805Z-paper`。

- v0.4.10 版本需求：`docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md`
- v0.4.10 OpenSpec：`openspec/changes/p4-agent-memory-control`
""",
    "docs/ROADMAP.md": """# Kronos Roadmap

更新时间：2026-05-11

v0.4.10 Agent 记忆与交接控制台见 `docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md` 和 `openspec/changes/p4-agent-memory-control`。
""",
    "docs/PRODUCT_CONTROL_PANEL.md": "# 产品控制面板\n\nv0.4.10 记忆控制台只读优先。\n",
    "docs/agent-harness/PROGRESS_LOG.md": """# Progress Log

## Remaining risks

- none recorded
""",
}


def _write_memory_repo(root):
    """Write a self-contained synthetic memory repo (CI has no local-only docs)."""
    for relative_path, content in _MEMORY_FILES.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root
