# Kronos 产品级总览看板

更新时间：2026-05-04

**最新验收**：`docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md`（2026-05-04，CC 全页面验收，功能链路全部通过，产品可用性部分通过）。

2026-05-01 补充：基于浏览器实操的产品体验复盘已落地到 `docs/AGENT_MVP_PRODUCT_UX_REVIEW.md`。复盘结论是：当前 Web 已能展示 Agent 批次和候选数据，但仍更像研发验收页，不能按“普通量化交易员可用产品”验收。Product UX Repair Batch 第一批已经完成，优先修正了主任务流、报告阅读、候选池信息架构和模型状态信任冲突；下一阶段继续补真正的 Agent 启动入口和候选证据挂载。

## 这份文档回答什么

这份文档面向产品经理视角，不展开工程细节。

它回答六个问题：

1. Kronos 当前到底是什么产品。
2. 当前 MVP 应该验收什么。
3. 当前已经能做什么。
4. 当前还不能做什么。
5. 旧 A 股 / 期货策略资产迁移到了哪一步。
6. Qlib / RD-Agent 方法论在产品里分别落在哪一层。

更细的工程状态见 `docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`、`TODO.md` 和 OpenSpec。研发准入级架构借鉴评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`，完整开发规划见 `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`，执行级任务拆分见 `docs/AGENT_MVP_EXECUTION_PLAN.md`，已有资产复用和归档边界见 `docs/AGENT_MVP_ASSET_INVENTORY.md`。

## 当前一句话结论

Kronos 的产品定位是 **加密货币策略研究 Agent**。

它不是“每天自动跑一次报告”的定时任务系统，也不是普通回测工具。它应该像研究员一样：理解研究目标，选择候选，提出假设，设计实验，调用确定性研究工具，读取结果，沉淀记忆，并给出下一轮研究决策。

当前最高优先级已调整为 **Product UX Repair Batch**。RD-Agent 式“提出假设 -> 生成实验 -> 跑验证 -> 读结果 -> 继续迭代”不是未来项，而是现在要做的 MVP 主线；但 2026-05-01 浏览器实操复盘证明，现有 Web 只是把这些能力展示出来了，还没有形成普通量化交易员可顺着完成任务的产品工作流。实现前置门槛已经补齐，Batch 1 已完成 Agent 基础契约、事件时间线、报告和错误报告；Batch 2 已完成本地 Agent Supervisor、单主任务队列、idle scanner、候选生命周期状态机、失败收敛和状态查询；Batch 3 已完成 Agent 角色、Prompt 版本、SecretStore、DeepSeek provider 和 LLM 调用事件；Batch 4 已完成确定性工具执行器和 `kronos agent run-once` 单轮闭环；Batch 5 已完成本地 Web API 后端；Batch 6 已完成本地 Web 研究工作台前端；Batch 7 已完成真实本地 Agent loop 集成验收；Batch 8 已完成 release readiness、错误分类、时间线恢复、DeepSeek 配置状态检查、secret 脱敏复查和 Web QA；Product UX Repair Batch 第一批已完成主任务流、报告阅读、候选池和模型状态信任修复。下一步优先补真正的 Agent 启动入口、候选详情证据挂载和图表化报告。

`kronos run today` 已经跑通，但它只是 Agent 的工具入口之一，不是产品终点。定时器也不是当前目标；只有当 Agent 已经能提出有意义的新假设或监控需求时，才考虑定时运行。

## 最新产品架构共识

Kronos 应该是一个本地优先、未来可远程化的 **常驻 Agent 软件**。

正确运行方式不是“每天跑一次”，而是：

```text
打开 Kronos
-> 后台 Agent Supervisor 启动
-> 检查材料队列和候选池
-> 有材料就连续推进研究
-> 没材料就低频巡检
-> 新材料出现后继续推进
```

关键共识：

- Agent 常驻运行，Web 是控制台，不是 Agent 本体。
- 有材料时持续推进研究队列，没材料时进入 idle scanner，例如每 30 分钟巡检一次。
- 任何重复实验都必须有新证据、新参数、新数据窗口、新迁移方案或新市场状态，不能机械重跑。
- MVP 阶段同一时间只推进一个主研究任务；主任务内部可以并行跑多币种、多窗口、多验证切片。
- dry-run、paper、testnet 允许 Agent 自动跑，因为它们属于验证链路。
- 真钱实盘准入和实际资金大小必须由用户确认。
- 候选必须沿固定生命周期推进：材料进入、迁移审查、假设、实验计划、验证、Agent 分析、投委会评分，再进入观察、改造、模拟盘、待实盘审批或淘汰。
- Agent 角色和 prompt 需要版本管理，每次结论都要能追溯当时使用的角色版本和模型。
- DeepSeek 等大模型接入后应在 Web 设置页配置，不要求用户手改配置文件。
- MVP 材料池只包含旧资产迁移、候选池待验证项、失败记录、模拟盘日志和用户手动导入资料；不自动抓论文、新闻或社媒。
- 每轮 Agent 输出必须能直接给产品经理看懂：结论、支持理由、反对理由、关键证据、最大风险、下一步动作和待审批事项。
- 知识库只写入研究结论、失败原因、状态变化、投委会分歧和用户审批记录，不把所有技术日志都塞进去。
- 一轮 Agent 研究最多推进到“给出下一步动作”，不能同轮无限递归自我继续。
- 连续两轮同类失败且没有新证据时，候选必须进入观察或淘汰。
- 产品边界确认到当前版本收敛；后续先做架构借鉴和 OpenSpec 准入，再进入实现拆解和开发。只有真钱实盘、密钥安全、不可逆操作或重大技术路线分叉才重新请求确认。

更完整的架构和技术选型记录见 `docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`。实现前架构借鉴准入评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md` 和 `openspec/changes/p0-agent-runtime-web-workbench/`。

