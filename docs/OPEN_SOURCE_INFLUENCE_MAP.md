# Kronos 开源借鉴与查漏补缺地图

更新时间：2026-04-28

## 这份文档回答什么

这份文档用于回答：

1. Kronos 每个能力环节借鉴了哪个开源项目或外部系统。
2. 借鉴的是方法论、接口设计、指标体系、工程模式，还是直接依赖。
3. 当前是否已经落地。
4. 后续应该从哪些方向查漏补缺。

Agent 常驻运行模型、Web MVP 技术栈和 Agent 框架选型边界见 `docs/AGENT_ARCHITECTURE_TECH_SELECTION.md`。

研发准入级架构借鉴评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。后续新增依赖或启动 Agent/Web 实现前，必须先检查该评审和 `openspec/changes/p0-agent-runtime-web-workbench/`，确认对应开源项目是架构借鉴、基础设施依赖、后续评估还是拒绝。

## 重要边界

“借鉴”不等于“直接使用代码”，更不等于抄别人的项目。

对 Agent 类项目，Kronos 当前关注的是：

- 它怎样组织 Agent 角色。
- 它怎样表达任务状态和状态流转。
- 它怎样把工具执行、模型输出和人工确认串起来。
- 它怎样记录事件、日志、报告和可观测性。
- 它怎样处理长任务、暂停恢复、错误和安全边界。

这些会被提炼成 Kronos 自己的 OpenSpec 和实现，而不是直接搬运上游代码。

当前 Kronos 的设计原则是：

- Qlib / RD-Agent 主要作为方法论和架构来源，不直接作为运行时底座。
- Alphalens、DuckDB、PyArrow、Pandas、Pydantic、Typer、httpx 等是当前直接依赖或开发依赖。
- Freqtrade、Optuna、CVXPY、LightGBM、RD-Agent、Qlib 是规划参考或方法论来源，不等于当前已经直接接入上游运行时。
- Binance 相关 SDK 不能盲目照搬；当前数据层使用自建 httpx REST adapter，后续新增重数据端点或执行层前再做 modular SDK spike。

## 当前直接依赖

这些项目已经进入当前 Python 环境或开发环境。

| 项目 | 当前用途 | 当前状态 | 查漏补缺点 |
|---|---|---|---|
| Pandas | 跨层研究数据结构、因子计算、验证输入输出 | 已使用 | 后续如列契约频繁漂移，需要补 DataFrame schema 检查 |
| DuckDB | 本地查询、实验账本查询、Parquet 数据分析 | 已使用 | 继续保持单机低运维路线，暂不引入数据库服务器 |
| PyArrow / Parquet | 行情与中间产物存储 | 已使用 | 长窗口数据增长后检查分区、压缩和查询速度 |
| Pydantic | 配置、schema、结构化数据校验 | 已使用 | 目前保护记录级数据，尚不覆盖全部 DataFrame 列契约 |
| Typer | 命令行入口 | 已使用 | 后续产品化时要包成固定研究流程，而不是暴露太多技术参数 |
| httpx | Binance REST 数据请求 | 已使用 | 已补 SOCKS 支持；后续执行层前要评估 Binance modular SDK |
| Alphalens Reloaded | 因子验证和 tear sheet 输出 | 开发依赖已使用 | 当前只放研究侧，不进入在线运行路径 |
| pytest / coverage | 测试与覆盖率 | 已使用 | 保持全量测试和 E2E 边界 |
| mypy / ruff | 类型检查和代码质量 | 已使用 | 继续作为工程质量门槛 |

## Agent MVP 研发准入选型

