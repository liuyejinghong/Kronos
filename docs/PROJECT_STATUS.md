# Kronos Project Status

更新时间：2026-05-05

## 一句话判断

2026-05-05 外部交易者视角全新试用已完成，记录见 `docs/EXTERNAL_TRADER_ONBOARDING_REVIEW_20260505.md`。结论是：当前 Agent/Web 对内部验收可理解，但全新用户还不能从 README 路径直接完成“跑一个 BTC 策略看看”。最高优先级需要从内部交付批次验收转向首次使用闭环修复：`quickstart` 必须跑出一个内置示例策略结果，README 主路径应改为 quickstart，Web 全新 clone 不应默认指向不存在的交付批次，Web 启动说明要覆盖前后端、依赖安装、API 地址和 localhost / 127.0.0.1 差异，并补齐本地 Docker 部署资产。

Kronos 已经从“让系统能跑”切换到 **Agent MVP** 阶段。架构借鉴、OpenSpec 准入、开发批次拆分、执行级任务拆分和旧资产盘点都已完成，Agent MVP Batch 1 到 Batch 8 已完成。

当前产品目标不是每天自动运行，也不是继续让单个研究模块变强，而是让 Kronos 成为能主动推进研究的加密货币策略研究 Agent：读上一轮结果，选下一轮方向，提出假设，生成实验，调用确定性工具，读结果，写记忆，并保留人工闸门。

最新产品架构共识：Kronos 应是本地优先、未来可远程化的常驻 Agent 软件。后端 Agent Supervisor 负责持续运行、研究队列、idle 巡检、候选生命周期状态机、Agent 角色版本、材料池、审批闸门、失败收敛和事件时间线；Web 是产品控制台，第一屏应展示候选资产看板、Agent 工作流时间线、候选详情页、状态变更记录、模型设置、材料导入、审批中心和候选评分维度。

产品边界确认到当前版本收敛。实现前置门槛已经补齐：架构借鉴评审、OpenSpec 约束、开发任务拆分和资产盘点都已落地。Batch 1 已固定 Agent 的基础契约、事件记录和报告产物；Batch 2 已补上本地 Agent Supervisor、单主任务队列、idle scanner、候选生命周期状态机、失败收敛和 CLI 状态查询；Batch 3 已补上角色注册、Prompt 版本、SecretStore、DeepSeek provider 和 LLM 调用事件；Batch 4 已补上确定性工具白名单、工具执行记录、选择性知识库写入规则和 `kronos agent run-once` 单轮闭环；Batch 5 已补上本地 FastAPI 后端、Web API schema、候选/Agent/事件/设置/材料/审批接口和 SSE；Batch 6 已补上本地 Next.js 研究工作台前端；Batch 7 已用真实本地材料跑通 Agent loop 集成验收，并让 Web 第一屏读取同一轮 Agent 摘要、事件和报告；Batch 8 已完成错误分类、时间线恢复、DeepSeek 配置状态检查、secret 脱敏复查、Web QA 和交付验收文档。当前进入产品验收。

Agent 架构和技术选型记录见 `docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`。研发准入级架构借鉴评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。Agent/Web/OpenSpec 准入见 `openspec/changes/p0-agent-runtime-web-workbench/`。完整开发规划见 `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`，执行级任务拆分见 `docs/AGENT_MVP_EXECUTION_PLAN.md`。已有资产复用和归档边界见 `docs/AGENT_MVP_ASSET_INVENTORY.md` 与 `docs/ARCHIVE_INDEX.md`。

## 当前阶段

| 层级 | 当前状态 | 业务意义 | 主要缺口 |
|---|---|---|---|
| 架构借鉴与 Spec 准入 | 已完成 | 已明确从哪些 Agent / 量化项目借鉴架构、哪些不直接接入，以及 Agent/Web/日志/报告如何验收 | 后续只在新增框架或重大路线变化时更新 |
| 开发规划 | 已完成 | 已把 Agent MVP 拆成 8 个开发批次，并补充每批硬退出条件，防止长期卡在 Batch 1 | 执行时按 `AGENT_MVP_EXECUTION_PLAN.md` 的任务 ID 推进 |
| 执行级任务拆分 | 已完成 | 每个 Batch 已拆成任务 ID、文件边界、输入输出、验收和禁止扩展项；Batch 1 到 Batch 8 已完成 | 下一步按验收反馈进入下一阶段 |
| 旧资产盘点 | 已完成 | 已确认数据、因子、验证、回测、实验账本、知识库和测试可复用；定时器、Run MVP 口径和空占位包已归档出主线 | 后续开发前先查资产清单，避免重复造轮子 |
| Agent MVP | Batch 8 已完成，可验收 | 已能从上一轮研究结果生成下一轮研究假设、读取专项证据、通过白名单确定性工具形成单轮 Agent 总报告；本地 Web 能读取本轮 Agent 摘要、事件时间线、候选池、设置、材料、审批和 DeepSeek 配置状态 | 下一步由产品验收决定是否进入候选评分、失败记忆约束和真实图表增强 |
| 首次使用闭环 | 外部交易者试用未通过 | 全新 clone 能安装、能生成 BTCUSDT 样例数据、能打开 Agent 和 Web；但没有内置可运行示例策略，`agent start` / `kronos run today` 都停在没有候选策略/因子 | P0 修复 quickstart 最小策略结果、README 主路径、完整示例策略和 Web 空状态 |
| Run MVP | V0.1 已跑通 | 证明系统入口、数据检查、研究工具和状态报告可用 | 现在只是 Agent 工具底座，不是产品终点 |
| 旧策略资产迁移 | 第一轮验证完成 | 12 个 legacy 候选已完成 90 天 crypto 复验 | 10 个候选待退休评审，2 个观察候选待专项复盘 |
| Web 研究工作台 | 首版可验收 | 已有 FastAPI 后端和 Next.js 本地前端，可展示候选池、Agent 时间线、候选详情、Agent run brief、ECharts 候选分布、masked LLM settings、DeepSeek 配置状态、材料导入和审批中心 | 下一步补更多真实研究图表、角色启停联动和审批项生成 |
| 研究工具底座 | 基础可用 | 数据、因子、验证、walk-forward、回测、报告、知识库可被 Agent 调用 | liquidation、更多实验入账和更强报告仍需增强 |
| 组合风控 | 基础能力已有 | 等通过验证的候选出现后可承接 | 当前没有候选可进入组合 |
| 执行上线 | 未开始 | 未来交易执行、监控、上线治理 | 当前不应推进 |

