# Kronos Agent MVP 架构借鉴与技术选型评审

更新时间：2026-04-28

## 结论先行

当前阶段 **不进入产品代码实现**。

Kronos Agent MVP 的研发准入顺序固定为：

```text
架构借鉴评审
-> OpenSpec 约束
-> 开发任务拆分
-> 产品代码实现
-> 运行证据和验收报告
```

这份文档是研发前置评审，不是实现说明。它的目标是通过阅读同类 Agent 项目来借鉴架构，而不是直接使用、复制或魔改别人的项目代码。Kronos 要吸收成熟项目里的运行模型、状态管理、角色分工、工具边界、可观测性和产品组织方式，同时保持自己的 crypto 量化研究主线。

## 重要纠偏

这里说的“技术选型”更准确地分两类：

1. **基础设施依赖**：FastAPI、Next.js、TanStack、ECharts、structlog 这类通用基础设施，可以按正常工程方式直接使用。
2. **Agent / 量化项目架构借鉴**：RD-Agent、Qlib、TradingAgents、LangGraph、CrewAI、Google ADK、OpenHands、Freqtrade、NautilusTrader、Hummingbot 这类项目，当前重点是学习架构模式，不是直接接入、照搬或抄代码。

所以后续开发的正确姿势是：

```text
研究同类项目的架构
-> 提炼适合 Kronos 的模式
-> 写入 OpenSpec 约束
-> 用 Kronos 自己的数据、Agent、工具、Web 和日志体系实现
```

## 选型原则

1. **先借鉴成熟架构模式，再写代码。** 已被 RD-Agent、Qlib、Freqtrade、LangGraph、TradingAgents 等项目验证过的结构，不重新发明；但不直接复制项目代码。
2. **研究真相来自确定性工具。** LLM 可以提出假设、质疑结论和写复盘，但不能替代数据、回测、walk-forward、lookahead 检查和实盘日志。
3. **Agent 是产品形态，不是一个 prompt。** Kronos 需要角色、状态机、工具执行、事件时间线、记忆、审批和版本管理。
4. **MVP 是功能收敛，不是粗糙实现。** Web 可以少做功能，但必须从第一天保留可维护架构、日志、报告、排查路径和未来远程化边界。
5. **本地优先，远程可扩展。** 当前按个人本地 Agent 软件设计，未来能扩展到远程访问、多用户、权限和部署。
6. **新依赖必须有明确触发条件。** Agent 类项目默认作为架构参考，不作为运行时依赖；只有在解决当前真实问题时才进入依赖。

## 当前推荐选型总览

| 能力域 | 当前参考 | 使用方式 | 评审结论 |
|---|---|---|---|
| Agent 研究方法 | RD-Agent | 架构借鉴 | 借鉴 R/D loop 作为当前 Agent MVP 方法论主线 |
| 量化研究纪律 | Qlib | 架构借鉴 | 借鉴 workflow / recorder / signal analysis，不采用 A 股默认数据格式 |
| 金融多 Agent 角色 | TradingAgents / Google ADK / CrewAI | 架构借鉴 | 借鉴角色分工和流程模式，多角色审查，不做无边界群聊 |
| Agent 状态机 | LangGraph | 架构借鉴 | 借鉴 durable execution / HITL / streaming / memory，MVP 先自建轻量状态机 |
| 本地 Agent 产品形态 | OpenHands | 架构借鉴 | 借鉴 local GUI + REST API + event flow，不引入代码执行运行时 |
| Crypto 交叉验证 | Freqtrade | 架构借鉴 / 后续外部校验 | 借鉴 dry-run/live/WebUI 和 lookahead-analysis，执行前作为安全网或等价证据 |
| 生产级执行候选 | NautilusTrader / Hummingbot | 后续评估 | 暂缓，不进入 Agent MVP |
| LLM provider | DeepSeek + provider abstraction | 基础设施依赖 | 首版低成本启动，保留多 provider 边界，不写死模型名 |
| LLM 网关 | LiteLLM | 暂缓 | 多 provider、fallback、成本管控成真需求后再引入 |
| Web 后端 | FastAPI + Uvicorn | 基础设施依赖 | 包住 Python 量化核心 |
| Web 前端 | Next.js App Router + TypeScript | 基础设施依赖 | 本地 Web 产品主入口 |
| UI 系统 | shadcn/ui + Tailwind + Radix | 基础设施依赖 | 产品后台骨架，不做粗糙模板 |
| 服务端状态 | TanStack Query | 基础设施依赖 | 候选池、详情页、设置页状态管理 |
| 表格 | TanStack Table | 基础设施依赖 | 候选池筛选、排序、分组、列状态 |
| 图表 | Apache ECharts | 基础设施依赖 | 收益、回撤、K 线、评分走势、候选对比 |
| 实时动态 | SSE | 基础设施能力 | Agent 时间线是后端到前端单向流 |
| 存储 | SQLite / DuckDB / JSONL / Parquet | 基础设施依赖或沿用 | 本地低运维，可审计，可重建 |
| 日志 | structlog + JSONL event timeline | 基础设施依赖或沿用 | MVP 必须强制结构化日志和事件流 |
| 观测标准 | OpenTelemetry | 暂缓 | 远程化、多服务、多进程后再接入 |
| 开放协议 | MCP / A2A | 预留边界 | MVP 不开放任意工具或外部 Agent 网络 |