| 来源 | 当前使用方式 | 结论 |
|---|---|---|
| RD-Agent | 架构借鉴：research/development loop | 作为 Agent MVP 方法论主线，不直接替代 Kronos 运行时 |
| Qlib | 架构借鉴：量化 workflow、recorder、signal analysis | 作为确定性研究纪律来源，不采用 A 股默认数据格式 |
| TradingAgents | 架构借鉴：金融多角色团队审查 | 用于研究员、反方、风控、投委会、执行复盘角色设计 |
| LangGraph | 架构借鉴：状态机、durable execution、HITL、streaming、memory | 首版自建轻量状态机，复杂后再评估依赖 |
| CrewAI / Google ADK | 架构借鉴：Agent / Flow / loop / parallel / HITL 模式 | 首版不绑定运行时框架 |
| OpenHands | 架构借鉴：本地 GUI + REST API + event flow 产品形态 | 不引入通用代码执行运行时 |
| Freqtrade | 架构借鉴：dry-run/live、WebUI、lookahead-analysis | 作为执行前安全网和交叉验证，不代替 Agent |
| NautilusTrader / Hummingbot | 后续执行层候选 | Agent MVP 暂缓 |
| DeepSeek | 首版直接接入 OpenAI-compatible API | 通过 provider abstraction 和 SecretStore 接入，不写死模型名 |
| LiteLLM | 后置 LLM gateway 候选 | 多 provider、fallback、成本管控成真需求后再引入 |
| structlog | 结构化日志 | MVP 直接采用或沿用 |
| OpenTelemetry | 观测标准 | 远程化、多进程、多服务后再接入 |
| MCP / A2A | 开放协议边界 | MVP 只预留，不开放任意工具或外部 Agent 网络 |

## 方法论与架构来源

这些项目主要提供思路，不代表当前直接集成。

| 来源 | Kronos 借鉴了什么 | 当前落地位置 | 当前状态 | 查漏补缺点 |
|---|---|---|---|---|
| Qlib | 研究 workflow：数据 -> 特征/因子 -> score -> signal 分析 -> portfolio analysis -> recorder | 数据层、因子平台、验证、实验记录、产品路线图 | 部分落地，当前主线 | 后续补更稳定的 workflow 配置和可复现实验入口 |
| Qlib | IC、Rank IC、分组收益、滚动验证、实验记录这些研究纪律 | signal diagnostics、walk-forward、experiment ledger | 部分落地 | 报告需要更产品化，长窗口验证还没完成 |
| Qlib | Recorder / experiment manager 思路 | JSONL ledger + DuckDB 查询层 | 初版落地 | 更多实验流需要自动入账 |
| RD-Agent | hypothesis -> experiment -> evaluate -> iterate 的研究 loop | Agent MVP | 当前主线，已启动 | 已有 `kronos agent propose`，下一步补工具调用和结果读取 |
| RD-Agent | 自动提出假设、自动生成实验、读取结果后继续迭代 | Agent 研究闭环 | 部分落地 | 人工审批、实验记录和失败记忆必须保留 |
| Freqtrade | 现实性和 lookahead 交叉验证安全网 | backtest bridge / crosscheck 规划 | 核心封装已有，外部运行未完全自动化 | 进入执行层前必须补真实 crosscheck 证据 |
| Optuna | 参数搜索和 walk-forward 调参方法论 | walk-forward 设计 | 当前用轻量 in-repo 搜索替代 | 搜索空间扩大后再正式引入 |
| SQLite FTS | 本地研究知识库、失败原因检索 | research knowledge base | 初版落地 | 后续先扩大自动喂数，再评估语义检索 |
| CVXPY | 组合优化未来候选 | portfolio construction 规划 | 暂缓 | alpha 未稳定前不引入，避免优化器掩盖信号质量 |
| LightGBM / MLP | ML 因子未来候选 | P4 ML factor 规划 | 暂缓 | 先证明基础因子研究闭环有效 |
| Polars | 高性能 ETL 候选 | 曾在规划中出现 | 已移除 | 只有出现明确性能瓶颈才重新评估 |

## Agent 架构与产品化工作台来源

这些项目主要用于设计 Kronos 的 Agent 运行模型、Web 工作台和未来扩展边界。

