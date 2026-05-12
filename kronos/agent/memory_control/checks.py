"""Rule-based checks for Agent memory drift and safety."""
# ruff: noqa: RUF001

from __future__ import annotations

import re
from pathlib import Path

from kronos.agent.memory_control.models import (
    MemoryCheckItem,
    MemoryCheckSeverity,
    MemoryCheckSummary,
)
from kronos.agent.memory_control.redaction import has_secret_like_text

_REQUIRED_FILES = [
    "MEMORY.md",
    "DECISIONS.md",
    "docs/agent-harness/PROGRESS_LOG.md",
    "TODO.md",
    "docs/PROJECT_STATUS.md",
    "docs/ROADMAP.md",
    "docs/PRODUCT_CONTROL_PANEL.md",
]
_REQUIRED_MEMORY_MARKERS = ["Boot Protocol", "Memory Write Triggers", "Verification Loop"]
_REQUIRED_DECISION_MARKERS = ["D-20260509-006", "Agent Memory Control"]
_RELEASE_DOC = "docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md"
_OPENSPEC_ROOT = "openspec/changes/p4-agent-memory-control"
_INDEX_FILES = ["TODO.md", "docs/PROJECT_STATUS.md", "docs/ROADMAP.md"]
_VERSION_RE = re.compile(r"当前版本：(?P<current>[\w.]+)\s*\|\s*下一版本：(?P<next>[\w.]+)")
_TODO_VERSION_RE = re.compile(r"版本：(?P<current>[\w.]+)\s*\|\s*下一版本：(?P<next>[\w.]+)")


def run_drift_check(project_root: str | Path) -> MemoryCheckSummary:
    """Run explicit drift and safety checks over repository memory files."""
    root = Path(project_root).resolve()
    items: list[MemoryCheckItem] = []
    items.extend(_required_file_checks(root))
    items.append(_version_consistency_check(root))
    items.extend(_marker_checks(root))
    items.extend(_index_checks(root))
    items.extend(_secret_checks(root))
    return _summary(items)


def _required_file_checks(root: Path) -> list[MemoryCheckItem]:
    items: list[MemoryCheckItem] = []
    for relative_path in _REQUIRED_FILES:
        exists = (root / relative_path).is_file()
        items.append(
            MemoryCheckItem(
                check_id=f"required-file:{relative_path}",
                severity=MemoryCheckSeverity.PASSED if exists else MemoryCheckSeverity.BLOCKING,
                title_zh=f"必备文件：{relative_path}",
                detail_zh="文件存在。" if exists else "文件缺失，不能伪造该来源的状态。",
                source_paths=[relative_path],
                suggestion_zh=None if exists else f"恢复或创建 {relative_path}。",
            )
        )
    return items


def _version_consistency_check(root: Path) -> MemoryCheckItem:
    sources: dict[str, tuple[str, str]] = {}
    for relative_path, pattern in {
        "TODO.md": _TODO_VERSION_RE,
        "docs/PROJECT_STATUS.md": _VERSION_RE,
    }.items():
        text = _read(root, relative_path)
        match = pattern.search(text)
        if match:
            sources[relative_path] = (match.group("current"), match.group("next"))

    inferred_version = next(iter(sources.values()), None)
    if inferred_version is None:
        version_file = root / "VERSION"
        if version_file.is_file():
            inferred_version = (version_file.read_text(encoding="utf-8").strip(), "unknown")

    roadmap_text = _read(root, "docs/ROADMAP.md")
    if inferred_version is not None and f"v{inferred_version[0]}" in roadmap_text:
        sources["docs/ROADMAP.md"] = inferred_version

    unique_versions = set(sources.values())
    if not sources:
        return MemoryCheckItem(
            check_id="version-consistency",
            severity=MemoryCheckSeverity.WARNING,
            title_zh="版本字段一致性",
            detail_zh="没有读到可比较的当前版本 / 下一版本字段。",
            source_paths=["TODO.md", "docs/PROJECT_STATUS.md", "docs/ROADMAP.md"],
            suggestion_zh="在 TODO 和 PROJECT_STATUS 顶部保留当前版本与下一版本字段。",
        )
    if len(unique_versions) == 1:
        current, next_version = next(iter(unique_versions))
        return MemoryCheckItem(
            check_id="version-consistency",
            severity=MemoryCheckSeverity.PASSED,
            title_zh="版本字段一致性",
            detail_zh=f"当前版本 {current}，下一版本 {next_version}。",
            source_paths=sorted(sources),
        )
    return MemoryCheckItem(
        check_id="version-consistency",
        severity=MemoryCheckSeverity.WARNING,
        title_zh="版本字段一致性",
        detail_zh=f"不同文件中的版本字段不一致：{sources}。",
        source_paths=sorted(sources),
        suggestion_zh="统一 TODO、PROJECT_STATUS、ROADMAP 中的当前版本和下一版本。",
    )