## 开源项目评审

### RD-Agent

评审结论：**强借鉴，不直接接管 Kronos 运行时。**

Kronos 要借鉴 RD-Agent 的 R/D 两段式 loop：

```text
提出研究想法
-> 设计实验
-> 调用确定性工具
-> 读取结果
-> 反馈下一轮
```

适配方式：

- `Research Agent` 提出假设、候选改造方向和实验计划。
- `Tool Executor` 调用 Kronos 现有数据、验证、回测、walk-forward、Freqtrade crosscheck 工具。
- `Reviewer / Risk / Committee Agent` 负责反方审查、风险审查和候选处置。
- 每一轮必须落盘：计划、工具输入、工具输出、Agent 结论、下一步动作。

不直接采用的原因：

- RD-Agent 不是为 Kronos 当前本地 crypto 研究数据结构写的。
- Kronos 已有数据、因子、实验账本、知识库和报告底座，直接迁移会造成重复系统。
- Agent 不能替代确定性验证和人工闸门。

### Qlib

评审结论：**作为量化研究纪律来源，继续保留；不采用其 A 股默认底座。**

借鉴点：

- 数据 -> 因子 -> signal analysis -> portfolio analysis -> recorder 的完整研究 workflow。
- IC、Rank IC、分组收益、turnover、decay、实验记录等研究纪律。
- Recorder / experiment manager 的可复现实验思想。

不直接采用的原因：

- Kronos 是 crypto-native，数据结构包含 1m K 线、funding、OI、未来 liquidation、交易执行日志等。
- Qlib 默认数据格式和 A 股研究假设不适合直接作为当前底层格式。

### TradingAgents

评审结论：**借鉴金融多角色团队，不照搬输入和交易决策。**

Kronos 的 Agent 不能是单一 prompt。应该至少包含：

- 研究员：提出候选和假设。
- 反方审查：挑战数据不足、过拟合和逻辑跳跃。
- 风控审查：检查回撤、尾部风险、流动性、资金费率、执行风险。
- 投委会裁决：汇总指标和分歧，给出观察、改造、模拟盘、待实盘审批、淘汰。
- 执行记录分析：读取 paper / testnet / future live logs，反哺研究。

不照搬原因：

- TradingAgents 偏股票市场和新闻/情绪/基本面讨论。
- Kronos 当前核心是 crypto 量化研究、旧策略迁移、因子验证、回测和交易日志反馈。

### Freqtrade

评审结论：**作为 crypto 执行和 lookahead 安全网；当前不替代 Kronos Agent。**

借鉴点：

- dry-run / live 的产品边界。
- WebUI / Telegram 运维体验。
- backtesting、plotting、money management、strategy optimization 生态。
- lookahead-analysis 作为防未来函数和回测偏差安全网。