| 来源 | Kronos 借鉴什么 | 当前落地位置 | 当前状态 | 查漏补缺点 |
|---|---|---|---|---|
| LangGraph | 状态机、checkpoint、durable execution、human-in-the-loop | Agent Supervisor / research loop 规划 | 强借鉴，暂不直接加依赖 | 先用轻量本地状态模型验证闭环；状态分支复杂后再评估直接引入 |
| Google ADK | coordinator、sequential、parallel、loop、critic、human-in-the-loop 等多 Agent 模式 | 多 Agent 角色和投委会流程规划 | 强借鉴，暂不绑定生态 | 把研究 Agent、验证 Agent、风控 Agent、投委会 Agent 放进明确流程 |
| CrewAI | Crews 与 Flows 分离，角色化 Agent 与确定性流程结合 | Agent 角色设计和流程边界 | 借鉴模式，暂不直接依赖 | Agent 可以讨论，但关键节点必须走确定性 Flow |
| OpenHands | action / observation 事件流、安全运行环境、沙箱执行 | Agent event timeline、未来策略代码执行安全边界 | 借鉴模式 | 后续 Agent 改代码或跑脚本前，必须补沙箱、审计和安全验证 |
| Dify | 产品化工作台、工作流、集成、可观测性 | Web 研究工作台规划 | 借鉴产品形态 | Kronos Web 应是候选池 + Agent 动态 + 证据工作台，不是日志页 |
| A2A | 外部 Agent 能力发现、协作、长任务互操作 | 未来外部 Agent 接入边界 | 预留 | MVP 暂不实现 |
| MCP | Agent 接工具和数据源的协议边界 | 未来工具接入边界 | 预留 | 必须先定义工具白名单、权限和沙箱策略 |
| AutoGen | 多 Agent 对话模式 | 历史参考 | 不作为新主线依赖 | 官方仓库已提示维护模式，优先看新一代模式和协议 |

## Web MVP 技术栈来源

| 来源 | Kronos 借鉴什么 | 当前结论 | 查漏补缺点 |
|---|---|---|---|
| FastAPI / Uvicorn | Python API 层、异步服务、未来 SSE / WebSocket 基础 | Web 后端首选 | 先包住现有 Python 量化核心，不把量化逻辑搬到前端 |
| Next.js App Router | 主流 React 产品后台框架、未来远程化部署路径 | Web 前端首选 | 从一开始按产品后台骨架设计 |
| shadcn/ui + Tailwind + Radix | 可维护、可定制的开源 UI 基础 | UI 基础首选 | 建立 Kronos 自己的研究工作台设计系统 |
| TanStack Query | 服务端状态、低频刷新、重试、缓存 | 候选池和详情数据读取首选 | 避免手写混乱 fetch 状态 |
| TanStack Table | 候选池筛选、排序、分组、列状态 | 候选资产看板表格首选 | 不手写不可维护 table |
| Apache ECharts | 收益、回撤、K 线、评分走势、候选对比 | 图表首选 | 后续补金融图表规范 |
| Server-Sent Events | 后端向前端推送 Agent 时间线 | MVP 实时动态首选 | 需要双向控制或多人协作时再评估 WebSocket |

## 功能环节映射

### 1. 数据底座

借鉴来源：
- Qlib 的数据抽象和数据处理分层。
- DuckDB / Parquet 的本地研究数据栈。
- Binance REST 生态。

当前 Kronos 做法：
- 不使用 Qlib 自带数据格式。
- 使用自建 Binance-first REST adapter。
- 使用 Parquet + DuckDB 做本地行情和实验数据。

当前缺口：
- 真实 liquidation 数据还没接入。
- 如果后续做更多 Binance 重数据端点或执行层，需要先做 Binance modular SDK spike。
- 若仍要求交易所原生周期对照，需要补 1h / 4h / 1d 重采样一致性验证。

### 2. 因子平台

借鉴来源：
- Qlib 的特征 / dataset / score 方法论。
- Alphalens 的因子分析体系。
- 本地旧 A 股 / 期货策略资产中的因子假设。

当前 Kronos 做法：
- 自建 Factor Protocol、registry、候选生命周期和验证门槛。
- 旧策略资产不整包迁移，只提炼成候选因子。
- 当前 12 个 legacy candidates 已进入候选库。

当前缺口：
- 12 个候选只完成短窗口真实数据 smoke run。
- 需要长窗口复验和失败原因分层。
- 需要更多产品可读报告，而不是只输出技术 artifact。

### 3. 验证与诊断

借鉴来源：
- Qlib 的 signal analysis。
- Alphalens 的 tear sheet。
- Walk-forward 研究方法。

