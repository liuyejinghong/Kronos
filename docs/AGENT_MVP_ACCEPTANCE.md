# Kronos Agent MVP 验收定义

更新时间：2026-04-30

## 当前纠偏

Kronos 的产品定位不是“每天自动跑一次报告”，也不是普通研究脚本集合。

Kronos 应该是一个 **加密货币策略研究 Agent**。

它要做的不是定时重复执行同一批实验，而是像研究员一样：

1. 理解当前研究目标。
2. 从旧 A 股 / 期货策略资产、已有候选库和研究记忆中提出假设。
3. 把假设拆成可验证的实验。
4. 调用确定性研究工具去跑验证。
5. 阅读实验结果。
6. 给出下一步研究动作。
7. 把失败、观察和有效线索沉淀为记忆。

## 一句话产品定义

Kronos Agent 是一个面向 crypto 市场的策略资产迁移和研究 Agent。

它的输入不是固定定时任务，而是研究目标，例如：

- 从旧策略资产里找下一批值得迁移的候选。
- 判断某个候选是否应该退休、观察、改造或进入下一层验证。
- 根据当前失败原因提出新的 crypto 适配假设。
- 为下一轮实验生成可执行研究计划。

它的输出不是技术日志，而是研究决策：

- 这个候选为什么失败。
- 是否值得继续研究。
- 下一步应该补什么数据、改什么假设、跑什么实验。
- 哪些线索应该进入知识库，避免重复研究。

## Agent 运行模型

Agent MVP 的运行方式不是手动执行一次，也不是每天定时跑一次。

Kronos 应该是一个本地常驻 Agent 软件：

```text
打开 Kronos
-> 后台 Agent Supervisor 启动
-> 检查材料队列和候选池
-> 有材料就连续推进研究
-> 没材料就进入低频巡检
-> 新材料出现后继续推进
```

材料包括：

- 旧资产迁移任务。
- 候选池里待验证策略。
- 新市场数据。
- 回测失败记录。
- 模拟执行日志。
- Agent 复盘结论。
- 用户后续导入的新策略、论文或因子。

idle 状态不是无意义重复跑。只有出现新证据、新参数、新数据窗口、新迁移方案或新市场状态，Agent 才应该重新实验。

MVP 的默认低频巡检可以先按 30 分钟理解，后续由配置控制。

MVP 的并发边界是：同一时间只推进一个主研究任务，防止 Agent 多线发散；主任务内部可以并行跑多币种、多时间窗口、多验证切片。

