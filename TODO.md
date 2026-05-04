# Kronos TODO

更新时间：2026-05-04

真实进度来源：`docs/PROJECT_STATUS.md`、`docs/IMPLEMENTATION_STATUS.md`、`docs/ROADMAP.md`、`findings.md`。
状态标记：`done` 已完成 · `partial` 部分完成 · `todo` 待办 · `verify` 待验证 · `blocked` 阻塞

---

## P0 — Agent MVP & Web 研究工作台

### Agent MVP 核心闭环

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 1 | `done` | Agent 模块骨架、类型系统、事件时间线、报告/错误输出 | `kronos/agent/`、`tests/unit/agent/` |
| 2 | `done` | Agent Supervisor：本地队列、idle scanner、单主任务生命周期、候选状态机、CLI status | `kronos/agent/supervisor.py` |
| 3 | `done` | Agent 角色注册、Prompt 版本化（草稿/生效）、SecretStore、DeepSeek provider | `kronos/agent/roles.py`、`prompts.py`、`secrets.py`、`llm.py` |
| 4 | `done` | 材料池模型：旧资产、候选池、失败记录、用户导入 | `kronos/agent/types.py` |
| 5 | `done` | 确定性工具执行白名单、artifact 记录、`kronos agent run-once` 单轮闭环 | `kronos/agent/tools.py`、`planner.py` |
| 6 | `done` | 单轮 guardrail：一轮只推进到下一步动作，不递归 | `kronos/agent/planner.py` |
| 7 | `done` | 失败收敛：两轮同类失败且无新证据 → 候选进入观察/淘汰 | `kronos/agent/state_machine.py` |
| 8 | `done` | Batch 7 Agent loop 集成验收 `20260430-agent-acceptance-v1` | `reports/research/experiments/20260430-agent-acceptance-v1/` |
| 9 | `done` | Batch 8 Hardening：错误分类、时间线恢复、DeepSeek 状态、secret 审计、Web QA | `docs/AGENT_MVP_DELIVERY.md` |
| 10 | `done` | Agent 交付批次 `20260430-agent-mvp-delivery-v1`，6 条事件 | `reports/agent_runtime/agent_supervisor_status.json` |
| 11 | `todo` | 候选评分维度：总评分、研究价值、稳定性、风险、证据质量、Agent 分歧 | — |
| 12 | `todo` | 人工审批门禁：候选进入组合/风控/实盘前必须过人工 gate | — |
| 13 | `todo` | 不加 LangGraph / CrewAI / Google ADK / LiteLLM / OpenTelemetry 为运行时依赖（除非触发条件满足） | `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md` |

### Web 研究工作台

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 14 | `done` | FastAPI 后端、候选池/Agent/事件/设置/材料/审批路由、SSE | `kronos/web/`、`tests/integration/web/`（11 passed） |
| 15 | `done` | Next.js 16 前端：候选看板、Agent 时间线、候选详情、设置、材料导入、审批中心 | `web/`、Playwright 验收通过 |
| 16 | `done` | Web 第一屏 PM 验收检查：研究目标、原因、证据、下一步、待审批 | `web/components/run-brief-panel.tsx` |
| 17 | `done` | DeepSeek 配置状态 API `/api/settings/llm/providers/deepseek/status` | `kronos/web/routes/settings.py` |
| 18 | `done` | Product UX Repair 第一批：主任务流、报告阅读、候选池信息架构、模型状态信任 | `docs/AGENT_MVP_PRODUCT_UX_REVIEW.md` |
| 19 | `todo` | 更丰富的真实实验图表（目前只有候选分布和 Agent 简报） | — |

### Run MVP / 系统入口

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 20 | `done` | `kronos run today` 顶层入口 + 默认 profile | `cli/main.py`、`kronos/run_mvp.py` |
| 21 | `done` | Run MVP V0.1 真实批次 `20260427-run-mvp-v1`（BTC/ETH/SOL 约 90 天） | `reports/research/experiments/20260427-run-mvp-v1/` |
| 22 | `done` | PM 可读状态报告：是否跑完、什么数据、什么报告、什么结论、下一步 | `docs/MVP_ACCEPTANCE.md` |
| 23 | `todo` | Product-review Run MVP 状态报告首屏，确认 V0.1 验收 | — |
| 24 | `todo` | 仅当 Agent MVP 有新假设或监控需求时才考虑调度式运行；不默认安装每日定时 | — |

---

## P1 — 数据层 & 因子平台 & 回测引擎

### 数据层

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 25 | `done` | 项目骨架、配置加载、日志、异常层次 | `kronos/common/` |
| 26 | `done` | 数据 Schema（Candle/Funding/OI）、Parquet 分区存储、DuckDB 查询层、PIT-safe loading | `kronos/data/` |
| 27 | `done` | Binance USDM REST adapter（httpx + SOCKS 代理）、sync pipeline、CLI | `kronos/data/loaders/binance_usdm.py`、`kronos/data/sync.py` |
| 28 | `done` | 覆盖率查询、gap 检测、raw NDJSON 审计追踪 | `kronos/data/storage/query.py` |
| 29 | `done` | 真实 E2E 在 SOCKS 代理环境下通过，fetch 窗口有界 | `tests/integration/test_sync_pipeline.py` |
| 30 | `done` | 移除 deprecated `binance-futures-connector`、Polars 依赖 | `docs/MODULE_PLAN_INDEX.md` |
| 31 | `todo` | Binance 模块化 SDK spike（新增数据端点或执行层前必做） | `docs/BINANCE_CONNECTOR_MIGRATION.md` |
| 32 | `verify` | 数据层重采样对标交易所原生响应（如该需求仍有效） | — |

