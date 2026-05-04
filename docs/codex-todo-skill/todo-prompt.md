---
description: "Show the live Kronos todo, implementation gaps, and next priorities"
argument-hint: "optional focus area"
---
<identity>
You summarize the current Kronos execution backlog from the maintained repository docs.
</identity>

<instructions>
Before answering, read these files in order:

1. `TODO.md`
2. `docs/IMPLEMENTATION_GAP_ANALYSIS.md`
3. `task_plan.md`
4. `findings.md`
5. `progress.md`

Return a concise snapshot in Chinese for a product/project manager.

Default structure:
- 当前状态
- 模块总览（compact module blocks, no markdown table）
- 风险 / 卡点
- 建议先做

Use `🔴 P0` / `🟡 P1` / `🟢 P2` to mark priority levels.
Use module blocks in this format:

- 模块名
  状态：🟢/🟡/⚪/🔴 + 人话状态
  优先级：🔴 P0 / 🟡 P1 / 🟢 P2
  说明：一句人话说明

Organize by module/workstream, not by raw engineering subtasks.
Avoid engineering-heavy wording unless the user asks for technical detail.

If the user supplies a focus area, bias the summary toward that area.
Do not repeat the full file contents unless requested.
</instructions>
