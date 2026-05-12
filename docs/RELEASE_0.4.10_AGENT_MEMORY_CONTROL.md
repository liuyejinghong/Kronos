# Kronos v0.4.10 版本需求：Agent 记忆与交接控制台

> 状态：已完成，待产品 review
> 版本目标：0.4.10
> 优先级：P1
> 约束来源：`docs/agent-harness/SETUP_REPORT_20260509.md`、`MEMORY.md`、`DECISIONS.md`、`TODO.md`、`docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`

## 版本定位

v0.4.9 仍然优先完成 Binance 测试网模拟盘状态和报告的 Web 展示，以及在用户授权后补真实 testnet 端到端证据。

v0.4.10 不抢 v0.4.9 主线。它要把 2026-05-09 建立的开发侧 Agent Harness 产品化，形成 **Agent 记忆与交接控制台**：让 Kronos 自己能展示、检查和复用研究记忆、决策、失败教训、当前状态和下一步。

这不是单纯的开发者文档功能。它服务 Kronos 的产品主线：

```text
研究目标 -> 候选选择 -> 假设生成 -> 实验计划 -> 验证 -> 解释 -> 记忆沉淀 -> 下一轮
```

如果 Kronos 是研究 Agent，那么它必须能回答：

1. 以前做过什么？
2. 为什么做这个决定？
3. 哪些方向已经失败，不能重复？
4. 现在卡在哪里？
5. 新 Agent 或新会话接手时应该先读什么？

## 为什么要做

当前 Kronos 已经有很多项目和研究产物：`TODO.md`、`docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`、`docs/PRODUCT_CONTROL_PANEL.md`、release docs、OpenSpec、Agent 报告、event timeline、知识库和测试网报告。

问题不是“没有记忆”，而是记忆分散：

- 新 agent 容易把旧 Agent MVP 结论当成当前产品边界；
- 用户需要靠人工提醒 agent 先读哪些文档；
- 失败教训、拒绝过的方案、版本边界和下一步缺少一个产品化视图；
- Web 工作台还不能告诉用户“现在这套研究系统记住了什么”。

v0.4.10 的目标是把这些记忆变成产品能力，而不是让它停留在内部 markdown。

## 产品承诺

1. Web 工作台能展示当前项目 / 研究状态卡。
2. Web 工作台能展示最近决策、失败教训和拒绝过的方案。
3. 用户能一键生成新 Agent 接手提示词。
4. 系统能检查 `MEMORY.md`、`DECISIONS.md`、`TODO.md`、`PROJECT_STATUS.md`、`ROADMAP.md` 之间的明显漂移。
5. 记忆显示和检查不得泄漏 API Key、交易所凭证、token 或其他秘密。
6. 记忆条目必须有来源指向，不能是不可追溯的模型自说自话。
7. 该能力首版只读为主；不自动替用户改写长期记忆。
8. Web 首屏必须让模拟用户一眼看懂当前版本、当前验收对象、最新成功运行、来源文档和建议下一步，避免再次出现“信息存在但用户不知道该验收什么”的问题。

## 产品边界

### In Scope

- Web 增加 Agent 记忆 / 交接页。
- 展示当前状态、当前产品边界、最高优先级、最近决策、失败教训、下一步。
- 展示 `MEMORY.md`、`DECISIONS.md` 和现有产品状态文档的摘要。
- 生成一键交接提示词，供 Codex / Cursor / Claude Code / 其他 agent 复用。
- 增加记忆一致性检查：缺文件、缺索引、版本字段冲突、明显状态冲突、秘密风险。
- 增加 CLI 或内部服务读取器，供 Web API 使用。
- 所有输出都以 PM / 交易研究者能理解的语言展示。

### Out of Scope

- 不引入向量数据库。
- 不把所有聊天记录自动入库。
- 不安装或强依赖 OpenHarness / Harness-Mem runtime。
- 不允许 Agent 自动覆盖 `MEMORY.md` 或 `DECISIONS.md`。
- 不做团队权限、多用户协作、云端同步。
- 不做主网实盘、策略生成、参数优化或交易执行扩展。

## 用户流程

### 查看当前记忆

1. 用户打开 Web 工作台。
2. 进入“Agent 记忆”页。
3. 系统展示：
   - 当前产品版本和边界；
   - 当前最高优先级；
   - 最近完成事项；
   - 最近决策；
   - 失败教训；
   - 下一步建议；
   - 需要人工确认的事项。

### 生成交接包

1. 用户点击“生成交接包”。
2. 系统生成一段可复制提示词。
3. 提示词包含：
   - 项目路径；
   - 必读文件；
   - 当前版本状态；
   - 当前待办；
   - 禁止事项；
   - 最近决策和风险；
   - 建议第一步。

### 检查记忆漂移

1. 用户点击“检查记忆一致性”，或运行 CLI 检查命令。
2. 系统读取记忆和状态文档。
3. 系统返回：
   - 通过项；
   - 警告项；
   - 阻塞项；
   - 建议修复位置。

## 功能需求

### 需求 1：记忆读取必须基于文件事实源

系统 SHALL 从仓库内文件读取 Agent 记忆和项目状态，不得只依赖当前聊天上下文。

#### 验收点

- 必须读取 `MEMORY.md`。
- 必须读取 `DECISIONS.md`。
- 必须读取 `docs/agent-harness/PROGRESS_LOG.md`。
- 必须读取 `TODO.md`、`docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`。
- 文件缺失时必须明确提示缺失项，而不是静默降级。

### 需求 2：Web 必须能展示 PM 可读的记忆控制台

系统 SHALL 在 Web 工作台展示 Agent 记忆摘要。