## 最新 Agent MVP 证据

| 项目 | 结果 |
|---|---|
| Agent 入口 | `kronos agent propose` |
| 最新批次 | `20260428-agent-mvp-v1` |
| 输入来源 | `reports/research/experiments/20260427-run-mvp-v1-research/auto_run_summary.json` |
| 选择候选 | `multi_timeframe_confirmation`、`trend_pullback_entry` |
| 研究假设 | 4 个 |
| 退休评审池 | 10 个候选 |
| 计划报告 | `reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.md` |
| 计划 JSON | `reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.json` |
| 专项证据 | `multi_timeframe_confirmation` 和 `trend_pullback_entry` 已按 Agent 计划执行 |
| Agent 决策批次 | `20260428-agent-mvp-v1-decision` |
| Agent 决策报告 | `reports/research/experiments/20260428-agent-mvp-v1-decision/agent_research_decision.md` |
| Agent 单轮闭环批次 | `20260430-agent-cycle-v1` |
| Agent 单轮闭环报告 | `reports/research/experiments/20260430-agent-cycle-v1/agent_run_report.md` |
| Agent 单轮闭环摘要 | `reports/research/experiments/20260430-agent-cycle-v1/agent_run_summary.json` |
| Agent loop 验收批次 | `20260430-agent-acceptance-v1` |
| Agent loop 验收报告 | `reports/research/experiments/20260430-agent-acceptance-v1/agent_run_report.md` |
| Agent loop 验收摘要 | `reports/research/experiments/20260430-agent-acceptance-v1/agent_run_summary.json` |
| Agent loop 验收事件 | `reports/research/experiments/20260430-agent-acceptance-v1/agent_events.jsonl`，6 条事件 |
| Agent MVP 交付批次 | `20260430-agent-mvp-delivery-v1` |
| Agent MVP 交付报告 | `reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md` |
| Agent MVP 交付摘要 | `reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_summary.json` |
| Agent MVP 交付事件 | `reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_events.jsonl`，6 条事件 |
| Web run summary API | `/api/agent/runs/20260430-agent-acceptance-v1/summary`，200 OK |
| Web 交付 run summary API | `/api/agent/runs/20260430-agent-mvp-delivery-v1/summary`，200 OK |
| DeepSeek 配置状态 API | `/api/settings/llm/providers/deepseek/status`，200 OK，当前为 `waiting_configuration` |
| 记忆沉淀 | 本轮只保留 2 条 Agent 研究记忆：`agent_research_plan` 和 `agent_research_decision` |

Agent 本轮结论：

- 不安装定时器。
- 不每天重复跑同一批候选。
- 已对观察名单候选做专项证据复盘。
- 已能用 `kronos agent run-once` 把计划、工具执行、结果读取和总报告串成一轮。
- `multi_timeframe_confirmation` 仅保留观察。
- `trend_pullback_entry` 进入候选改造，不进入组合或实盘。
- 大部分旧策略候选进入退休评审池。
- 下一轮应从旧策略参数微调转向 crypto-native 机制改造。

## Run MVP 证据

| 项目 | 结果 |
|---|---|
| 入口 | `kronos run today` |
| 批次 | `20260427-run-mvp-v1` |
| 状态 | 成功 |
| 数据样本 | BTC/ETH/SOL 各约 90.14 天、约 13 万根 1m K 线 |
| 研究结果 | 12 个候选完成评估，0 个晋升，0 个 skipped |
| 状态报告 | `reports/research/experiments/20260427-run-mvp-v1/kronos_run_status.md` |

解释：

- 这个批次证明底层工具能跑。
- 这个批次不等于 Agent MVP 完成。
- 后续是否运行，由 Agent 的研究计划决定，不由定时器决定。

