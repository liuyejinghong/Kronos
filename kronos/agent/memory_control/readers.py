"""Read repository memory files and build PM-facing summaries."""
# ruff: noqa: RUF001

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kronos.agent.memory_control.checks import run_drift_check
from kronos.agent.memory_control.handoff import build_handoff_pack
from kronos.agent.memory_control.models import (
    AgentMemoryDashboard,
    AgentMemoryState,
    MemorySourceRef,
    MemorySummaryItem,
)
from kronos.agent.memory_control.redaction import redact_text

REQUIRED_SOURCE_LABELS = {
    "MEMORY.md": "长期项目记忆",
    "DECISIONS.md": "决策日志",
    "docs/agent-harness/PROGRESS_LOG.md": "Agent Harness 进度",
    "TODO.md": "当前待办",
    "docs/PROJECT_STATUS.md": "项目状态",
    "docs/ROADMAP.md": "路线图",
    "docs/PRODUCT_CONTROL_PANEL.md": "产品控制面板",
}

_TODO_VERSION_RE = re.compile(r"版本：(?P<current>[\w.]+)\s*\|\s*下一版本：(?P<next>[\w.]+)")
_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_DECISION_RE = re.compile(
    r"^##\s+(?P<id>D-\d{8}-\d{3})\s+-\s+(?P<title>.+?)\n(?P<body>.*?)(?=^##\s+D-\d{8}-\d{3}\s+-|\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class MemoryFileSet:
    """Loaded repository files keyed by relative path."""

    root: Path
    contents: dict[str, str | None]

    def text(self, relative_path: str) -> str:
        return self.contents.get(relative_path) or ""

    def exists(self, relative_path: str) -> bool:
        return self.contents.get(relative_path) is not None


def build_memory_dashboard(project_root: str | Path) -> AgentMemoryDashboard:
    """Build the full Agent Memory Control payload from repository files."""
    root = Path(project_root).resolve()
    files = load_memory_files(root)
    state = build_current_state(files)
    decisions = extract_decisions(files)
    lessons = extract_lessons(files)
    check = run_drift_check(root)
    handoff = build_handoff_pack(root, state=state, decisions=decisions, lessons=lessons)
    sources = [
        MemorySourceRef(path=path, label_zh=label, exists=files.exists(path))
        for path, label in REQUIRED_SOURCE_LABELS.items()
    ]
    return AgentMemoryDashboard(
        state=state,
        decisions=decisions,
        lessons=lessons,
        sources=sources,
        handoff=handoff,
        check=check,
    )


def load_memory_files(project_root: Path) -> MemoryFileSet:
    """Load the canonical memory and product-control files."""
    contents: dict[str, str | None] = {}
    for relative_path in REQUIRED_SOURCE_LABELS:
        path = project_root / relative_path
        contents[relative_path] = path.read_text(encoding="utf-8") if path.is_file() else None
    return MemoryFileSet(root=project_root, contents=contents)


def build_current_state(files: MemoryFileSet) -> AgentMemoryState:
    """Extract the dashboard first-screen state."""
    current_version, next_version = _extract_versions(files)
    memory_text = files.text("MEMORY.md")
    project_status = files.text("docs/PROJECT_STATUS.md")
    todo = files.text("TODO.md")

    return AgentMemoryState(
        current_version=current_version,
        next_version=next_version,
        current_acceptance_target_zh=_current_acceptance_target(project_status),
        latest_successful_run_zh=_latest_successful_run(memory_text, project_status),
        product_boundary_zh=_first_matching_sentence(
            project_status,
            "当前产品边界",
            fallback=_first_matching_bullet(
                memory_text,
                "The current product boundary",
                fallback="研究报告、Agent 复盘、策略草案、只读观察计划和 Binance testnet 模拟盘仍是当前边界；主网实盘不在当前范围。",
            ),
        ),
        highest_priority_zh=_extract_v0410_goal(todo),
        next_action_zh=_next_action(current_version, next_version, project_status),
        source_paths=[
            "MEMORY.md",
            "TODO.md",
            "docs/PROJECT_STATUS.md",
            "docs/ROADMAP.md",
            "docs/PRODUCT_CONTROL_PANEL.md",
        ],
    )


def extract_decisions(files: MemoryFileSet, *, limit: int = 5) -> list[MemorySummaryItem]:
    """Extract recent decisions and rejected alternatives from DECISIONS.md."""
    decisions_text = files.text("DECISIONS.md")
    items: list[MemorySummaryItem] = []
    for match in _DECISION_RE.finditer(decisions_text):
        raw_title = match.group("title").strip()
        title = _decision_title_zh(raw_title)
        body = match.group("body")
        decision = _field_text(body, "Decision")
        rejected = _first_line_with_prefix(body, "Rejected:")
        body_zh = _decision_body_zh(raw_title, decision=decision, rejected=rejected, body=body)
        items.append(
            MemorySummaryItem(
                title_zh=title,
                body_zh=body_zh,
                source_paths=["DECISIONS.md"],
            )
        )
        if len(items) >= limit:
            break
    if items:
        return items
    return [
        MemorySummaryItem(
            title_zh="未读取到结构化决策",
            body_zh="DECISIONS.md 缺少可解析的 D-YYYYMMDD-NNN 决策段落。",
            source_paths=["DECISIONS.md"],
        )
    ]


def extract_lessons(files: MemoryFileSet, *, limit: int = 5) -> list[MemorySummaryItem]:
    """Extract recent durable lessons from memory and progress docs."""
    memory_text = files.text("MEMORY.md")
    progress_text = files.text("docs/agent-harness/PROGRESS_LOG.md")
    lessons: list[MemorySummaryItem] = []

    for line in _section_bullets(memory_text, "Durable Operating Lessons"):
        lessons.append(
            MemorySummaryItem(
                title_zh="长期操作教训",
                body_zh=redact_text(line),
                source_paths=["MEMORY.md"],
            )
        )
        if len(lessons) >= limit:
            return lessons

    for line in _section_bullets(progress_text, "Remaining risks"):
        lessons.append(
            MemorySummaryItem(
                title_zh="近期剩余风险",
                body_zh=redact_text(line),
                source_paths=["docs/agent-harness/PROGRESS_LOG.md"],
            )
        )
        if len(lessons) >= limit:
            return lessons

    return lessons


def _extract_versions(files: MemoryFileSet) -> tuple[str, str]:
    todo = files.text("TODO.md")
    match = _TODO_VERSION_RE.search(todo)
    if match:
        return match.group("current"), match.group("next")

    version_file = files.root / "VERSION"
    current = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "unknown"
    next_version = "0.4.10" if current == "0.4.9" else "unknown"
    return current, next_version


def _extract_v0410_goal(todo: str) -> str:
    index = todo.find("## v0.4.10")
    if index < 0:
        return "v0.4.10 Agent 记忆与交接控制台。"
    excerpt = todo[index : index + 800]
    for line in excerpt.splitlines():
        stripped = line.strip()
        if stripped.startswith("> 产品目标："):
            return redact_text(stripped.removeprefix("> 产品目标：").strip())
    return "v0.4.10 Agent 记忆与交接控制台。"


def _current_acceptance_target(project_status: str) -> str:
    if "v0.4.10 已完成" in project_status:
        return "v0.4.10 Agent 记忆与交接控制台：只读展示状态、决策、教训、交接包和漂移检查。"
    return _first_matching_sentence(
        project_status,
        "v0.4.10 已规划为",
        fallback="v0.4.10 Agent 记忆与交接控制台：把持久化 Agent Harness 产品化。",
    )


def _latest_successful_run(memory_text: str, project_status: str) -> str:
    if "v0.4.10 已完成" in project_status and "20260509T134805Z-paper" in project_status:
        return (
            "v0.4.10 多画像模拟用户验收已通过，记录在 "
            "`docs/KRONOS_V0410_PERSONA_ACCEPTANCE_20260511.md`；上一条真实 testnet "
            "E2E 为 `20260509T134805Z-paper`，ETHUSDT BUY 0.01，order id "
            "`8693595272`，状态 `FILLED`。"
        )
    for text in (project_status, memory_text):
        sentence = _first_matching_sentence(text, "20260509T134805Z-paper", fallback="")
        if sentence:
            return redact_text(sentence)
    return "最新成功验收记录来自 v0.4.9 多画像模拟用户验收和 testnet run `20260509T134805Z-paper`。"


def _next_action(current_version: str, next_version: str, project_status: str) -> str:
    if current_version == "0.4.10" and next_version == "0.4.11":
        return (
            "产品 review v0.4.10 首屏、交接包和漂移检查；通过后规划 v0.4.11 "
            "失败记忆约束。"
        )
    if "当前推荐顺序" in project_status:
        sentence = _first_matching_sentence(project_status, "规划 v", fallback="")
        if sentence:
            return sentence
    return "先按当前版本文档完成产品 review，再进入下一版本规划。"


def _first_matching_sentence(text: str, needle: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        if needle in stripped:
            return redact_text(stripped)
    return fallback


def _first_matching_bullet(text: str, needle: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and needle in stripped:
            return redact_text(stripped.removeprefix("- ").strip())
    return fallback


def _field_text(body: str, field: str) -> str | None:
    prefix = f"{field}:"
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        first = line.removeprefix(prefix).strip()
        continuation: list[str] = [first] if first else []
        for follow in lines[index + 1 :]:
            if re.match(r"^[A-Z][A-Za-z-]*:", follow) or follow.startswith("## "):
                break
            if follow.strip():
                continuation.append(follow.strip())
        return " ".join(continuation).strip()
    return None


def _decision_title_zh(title: str) -> str:
    known_titles = {
        "Treat v0.4.9 acceptance as multi-persona, not single-run only": (
            "v0.4.9 验收必须按多画像流程，不只看单次 testnet run"
        ),
        "Complete v0.4.9 with a real testnet E2E acceptance run": (
            "v0.4.9 必须同时完成 Web 可见性和真实 testnet E2E"
        ),
        "Complete v0.4.9 as read-only Web paper status": (
            "v0.4.9 Web paper 状态保持只读展示"
        ),
        "Require release docs and OpenSpec before every version": (
            "每个版本开工前必须先有 release doc 和 OpenSpec"
        ),
        "Plan Agent Memory Control for v0.4.10 after testnet Web status": (
            "v0.4.10 在 testnet Web 状态之后产品化 Agent 记忆"
        ),
        "Do not store secrets or raw transcripts in memory": (
            "长期记忆不得保存 secrets 或原始长 transcript"
        ),
        "Do not add a runtime OpenHarness or Harness-Mem dependency yet": (
            "暂不引入 OpenHarness / Harness-Mem runtime 依赖"
        ),
        "Treat existing Kronos control docs as product truth": (
            "现有 Kronos 控制文档仍是产品事实源"
        ),
    }
    return known_titles.get(title, redact_text(title))


def _decision_body_zh(
    title: str,
    *,
    decision: str | None,
    rejected: str | None,
    body: str,
) -> str:
    known_bodies = {
        "Treat v0.4.9 acceptance as multi-persona, not single-run only": (
            "v0.4.9 的产品验收等于真实 testnet run 加多画像模拟用户检查；单次成功订单不足以代表完整产品验收。"
        ),
        "Complete v0.4.9 with a real testnet E2E acceptance run": (
            "v0.4.9 只有在 Web paper 状态可见和真实 Binance testnet E2E 都通过后才算完成。"
        ),
        "Complete v0.4.9 as read-only Web paper status": (
            "Web 只读取 paper 状态、订单、成交、错误和报告，不提供绕过 preflight 的下单入口。"
        ),
        "Require release docs and OpenSpec before every version": (
            "每个版本都要先有 release doc、OpenSpec proposal/design/tasks/spec 和主索引，再开始正常开发。"
        ),
        "Plan Agent Memory Control for v0.4.10 after testnet Web status": (
            "Agent Memory Control 排在 v0.4.9 之后，首版必须只读、带来源、脱敏，并只给建议式更新。"
        ),
    }
    if title in known_bodies:
        return known_bodies[title]
    parts = [decision] if decision else []
    if rejected:
        parts.append(rejected)
    return redact_text(" ".join(parts) or _compact_body(body))


def _first_line_with_prefix(body: str, prefix: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped
    return None


def _compact_body(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("Status:", "Context:", "Consequences:")):
            return stripped
    return "暂无可读摘要。"


def _section_bullets(text: str, heading: str) -> list[str]:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if match is None:
        return []
    next_heading = _HEADING_RE.search(text, match.end())
    section = text[match.end() : next_heading.start() if next_heading else len(text)]
    bullets: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped.removeprefix("- ").strip())
    return bullets