已有资产盘点结论见 `docs/AGENT_MVP_ASSET_INVENTORY.md`：数据、因子、验证、walk-forward、回测、实验账本、知识库和测试都要复用；定时器、Run MVP 口径、早期状态文档和空占位包已经从当前 Agent MVP 主线归档。

## Web MVP 形态

Kronos Web MVP 应该是研究工作台，而不是粗糙日志页。

MVP 打开方式：

```text
启动本地 Kronos Web 服务
-> 用浏览器打开本地研究工作台
```

桌面 App 后置。浏览器关闭不等于 Agent 停止，真正运行主体是后端 Agent Supervisor。

第一版至少包含六块产品信息架构：

1. **候选资产看板**：低频刷新，显示候选、来源、生命周期状态、评分、证据、最大问题和下一步。
2. **Agent 工作流时间线**：准实时展示唯一当前主研究任务在做什么，事件分为 info / decision / warning / approval_required / error，但不刷屏。
3. **候选详情页**：展示迁移审查、回测、滚动验证、Agent 分歧、失败原因、投委会结论和状态变更记录。
4. **设置页**：配置 LLM provider、模型、API Key、角色启停和 prompt 版本。
5. **材料导入**：上传或粘贴策略说明、因子说明、论文摘要和交易复盘。
6. **审批中心**：处理 prompt 生效、候选进入模拟盘、候选申请真钱实盘。

Web 首版打开后必须能回答五个问题：现在在研究什么，为什么研究它，证据是什么，下一步是什么，哪里需要用户审批。

技术方向：

- 后端：FastAPI + Uvicorn。
- 前端：Next.js App Router + TypeScript。
- UI：shadcn/ui + Tailwind + Radix。
- 数据刷新：TanStack Query。
- 候选池表格：TanStack Table。
- 图表：Apache ECharts。
- Agent 动态：MVP 先用 SSE，未来需要双向控制再评估 WebSocket。
- 模型配置：Web 设置页配置，后端 SecretStore 本地保存和调用，不把密钥放在前端。
- Prompt 生效：新版本先保存为草稿，人工确认后成为 active；MVP 每个角色只启用一个 active 模型。

MVP 是功能最小化的可行产品，不是产品逻辑和工程扩展性都最低的临时看板。

## 当前最新进展

### Agent MVP 已启动

已新增 Agent 入口：

```bash
kronos agent propose
kronos agent status
kronos agent conclude
kronos agent run-once
```

它当前能读取上一轮确定性研究结果，自动完成：

- 选择下一轮候选。
- 提出下一轮研究假设。
- 生成可执行实验计划。
- 明确成功标准、失败标准和人工闸门。
- 把 Agent 计划写入研究知识库。