当前 Kronos 做法：
- 已有 IC / ICIR、分组收益、turnover、decay、相关性等核心诊断。
- 已有候选晋升门槛和短窗口真实数据跑批。

当前缺口：
- 报告需要更像产品结论，而不是指标清单。
- 需要长窗口验证。
- liquidation / regime 相关诊断还要等数据接入。

### 4. 回测与交叉验证

借鉴来源：
- Qlib 的研究回测思路。
- Freqtrade 的 lookahead-analysis 和现实性安全网。
- 本地旧项目的回测骨架经验。

当前 Kronos 做法：
- 自建薄研究回测，不做完整交易仿真。
- Freqtrade bridge 已有核心封装。

当前缺口：
- 外部 Freqtrade 真实运行还没有完全自动化。
- 当前回测服务于研究判断，不代表实盘交易能力。

### 5. 实验记录与知识库

借鉴来源：
- Qlib Recorder / ExpManager。
- SQLite FTS。
- RD-Agent / noesis-agent 的失败记忆和研究历史思路。

当前 Kronos 做法：
- JSONL ledger 作为实验事实来源。
- DuckDB 做跨实验查询。
- SQLite + FTS 记录失败原因、晋升结果和研究记忆。

当前缺口：
- 还没有覆盖所有实验流。
- 后续需要让 PM 报告能引用知识库里的失败结论。
- 语义检索先暂缓，等 FTS 不够用再评估。

### 6. 组合与风控

借鉴来源：
- Qlib 的 portfolio analysis 思路。
- 传统 rule-based allocator。
- CVXPY 作为后续候选。

当前 Kronos 做法：
- 先用透明规则 allocator。
- 已有硬约束、回撤降仓、funding 预算、流动性缩放等初版风控。

当前缺口：
- 还没有稳定 validated 因子输入。
- 风控输入仍偏简单，需要接入诊断、walk-forward、市场状态。
- CVXPY 暂缓。

### 7. 通知与运营

借鉴来源：
- Notifier Protocol 这种通道抽象。
- Telegram 作为首个轻量通知通道。

当前 Kronos 做法：
- 已有共享 notifier 接口和 Telegram 通道。
- 已能从 risk verdict 发出通知。

当前缺口：
- 事件来源还少。
- 暂不急着扩多渠道，等执行层启动后再深化。

### 8. RD-Agent 风格研究 Agent

借鉴来源：
- RD-Agent 的研究假设生成、实验实现、评估反馈和持续迭代 loop。

当前 Kronos 做法：
- RD-Agent 方法论已经进入当前 Agent MVP。
- `kronos agent propose` 会读取上一轮确定性研究结果，选择下一轮候选，提出研究假设，并生成实验计划。
- `kronos agent conclude` 会读取专项证据结果，输出观察 / 改造 / 退休 / 补数据建议。
- Agent 计划和 Agent 决策会写入研究知识库。

当前缺口：
- Agent 还没有把计划、专项实验和结果读取串成一个命令。
- 需要更强的失败记忆约束，避免重复提出已失败方向。
- 需要人工审批机制，确保自动生成的候选不能绕过验证门槛。

### 9. 常驻 Agent Supervisor

借鉴来源：
- LangGraph 的状态机和 durable execution。
- Freqtrade 的常驻 bot loop。
- RD-Agent 的研究迭代 loop。
- OpenHands 的 event-driven action / observation 模式。

当前 Kronos 做法：
- 产品上确定为 always-on Agent Supervisor，而不是每天固定定时任务。
- 有材料时连续推进 research queue。
- 没材料时进入 idle scanner，例如每 30 分钟巡检新材料、新数据、新失败和新待办。
- Web 展示 Agent event timeline。

当前缺口：
- 还没有真正的常驻 supervisor 进程。
- 还没有 research queue 和 idle scanner。
- 还没有 Web 事件时间线。

### 10. 本地 Web 研究工作台

借鉴来源：
- Dify 的产品化工作台和可观测性。
- RD-Agent UI 的 R&D 过程可视化思路。
- Next.js / shadcn / TanStack / ECharts 生态。

