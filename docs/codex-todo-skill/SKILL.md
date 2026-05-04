---
name: todo
description: Show the live Kronos backlog, implementation gap analysis, verification blockers, and next execution priorities. Use when the user asks for todo, backlog, current status, next priorities, or what remains to be done in Kronos.
---

# Kronos Todo

Use the repository-maintained backlog and audit docs as the source of truth.
Write for a product manager or project manager, not an engineer.

## Required Reads

Read these files in order before answering:

1. `TODO.md`
2. `docs/IMPLEMENTATION_GAP_ANALYSIS.md`
3. `task_plan.md`
4. `findings.md`
5. `progress.md`

## What To Return

Provide a concise, PM-friendly snapshot in Chinese with:

- plain-language status
- priority buckets using `P0 / P1 / P2`
- traffic-light emoji for urgency
- what is done / in progress / not started
- blockers and risks in non-engineering-heavy language

Use this structure by default:

**当前状态**
- One short paragraph in plain Chinese

**模块总览**
- Do NOT use markdown tables
- Group by module or workstream, not by abstract status buckets
- Use one compact block per module in this format:

```text
- 数据底座
  状态：🟢 基本完成
  优先级：🟡 P1
  说明：一句人话说明
```

Example priority labels:
- `🔴 P0` = must handle now / blocking
- `🟡 P1` = important next
- `🟢 P2` = later / lower urgency

Example status labels:
- `🟢` 已完成 / 基本完成
- `🟡` 进行中 / 半完成
- `⚪` 未开始
- `🔴` 阻塞

After the table, add a short section:

**风险 / 卡点**
- Flat bullets, plain language

**建议先做**
- 3-5 flat bullets, plain language

Do not include "next week plan" style planning unless the user explicitly asks.

## Rules

- Treat `TODO.md` as the live execution backlog.
- Treat `docs/IMPLEMENTATION_GAP_ANALYSIS.md` as the audit/reference document.
- If they disagree, prefer the audit doc plus current verification evidence.
- Do not dump full file contents unless the user explicitly asks.
- If the user asks to update status, edit `TODO.md` and sync material findings into `task_plan.md`, `findings.md`, and `progress.md`.
- Distinguish clearly between:
  - implemented
  - partially implemented
  - unimplemented
  - blocked by environment
- Prefer PM wording:
  - say "数据底座" instead of "Layer 1 ingestion/storage/query stack"
  - say "回测系统" instead of "backtest engine module"
  - say "实验记录与对比" instead of "experiment ledger and DuckDB query layer"
- Minimize code/file detail unless the user asks for technical depth.
- Avoid markdown tables because terminal rendering with Chinese text and emoji is unstable.
- Default grouping should be:
  - 数据底座
  - 因子平台
  - 回测系统
  - 实验记录与对比
  - 文档/验证/工程基础设施

## Usage Examples

- `$todo`
- `todo`
- `show me the backlog`
- `what's left in Kronos`
