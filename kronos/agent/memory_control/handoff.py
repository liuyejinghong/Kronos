"""Generate copyable Agent handoff prompts from repository memory."""
# ruff: noqa: RUF001

from __future__ import annotations

from pathlib import Path

from kronos.agent.memory_control.models import (
    AgentHandoffPack,
    AgentMemoryState,
    MemorySummaryItem,
)
from kronos.agent.memory_control.redaction import redact_text

_SOURCE_PATHS = [
    "AGENTS.md",
    "MEMORY.md",
    "DECISIONS.md",
    "docs/agent-harness/PROGRESS_LOG.md",
    "TODO.md",
    "docs/PROJECT_STATUS.md",
    "docs/ROADMAP.md",
    "docs/PRODUCT_CONTROL_PANEL.md",
    "docs/RELEASE_0.4.10_AGENT_MEMORY_CONTROL.md",
    "openspec/changes/p4-agent-memory-control/",
]


def build_handoff_pack(
    project_root: str | Path,
    *,
    state: AgentMemoryState,
    decisions: list[MemorySummaryItem],
    lessons: list[MemorySummaryItem],
) -> AgentHandoffPack:
    """Build a concise handoff prompt for a new Agent session."""
    root = Path(project_root).resolve()
    decision_lines = "\n".join(f"- {item.title_zh}: {item.body_zh}" for item in decisions[:3])
    lesson_lines = "\n".join(f"- {item.body_zh}" for item in lessons[:3])
    source_lines = "\n".join(f"- `{path}`" for path in _SOURCE_PATHS)
    prompt = f"""# Kronos Agent Handoff

项目路径：`{root}`

你接手的是 Kronos 本地加密货币策略研究 Agent。

## 先读这些事实源
{source_lines}

## 当前状态
- 当前版本：{state.current_version}
- 下一版本：{state.next_version}
- 当前验收对象：{state.current_acceptance_target_zh}
- 最新成功运行 / 验收记录：{state.latest_successful_run_zh}
- 产品边界：{state.product_boundary_zh}
- 当前最高优先级：{state.highest_priority_zh}
- 建议第一步：{state.next_action_zh}

## 最近决策
{decision_lines or "- 先查看 `DECISIONS.md`。"}

## 最近教训
{lesson_lines or "- 先查看 `MEMORY.md` 和 `docs/agent-harness/PROGRESS_LOG.md`。"}

## 禁止事项
- 不把 API Key、Secret、token、交易所凭证写入 Markdown 记忆或 Web 输出。
- 不触碰 mainnet / 真实资金；testnet 也必须保留凭证、候选、观察计划、preflight 和人工授权闸门。
- 不自动覆盖 `MEMORY.md` 或 `DECISIONS.md`；首版只读和建议式更新。
- 不从聊天历史猜当前状态，必须回到文件事实源。
"""
    return AgentHandoffPack(
        title_zh="Kronos v0.4.10 Agent 接手提示词",
        prompt_md=redact_text(prompt),
        source_paths=_SOURCE_PATHS,
    )
