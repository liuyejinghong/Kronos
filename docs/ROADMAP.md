# Kronos Roadmap

更新时间：2026-05-07

## 目标

Kronos 的路线图目标是把系统推进成 **加密货币策略研究 Agent**。

当前主线不是定时运行，也不是继续堆孤立模块，而是形成一条 Agent 研究闭环：

研究目标 -> 候选选择 -> 假设生成 -> 实验计划 -> 确定性工具验证 -> 结果解释 -> 记忆沉淀 -> 人工闸门

候选自身必须沿统一生命周期推进：

材料进入 -> 迁移审查 -> 假设 -> 实验计划 -> 验证中 -> Agent 分析 -> 投委会评分 -> 观察 / 改造 / 模拟盘 / 待实盘审批 / 淘汰

Qlib 风格能力是工具底座，RD-Agent 风格能力是当前 MVP 主线。

Agent 架构和技术选型记录见 `docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`。研发准入级架构借鉴评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。Agent/Web/OpenSpec 准入见 `openspec/changes/p0-agent-runtime-web-workbench/`。已有资产复用和归档边界见 `docs/AGENT_MVP_ASSET_INVENTORY.md`。v0.4.3 策略起草的版本需求与 OpenSpec 入口见 `docs/RELEASE_0.4.3_STRATEGY_AUTHORING.md` 和 `openspec/changes/p4-strategy-authoring/`。

## 路线图原则

1. Agent 是产品形态，定时器只是后续工具。
2. Agent 负责提出下一步研究问题，确定性工具负责验证。
3. 旧策略资产只作为候选因子和研究素材，不整包迁移。
4. 没有验证通过的候选，不进入组合、风控或实盘。
5. 所有 Agent 建议都必须能追溯到实验结果、失败记忆或明确假设来源。
6. 人工闸门必须保留在候选实现、候选退休、组合接入和实盘之前。
7. Agent 角色和 prompt 必须版本化，不能把第一版 prompt 当成长期固定资产。
8. LLM provider、模型和 API Key 应通过 Web 配置；实验真相仍来自确定性工具。
9. Prompt 新版本必须人工确认后才能 active；MVP 每个角色只启用一个 active 模型。
10. 首版优先接 DeepSeek，但 provider 抽象必须保留，API Key 由本地后端 SecretStore 保存。
11. MVP 材料池来自旧资产、候选池、失败记录、模拟盘日志和用户导入资料；不自动抓论文、新闻或社媒。
12. 知识库只写入研究结论、失败原因、状态变化、投委会分歧和用户审批记录。
13. 一轮 Agent 研究最多推进到下一步动作，不允许同轮无限递归。
14. 连续两轮同类失败且无新证据时，候选进入观察或淘汰。
15. 产品边界确认到当前版本收敛，后续进入实现；只有高风险或方向分叉事项才重新请求确认。
16. 实现前必须先完成同类 Agent 项目的架构借鉴评审和 OpenSpec 约束，避免重复造轮子或框架先行；架构借鉴不等于直接复制、接入或魔改上游项目。

## 阶段路线

### 阶段 A-1：Agent MVP 架构借鉴与 Spec 准入

目标：在产品代码实现前，把同类 Agent 项目的架构借鉴、基础设施依赖、日志报告和研发约束固定下来。

状态：已完成，后续只在新增框架依赖或重大路线变化时更新。

已完成：

