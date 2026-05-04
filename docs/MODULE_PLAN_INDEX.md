# Kronos Module Plan Index and Technical Selection Review

更新时间：2026-04-29

## 用途

这份文档把当前 Kronos 的模块规划、进度口径和技术选型放在同一张图里。

它不是替代 `TODO.md` 的执行清单，也不是替代 OpenSpec 的详细设计。它的作用是回答三个问题：

1. 项目被拆成了哪些功能模块。
2. 每个模块原计划采用什么技术或开源框架。
3. 这些技术选型现在应当保留、收紧、替换还是暂缓。

如果要从产品视角查看“每个能力环节借鉴了哪个开源项目的什么部分”，优先阅读 `docs/OPEN_SOURCE_INFLUENCE_MAP.md`。

Agent 常驻运行模型、Web MVP 技术栈和 Agent 框架选型见 `docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`。

研发准入级架构借鉴与技术选型评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。Agent runtime、Web workbench、日志报告和技术治理的实现前 OpenSpec 见 `openspec/changes/p0-agent-runtime-web-workbench/`。已有资产复用和归档边界见 `docs/AGENT_MVP_ASSET_INVENTORY.md`。

## 总体判断

旧规划不需要推倒重来。大部分技术选型是偏保守、低运维、适合单机量化研究系统的，例如 Parquet + DuckDB、Pandas、Pydantic、Alphalens、Freqtrade、JSONL + DuckDB、SQLite + FTS、rule-based allocator。

Agent MVP 进入实现前要求的研发准入级技术选型、OpenSpec、开发批次、执行级任务拆分和资产盘点已经完成。当前可以从 `docs/AGENT_MVP_EXECUTION_PLAN.md` 的 B1.T1 开始写产品代码。

但旧规划有几个必须修正或收紧的点：

- `binance-futures-connector` 已被官方仓库标记为 deprecated。本项目已将它从运行时依赖路径移除；当前数据层采用 Binance-first REST adapter，后续凡是继续做 Binance 重数据端点或执行层，都应先做 modular SDK spike。
- Optuna 可以作为后续标准调参框架，但当前 walk-forward 的轻量搜索已经能支撑早期闭环，不应为了“符合规划”立刻加依赖。
- Polars 没有当前代码使用，已从运行时依赖移除。短期保留 Pandas 主接口，Polars 只作为未来 ETL 性能优化候选。
- LightGBM、MLP、CVXPY、语义向量库、执行层和监控系统都应继续暂缓，避免研究闭环还没稳定就扩复杂度。

## 状态口径

| 结论 | 含义 |
|---|---|
| 保留 | 选型仍适合当前阶段，可以继续按原方向推进 |
| 保留但收紧 | 方向对，但需要限制使用边界或补验收标准 |
| 调整 | 旧选型有风险或已经过时，需要替换或重写规划 |
| 暂缓 | 现在不是关键路径，先不实现、不加依赖 |
| 拒绝 | 当前阶段不采用，除非后续目标发生变化 |

## 模块索引