def _marker_checks(root: Path) -> list[MemoryCheckItem]:
    checks: list[MemoryCheckItem] = []
    memory_text = _read(root, "MEMORY.md")
    missing_memory_markers = [
        marker for marker in _REQUIRED_MEMORY_MARKERS if marker not in memory_text
    ]
    checks.append(
        MemoryCheckItem(
            check_id="memory-required-markers",
            severity=(
                MemoryCheckSeverity.PASSED
                if not missing_memory_markers
                else MemoryCheckSeverity.BLOCKING
            ),
            title_zh="MEMORY.md 必备段落",
            detail_zh=(
                "Boot Protocol、Memory Write Triggers、Verification Loop 均存在。"
                if not missing_memory_markers
                else f"缺少段落：{', '.join(missing_memory_markers)}。"
            ),
            source_paths=["MEMORY.md"],
            suggestion_zh=None if not missing_memory_markers else "补齐 MEMORY.md 的必备记忆协议段落。",
        )
    )

    decisions_text = _read(root, "DECISIONS.md")
    missing_decision_markers = [
        marker for marker in _REQUIRED_DECISION_MARKERS if marker not in decisions_text
    ]
    checks.append(
        MemoryCheckItem(
            check_id="decision-harness-markers",
            severity=(
                MemoryCheckSeverity.PASSED
                if not missing_decision_markers
                else MemoryCheckSeverity.WARNING
            ),
            title_zh="Agent Harness 决策记录",
            detail_zh=(
                "DECISIONS.md 已记录 v0.4.10 Agent Memory Control 决策。"
                if not missing_decision_markers
                else f"缺少决策标记：{', '.join(missing_decision_markers)}。"
            ),
            source_paths=["DECISIONS.md"],
            suggestion_zh=(
                None
                if not missing_decision_markers
                else "补充 Agent Memory Control 的 durable decision。"
            ),
        )
    )
    return checks


def _index_checks(root: Path) -> list[MemoryCheckItem]:
    items: list[MemoryCheckItem] = []
    for relative_path in _INDEX_FILES:
        text = _read(root, relative_path)
        missing = [
            token
            for token in (_RELEASE_DOC, _OPENSPEC_ROOT)
            if token not in text
        ]
        items.append(
            MemoryCheckItem(
                check_id=f"v0410-index:{relative_path}",
                severity=MemoryCheckSeverity.PASSED if not missing else MemoryCheckSeverity.WARNING,
                title_zh=f"v0.4.10 索引：{relative_path}",
                detail_zh=(
                    "已索引 release doc 和 OpenSpec。"
                    if not missing
                    else f"缺少索引：{', '.join(missing)}。"
                ),
                source_paths=[relative_path, _RELEASE_DOC, _OPENSPEC_ROOT],
                suggestion_zh=None if not missing else f"在 {relative_path} 中补齐 v0.4.10 索引。",
            )
        )
    return items


def _secret_checks(root: Path) -> list[MemoryCheckItem]:
    items: list[MemoryCheckItem] = []
    for relative_path in _REQUIRED_FILES:
        text = _read(root, relative_path)
        has_secret = has_secret_like_text(text)
        items.append(
            MemoryCheckItem(
                check_id=f"secret-scan:{relative_path}",
                severity=MemoryCheckSeverity.WARNING if has_secret else MemoryCheckSeverity.PASSED,
                title_zh=f"疑似 secret 扫描：{relative_path}",
                detail_zh=(
                    "发现疑似 API Key / Secret / token，请人工复核；UI 不会展示完整值。"
                    if has_secret
                    else "未发现疑似 secret。"
                ),
                source_paths=[relative_path],
                suggestion_zh=(
                    f"检查 {relative_path}，确认是否需要移除或脱敏。"
                    if has_secret
                    else None
                ),
            )
        )
    return items


def _summary(items: list[MemoryCheckItem]) -> MemoryCheckSummary:
    passed_count = sum(item.severity == MemoryCheckSeverity.PASSED for item in items)
    warning_count = sum(item.severity == MemoryCheckSeverity.WARNING for item in items)
    blocking_count = sum(item.severity == MemoryCheckSeverity.BLOCKING for item in items)
    if blocking_count:
        status = MemoryCheckSeverity.BLOCKING
    elif warning_count:
        status = MemoryCheckSeverity.WARNING
    else:
        status = MemoryCheckSeverity.PASSED
    return MemoryCheckSummary(
        status=status,
        passed_count=passed_count,
        warning_count=warning_count,
        blocking_count=blocking_count,
        items=items,
    )


def _read(root: Path, relative_path: str) -> str:
    path = root / relative_path
    return path.read_text(encoding="utf-8") if path.is_file() else ""