Kronos 适配方式：

- 在候选进入模拟盘或实盘申请前，必须经过 Freqtrade crosscheck 或等价现实性检查。
- 研究型回测继续由 Kronos 薄引擎承担，Freqtrade 不替代 Agent 研究闭环。
- 只生成配置不够，后续必须记录实际 crosscheck 运行证据。

### NautilusTrader / Hummingbot

评审结论：**后续执行层候选，Agent MVP 暂缓。**

NautilusTrader 的价值在于研究、回测、sandbox、live 共享确定性事件驱动语义，适合未来生产级执行层评估。

Hummingbot 的价值在于 crypto bot 和 connector 生态，适合未来交易执行、做市或高频方向评估。

暂缓原因：

- 当前还没有候选策略通过完整验证。
- 执行层会引入订单、仓位、对账、风控、事故处理等复杂度，不能抢在研究 Agent MVP 之前。

### LangGraph / CrewAI / Google ADK

评审结论：**强借鉴模式，首版不直接绑定运行时框架。**

借鉴点：

- LangGraph：durable execution、streaming、human-in-the-loop、memory、checkpoint。
- CrewAI：Agent / Crew / Flow 分离、状态持久化、guardrail、human-in-the-loop。
- Google ADK：workflow agents、sequential / loop / parallel agents、tool confirmation、observability。

Kronos 首版做法：

- 自建轻量 `AgentRun`、`AgentTask`、`AgentEvent`、`CandidateState`、`PromptVersion` schema。
- 单主研究任务，内部子验证可以并行。
- 每个状态变化写 append-only event timeline。
- 每个 LLM 调用记录 role、prompt version、model provider、model name 和 artifact path。

触发正式引入框架的条件：

- 状态分支和恢复逻辑明显复杂。
- 需要可靠暂停、恢复、回放、时间旅行或跨进程运行。
- 自建状态机开始成为维护负担。

### OpenHands

评审结论：**借鉴本地 Agent 软件形态，不引入其代码执行运行时。**

借鉴点：

- 本地 GUI + REST API + React 应用的产品形态。
- action / observation 事件流。
- Agent 行为可观察、可审计、可恢复的理念。

Kronos 当前不需要 OpenHands 的通用代码执行环境。后续如果允许 Agent 修改策略代码或生成因子代码，必须先补沙箱、审计、测试和人工审批。

### MCP / A2A

评审结论：**预留协议边界，MVP 不开放。**

MCP 适合未来把外部工具、数据库、文档库和本地工具接入 Agent。

A2A 适合未来让 Kronos 与其他 Agent 系统互操作。

当前不开放的原因：

- 工具权限、密钥、交易执行和本地文件安全还没有产品化边界。
- MVP 要先证明本地研究闭环，而不是先做外部 Agent 网络。

### DeepSeek / LiteLLM

评审结论：**DeepSeek 首版直接接入；LiteLLM 暂缓。**

DeepSeek 当前支持 OpenAI / Anthropic 兼容格式，适合作为低成本启动模型。Kronos 应通过 provider abstraction 接入：

- provider：`deepseek`
- base_url：由配置保存
- model：由 Web 设置页选择
- api_key：本地后端 SecretStore 保存
- timeout / retry / cost fields：作为调用元数据记录

注意：模型名会变化，业务逻辑不能写死 `deepseek-chat` 或某个临时兼容名。

LiteLLM 的价值是统一 100+ 模型供应商、fallback、成本统计、网关和管理后台。当前首版只有 DeepSeek，一个轻量 provider adapter 更合适。等出现以下条件再评估 LiteLLM：

- 至少两个 LLM provider 常态并存。
- 需要 fallback / routing / budget / cost reporting。
- 需要把模型调用能力变成团队共享网关。

## 日志、报告和排查标准

日志不是后补项。Agent MVP 的最小日志和报告能力如下。

### 结构化日志

后端日志使用 `structlog` 或等价 structured logging 输出 JSON-friendly 事件。