| 阶段 | 模块 | 规划来源 | 原计划技术选型 | 当前判断 | 当前进度 | 下一步 |
|---|---|---|---|---|---|---|
| Global | 全局模块契约 | [global-module-contracts](../openspec/changes/global-module-contracts/design.md), [global-code-standards](../openspec/changes/global-code-standards/design.md) | Pandas DataFrame、共享类型、Pydantic 配置、分层接口 | 保留 | 已有共享类型和代码规范，但文档仍需随状态同步 | 新模块启动前先确认输入输出契约，不直接绕过公共入口 |
| P0 | Agent MVP 架构借鉴与 Spec 准入 | [AGENT_MVP_TECH_SELECTION_REVIEW](./AGENT_MVP_TECH_SELECTION_REVIEW.md), [p0-agent-runtime-web-workbench](../openspec/changes/p0-agent-runtime-web-workbench/design.md) | architecture-reference / infrastructure-dependency / future-candidate / reject 架构评审；OpenSpec 约束 runtime、workbench、observability、technology governance | 保留 | 架构借鉴评审、OpenSpec、开发规划和执行计划已完成 | 后续只在新增框架依赖或重大路线变化时更新 |
| P0 | Agent MVP 资产复用与归档边界 | [AGENT_MVP_ASSET_INVENTORY](./AGENT_MVP_ASSET_INVENTORY.md), [ARCHIVE_INDEX](./ARCHIVE_INDEX.md) | 复用数据、因子、验证、回测、实验账本、知识库和测试；归档 Run MVP / 定时器旧口径 | 保留 | 已完成 | Batch 1 开发前先查资产清单，避免重复造轮子 |
| P0 | Agent Supervisor / 研究循环 | [AGENT_ARCHITECTURE_TECH_SELECTION](./AGENT_ARCHITECTURE_TECH_SELECTION.md), [AGENT_MVP_ACCEPTANCE](./AGENT_MVP_ACCEPTANCE.md), [p0-agent-runtime-web-workbench](../openspec/changes/p0-agent-runtime-web-workbench/design.md) | 本地 always-on supervisor、research queue、idle scanner、event timeline、人工闸门；MVP 单主研究任务，子验证可并行；候选生命周期状态机；Agent 角色和 prompt 版本管理；材料池和输出契约；单轮防递归边界 | 保留，等 spec 准入后实现 | 产品架构已确定，CLI Agent MVP 已有 propose / conclude，常驻 supervisor 未实现 | 先按 OpenSpec 做轻量本地 supervisor、队列、状态机和事件流；默认只推进一个当前主研究任务；暂不直接引入 LangGraph / CrewAI / ADK |
| P0 | Web 研究工作台 | [AGENT_ARCHITECTURE_TECH_SELECTION](./AGENT_ARCHITECTURE_TECH_SELECTION.md), [PRODUCT_CONTROL_PANEL](./PRODUCT_CONTROL_PANEL.md), [p0-agent-runtime-web-workbench](../openspec/changes/p0-agent-runtime-web-workbench/design.md) | FastAPI + Uvicorn、Next.js App Router + TypeScript、shadcn/ui、TanStack Query/Table、ECharts、SSE、Web 模型设置页、材料导入、审批中心、评分维度、事件级别 | 保留，等 spec 准入后实现 | 产品形态和技术栈已确定，代码未开始 | 先定义 API schema、候选池看板、单主任务 Agent 时间线、候选详情页、候选生命周期状态、模型配置页、材料导入和审批中心；本地优先但保留远程化 |
| P1 | 数据层 | [p1-data-layer](../openspec/changes/p1-data-layer/design.md) | Binance-first REST adapter、Pydantic、Parquet、DuckDB、PyArrow、Typer CLI | 保留，deprecated connector 已从依赖路径移除，SOCKS 支持已显式声明 | 基础完成，真实 E2E 已通过 | 后续新增 Binance 重端点或执行层前先做 modular SDK spike；如仍要求原生对照，再补 1h/4h/1d 重采样校验 |
| P1 | 因子平台 | [p1-factor-platform](../openspec/changes/p1-factor-platform/design.md) | Pandas、Parquet cache、Alphalens、Pydantic schema | 保留但收紧 | 进行中，注册、物化、缓存、验证、Alphalens、版本化报告目录和候选晋升入口已有主链路 | 用本地 curated 数据跑第一批真实候选晋升 |
| P1 | 回测引擎 | [p1-backtest-engine](../openspec/changes/p1-backtest-engine/design.md) | 薄向量化 research engine、Pandas/NumPy、Freqtrade bridge | 保留 | 基础版完成，有成本、资金费率钩子、交易记录、指标和 bridge 封装 | 不扩成完整执行仿真，优先服务候选因子研究闭环 |
| P2 | 实验管理 | [p2-experiment-management](../openspec/changes/p2-experiment-management/design.md) | append-only JSONL 作为事实来源，DuckDB 查询层 | 保留 | 进行中，已覆盖 backtest、factor validation、diagnostics、walk-forward 记录 | 自动接入更多实验流，确保 run_id 横向贯通 |
| P2 | 因子家族 | [p2-factor-families](../openspec/changes/p2-factor-families/design.md) | 旧候选因子重组、funding/OI/liquidation 等 crypto-native 输入 | 保留但收紧 | 进行中，12 条 legacy candidate 已有实现映射或 scaffold，第一批短窗口真实数据晋升已跑完 | 用更长历史窗口复验第一批 rejected 结果；接入真实 liquidation 数据 |
| P2 | 信号诊断 | [p2-signal-diagnostics](../openspec/changes/p2-signal-diagnostics/design.md) | IC、Rank IC、分组收益、换手、decay、相关性、Alphalens tear sheet | 保留 | 进行中，核心统计和实验记录已落地 | 增加更可读的报告输出，后续补 liquidation/regime 诊断 |
| P2 | Walk-forward | [p2-walkforward](../openspec/changes/p2-walkforward/design.md) | nested split、Optuna 或等价搜索、lookahead audit | 保留但收紧 | 进行中，轻量 in-repo 搜索、候选晋升、批量晋升、市场数据晋升编排、CLI、报告、知识库记录、第一批真实批次和 auto-run 编排已落地 | 长窗口复验第一批结果；Optuna 等需要更大搜索空间时再正式引入 |
| P3 | Freqtrade 交叉验证 | [p3-freqtrade-crosscheck](../openspec/changes/p3-freqtrade-crosscheck/design.md) | Freqtrade signal export、config generation、lookahead detection、equity comparison | 保留但收紧 | 回测 bridge 已有核心封装，但外部 Freqtrade 执行未完全自动化 | 在任何“可进入执行层”结论前，必须能跑真实外部 crosscheck 或有等价证据 |
| P3 | 组合构建 | [p3-portfolio-construction](../openspec/changes/p3-portfolio-construction/design.md) | rule-based allocator、ranking、position cap、vol target、exposure control，CVXPY 后置 | 保留 | 进行中，标准 entrypoint 和规则 allocator 已有 | 用真实 diagnostics 和 walk-forward 输出驱动再平衡与权重 |
| P3 | 风控引擎 | [p3-risk-engine](../openspec/changes/p3-risk-engine/design.md) | standalone risk engine、硬约束、drawdown/funding/liquidity controls、RiskVerdict | 保留 | 进行中，helper 级组合风控和风险通知链路已存在 | 把输入从简单 flags 升级为诊断、组合和市场状态驱动 |
| P3 | 通知系统 | [p3-notification-system](../openspec/changes/p3-notification-system/design.md) | Notifier Protocol、Telegram 首通道、in-memory 测试通道 | 保留 | 初版完成 | 继续保持 Protocol 边界；执行层启动前补 fallback 或多通道策略 |
| P4 | 研究知识库 | [p4-knowledge-base](../openspec/changes/p4-knowledge-base/design.md) | SQLite + FTS，后续预留 embedding | 保留 | 初版完成 | 自动吸收更多实验流；确认 FTS 不够用后再评估语义检索 |
| P4 | 因子自动生成 | [p4-factor-auto-generation](../openspec/changes/p4-factor-auto-generation/design.md) | AI 生成 proposal，人工审批，实验记录追踪 | 暂缓 | 只有规划 | 等研究闭环和知识库消费稳定后再启动 |
| P4 | ML 因子 | [p4-ml-factors](../openspec/changes/p4-ml-factors/design.md) | LightGBM、简单 MLP、模型产物版本化 | 暂缓 | 只有规划，依赖未加入 | 不在当前阶段加 ML 依赖；先证明基础因子研究闭环有效 |
| P5 | 执行层 | [p5-execution-layer](../openspec/changes/p5-execution-layer/design.md) | Binance execution adapter、订单意图、testnet、审计日志 | 暂缓，且 Binance modular SDK 需先做 spike | 未开始 | 研究闭环、组合和风控稳定后再启动；启动前先完成 Binance modular SDK spike |
| P5 | 监控系统 | [p5-monitoring](../openspec/changes/p5-monitoring/design.md) | runtime status、metrics、alerts、health checks | 暂缓 | 只有规划 | 等执行层边界确定后再选具体监控栈 |
| P6 | 治理上线 | 当前为路线级规划 | 版本、审批、回滚、事故复盘 | 暂缓 | 未开始 | 至少一个候选策略完成完整研究和风控审查后再设计 |