- 新增研发准入级架构借鉴评审：`docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。
- 新增 OpenSpec change：`openspec/changes/p0-agent-runtime-web-workbench/`。
- 明确 RD-Agent、Qlib、TradingAgents、Freqtrade、LangGraph、CrewAI、Google ADK、OpenHands、DeepSeek、LiteLLM、OpenTelemetry、MCP、A2A 等项目的架构借鉴、基础设施依赖、后续评估和拒绝边界。
- 将结构化日志、Agent event timeline、PM 可读报告、机器摘要和错误报告写成 MVP 必需能力。
- 新增完整开发规划：`docs/AGENT_MVP_DEVELOPMENT_PLAN.md`。
- 新增执行级开发计划：`docs/AGENT_MVP_EXECUTION_PLAN.md`。
- 新增资产盘点和归档索引：`docs/AGENT_MVP_ASSET_INVENTORY.md`、`docs/ARCHIVE_INDEX.md`。

下一步：

- 产品验收 `docs/AGENT_MVP_DELIVERY.md` 和 Web 默认交付批次 `20260430-agent-mvp-delivery-v1`。
- 开发时复用已有数据、因子、验证、回测、实验账本、知识库和测试，不把定时器或 Run MVP 口径拉回产品核心。
- 新增框架依赖前，再确认触发条件、替代方案和验收证据。

### 阶段 A0.3：AI 自然语言策略起草

目标：把用户的自然语言策略想法转成可验证的策略草案，并沿现有 `validate → smoke-test → register → report` 链路推进。

状态：已完成。v0.4.3 首版只支持 R-breaker 日内突破模板；不支持任意策略代码生成、历史重放、模拟盘或实盘执行。

约束入口：

- 版本需求：`docs/RELEASE_0.4.3_STRATEGY_AUTHORING.md`
- OpenSpec：`openspec/changes/p4-strategy-authoring/`

已完成：

- 新增 `kronos strategy draft --prompt "..."`。
- 草案产出策略概要、trace JSON 和可编辑 TOML。
- 缺品种/周期时输出澄清问题；模板不支持时明确拒绝。
- 草案继续进入 `validate → smoke-test → register`，不绕过现有闸门。
- Agent console 新增“描述策略想法，先起草配置”分支。
- Docker 场景输出可复制的容器命令。

完成标准：

- R-breaker 相关自然语言输入能生成可校验 TOML 草案。
- 信息不足时不静默补全，而是输出澄清问题。
- 不支持模板不生成伪草案。
- 版本需求、OpenSpec、TODO、PROJECT_STATUS 和 CHANGELOG 口径一致。

### 阶段 A0：Kronos Agent MVP

目标：让 Kronos 从“能跑工具”升级为“能主动推进研究的 Agent”。

状态：Agent MVP Batch 8 已完成，当前进入产品验收。

已完成：

- 新增 `kronos agent propose`。
- Agent 能读取上一轮研究摘要。
- Agent 能选择下一轮候选。
- Agent 能生成研究假设和实验计划。
- Agent 能写出中文计划报告和 JSON。
- Agent 能把计划写入研究知识库。
- 已跑真实 Agent MVP 批次 `20260428-agent-mvp-v1`。
- 已按 Agent 计划执行两个专项证据复盘。
- 已新增 `kronos agent conclude`，读取专项证据结果并输出 Agent 处置建议。
- 已完成 Agent Runtime Skeleton：本地 Supervisor、单主任务队列、idle scanner、候选生命周期状态机、失败收敛和 `kronos agent status`。
- 已完成 Prompt / Role / LLM Provider / SecretStore：默认多角色、Prompt 草稿 / 生效版本、本地 SecretStore、DeepSeek provider 和 LLM 调用事件。
- 已完成 deterministic tool executor：白名单工具、工具执行记录、artifact path、错误记录和 secret-like 字段脱敏。
- 已新增 `kronos agent run-once`，把 Agent 计划、确定性工具执行、结果读取和 Agent 总报告串成单轮闭环。
- 已完成 Local Web API：FastAPI app factory、候选池、Agent 状态、事件列表、SSE、masked LLM settings、材料导入和审批事件记录。
- 已完成 Web Research Workbench：Next.js 本地前端、候选资产看板、Agent 时间线、候选详情、ECharts 候选分布、LLM 设置、材料导入和审批中心。
- 已完成 Agent Loop Integration Acceptance：真实本地材料跑通 `20260430-agent-acceptance-v1`，Web 第一屏、run summary API、事件时间线和报告读取同一轮结果。
- 已完成 Hardening and Release Readiness：错误分类、用户可读错误影响、时间线恢复、DeepSeek 配置状态接口、secret 脱敏复查、Web QA 和交付验收文档。

当前验收证据：

- Agent 计划报告：`reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.md`
- Agent 计划 JSON：`reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.json`
- Agent 输入：`20260427-run-mvp-v1-research` 的 90 天研究结果
- Agent 输出：2 个下一轮候选、4 个研究假设、10 个退休评审候选
- Agent 决策报告：`reports/research/experiments/20260428-agent-mvp-v1-decision/agent_research_decision.md`
- Agent 决策：`multi_timeframe_confirmation` 仅保留观察，`trend_pullback_entry` 进入候选改造
- Agent 单轮闭环报告：`reports/research/experiments/20260430-agent-cycle-v1/agent_run_report.md`
- Agent 单轮闭环摘要：`reports/research/experiments/20260430-agent-cycle-v1/agent_run_summary.json`
- Agent loop 验收报告：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_report.md`
- Agent loop 验收摘要：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_summary.json`
- Agent loop 事件：`reports/research/experiments/20260430-agent-acceptance-v1/agent_events.jsonl`，6 条事件
- Web run summary API：`/api/agent/runs/20260430-agent-acceptance-v1/summary`，200 OK
- Agent MVP 交付批次：`20260430-agent-mvp-delivery-v1`
- Agent MVP 交付报告：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md`
- Agent MVP 交付文档：`docs/AGENT_MVP_DELIVERY.md`
- DeepSeek 配置状态 API：`/api/settings/llm/providers/deepseek/status`，200 OK
- Local Web API 测试：`tests/integration/web`，`11 passed`
- Web Workbench 前端检查：`npm run typecheck`、`npm run lint`、`npm run build`
- Web Workbench 浏览器验收：桌面和 390px 窄屏可读，候选池、Agent 时间线、候选详情、设置、材料导入和审批中心可读