每条核心事件至少包含：

| 字段 | 含义 |
|---|---|
| `run_id` | 本次 Agent 或工具运行 ID |
| `task_id` | 当前主研究任务 |
| `candidate_id` | 候选策略 / 因子 / 实验对象 |
| `event_id` | 事件唯一标识 |
| `event_type` | planning / tool_start / tool_finish / model_call / decision / approval / error |
| `level` | info / decision / warning / approval_required / error |
| `role_id` | Agent 角色 |
| `prompt_version` | 使用的 prompt 版本 |
| `model_provider` | LLM 供应商 |
| `model_name` | 模型名 |
| `status` | queued / running / succeeded / failed / waiting_approval |
| `artifact_paths` | 关联报告、JSON、日志、图表路径 |
| `error_code` | 失败分类 |
| `traceback_ref` | 详细 traceback 或错误文件路径，不能塞进 UI 大段展示 |

### Event Timeline

Agent 每个重要动作必须追加到 `event timeline`：

```text
material_detected
-> hypothesis_created
-> experiment_planned
-> tool_execution_started
-> tool_execution_finished
-> agent_analysis_started
-> committee_scored
-> approval_required
-> candidate_state_changed
```

Web 首屏展示的是这个时间线的产品摘要，不是原始技术日志。

### PM 可读报告

每轮 Agent run 必须至少输出：

- `agent_run_report.md`：中文、产品经理可读。
- `agent_run_summary.json`：机器可读摘要。
- `agent_events.jsonl`：append-only 事件流。
- `agent_errors.md`：如失败，必须说明失败环节、直接影响、用户能否处理、下一步动作。

报告第一屏必须回答：

1. Kronos 现在在研究什么。
2. 为什么研究它。
3. 用了哪些数据和证据。
4. 当前结论是什么。
5. 下一步是什么。
6. 是否需要用户审批。

### 禁止事项

- 禁止把 API Key、完整 secret、敏感 headers 写入日志、报告、event timeline 或前端 localStorage。
- 禁止只输出技术 traceback 而没有用户可读失败说明。
- 禁止没有 `run_id`、`artifact_paths` 和 `prompt_version` 的 Agent 结论进入知识库。
- 禁止 Agent 在同一轮无限递归推进；一轮最多到下一步动作。

## 研发准入门槛

进入实现前，必须满足：

- [ ] 本文档存在并作为架构借鉴与技术选型评审入口。
- [ ] OpenSpec 覆盖 Agent runtime、Web workbench、observability/logging/reporting、technology governance。
- [ ] `TODO.md` 按 spec 拆成可执行任务，而不是直接从旧功能清单继续写代码。
- [ ] 每个新增依赖都有“采用方式”和“触发条件”。
- [ ] 日志字段、报告产物和排查路径写进 spec。
- [ ] Web MVP 的 API schema、event schema、approval schema 先于 UI 实现确定。

## 外部资料

- [RD-Agent](https://github.com/microsoft/RD-Agent)
- [Qlib](https://github.com/microsoft/qlib)
- [TradingAgents](https://github.com/TauricResearch/TradingAgents)
- [Freqtrade](https://github.com/freqtrade/freqtrade)
- [Freqtrade lookahead-analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- [NautilusTrader](https://github.com/nautechsystems/nautilus_trader)
- [Hummingbot](https://github.com/hummingbot/hummingbot)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [CrewAI](https://docs.crewai.com/)
- [Google ADK](https://adk.dev/)
- [OpenHands](https://github.com/OpenHands/OpenHands)
- [A2A](https://github.com/a2aproject/A2A)
- [MCP](https://modelcontextprotocol.io/)
- [DeepSeek API](https://api-docs.deepseek.com/)
- [LiteLLM](https://github.com/BerriAI/litellm)
- [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/)
- [structlog](https://www.structlog.org/en/stable/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js App Router](https://nextjs.org/docs/app)
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview)
- [TanStack Table](https://tanstack.com/table/latest/docs/introduction)
- [Apache ECharts](https://echarts.apache.org/en/index.html)