## 技术选型评估

### 应保留的选择

| 技术选择 | 评估 | 原因 |
|---|---|---|
| Parquet + DuckDB | 保留 | 官方文档支持直接查询 Parquet、glob 扫描、多文件读取、投影和过滤下推。对本地研究系统来说，低运维和高可移植性比数据库服务器更重要。 |
| Pandas DataFrame 作为跨层研究接口 | 保留 | Alphalens、Freqtrade bridge、报告和多数研究工具都天然消费 DataFrame。Polars 可作为未来局部 ETL 优化候选，但当前不进入运行时依赖。 |
| Pydantic | 保留 | 适合配置和入库前 schema 校验。后续若 DataFrame schema 问题频繁，再评估 pandera 或本地 schema validator。 |
| Alphalens | 保留但收紧 | 只放在 research / validation / tear sheet 路径，不进入在线运行主路径。 |
| 自研薄回测 + Freqtrade 复核 | 保留 | 自研引擎负责研究速度和解释性，Freqtrade 负责现实性和 lookahead 检查。不要把自研引擎扩成完整执行仿真。 |
| JSONL + DuckDB 实验账本 | 保留 | JSONL 作为 append-only 事实来源，DuckDB 做查询和比较，适合当前单机研究阶段。 |
| SQLite + FTS 知识库 | 保留 | 低依赖、可审计，足够验证“研究记忆是否真的被消费”。语义检索后置。 |
| rule-based allocator | 保留 | alpha 尚未稳定前，透明规则比优化器更容易定位问题。CVXPY 后置是正确选择。 |
| Notifier Protocol + Telegram 首通道 | 保留 | 首通道足够轻，Protocol 能避免调用方绑死 Telegram。执行层前再补 fallback。 |
| FastAPI + Uvicorn 作为 Web 后端 | 保留 | 保留 Python 量化核心，API 层负责产品化访问、事件流和未来远程化。 |
| Next.js App Router + TypeScript 作为 Web 前端 | 保留 | 主流产品后台框架，适合本地优先并保留远程部署路径。 |
| shadcn/ui + Tailwind + Radix | 保留 | 组件可控、可定制，适合形成 Kronos 自己的研究工作台设计系统。 |
| TanStack Query / Table | 保留 | 候选池需要低频刷新、缓存、重试、筛选、排序和分组，不应手写临时表格状态。 |
| Apache ECharts | 保留 | 能覆盖收益曲线、回撤、K 线、评分走势和候选对比等金融图表需求。 |
| SSE 作为 Agent 动态首版实时通道 | 保留 | 当前主要是后端向前端推送 Agent event timeline，单向事件流更轻。 |
| 轻量本地 Agent Supervisor | 保留 | 先验证 always-on 研究循环、队列、idle scanner 和人工闸门，再考虑更重运行时。 |
| Agent prompt registry | 保留 | Agent 角色需要持续迭代，必须记录 prompt 版本、模型供应商和模型名，保证每次结论可追溯；新 prompt 版本需人工确认后才能 active。 |
| Web 模型设置页 | 保留 | LLM 接入是产品能力，用户应在 Web 配置 provider、model、API Key 和角色启停，而不是手改配置文件；首版优先 DeepSeek，但保留 provider 抽象。 |
| SecretStore 抽象 | 保留 | API Key 由本地后端保存和调用，Web 只展示 masked 状态；未来远程化再补权限、加密和多用户隔离。 |
| 材料导入和材料池 | 保留 | MVP 材料来自旧资产迁移、候选池、失败记录、模拟盘日志和用户手动导入；不自动抓论文、新闻、社媒，避免噪音和不可控成本。 |
| 审批中心 | 保留 | prompt 生效、候选进入模拟盘、候选申请真钱实盘需要清晰入口和审计记录。 |
| 选择性知识库写入 | 保留 | 知识库只沉淀研究结论、失败原因、状态变化、投委会分歧和用户审批记录，不把技术日志当知识。 |
| 单轮防递归 | 保留 | 一轮研究最多推进到下一步动作；下一轮必须由新材料、新证据、新审批或明确排队任务触发，避免 Agent 自我循环。 |
| 失败收敛规则 | 保留 | 连续两轮同类失败且没有新证据时进入观察或淘汰，防止重复重跑。 |
| 候选评分维度 | 保留 | Web 不只展示总分，还要展示研究价值、稳定性、风险、证据质量和 Agent 分歧。 |
| 事件级别 | 保留 | Event timeline 统一使用 info / decision / warning / approval_required / error。 |