下一步：

- 产品验收 Agent MVP 交付批次。
- 让 Agent 用知识库避免重复提出已失败且无新证据的方向。
- 建立候选评分维度和更强的失败记忆约束。
- 围绕 `trend_pullback_entry` 设计 crypto-native 改造 proposal。

完成标准：

- 给定研究目标，Agent 能提出下一轮研究假设。
- 假设能落成可执行实验。
- 实验结果来自确定性工具。
- Agent 能读结果并给出退休、观察、改造、深研或补数据建议。
- Agent 能把结论写入记忆，影响下一轮决策。

### 阶段 A0S：Run MVP / 工具入口

目标：证明底层工具能被启动，并能输出产品可读状态。

状态：V0.1 已完成，作为 Agent 工具底座保留。

已完成：

- 顶层入口 `kronos run today`。
- 默认 BTC/ETH/SOL、1m K 线、90 天最低历史、本地数据优先、不自动交易。
- 系统级状态页 `kronos_run_status.md`。
- 缺数据失败说明。
- 真实批次 `20260427-run-mvp-v1` 跑通。

注意：

- Run MVP 不是当前产品 MVP。
- `research auto-run` 不是产品核心。
- 定时器不作为当前阶段目标。

### 阶段 A0W：本地 Web 研究工作台

目标：让产品经理通过 Web 验收 Kronos，而不是通过 CLI 日志判断进度。

状态：首版已完成，并已接入 Agent loop 验收批次。

第一版范围：

- 候选资产看板。
- Agent 工作流时间线。
- 候选详情页。
- 人工闸门状态展示。
- 候选生命周期状态和状态变更记录。
- Agent 角色、prompt 版本和 LLM 设置页。
- 材料导入入口。
- 审批中心。
- 候选评分维度：总评分、研究价值、稳定性、风险、证据质量、Agent 分歧。
- Event timeline 级别：info / decision / warning / approval_required / error。

技术选型：

- FastAPI + Uvicorn。
- Next.js App Router + TypeScript。
- shadcn/ui + Tailwind + Radix。
- TanStack Query / Table。
- Apache ECharts。
- SSE。

完成标准：