另一个入口 `kronos agent conclude` 已经能读取专项证据结果，输出 Agent 处置建议，并写入研究知识库。

Batch 2 之后，`kronos agent status` 已经能显示当前是否有 Agent 主任务在运行、当前 run、当前 task、上一条事件和 pending 数量。它还不是完整后台常驻服务，但已经具备后续 Web 时间线和控制台状态页的本地状态骨架。

Batch 3 之后，系统已经具备 Agent 角色注册、Prompt 草稿 / 生效版本、本地 SecretStore 脱敏状态和 DeepSeek provider 适配。没有 DeepSeek key 时不会卡死，而是返回“待配置”；有 key 后也不会把明文密钥写入事件、报告或测试快照。

Batch 4 之后，系统已经能用白名单确定性工具串起一轮 Agent 研究：先生成计划，再读取专项证据，最后输出 Agent 总报告、summary 和事件时间线。它不会在同一轮里无限自我递归，也不会进入组合、风控或实盘。

Batch 5 之后，系统已经有本地 FastAPI 后端：Web 可以通过 API 读取候选池、Agent 状态、事件时间线、SSE 流、masked LLM 设置、材料导入和审批事件。API 不返回明文密钥，材料导入也不会直接绕过迁移审查或进入交易链路。

Product UX Repair Batch 第一批之后，系统已经有本地 Next.js 研究工作台，并且默认读取 Agent MVP 交付批次：浏览器第一屏可以看到当前状态、结论来源、下一步动作、候选池入口、可阅读报告、模型设置、材料导入和审批中心。它已经从“工程能力展示页”推进为“可走通第一层产品任务流”的本地工作台，但真正的下一轮 Agent 启动、候选证据挂载和更完整的图表化报告仍未完成。

最新 Agent MVP 批次：

- 批次：`20260428-agent-mvp-v1`
- 输入：`20260427-run-mvp-v1-research` 的上一轮研究摘要
- 结果：选择 2 个下一轮候选，形成 4 个研究假设
- 计划报告：`reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.md`
- 计划 JSON：`reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.json`
- 结果读取批次：`20260428-agent-mvp-v1-decision`
- 决策报告：`reports/research/experiments/20260428-agent-mvp-v1-decision/agent_research_decision.md`
- 单轮闭环批次：`20260430-agent-cycle-v1`
- 单轮闭环报告：`reports/research/experiments/20260430-agent-cycle-v1/agent_run_report.md`
- 单轮闭环摘要：`reports/research/experiments/20260430-agent-cycle-v1/agent_run_summary.json`
- Agent loop 验收批次：`20260430-agent-acceptance-v1`
- Agent loop 验收报告：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_report.md`
- Agent loop 验收摘要：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_summary.json`
- Agent loop 事件：`reports/research/experiments/20260430-agent-acceptance-v1/agent_events.jsonl`，6 条事件
- Web run summary API：`/api/agent/runs/20260430-agent-acceptance-v1/summary`
- Agent MVP 交付批次：`20260430-agent-mvp-delivery-v1`
- Agent MVP 交付报告：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md`
- Agent MVP 交付摘要：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_summary.json`
- Agent MVP 交付文档：`docs/AGENT_MVP_DELIVERY.md`

Agent 本轮选择的下一轮候选：

- `multi_timeframe_confirmation`：多时间框架确认。
- `trend_pullback_entry`：趋势内回踩入场。

Agent 给出的主要产品判断：

- 下一轮不应该每天重复跑同一批候选。
- 应先对观察名单候选做专项证据复盘。
- 10 个弱候选进入退休评审池。
- 研究方向应从旧策略参数微调转向 crypto-native 机制改造。
- 任何候选都不能绕过人工闸门进入组合或实盘。

Agent 读取专项证据后的新判断：

- `multi_timeframe_confirmation`：强支持切片 0 个，弱正向切片 1 个，仅保留观察。
- `trend_pullback_entry`：强支持切片 0 个，弱正向切片 5 个，适合进入候选改造，不进入组合或实盘。

### Run MVP 是工具底座

最新 Run MVP 批次 `20260427-run-mvp-v1` 证明底层工具能跑：

- 系统运行成功。
- 使用 BTC/ETH/SOL 各约 90.14 天、约 13 万根 1m K 线。
- 12 个旧策略候选全部完成评估。
- 0 个候选进入组合或实盘。
- 0 个 skipped。

