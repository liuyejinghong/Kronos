"""Tests for the Agent Memory Control file-backed harness."""

from __future__ import annotations

import shutil
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


def _write_memory_repo(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[3]
    files = [
        "MEMORY.md",
        "DECISIONS.md",
        "TODO.md",
        "docs/PROJECT_STATUS.md",
        "docs/ROADMAP.md",
        "docs/PRODUCT_CONTROL_PANEL.md",
        "docs/agent-harness/PROGRESS_LOG.md",
    ]
    for relative_path in files:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative_path, target)
    return tmp_path