#### 验收点

- 显示当前版本、下一版本、产品边界和最高优先级。
- 首屏必须展示当前验收对象、最新成功运行 / 验收记录、来源文档和建议下一步。
- 显示最近决策和被拒绝方案。
- 显示最近经验教训和下一步。
- 显示每条摘要的来源文件。
- 默认不暴露内部类名、函数名和长路径噪音。

### 需求 3：必须能生成一键交接包

系统 SHALL 生成一个可复制的新 Agent 接手提示词。

#### 验收点

- 交接包必须包含项目路径和必读文件。
- 交接包必须包含当前产品边界和当前待办。
- 交接包必须包含安全禁令：不写 secrets、不碰主网、不绕过人工闸门。
- 交接包必须指向来源文档，而不是复制大段全文。

### 需求 4：必须检查记忆漂移

系统 SHALL 检查关键记忆文件和产品状态文件之间的明显冲突。

#### 验收点

- 检查 `TODO.md`、`PROJECT_STATUS.md`、`ROADMAP.md` 中当前版本 / 下一版本是否一致。
- 检查 `MEMORY.md` 是否包含 Boot Protocol、Memory Write Triggers 和 Verification Loop。
- 检查 `DECISIONS.md` 是否有最新 harness 决策。
- 检查 release docs 和 OpenSpec 是否被 TODO / ROADMAP 索引。
- 检查记忆文件是否出现疑似 API Key / Secret / token。

### 需求 5：记忆写入必须保留人工闸门

系统 SHALL 首版保持只读和建议式更新，不自动覆盖长期记忆。

#### 验收点

- Web 可以提示“建议更新哪份文件”，但不能无确认自动改写。
- CLI 检查可以输出建议 patch 或建议位置，但默认不写文件。
- 任何自动写入能力都必须另走后续版本需求和审批。

## 推荐模块边界

- `kronos/agent/memory_control/`：文件读取、摘要模型、漂移检查、交接包生成。
- `kronos/web/routes/memory.py`：Web API，只返回脱敏摘要和检查结果。
- `web/app` 或 `web/components`：Agent 记忆控制台页面。
- `scripts/harness_memory_check.py`：保留为开发侧轻量校验，可复用规则但不直接作为产品 API。
- `tests/unit/agent/`：记忆解析、漂移检查、脱敏和交接包生成。
- `tests/integration/web/`：API 和 Web 页面读取路径。

## 数据与产物

首版不新增数据库。读取和输出围绕现有文件：

- `MEMORY.md`
- `DECISIONS.md`
- `docs/agent-harness/PROGRESS_LOG.md`
- `TODO.md`
- `docs/PROJECT_STATUS.md`
- `docs/ROADMAP.md`
- `docs/PRODUCT_CONTROL_PANEL.md`
- `docs/agent-harness/SETUP_REPORT_20260509.md`
- `docs/agent-harness/USAGE_GUIDE.md`

可选输出：

- `reports/agent_memory/memory_check_<timestamp>.json`
- `reports/agent_memory/memory_check_<timestamp>.md`

## 安全规则

- 不显示原始 API Key / Secret / token。
- 不从 `.env`、SecretStore 或用户本地密钥文件读取明文。
- 不把测试网凭证、主网凭证或私有 webhook 写入交接包。
- 检查器发现疑似秘密时，必须提示风险和文件位置，但不要在 UI 中展开完整值。
- 记忆控制台不能成为绕过人工闸门的执行入口。

## 测试与验证

至少需要覆盖：

- 单元测试：文件缺失、字段提取、版本冲突、OpenSpec 索引缺失、疑似 secret 脱敏。
- 集成测试：Web API 返回当前状态、决策摘要、交接包和漂移检查。
- 前端测试 / 手工验证：Web 页面在桌面和窄屏可读，不把长路径挤爆布局。
- 安全测试：构造含 secret-like 字符串的 fixture，确认输出脱敏。
- 文档验证：`TODO.md`、`PROJECT_STATUS.md`、`ROADMAP.md`、`PRODUCT_CONTROL_PANEL.md` 均索引 v0.4.10 文档和 OpenSpec。

## 完成标准

v0.4.10 完成时，必须满足：

1. 有完整版本需求文档和 OpenSpec 约束。
2. Web 工作台有 Agent 记忆 / 交接控制台入口。
3. 用户能在首屏看到当前版本、当前验收对象、最新成功运行、来源文档和下一步。
4. 用户能复制一键交接提示词。
5. 系统能检查记忆漂移并输出可理解结果。
6. 所有输出脱敏，不泄漏 secrets。
7. 该能力不改变 v0.4.9 测试网模拟盘主线，不绕过交易人工闸门。

## 关键风险

| 风险 | 根因 | 必须怎么控 |
|---|---|---|
| 变成第二套项目管理系统 | 记忆控制台复制 TODO / Roadmap 内容 | 只做摘要和索引，状态事实仍来自现有文档 |
| 记忆污染 | 自动把模型猜测写进长期记忆 | 首版只读和建议式更新，写入必须人工确认 |
| 泄漏秘密 | 扫描文件时展示 secret-like 值 | 脱敏输出，禁止读取密钥源，测试覆盖 |
| UI 工程化过重 | 展示长文件路径和内部类名 | 默认 PM 可读摘要，技术细节折叠 |
| 抢 v0.4.9 主线 | 记忆控制台比测试网状态更早进入实现 | 明确排到 v0.4.10 P1，v0.4.9 继续做 testnet Web 状态 |

## OpenSpec 约束

实现前必须先满足 `openspec/changes/p4-agent-memory-control/`。在 OpenSpec 没有通过前，不进入代码实现。