这个结果的意义是：Agent 有确定性工具可以调用。它不能证明产品 MVP 已完成，因为产品 MVP 现在是 Agent 研究闭环。

## Qlib / RD-Agent 在 Kronos 里的位置

### Qlib 风格研究底座

状态：已形成 Agent 可调用工具箱。

产品含义：

- 让研究过程可复现、可比较、可审计。
- 用数据、验证、报告和实验记录判断策略，不靠感觉。
- 给 Agent 提供确定性工具，防止模型编造结论。

当前已落地：

- 数据接入。
- 因子计算。
- 候选验证。
- walk-forward。
- 回测基础版。
- 实验记录。
- 中文报告。
- 研究知识库。

### RD-Agent 风格研究 Agent

状态：当前 MVP 主线，已开始落地。

产品含义：

- 系统不只是验证用户指定的候选，还要主动提出下一步研究假设。
- Agent 负责“下一步研究什么”和“为什么研究它”。
- 确定性研究工具负责计算和验证。
- 人类负责关键闸门：候选退休、候选实现、组合接入和实盘。

当前已落地：

- `kronos agent propose`：从上一轮结果生成下一轮假设和实验计划。
- `kronos agent conclude`：读取确定性专项证据结果，输出观察 / 改造 / 退休 / 补数据建议。
- Agent 计划报告和 JSON。
- Agent 计划和 Agent 决策写入研究知识库。

当前还差：

- Agent 对失败记忆做更强约束，避免重复提出已失败方向。
- 新候选 proposal 到候选实现的人工审批流程。
- 完整 experiment ledger 串联、更多真实图表和 Batch 8 hardening。

## 产品阶段

### 阶段 0：架构借鉴与 OpenSpec 准入

状态：已完成。

完成标准：

- 架构借鉴评审能解释每个关键开源项目借鉴什么、不借什么、为什么，并明确不复制或直接接入 Agent 类项目。
- OpenSpec 明确约束 Agent runtime、Web research workbench、日志报告和技术治理。
- 下一批开发任务从 OpenSpec 拆出，而不是直接从会话讨论进入代码。
- 已有资产复用、适配、延期和主线归档边界清楚。

当前已完成：

- `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`
- `openspec/changes/p0-agent-runtime-web-workbench/`
- `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`
- `docs/AGENT_MVP_EXECUTION_PLAN.md`
- `docs/AGENT_MVP_ASSET_INVENTORY.md`
- `docs/ARCHIVE_INDEX.md`

下一步：

- 从执行计划中的 Batch 8 继续：做 hardening、报告模板打磨、错误分类、事件重放、secret 脱敏复查和 OpenSpec/TODO 风险收口。

### 阶段 1：Kronos Agent MVP

状态：进行中，Batch 7 已完成，下一步进入 hardening 和 release readiness。

完成标准：

- 给定一个研究目标，Agent 能提出下一轮研究假设。
- 假设能落成可执行实验。
- 实验结果来自确定性工具。
- Agent 能读结果并给出退休、观察、改造、深研或补数据建议。
- Agent 能把结论写入记忆，影响下一轮决策。
- Agent 不能绕过人工审批进入组合、风控或实盘。

当前已完成的第一步：

- 已有 `kronos agent propose`。
- 已生成 `20260428-agent-mvp-v1` Agent 研究计划。
- 已按 Agent 计划执行两个专项证据复盘。
- 已用 `kronos agent conclude` 读取专项证据并生成处置建议。
- 已用 `kronos agent run-once` 将计划、白名单工具执行、结果读取和 Agent 总报告串成单轮闭环。
- 已完成 Local Web API，后续 Web 第一屏可以读取候选池、Agent 状态、事件、设置、材料和审批数据。
- 已完成本地 Web 研究工作台，浏览器第一屏可以读取候选池、Agent 时间线、候选详情、模型设置、材料导入和审批中心。
- 已完成 Batch 7 Agent loop 集成验收：Web、报告、summary API、事件时间线和知识库都能追溯到同一批次 `20260430-agent-acceptance-v1`。

下一步：

- 把失败记忆纳入下一轮候选生成，避免重复研究。
- 做 Batch 8 收口，确认产品经理只通过 Web 和报告也能稳定验收真实 Agent run。