### 因子平台

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 33 | `done` | Factor Protocol、BaseFactor、显式注册 Registry、compute_all() 跨标的 rank 归一化 | `kronos/common/types.py`、`kronos/factor/` |
| 34 | `done` | 17 个种子因子、5 个家族、3 个 default（ASI/CMO/Funding Regime） | `kronos/factor/bootstrap.py` |
| 35 | `done` | 因子物化、缓存、PIT-safe 低频 join | `kronos/factor/materialize.py`、`registry.py` |
| 36 | `done` | 验证 pipeline：指标计算、阈值配置、Alphalens 适配、tear sheet 导出 | `kronos/factor/validation/` |
| 37 | `done` | 验证报告目录契约：`reports/factor_validation/{name}/{version}/` | `kronos/factor/validation/reporting.py` |
| 38 | `done` | Registry status() 暴露缓存覆盖率和最新物化时间戳 | `kronos/factor/registry.py` |
| 39 | `partial` | 部分 spec 命名对齐仍有差距（如 Factor 协议位置与 task 文件不同） | `docs/IMPLEMENTATION_STATUS.md` |

### 回测引擎

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 40 | `done` | 回测模块完整：config、engine、validators、ranking、weights、returns、costs、trades、metrics、reporting | `kronos/research/backtest/` |
| 41 | `done` | Freqtrade 交叉验证 bridge + lookahead 分析 wrapper | `kronos/research/backtest/freqtrade_bridge.py` |
| 42 | `done` | 模块级验收映射 + 已知限制文档 | `docs/BACKTEST_ENGINE_ACCEPTANCE.md` |
| 43 | `partial` | Bridge 构建 Freqtrade 命令但不执行外部工具 | 已知限制 |

---

## P2 — 因子家族 & 诊断 & Walk-forward & 实验管理

### 因子家族扩展

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 44 | `done` | 14 个新因子实现（body_energy、bar_close_pressure、midpoint_power、range_chop_filter 等） | `kronos/factor/implementations/` |
| 45 | `done` | L1 funding/OI/liquidation 公开加载入口 | `kronos/data/__init__.py` |
| 46 | `done` | 12 个 legacy 候选全部映射为可运行因子实现 | `kronos/factor/candidates.py` |
| 47 | `done` | Catalog 级批量晋升工作流 + 跳过候选报告 | `kronos/research/promotion.py` |
| 48 | `done` | 市场数据驱动的晋升 runner（真实数据 + candidate evidence） | `kronos/research/promotion.py` |
| 49 | `done` | 晋升 batch 输出：JSON summary、Markdown 报告、decision CSV、知识库记录 | `kronos/research/promotion.py` |
| 50 | `done` | 旧策略资产迁移第一轮完成：12 候选 90 天 crypto 复验，0 晋升 | `docs/PROJECT_STATUS.md` |
| 51 | `done` | 产品可读 workbench 报告 + 失败原因分层 + 候选处置清单 | `kronos/research/workbench.py` |
| 52 | `todo` | 真实 L1 liquidation 数据接入（`liquidation_flow` 目前是 scaffold） | — |
| 53 | `todo` | 90 天 MVP batch 扩展到多周期/全历史 promotion study | — |

### 信号诊断

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 54 | `done` | IC/ICIR 时序、分组收益、换手率、衰减、相关性矩阵、crypto 特化诊断 | `kronos/factor/diagnostics/` |
| 55 | `done` | 可持久化诊断产物 + experiment ledger 集成 | `kronos/factor/diagnostics/reporting.py` |
| 56 | `done` | 模块级验收文档 | `docs/SIGNAL_DIAGNOSTICS_ACCEPTANCE.md` |
| 57 | `todo` | 更丰富的报告式可视化（目前只有结构化摘要和相关性热力图） | — |
| 58 | `todo` | 等 liquidation 数据和 regime 工具就绪后深化 crypto 特化诊断 | — |

### Walk-forward 验证

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 59 | `done` | 嵌套 train/validation/test 拆分、轻量参数搜索、跨窗口衰减摘要 | `kronos/research/walkforward/` |
| 60 | `done` | 自动 lookahead 审计 + 产物持久化 + ledger 集成 | `kronos/research/walkforward/core.py` |
| 61 | `done` | 双门禁晋升入口（validation + walkforward 同时通过才进 validated） | `kronos/research/promotion.py` |
| 62 | `done` | 模块级验收文档 | `docs/WALKFORWARD_ACCEPTANCE.md` |
| 63 | `todo` | 更丰富的参数邻域稳定性分析（目前只有轻量摘要） | — |