完整技术选型见 `docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`。实现前准入级架构借鉴评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`，对应 OpenSpec 见 `openspec/changes/p0-agent-runtime-web-workbench/`。

## 候选生命周期

Web 和 Agent Supervisor 必须共用同一套候选生命周期：

```text
材料进入
-> 迁移审查
-> 假设
-> 实验计划
-> 验证中
-> Agent 分析
-> 投委会评分
-> 观察 / 改造 / 模拟盘 / 待实盘审批 / 淘汰
```

验收口径：

- 用户能看到候选当前处于哪个状态。
- 用户能看到为什么进入这个状态。
- 用户能看到是谁推动了状态变化：Agent、确定性工具、用户审批或外部材料。
- `模拟盘 / paper / testnet` 可以由 Agent 自动推进。
- `待实盘审批` 必须停在人工闸门，不能自动变成真钱交易。

## Agent 角色和模型配置

Agent MVP 不是单一 prompt。第一版至少要能表达以下角色：

- 研究员。
- 反方审查。
- 风控审查。
- 投委会裁决。
- 执行记录分析。

验收口径：

- 每个角色必须有可追踪的 prompt 版本。
- Prompt 修改不能覆盖旧版本，必须生成新版本。
- Prompt 新版本可以保存为草稿，但必须经过人工确认后才能成为 active 版本。
- MVP 每个角色只启用一个 active 模型；多模型 A/B 和自动对照后置。
- 每次 Agent 结论必须记录使用的角色、prompt 版本、模型供应商和模型名。
- Web 设置页必须能配置 LLM provider、模型、API Key、角色启停和默认模型。
- DeepSeek 可以作为启动默认供应商，但后续要保留切换其他模型的能力，provider 不能写死到业务逻辑。
- API Key 不能出现在前端代码、事件时间线或报告里。
- API Key 由本地后端 SecretStore 保存和调用，Web 只展示 masked 状态和连通性检查结果。

## Web 验收面

Agent MVP 的主要验收面应是本地 Web 研究工作台，CLI 只作为开发、调试和兜底入口。

产品访谈边界到当前版本收敛。后续先完成同类 Agent 项目的架构借鉴评审、OpenSpec 约束和开发任务拆分，再进入实现；只有遇到真钱实盘、密钥安全、不可逆操作、重大技术路线分叉或验收口径冲突时，才重新请求用户确认。

Web 第一版至少要能回答：

1. 当前有哪些候选资产。
2. 每个候选来自旧资产迁移、公开策略还是 Agent 新假设。
3. 每个候选当前状态是什么。
4. Agent 正在推进哪一轮研究。
5. 候选为什么继续、观察、改造或淘汰。
6. 哪些动作等待人工闸门。
7. 当前主研究任务是什么，以及它拆出了哪些子验证。
8. 候选生命周期上一次状态变化是什么，变化原因是什么。
9. 当前启用了哪些 Agent 角色、角色版本和模型配置。
10. 本轮 Agent 的结论、支持理由、反对理由、关键证据、最大风险、下一步动作和待审批事项是什么。
11. 现在在研究什么，为什么研究它，证据是什么，下一步是什么，哪里需要用户审批。

第一版信息架构：

- 候选资产看板。
- Agent 工作流时间线。
- 候选详情页。
- Agent / 模型设置页。
- 材料导入入口。
- 待审批事项入口。

这不是功能膨胀，而是产品可验收的最低信息结构。

## 材料、审批和记忆验收边界

MVP 材料池默认包含：

- 旧资产迁移材料。
- 候选池待验证项。
- 失败记录。
- 模拟盘 / paper / testnet 日志。
- 用户手动导入资料。

用户导入资料先支持 Web 上传或粘贴文本，类型包括策略说明、因子说明、论文摘要和交易复盘。MVP 暂不自动抓论文、新闻、社媒或外部网页。

MVP 审批类型先固定为：

- 启用 prompt 版本。
- 让候选进入模拟盘。
- 让候选申请真钱实盘。

paper / testnet 可以由 Agent 自动运行，但 Web 必须显示每次模拟交易、失败原因和 Agent 复盘。

知识库只写入研究结论、失败原因、候选状态变化、投委会分歧和用户审批记录。技术日志、逐条模型原文和完整事件流不直接写入知识库。

## 防跑偏验收边界

- 一轮 Agent 研究最多推进到“给出下一步动作”，不能同轮无限递归自我继续。
- 下一轮必须由新材料、新证据、新用户审批或明确排队任务触发。
- 连续两轮同类失败且没有新证据时，候选必须进入 `observe` 或 `retired`。
- Web 候选评分必须展示总评分、研究价值、稳定性、风险、证据质量和 Agent 分歧。
- MVP 用户干预点只包含暂停当前主任务、跳过候选、要求补充验证、批准审批事项。
- Event timeline 默认分为 `info`、`decision`、`warning`、`approval_required`、`error`。

## Agent MVP 要包含什么

Agent MVP 的最小闭环是：

1. **任务理解**
   - 用户给一个研究目标。
   - Agent 能把目标改写成明确研究任务。

2. **候选选择**
   - Agent 能从当前 12 个候选、旧策略资产线索和研究记忆中选择下一步研究对象。
   - 不能只机械重复跑全部候选。

3. **假设生成**
   - Agent 能提出一个或多个可验证假设。
   - 假设必须说明来源：旧策略、crypto 市场机制、失败原因、观察名单或数据缺口。

4. **实验设计**
   - Agent 能把假设转成实验计划。
   - 实验计划要说明使用哪些币种、时间窗口、数据、验证方法和通过/失败标准。

5. **工具调用**
   - Agent 调用现有确定性研究工具执行实验。
   - 研究工具负责计算，Agent 不凭空编造结果。

6. **结果解释**
   - Agent 读取报告和结构化结果。
   - 输出退休、观察、改造、深研或补数据建议。

7. **记忆沉淀**
   - Agent 把结论、失败原因和下一步写入研究知识库。
   - 后续不要重复提出已经失败且无新证据的方向。

8. **人工闸门**
   - Agent 可以建议，但不能自动把候选送入组合、风控或实盘。

## 不包含什么

Agent MVP 不包含：

- 每天无脑定时运行。
- 自动交易。
- 自动下单。
- 直接把旧策略整包迁移成 crypto 策略。
- 让 LLM 自己编造回测结果。
- 绕过实验结果直接给策略结论。
- 绕过人工确认进入组合或实盘。

## 当前已落地的验收闭环

Agent MVP 已经不再只是规划，也不只是单个 CLI 工具。

已新增入口：

```bash
kronos agent propose
kronos agent conclude
kronos agent run-once
```

当前已经完成：

1. 读取上一轮确定性研究结果。
2. 选择下一轮候选。
3. 提出研究假设。
4. 生成可执行实验计划。
5. 调用白名单确定性工具完成计划和结果读取。
6. 输出 `agent_run_report.md`、`agent_run_summary.json` 和 `agent_events.jsonl`。
7. 把 Agent 计划和决策写入研究知识库。
8. 把同一轮结果发布到本地 Web runtime，让 Web 第一屏、运行摘要和时间线可读。
9. 完成 release readiness：错误分类、时间线恢复、DeepSeek 配置状态检查、secret 脱敏复查和 Web QA。

最新验收批次：

- Agent loop 验收批次：`20260430-agent-acceptance-v1`
- 输入：`reports/research/experiments/20260427-run-mvp-v1-research/auto_run_summary.json`
- 专项证据：`reports/research/experiments/20260428-agent-mvp-v1-evidence-trend_pullback_entry/watchlist_evidence_review.json`、`reports/research/experiments/20260428-agent-mvp-v1-evidence-multi_timeframe_confirmation/watchlist_evidence_review.json`
- Agent run report：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_report.md`
- Agent run summary：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_summary.json`
- Agent events：`reports/research/experiments/20260430-agent-acceptance-v1/agent_events.jsonl`
- Web runtime：`reports/agent_runtime/20260430-agent-acceptance-v1/agent_events.jsonl`
- Web run summary API：`/api/agent/runs/20260430-agent-acceptance-v1/summary`
- Agent MVP 交付批次：`20260430-agent-mvp-delivery-v1`
- Agent MVP 交付报告：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md`
- Agent MVP 交付摘要：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_summary.json`
- Agent MVP 交付事件：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_events.jsonl`
- Agent MVP 交付说明：`docs/AGENT_MVP_DELIVERY.md`
- DeepSeek 配置状态 API：`/api/settings/llm/providers/deepseek/status`