### 必须调整或重点观察的选择

| 风险点 | 判断 | 处理建议 |
|---|---|---|
| Binance connector | 已调整运行时依赖，后续仍需 spike | 当前数据层不依赖 `binance-futures-connector`，改为 Binance-first REST adapter。下一次做 Binance 重数据端点或执行层前，应先做 adapter spike，优先评估 `binance-sdk-derivatives-trading-usds-futures`。 |
| Optuna | 保留概念，不急加依赖 | OpenSpec 要求 Optuna 或等价搜索；当前轻量搜索已满足早期 walk-forward。只有搜索空间扩大、trial 追踪成为瓶颈时再正式加入 Optuna。 |
| Polars | 已移除，后续按需评估 | 当前没有代码使用，公共接口仍保持 Pandas。若未来用于 ETL，需要明确边界、转换点和性能收益。 |
| Freqtrade | 保留但必须自动化 | 作为 lookahead 和现实性安全网是对的；风险是只生成配置、不实际执行。准备进入执行层前必须补真实运行证据。 |
| httpx 代理行为 | 保留 | 当前环境使用 SOCKS 代理，项目已通过 `httpx[socks]` 显式声明支持，真实 E2E 已恢复。 |
| DataFrame schema | 观察 | Pydantic 保护记录级数据，不天然保护 DataFrame 列契约。若后续列漂移频繁，应加轻量 DataFrame schema 检查。 |
| LangGraph / CrewAI / ADK | 观察，先借鉴模式 | 它们对状态机、多 Agent 和流程控制有价值，但当前不应为了框架而重写现有量化工具底座。等状态分支、暂停恢复、并发协作复杂后再评估正式接入。 |
| MCP / A2A | 观察，预留边界 | 未来可用于外部工具和外部 Agent 互操作，但 MVP 应先完成本地研究闭环和安全边界。 |

