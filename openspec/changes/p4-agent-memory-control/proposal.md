## Why

Kronos 已经形成研究报告、Agent 复盘、策略草案、只读观察计划和测试网模拟盘链路，但项目和研究记忆分散在多个文件和报告中。

用户已经明确要求把 Harness Engineering 的结论产品化：新 agent、新会话或模型切换后，仍然能知道之前做过什么、为什么这么做、哪些方向不能重复，以及下一步应该做什么。

v0.4.10 要把这件事变成产品能力：Web 工作台里的 Agent 记忆与交接控制台。

## What Changes

- 新增 Agent 记忆控制台页面。
- 新增记忆摘要 API：当前状态、决策、教训、下一步。
- 新增一键交接包生成。
- 新增记忆漂移检查：版本冲突、缺索引、缺必备记忆段、疑似 secret。
- 新增安全边界：只读优先，不自动覆盖长期记忆，不泄漏 secrets。

## Capabilities

### New Capabilities

- `agent-memory-dashboard`: Web 展示当前状态、决策、教训和下一步。
- `agent-handoff-pack`: 生成可复制的新 Agent 接手提示词。
- `agent-memory-drift-check`: 检查记忆、TODO、项目状态和路线图之间的明显漂移。

### Modified Capabilities

- `web-workbench`: 新增 Agent 记忆 / 交接入口。
- `agent-knowledge-base`: 后续可把研究失败记忆和项目记忆统一到可展示的产品视图，但首版不迁移底层存储。

## Impact

- **新增用户路径**：`Web 工作台 -> Agent 记忆 -> 查看状态 / 生成交接包 / 检查漂移`。
- **新增开发约束**：长期记忆和项目状态必须有索引关联，不允许无来源的模型总结覆盖事实源。
- **不变约束**：v0.4.9 测试网模拟盘状态展示仍是下一主线；v0.4.10 不引入自动交易、自动实盘或自动记忆覆盖。