本批 Agent 选择：

- `multi_timeframe_confirmation`
- `trend_pullback_entry`

本批 Agent 提出：

- 2 个观察名单专项复盘假设。
- 1 个旧策略候选批量退休评审假设。
- 1 个 crypto-native 机制改造假设。

专项证据读取结果：

- `multi_timeframe_confirmation`：强支持切片 0 个，弱正向切片 1 个，仅保留观察。
- `trend_pullback_entry`：强支持切片 0 个，弱正向切片 5 个，进入候选改造，不进入组合或实盘。

## 当前已有基础

当前已有的东西已经覆盖 Agent MVP 的最小研究闭环：

- 数据接入和覆盖检查。
- 12 个旧策略候选因子。
- 候选验证和晋升流程。
- 观察名单补证据。
- 中文研究报告。
- 失败原因分层。
- SQLite + FTS 研究知识库。
- `kronos run today` 系统入口。
- `kronos agent run-once` 单轮 Agent 验收入口。
- 本地 Web 研究工作台的候选池、Agent 摘要、时间线、设置、材料和审批入口。

这些能力可以被 Agent 调用。当前已经形成“读上一轮结果 -> 生成计划 -> 调用确定性工具 -> 读取结果 -> 输出报告和时间线 -> 写入研究记忆”的 Agent MVP 最小闭环。

## Agent MVP 当前缺口

当前最重要缺口：

- Agent 还没有把失败记忆强约束到候选生成逻辑里。
- 新候选 proposal 到候选实现之间还没有人工审批流程。
- Agent run 还没有完整写入 experiment ledger，本轮已串起 artifact path 和 knowledge base。
- Web 图表仍以候选分布为主，收益、回撤、K 线和评分走势需要后续真实实验图表。

## 验收标准

Agent MVP 通过，不是看它是否每天运行。

通过标准是：

- 给定一个研究目标，Agent 能提出下一轮研究假设。
- 假设能落成可执行实验，而不是空泛建议。
- 实验结果来自确定性工具，不来自模型臆测。
- Agent 能读懂实验结果并给出资产处置建议。
- Agent 能解释为什么不继续研究某个方向。
- Agent 能把结论写入记忆，用于下一轮决策。

## 第一版建议验收任务

建议第一个 Agent MVP 任务是：

> 基于当前 12 个旧策略候选的 90 天验证结果，选择下一步最值得研究的方向，并生成一轮新的 crypto 适配实验计划。

它应该输出：

- 应该退休的候选。
- 只保留观察的候选。
- 需要 crypto 改造的候选。
- 下一轮新增候选或新数据需求。
- 具体实验计划。
- 为什么不是每天重复跑同一批候选。

当前状态：

- 第一版计划已完成：`20260428-agent-mvp-v1`。
- 第一版结果读取已完成：`20260428-agent-mvp-v1-decision`。
- Agent loop 集成验收已完成：`20260430-agent-acceptance-v1`。
- 下一版应补：更强失败记忆约束、候选评分维度、审批项生成和 Batch 8 hardening。