## 项目控制台

| 模块 | 状态 | 已有能力 | 下一步 |
|---|---|---|---|
| Agent 研究闭环 | Batch 7 已完成 | 能读取上一轮结果，生成假设、执行白名单确定性工具、读取专项证据结果，并输出 Agent 总报告、事件和 summary；Web 工作台已能读取本轮摘要、证据、风险、下一步和时间线 | Batch 8 做 hardening、报告打磨、剩余风险收口 |
| 数据层 | 基础完成 | Binance USDM 拉取、Parquet 存储、查询、覆盖率、gap 检查 | 按 Agent 需求补 liquidation 等数据 |
| 因子平台 | 进行中 | 因子协议、注册、物化、缓存、验证、候选生命周期 | 服务 Agent 新候选 proposal |
| 旧策略迁移 | 第一轮完成 | 12 个候选已完成 90 天复验 | 退休评审和观察名单专项复盘 |
| 信号诊断 | 进行中 | IC、Rank IC、ICIR、分组收益、换手、衰减 | 输出更适合 Agent 读取的摘要 |
| 回测引擎 | 基础完成 | 研究型回测、成本、资金费率钩子、指标、Freqtrade bridge | 等 Agent 提出可验证候选后使用 |
| 实验管理 | 进行中 | run_id、ledger、DuckDB 查询、artifact 目录 | Agent 每轮计划和结果都应入账 |
| 知识库 | 初版完成 | SQLite + FTS 记录实验、失败、候选处置、Agent 计划 | 收紧为只沉淀研究结论、失败原因、状态变化、投委会分歧和用户审批记录 |
| 组合风控 | 基础能力已有 | 目标仓位、规则 allocator、风险 verdict | 等候选通过验证后启动 |

## 当前验证快照

| 验证项 | 结果 |
|---|---|
| Agent Batch 4 测试 | `tests/unit/agent` 和 `tests/integration/test_cli.py::TestAgentCLI` 已通过 |
| Web API Batch 5 测试 | `tests/integration/web` 通过，`11 passed` |
| Web Workbench Batch 6 前端检查 | `npm run typecheck`、`npm run lint`、`npm run build` 通过 |
| Web Workbench Batch 6 浏览器验收 | Playwright 验证桌面和 390px 窄屏无整页横向溢出；候选池、Agent 时间线、候选详情、设置、材料导入、审批中心可读 |
| Agent Loop Batch 7 测试 | `92 passed`，覆盖 `tests/unit/agent`、`tests/unit/research/knowledge_base`、CLI run-once 和 Web routes |
| Agent Loop Batch 7 后端检查 | `ruff` 通过，`mypy kronos/agent kronos/research/knowledge_base kronos/web cli` 通过 |
| Agent Loop Batch 7 前端检查 | `npm run typecheck`、`npm run lint`、`npm run build` 通过 |
| Agent Loop Batch 7 浏览器验收 | Playwright 验证桌面和 390px 窄屏均能读取 `20260430-agent-acceptance-v1`、Agent brief、结论和 6 条事件，且无整页横向溢出 |
| Release Readiness Batch 8 后端检查 | `ruff` 通过，`mypy kronos/agent kronos/web` 通过，Batch 8 targeted tests `45 passed` |
| Release Readiness Batch 8 前端检查 | `npm run typecheck`、`npm run lint`、`npm run build` 通过 |
| Release Readiness Batch 8 浏览器验收 | Playwright 验证桌面和 390px 窄屏均能读取 `20260430-agent-mvp-delivery-v1`、Agent 结论和 DeepSeek 配置状态，且无整页横向溢出 |
| Release Readiness Batch 8 安全复查 | 交付批次 report/event/runtime secret 扫描无命中，`git diff --check` 通过 |
| 项目级 ruff | 通过，覆盖 `kronos tests cli` |
| 项目级 mypy | 通过，覆盖 `113 source files` |
| 项目级非 E2E 测试 | `487 passed, 5 deselected` |
| 上轮全量测试含真实 E2E | `399 passed` 快照，本轮未重跑真实 E2E |

## 当前最高优先级

1. 首次使用闭环修复：让全新用户执行 README 主路径后能跑出一个 BTC 示例策略结果，证据见 `docs/EXTERNAL_TRADER_ONBOARDING_REVIEW_20260505.md`。
2. README 和 quickstart 口径收敛：主路径优先 `uv run kronos quickstart`，并说明 Web 后端、前端依赖、API 地址、端口冲突、localhost / 127.0.0.1 差异和 DeepSeek 配置边界。
3. Web 全新 clone 空状态修复：没有 `reports/` 时不要默认展示 `20260430-agent-mvp-delivery-v1`，而是引导运行 quickstart 或导入已有报告。
4. 补 Docker 本地部署资产：Dockerfile / compose / `.env.example` / 健康检查，满足“本地 Docker 全新部署”试用。
5. 暂不推进组合风控、执行或实盘。

## 维护规则

- `ROADMAP.md`：阶段计划和优先级
- `TODO.md`：可执行待办
- `CLAUDE.md`：开发指南
