## ADDED Requirements

### Requirement: Agent memory must be read from repository files
系统 SHALL 从仓库内持久化文件读取 Agent 记忆和当前项目状态，不得只依赖当前聊天上下文。

#### Scenario: User opens memory dashboard
- **WHEN** 用户打开 Agent 记忆控制台
- **THEN** 系统 MUST 读取 `MEMORY.md`
- **AND** 系统 MUST 读取 `DECISIONS.md`
- **AND** 系统 MUST 读取 `docs/agent-harness/PROGRESS_LOG.md`
- **AND** 系统 MUST 读取 `TODO.md`、`docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`

#### Scenario: Required memory file is missing
- **WHEN** 必需记忆文件不存在
- **THEN** 系统 MUST 显示缺失文件
- **AND** 系统 MUST NOT 伪造该文件中的状态

### Requirement: Memory dashboard must show PM-readable state
系统 SHALL 在 Web 工作台展示 PM / 交易研究者可读的 Agent 记忆摘要。

#### Scenario: Dashboard renders current state
- **WHEN** 用户查看 Agent 记忆控制台
- **THEN** 系统 MUST 显示当前版本、下一版本、产品边界、最高优先级和下一步
- **AND** 每条摘要 MUST 指向来源文件

#### Scenario: Dashboard first screen is acceptance-oriented
- **WHEN** 模拟用户打开 Agent 记忆控制台首屏
- **THEN** 系统 MUST 显示当前验收对象
- **AND** 系统 MUST 显示最新成功运行或验收记录
- **AND** 系统 MUST 显示对应来源文档
- **AND** 系统 MUST 显示建议下一步

#### Scenario: Dashboard renders decisions and lessons
- **WHEN** 用户查看决策与教训区
- **THEN** 系统 MUST 显示最近决策、拒绝方案和经验教训
- **AND** 系统 MUST 默认隐藏不必要的内部实现噪音

### Requirement: Handoff pack must be generated from current memory
系统 SHALL 生成可复制的新 Agent 接手提示词。

#### Scenario: User generates handoff pack
- **WHEN** 用户点击生成交接包
- **THEN** 系统 MUST 输出项目路径、必读文件、当前边界、当前待办和禁止事项
- **AND** 系统 MUST 引用来源文件
- **AND** 系统 MUST NOT 包含 secrets

### Requirement: Memory drift check must detect obvious inconsistencies
系统 SHALL 检查关键记忆文件和产品状态文件之间的明显漂移。

#### Scenario: Version fields disagree
- **WHEN** `TODO.md`、`PROJECT_STATUS.md`、`ROADMAP.md` 中版本字段明显不一致
- **THEN** 系统 MUST 返回 warning 或 blocking 检查项
- **AND** 系统 MUST 指出冲突来源文件

#### Scenario: Release docs are not indexed
- **WHEN** v0.4.10 release doc 或 OpenSpec 没有被 TODO / ROADMAP / PROJECT_STATUS 索引
- **THEN** 系统 MUST 返回 warning
- **AND** 系统 MUST 提示应更新的索引文件

### Requirement: Memory output must be redacted and read-only by default
系统 SHALL 对记忆控制台输出做脱敏，并在首版保持只读优先。

#### Scenario: Secret-like value appears in memory docs
- **WHEN** 记忆文件包含疑似 API Key、Secret 或 token
- **THEN** 系统 MUST 在输出中脱敏
- **AND** 系统 MUST 提示风险文件位置
- **AND** 系统 MUST NOT 展示完整秘密值

#### Scenario: Drift check suggests memory update
- **WHEN** 系统发现应更新的记忆或状态文件
- **THEN** 系统 MAY 给出建议
- **AND** 系统 MUST NOT 默认自动覆盖长期记忆文件
