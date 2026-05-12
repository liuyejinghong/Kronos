## Context

Kronos 的产品主线已经明确是加密货币策略研究 Agent。Agent 的核心能力不仅是跑工具，还包括记住历史研究、失败原因、决策依据和下一步。

当前项目已经有开发侧持久化 Harness：

- `MEMORY.md`
- `DECISIONS.md`
- `docs/agent-harness/PROGRESS_LOG.md`
- `docs/agent-harness/SETUP_REPORT_20260509.md`
- `docs/agent-harness/USAGE_GUIDE.md`
- `.cursor/rules/`

这些文件解决了“开发 agent 怎么接手”的问题。v0.4.10 要把它进一步转成 Kronos 产品能力，让用户在 Web 工作台看到“系统到底记住了什么”。

## Goals / Non-Goals

### Goals

- Web 展示当前项目 / 研究状态、版本边界和最高优先级。
- Web 展示最近决策、拒绝方案和经验教训。
- 生成一键交接包，帮助新 Agent 恢复上下文。
- 检查关键记忆文件和产品状态文档之间的明显漂移。
- 保持只读和人工确认边界，不自动覆盖长期记忆。

### Non-Goals

- 不引入向量数据库。
- 不存储全量聊天记录。
- 不强依赖 OpenHarness / Harness-Mem runtime。
- 不把记忆控制台做成执行控制台。
- 不做多用户权限、云同步或团队协作。

## Decisions

### D1: 文件是事实源，Web 只是视图

**决策**：首版从仓库文件读取记忆和状态，不新增数据库。

**理由**：

- Kronos 已经有成熟的文件控制层。
- 文件可审阅、可 diff、可被 Codex / Cursor / Claude Code 共同读取。
- 数据库会过早引入迁移、同步和权限复杂度。

### D2: 记忆控制台只读优先

**决策**：首版可以提示建议更新位置，但不自动覆盖 `MEMORY.md` 或 `DECISIONS.md`。

**理由**：

- 长期记忆被污染比短期忘记更危险。
- 用户已经强调“提前约束才不会出错”，所以先设人工闸门。

### D3: 摘要必须带来源

**决策**：每条当前状态、决策、教训和下一步都必须指向来源文件。

**理由**：

- 防止模型凭空总结。
- 方便用户 review 和后续 agent 追溯。

### D4: 漂移检查先做显式规则

**决策**：首版用规则检查版本号、索引、必备段落和 secret-like 字符串，不做 LLM 语义判断。

**理由**：

- 显式规则可测试、可重复、可解释。
- LLM 语义判断可以后续作为建议层，不适合做首版硬门槛。

## Proposed Architecture

```text
Repository files
      |
      v
Memory readers / parsers
      |
      +--> Current state summary
      +--> Decision summary
      +--> Lesson summary
      +--> Handoff prompt
      +--> Drift check
      |
      v
Web API
      |
      v
Web Memory Control page
```

## Recommended Modules

- `kronos/agent/memory_control/models.py`
  - 结构化摘要、决策、教训、检查结果和交接包模型。
- `kronos/agent/memory_control/readers.py`
  - 读取 repo 文件并做最小解析。
- `kronos/agent/memory_control/checks.py`
  - 版本一致性、索引完整性、必备段落和 secret-like 检查。
- `kronos/agent/memory_control/handoff.py`
  - 生成一键交接提示词。
- `kronos/web/routes/memory.py`
  - Web API。
- `web/`
  - Agent 记忆控制台页面和组件。

## Data Sources

- `MEMORY.md`
- `DECISIONS.md`
- `docs/agent-harness/PROGRESS_LOG.md`
- `TODO.md`
- `docs/PROJECT_STATUS.md`
- `docs/ROADMAP.md`
- `docs/PRODUCT_CONTROL_PANEL.md`
- `docs/agent-harness/SETUP_REPORT_20260509.md`
- `docs/agent-harness/USAGE_GUIDE.md`

## API Shape

Recommended endpoints:

- `GET /api/agent/memory/summary`
- `GET /api/agent/memory/decisions`
- `GET /api/agent/memory/handoff`
- `GET /api/agent/memory/check`

All responses must be local-only and redacted.

## UI Shape

The page should show four panels:

1. **当前状态**：版本、边界、最高优先级、下一步。
2. **决策与教训**：最近决策、拒绝方案、失败教训。
3. **交接包**：可复制的新 Agent 提示词。
4. **一致性检查**：通过、警告、阻塞和建议修复位置。

Do not render this as a marketing page. It is an operational research console.

## Safety Rules

- Do not read `.env`, SecretStore raw values, or credential files.
- Redact secret-like strings if encountered in memory docs.
- Do not expose full suspicious secret values in API or Web UI.
- Do not allow this page to start paper trading or live trading.
- Do not auto-apply memory updates.

## Risks / Trade-offs

- **[记忆重复]** -> Mitigation：`MEMORY.md` 只做摘要和导航，事实仍回到 product docs。
- **[记忆污染]** -> Mitigation：只读优先，写入另走人工确认。
- **[规则过硬误报]** -> Mitigation：把结果分为 passed / warning / blocking，不把 warning 当失败。
- **[过度工程化]** -> Mitigation：首版不加 DB、不加 vector search、不加 runtime dependency。