- 用户打开本地 Web 后能看懂当前候选池、Agent 当前动作、候选证据、最大问题和下一步。
- MVP 以本地 Web 服务 + 浏览器打开，不做桌面 App。
- 浏览器关闭不等于 Agent 停止；真正的运行主体是后端 Agent Supervisor。
- Web 保留未来远程访问和权限化扩展边界。
- Web 能配置 DeepSeek 等 LLM provider、模型和 API Key；密钥不出现在前端代码、事件时间线或报告里。
- Web 能上传或粘贴策略说明、因子说明、论文摘要和交易复盘。
- Web 能展示 prompt 生效、进入模拟盘、申请真钱实盘三类审批事项。
- Web 首版能回答：现在在研究什么、为什么研究它、证据是什么、下一步是什么、哪里需要用户审批。

### 阶段 B：旧策略资产迁移验证

目标：把本地 A 股 / 期货机构级策略资产从“历史资产”变成“crypto 可验证候选来源”。

状态：第一轮验证完成，等待产品评审。

已完成：

- 34 个 legacy 策略收束为 10 个因子家族和 12 个候选因子假设。
- 当前 12 个候选已进入 Kronos 候选库。
- 90 天级别 crypto 真实数据验证完成。
- 0 个候选晋升，0 个进入组合或实盘。
- Agent 已基于上一轮结果选出 `multi_timeframe_confirmation` 和 `trend_pullback_entry` 作为下一轮观察候选。
- 两个观察候选已完成专项证据复盘；`multi_timeframe_confirmation` 仅保留观察，`trend_pullback_entry` 适合进入候选改造但不进入组合或实盘。

下一步：

- 产品评审 10 个退休候选。
- 围绕 `trend_pullback_entry` 做 crypto-native 改造 proposal。
- 围绕 funding、open interest、liquidation、多周期确认等 crypto-native 机制提出新候选。

### 阶段 C：研究工具底座增强

目标：继续强化 Agent 可调用的确定性工具。

状态：持续增强。

优先项：

- 观察名单专项证据复盘。
- liquidation 数据接入。
- 更多实验流自动进入 ledger 和知识库。
- 更清晰的 PM 可读报告。
- Freqtrade 真实外部 crosscheck 自动化。

不优先：

- 复杂优化器。
- ML 因子平台。
- 语义检索。
- 多交易所抽象。

### 阶段 D：组合与风控深化

目标：把通过验证的候选接到组合和风控。

状态：等待阶段 A0/B 产出有效候选后启动。

启动条件：

- 至少有一个候选通过完整研究验证。
- Agent 给出的候选处置通过人工闸门。
- 风控输入能回溯到诊断、walk-forward 或市场状态。

### 阶段 E：执行、监控和上线治理

目标：从研究系统进入可交易系统。

状态：暂缓。

启动条件：

- 研究闭环稳定。
- 组合风控链路稳定。
- 有通过完整验证和人工审批的候选策略。

## 当前推荐顺序

1. 产品验收 Agent MVP 交付文档：`docs/AGENT_MVP_DELIVERY.md`。
2. 打开 Web 工作台读取 `20260430-agent-mvp-delivery-v1`，确认候选池、Agent 摘要、event timeline、artifact references、masked settings、DeepSeek 配置状态和审批入口一致。
3. 产品评审 Agent MVP 交付报告：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md`。
4. 产品评审退休候选池。
5. 围绕 `trend_pullback_entry` 设计 crypto-native 改造 proposal。
6. 在没有候选通过前，不推进组合、风控、执行或定时器。

## 暂缓事项

- 不安装每日定时器作为 MVP。
- 不做自动交易。
- 不做自动下单。
- 不急着扩通知渠道。
- 不急着上复杂优化器或 ML 因子平台。
- 不把旧策略仓库整包搬进 Kronos。

## 每轮推进前检查

每次开始一个模块前，先回答：

1. 这一步是否服务 Agent 研究闭环？
2. 它是否让 Agent 更会选择、假设、实验、读结果或记忆？
3. 它是否只是定时重复运行？
4. 它是否会绕过人工闸门？
5. 完成后用什么报告、JSON、测试或知识库记录证明？