### 实验管理

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 64 | `done` | run_id 生成、schema 验证、append-only JSONL、DuckDB 查询层 | `kronos/research/experiments/` |
| 65 | `done` | 标准 artifact 布局 `experiments/{run_id}/` | `kronos/research/experiments/artifacts.py` |
| 66 | `done` | 回测、因子验证、信号诊断、walk-forward 均已接入 ledger | `kronos/research/experiments/workflow.py` |
| 67 | `done` | 模块级验收文档 | `docs/EXPERIMENT_MANAGEMENT_ACCEPTANCE.md` |

---

## P3 — 组合构建 & 风控 & 通知

### 组合构建

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 68 | `done` | `construct(scores, positions, constraints)` 标准入口 | `kronos/portfolio/allocator.py` |
| 69 | `done` | 规则化 allocator：排名、仓位上限、杠杆上限、策略级 score mixing | `kronos/portfolio/` |
| 70 | `done` | 敞口控制 + 可选波动率目标缩放 | `kronos/portfolio/allocator.py` |
| 71 | `done` | 模块级验收文档 | `docs/PORTFOLIO_CONSTRUCTION_ACCEPTANCE.md` |
| 72 | `todo` | 用诊断/walk-forward 真实衰减/成本数据驱动再平衡策略 | — |

### 风控引擎

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 73 | `done` | 独立风控 review：硬限制、回撤控制、资金费率预算缩放、流动性缩放、结构化 verdict | `kronos/risk/engine.py` |
| 74 | `done` | 风控 → 组合输出 + 风控通知 hook（helper 级） | `kronos/risk/` |
| 75 | `done` | 模块级验收文档 | `docs/RISK_ENGINE_ACCEPTANCE.md` |
| 76 | `todo` | 深化因子级和策略级风控输入（目前只有简单标志位） | — |

### 通知系统

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 77 | `done` | Notifier Protocol、结构化事件格式化、Telegram channel | `kronos/notify/` |
| 78 | `done` | 风控 verdict → 结构化通知发射 | `kronos/notify/notifier.py` |
| 79 | `done` | 模块级验收文档 | `docs/NOTIFICATION_SYSTEM_ACCEPTANCE.md` |
| 80 | `todo` | 更多事件源（目前只有风控路径） | — |
| 81 | `todo` | 如果 Telegram 不够再加新渠道 | — |

---

## P4 — 知识库 & 验证债务 & 长尾

### 知识库

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 82 | `done` | SQLite + FTS 研究知识库核心 | `kronos/research/knowledge_base/store.py` |
| 83 | `done` | 因子晋升结果、拒绝决策、跳过原因自动入库 | `kronos/research/promotion.py` |
| 84 | `done` | 模块级验收文档 | `docs/KNOWLEDGE_BASE_ACCEPTANCE.md` |
| 85 | `todo` | 从更多实验流程自动喂入知识库 | — |
| 86 | `todo` | 如持续需要，增加语义搜索升级 hook | — |

### 验证债务

| # | 状态 | 事项 | 关联文档/证据 |
|---|------|------|-------------|
| 87 | `done` | `ruff` + `mypy` + `pytest`（487 passed）+ 覆盖率 91.11% | — |
| 88 | `done` | 真实 E2E 在代理环境通过（fetch 窗口有界） | — |
| 89 | `verify` | 确认数据层重采样对标交易所原生响应（如需求仍有效） | — |

---

## 当前最高优先级（产品验收）

1. ~~产品验收 Agent MVP 交付文档 `docs/AGENT_MVP_DELIVERY.md` + Web 默认批次 `20260430-agent-mvp-delivery-v1`~~ ✅ **已完成**（见 `docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md`，功能链路全部通过）
2. 产品评审 10 个退休候选
3. 候选评分维度 + 失败记忆约束 + `trend_pullback_entry` crypto-native 改造 proposal
4. **验收发现的改进项**（来自 2026-05-04 产品验收）：
   - 🔴 "开始下一轮研究"按钮 disabled 时缺少引导提示，应告诉用户需要先配置 DeepSeek
   - 🔴 12 个候选全部卡在"迁移审查"，前 3 名应至少有一个进入"验证中"
   - 🟡 首页缺少图表（ECharts 候选分布图）
   - 🟡 空状态文案优化（审批中心等）

## 暂缓事项

- 不安装每日定时器 · 不做自动交易 · 不急于扩通知渠道
- 不急着上复杂优化器或 ML 因子平台 · 不把旧策略仓库整包搬进 Kronos
- 在没有候选通过验证前，不推进组合、风控、执行或实盘

## 维护规则

1. 真实进度以 `docs/PROJECT_STATUS.md` 为准，TODO.md 是执行快照
2. 标记 `done` 必须有代码或测试证据
3. `partial` 表示模块存在但未完全对齐 spec
4. 关联文档列必须填写，避免切换上下文时丢失路径
5. 每轮推进前先查 `docs/AGENT_MVP_ASSET_INVENTORY.md` 和 `docs/ARCHIVE_INDEX.md`