当前 Kronos 做法：
- 产品方向已确定：本地优先，未来可远程化。
- 第一屏应是候选资产看板 + Agent 工作流时间线 + 候选详情页。
- CLI 保留为开发、调试和兜底入口，不作为产品经理主入口。

当前缺口：
- Web 应用还未实现。
- 需要定义 API schema、候选池视图、Agent event schema 和审批动作。

## 不采用或暂缓的内容

| 项目 / 方案 | 当前结论 | 原因 |
|---|---|---|
| Qlib 原生 A 股配置 | 不采用 | Kronos 是 crypto-native，市场结构不同 |
| Qlib 底层二进制数据格式 | 不采用 | 不适合当前分钟级 crypto + funding / OI 数据组织 |
| Qlib model zoo | 暂缓 | 当前还没有到 ML 因子阶段 |
| RD-Agent 直接接管研究结论 | 不采用 | Agent 可以提出假设，验证必须由确定性研究底座完成 |
| RD-Agent 直接交易 | 不采用 | RD-Agent 不是交易执行层 |
| Binance deprecated futures connector | 已移除 | 上游已 deprecated，当前改用 httpx REST adapter |
| Polars | 已移除 | 当前没有实际代码使用 |
| TimescaleDB / Postgres | 暂缓 / 拒绝 | 当前单机研究阶段 Parquet + DuckDB 更合适 |
| ccxt 多交易所抽象 | 暂缓 | 当前聚焦 Binance USDM，不提前扩复杂度 |
| CVXPY 默认组合优化 | 暂缓 | alpha 未稳定前不应让优化器掩盖问题 |
| LightGBM / MLP | 暂缓 | 先完成基础因子研究闭环 |
| 直接引入 LangGraph / CrewAI / ADK 作为运行时依赖 | 暂缓 | 先借鉴架构模式，避免框架先行；等状态分支和恢复复杂后再评估 |
| WebSocket | 暂缓 | MVP 的 Agent 动态主要是后端单向推送，SSE 更轻 |
| MCP / A2A 正式接入 | 暂缓 | 先完成本地研究闭环和安全边界，再接外部工具或外部 Agent |
| Streamlit / Dash / NiceGUI 作为主产品界面 | 不采用 | 适合临时研究页，不适合作为长期产品后台和远程化基础 |

## 查漏补缺清单

### P0：当前必须看

- 技术选型准入：`docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。
- Agent/Web/OpenSpec 准入：`openspec/changes/p0-agent-runtime-web-workbench/`。
- Agent MVP：已能生成下一轮假设、实验计划，并读取专项证据结果；下一步把这些步骤串成一个命令。
- Agent 计划验收：`reports/research/experiments/20260428-agent-mvp-v1/agent_research_plan.md`。
- Agent 决策验收：`reports/research/experiments/20260428-agent-mvp-v1-decision/agent_research_decision.md`。
- 观察名单专项复盘：`multi_timeframe_confirmation` 仅保留观察，`trend_pullback_entry` 进入候选改造。
- 退休评审：10 个旧策略候选需要产品确认是否正式退休。
- crypto-native 改造：下一轮候选应围绕 funding、OI、liquidation、多周期确认等 crypto 机制提出。

### P1：研究闭环稳定后看

- Freqtrade 真实外部 crosscheck 自动化。
- liquidation 数据接入。
- 更多实验流自动进入 ledger 和知识库。
- 组合与风控消费真实诊断结果。

### P2：后续自动化和扩展

- Agent 自动调用实验工具并读取新结果。
- Optuna 正式引入。
- ML 因子和 Qlib-style benchmark。
- 语义检索或向量知识库。
- 执行层和监控系统。

## 维护规则

1. 新增一个模块前，先在本文件里明确它借鉴哪个项目、借什么、不借什么。
2. 新增一个第三方依赖前，先更新 `MODULE_PLAN_INDEX.md` 和本文件。
3. 如果一个项目只是方法论来源，不要把它写成运行时依赖。
4. 如果一个项目已经 deprecated 或不适合当前阶段，要明确写成“已移除”“暂缓”或“不采用”。
5. 面向产品经理汇报时，只从本文件抽象出“当前能做什么”和“还缺什么”，不要展开技术实现细节。