### 阶段 1S：Run MVP / 工具入口

状态：V0.1 已跑通。

业务含义：

- 证明系统能被启动。
- 证明底层研究工具能跑。
- 证明有状态报告和失败说明。
- 后续由 Agent 决定什么时候调用它，而不是机械每日运行。

### 阶段 2：旧策略资产迁移工厂

状态：第一轮迁移验证完成，等待产品评审。

当前结论：

- 旧策略不整包迁移，只作为候选因子矿。
- 34 个 legacy 策略已收束为 10 个因子家族和 12 个候选因子假设。
- 当前 12 个候选已完成 90 天级别 crypto 复验。
- 0 个候选进入组合或实盘。
- 10 个候选进入退休评审池。
- `multi_timeframe_confirmation` 和 `trend_pullback_entry` 进入下一轮 Agent 观察名单。
- 两个观察候选已完成专项证据复盘；`multi_timeframe_confirmation` 仅保留观察，`trend_pullback_entry` 适合进入候选改造但不进入组合或实盘。

下一步：

- 产品评审退休池。
- 围绕 `trend_pullback_entry` 做 crypto-native 改造 proposal。
- 围绕 funding、open interest、liquidation、多周期确认等 crypto-native 机制提出新候选。

### 阶段 3：组合与风控验证

状态：基础能力已有，但产品阶段未启动。

启动条件：

- 至少有一个候选通过完整研究验证。
- Agent 给出的候选处置通过人工闸门。

当前不要提前推进。

### 阶段 4：执行、监控和上线

状态：未开始。

启动条件：

- 有通过完整验证和风控审查的候选策略。
- 有人工审批、回滚和监控要求。

当前不要提前推进。

## 当前能做什么

- 可以拉取和检查真实 Binance 行情数据。
- 可以对 BTC、ETH、SOL 做旧策略候选研究。
- 可以跑 12 个 legacy candidate factors。
- 可以输出候选晋升、失败、观察和退休建议。
- 可以生成 PM 可读中文研究报告。
- 可以生成系统级运行状态页。
- 可以让 Agent 基于上一轮结果提出下一轮研究假设和实验计划。
- 可以让 Agent 读取专项证据结果并给出处置建议。
- 可以用一个 `kronos agent run-once` 命令跑完一轮 Agent 计划、确定性工具执行、结果读取和总报告。
- 可以通过本地 Web API 读取候选池、Agent 状态、Agent 事件、SSE 时间线、masked LLM 设置、材料导入和审批记录。
- 可以通过本地 Web 工作台读取 Batch 7 Agent loop 验收批次的研究目标、结论、风险、证据、报告和 6 条事件。
- 可以把 Agent 计划、Agent 决策和失败记忆写入研究知识库。

## 当前不能做什么

- 不能说整体 Agent MVP 已完成。
- 不能自动交易。
- 不能自动下单。
- 不能把旧 A 股 / 期货策略当作已经适配 crypto 的策略。
- 不能把当前 `auto-run` 当作产品核心。
- 不能让定时器替代 Agent 决策。
- 不能让 Agent 编造实验结果。
- 不能让 Agent 自动绕过人工审批进入组合或实盘。

## 下一次产品汇报看什么

下一次不汇报“写了哪些模块”，只汇报这些产品问题：

1. 产品经理只看 Web 第一屏和 `agent_run_report.md`，是否能判断本轮 Agent 做了什么。
2. Agent 结论、支持理由、反对理由、最大风险和下一步是否足够清楚。
3. 事件时间线是否能排查“Agent 做到哪一步”。
4. 知识库是否只沉淀研究结论，不污染原始技术日志。
5. 哪些动作需要产品经理人工确认。
6. Batch 8 后是否可以进入一次正式 MVP 验收。

## 当前默认推进口径

如果没有另行指定，默认按以下口径推进：

- 产品核心：Agent 研究闭环。
- 工具底座：Qlib 风格确定性研究工具。
- 研究方法：RD-Agent 风格假设和实验循环。
- 币种池：BTCUSDT、ETHUSDT、SOLUSDT。
- 输出：中文产品报告和 Agent 研究计划。
- 定时器：暂不安装，不作为 MVP 目标。
- 交易：不自动交易，不自动下单。