### 当前应拒绝或暂缓的选择

| 选择 | 当前结论 | 原因 |
|---|---|---|
| TimescaleDB / Postgres 作为早期行情库 | 拒绝 | 当前阶段会增加运维和迁移成本，Parquet + DuckDB 更合适。 |
| ccxt / 多交易所抽象 | 暂缓 | 现在目标是 Binance USDM 研究闭环，不应提前引入多交易所复杂度。 |
| 向量数据库或 embedding 平台 | 暂缓 | SQLite + FTS 还没有被证明不够用。 |
| 完整事件驱动回测引擎 | 暂缓 | 会和 Freqtrade/执行层职责重叠，且会拖慢研究闭环。 |
| 默认 CVXPY 优化器 | 暂缓 | alpha 未稳定时容易掩盖问题。 |
| LightGBM / MLP 因子平台 | 暂缓 | 研究闭环未完成前，上 ML 只会放大实验治理压力。 |
| 执行层和监控栈 | 暂缓 | 必须等研究、组合、风控链路稳定后再启动。 |
| Streamlit / Dash / NiceGUI 作为主产品界面 | 拒绝 | 适合临时研究页，不适合作为长期产品后台、远程化、复杂候选池和 Agent 事件流基础。 |
| WebSocket 作为 MVP 默认实时通道 | 暂缓 | 当前只需要单向展示 Agent 动态，SSE 更简单；未来需要双向控制和多人协作再评估。 |
| 分布式任务队列 | 暂缓 | MVP 是本地个人常驻软件，本地 research queue 足够；多 worker 或远程化后再评估。 |

## 技术选型治理规则

1. OpenSpec 写了某个框架，不等于项目已经正式采用。只有进入 `pyproject.toml`、有代码入口、有测试或验收证据，才算落地。
2. 每个模块启动前先检查依赖是否仍被维护，尤其是交易所 SDK、执行框架和数据接口。
3. 新依赖必须解决当前模块的具体问题，不为了贴合旧规划而加入。
4. 研究层依赖和运行时依赖要隔离。Alphalens、Optuna、ML 框架不能无意进入在线主路径。
5. 如果一个开源框架只作为安全网，例如 Freqtrade，验收标准必须包含“它真的被运行或等价结果被记录”，而不是只生成配置文件。
6. 技术选型变更先更新本文件和 `TODO.md`，再推进代码改造。

## 当前技术选型优先级

1. Binance SDK 选型已先完成依赖迁出；后续在新增重数据端点或执行层前做 modular SDK spike。
2. 先完成 P2 候选因子晋升闭环，不急着引入 Optuna、ML 或执行层。
3. 冻结因子验证报告目录契约，避免“模块有了但 artifact 不可追踪”。
4. 让 Freqtrade crosscheck 从配置生成走向真实可运行验证。
5. 建立 Agent Supervisor 和 Web 研究工作台的最小产品骨架。
6. Polars 已从当前依赖中移除；未来只有出现明确 ETL 性能瓶颈时再评估引入。
7. Agent/Web 实现必须先从 `p0-agent-runtime-web-workbench` 拆任务，不再直接从旧讨论进入代码。

## 外部资料

- [DuckDB Parquet documentation](https://duckdb.org/docs/stable/data/parquet/overview.html)
- [DuckDB querying Parquet files guide](https://duckdb.org/docs/stable/guides/file_formats/query_parquet)
- [Binance futures connector deprecated repository](https://github.com/binance/binance-futures-connector-python)
- [Binance modular connector repository](https://github.com/binance/binance-connector-python)
- [Freqtrade lookahead-analysis documentation](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- [Optuna official site](https://optuna.org/)
- [SQLite FTS5 documentation](https://www.sqlite.org/fts5.html)
- [Pydantic latest documentation](https://docs.pydantic.dev/latest/)
