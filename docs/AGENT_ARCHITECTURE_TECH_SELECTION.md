# Kronos Agent 架构与技术选型记录

更新时间：2026-04-28

## 这份文档回答什么

这份文档记录 Kronos Agent 化方向的产品共识和技术选型依据。

研发准入级架构借鉴评审见 `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`。后续进入实现前，必须先以该评审和 `openspec/changes/p0-agent-runtime-web-workbench/` 为准完成任务拆分；本文只记录架构共识和选型边界，不直接授权开写产品代码，也不表示要复制或直接接入同类 Agent 项目。

它回答五个问题：

1. Kronos 的 Agent 运行模型是什么。
2. 哪些开源 Agent / 量化项目值得借鉴。
3. 借鉴什么，不借什么。
4. Web MVP 从第一天应该采用什么产品级技术栈。
5. 哪些技术选型暂缓，避免为了追热点增加复杂度。

## 当前研发准入结论

当前顺序固定为：

```text
架构借鉴评审
-> OpenSpec 约束
-> 开发任务拆分
-> 产品代码实现
-> 运行证据和验收报告
```

本阶段不新增产品代码。新增依赖或框架前必须先说明：

- 这个开源项目是架构借鉴、基础设施依赖、未来候选，还是明确拒绝。
- 它解决当前 Agent MVP 的哪个问题。
- 不采用现有轻量方案会造成什么风险。
- 验收时用什么日志、报告、测试或 Web 证据证明它有效。

## 当前产品共识

Kronos 不是每天定时跑一次报告的系统，也不是手动 CLI 脚本集合。

Kronos 应该是一个本地优先、未来可远程化的 **常驻 Agent 软件**：

```text
打开 Kronos
-> 后台 Agent Supervisor 启动
-> 检查材料队列和候选池
-> 有材料就连续推进研究
-> 没材料就低频巡检
-> 新材料出现后继续推进
-> Web 控制台展示候选池、Agent 动态、证据和审批闸门
```

MVP 的第一屏是研究工作台，不是技术日志：

- 候选资产看板：低频刷新，显示候选、来源、状态、评分、证据、最大问题和下一步。
- Agent 工作流时间线：准实时展示当前在做什么，但不刷屏。
- 候选详情页：展示迁移审查、回测、滚动验证、Agent 分歧、失败原因和投委会结论。

MVP 的打开方式已确定为：

```text
启动本地后端服务
-> 自动或手动打开浏览器
-> 访问本地 Web 研究工作台
```

桌面 App 暂不作为 MVP 目标。后续如果需要桌面化，可以在现有 Web 前端和本地后端之上再包装，不应为了桌面壳重写产品逻辑。

人类只卡两个闸门：

1. 是否允许某个候选进入真钱实盘。
2. 实际给它多少资金。

dry-run、paper、testnet 这类不动真钱的模拟执行，可以由 Agent 自动跑，因为它属于验证链路。

## 总体架构建议

Kronos Agent MVP 应采用：

```text
Always-on Supervisor
-> Research Queue
-> Idle Scanner
-> State Machine Research Loop
-> Role Agents
-> Deterministic Tool Executor
-> Agent Analysis / Debate
-> Committee Scoring
-> Candidate Pool Update
-> Event Timeline
-> Human Approval Gates
```

产品上表现为：

```text
材料池
-> 调度器
-> 多 Agent 分工
-> 实验执行
-> 结果分析
-> 投委会评分
-> 候选池更新
-> 下一轮
```

关键边界：

- Agent 可以提出假设，但实验结果必须来自确定性工具。
- Agent 可以自动迁移审查、跑实验、写复盘，但不能自动动真钱。
- Agent 不是一个 prompt，而是一组角色、状态机、工具和记忆。
- Agent 角色和 prompt 必须有版本管理，不能把第一版 prompt 当成永久正确。
- LLM 供应商、模型和 API Key 应通过 Web 配置；前端只负责配置体验，敏感信息必须由本地后端保存和调用。
- 旧 A 股 / 期货资产不是直接搬进来跑，而是作为候选材料进入迁移验证流程。
- MVP 阶段同一时间只推进一个主研究任务，避免 Agent 在多个方向上同时发散。
- 一个主研究任务内部允许子验证并行，例如多币种、多时间窗口、多验证切片并行跑。

## 开源架构借鉴结论

| 项目 / 协议 | 借鉴点 | Kronos 当前结论 | 不直接采用的原因 |
|---|---|---|---|
| LangGraph | 状态机、durable execution、checkpoint、human-in-the-loop、长期运行 Agent | 强借鉴。Kronos 研究循环应按状态机和 checkpoint 设计 | MVP 不急着直接加依赖；先用轻量本地状态模型验证产品闭环 |
| Google ADK | coordinator、sequential、parallel、loop、critic、human-in-the-loop 等多 Agent 模式 | 强借鉴。Kronos 多 Agent 角色应进入明确流程，不做无边界群聊 | 先借模式，不绑死 Google 生态 |
| CrewAI | Crews 与 Flows 分离，角色化 Agent 与确定性流程结合 | 借鉴角色和流程分离。Kronos 可以有 Agent 讨论，但关键节点必须走确定性 Flow | 直接引入会增加抽象层，且 Kronos 已有量化工具底座 |
| OpenHands | action / observation 事件流，安全运行环境，沙箱执行 | 借鉴事件流和安全隔离。后续 Agent 改策略代码或跑实验必须有审计和隔离 | 当前 MVP 先不引入完整代码执行运行时 |
| Dify | 产品化工作台、工作流、集成、可观测性 | 借鉴产品形态。Kronos Web 应是研究工作台，不是日志页 | Dify 是通用 Agent 平台，不是 crypto 量化研究底座 |
| A2A | Agent 之间互操作、能力发现、长任务协作 | 作为未来互操作边界预留 | MVP 阶段还不需要外部 Agent 网络 |
| MCP | Agent 接工具和数据源的开放协议 | 作为未来工具接入边界预留 | 安全边界要先设计清楚，不能盲目开放本地工具 |
| AutoGen | 多 Agent 对话模式和群聊调度 | 只作为历史参考 | 官方仓库已提示维护模式，新项目不宜把它作为主线依赖 |
| RD-Agent | hypothesis -> experiment -> feedback -> iterate 的研究闭环 | 当前 Agent MVP 方法论主线 | 不直接接管交易或验证真相层 |
| Qlib | 严肃量化研究 workflow、recorder、signal analysis | 确定性工具底座 | 不采用 A 股默认配置和底层数据格式 |
| Freqtrade | 常驻交易循环、dry-run/live 运行模式、lookahead safety net | 后续执行/交叉验证参考 | 不能代替 Kronos 的研究 Agent |
| NautilusTrader | backtest / sandbox / live 的事件驱动一致性、执行对账 | 后续执行层参考 | 当前还没进入生产级执行阶段 |

## MVP 技术选型

### Agent 后端

| 能力 | MVP 选择 | 原因 | 后续升级 |
|---|---|---|---|
| Agent Supervisor | 自建轻量 supervisor | 与现有 Python 量化工具贴合，先验证产品闭环 | 长运行复杂后再评估 LangGraph 或等价状态机运行时 |
| 状态存储 | SQLite / DuckDB / JSONL 组合 | 当前项目已有实验账本和知识库基础，低运维，可审计 | 多用户远程化后再评估 Postgres |
| 任务队列 | 本地 research queue | MVP 是个人本地常驻软件，不需要分布式队列 | 远程化或多 worker 后再评估 Celery / Dramatiq / Redis queue |
| 实时事件 | append-only event timeline + SSE | Agent 动态是后端到前端单向推送，SSE 足够轻 | 双向协作和远程控制复杂后再升级 WebSocket |
| 人工闸门 | 明确状态 + Web 审批动作 | 实盘准入和真钱资金必须由用户确认 | 远程化后补权限、审计、审批记录 |
| Prompt 版本 | 本地 prompt registry + version id | Agent 角色需要持续迭代，实验结论必须能追溯到当时使用的 prompt | 后续可做 A/B prompt、不同模型对照和角色评分回放 |
| LLM 配置 | Web 设置页配置 provider / model / API Key | 用户不应通过改配置文件才能接入 DeepSeek 或其他模型 | 远程化后补权限、密钥加密和多租户隔离 |

### 日志、报告和排查

| 能力 | MVP 选择 | 原因 | 后续升级 |
|---|---|---|---|
| 结构化日志 | `structlog` 或等价 JSON-friendly logger | 本地长运行 Agent 必须能按 run、candidate、role、prompt、model 和 error 追查 | 远程化后接 OpenTelemetry |
| Agent 事件流 | append-only `agent_events.jsonl` | Web 时间线和排障都需要事实来源，不依赖浏览器页面存活 | 多进程后补事件索引和 trace |
| PM 报告 | `agent_run_report.md` | 产品经理第一屏需要看懂研究目标、原因、证据、结论、下一步和审批 | 后续 Web 直接渲染结构化摘要 |
| 机器摘要 | `agent_run_summary.json` | Web、知识库和后续 Agent 复查需要稳定 schema | 后续接入统一 experiment ledger 查询 |
| 错误报告 | `agent_errors.md` | 失败时不能只给 traceback，必须说明影响和下一步 | 后续接通知和监控 |
| OTel | 暂缓 | OpenTelemetry 适合多服务、多进程、远程观测；当前单机 MVP 先强制日志和事件产物 | 远程化或多服务后再接 |

### Web 产品栈

| 能力 | MVP 选择 | 原因 | 不采用 |
|---|---|---|---|
| 后端 API | FastAPI + Uvicorn | Python 原生、类型清晰、性能足够、适合包住量化核心 | 不用 Flask 临时堆 API |
| 前端框架 | Next.js App Router + TypeScript | 主流、可扩展、方便未来远程后台化 | 不用纯静态页面凑 MVP |
| UI 系统 | shadcn/ui + Tailwind + Radix | 开源、可定制、能形成自己的产品设计系统 | 不用粗糙模板页 |
| 数据请求 | TanStack Query | 候选池低频刷新、缓存、重试和后台更新都适合 | 不手写混乱 fetch 状态 |
| 候选池表格 | TanStack Table | 筛选、排序、分组、列状态和候选排名会越来越复杂 | 不手写不可维护 table |
| 图表 | Apache ECharts | 适合收益、回撤、K 线、评分走势和候选对比 | 不用功能不足的简单图表库做长期主图表 |
| 实时 Agent 动态 | SSE | 单向事件流足够，简单、稳定、容易调试 | MVP 不急上复杂 WebSocket |
| 设置页 | Web 内配置 LLM provider、模型、API Key、角色启停和 prompt 版本 | 模型接入是产品能力，不应隐藏在命令行或配置文件里 | 不把 API Key 存在浏览器 localStorage |

这意味着：MVP 可以功能少，但不能做成没有产品逻辑、不可扩展的粗糙看板。

## Agent 角色与 Prompt 版本管理

MVP 默认保留五类 Agent 角色：

| 角色 | 职责 | 典型输出 |
|---|---|---|
| 研究员 | 从材料、失败记录和市场机制中提出可验证假设 | 假设、实验计划、候选改造方向 |
| 反方审查 | 挑战假设、识别过拟合、数据不足和逻辑跳跃 | 反对意见、补证据要求 |
| 风控审查 | 关注回撤、尾部风险、流动性、资金费率和执行风险 | 风险结论、阻断理由 |
| 投委会裁决 | 汇总确定性指标和多 Agent 分歧，给出候选处置 | 观察 / 改造 / 模拟盘 / 待审批 / 淘汰 |
| 执行记录分析 | 读取 dry-run、paper、testnet 和未来实盘日志，反哺研究 | 交易复盘、异常归因、下一轮修正 |

Prompt 版本管理要求：

- 每个角色都有 `role_id`、`prompt_version`、`model_provider`、`model_name` 和启停状态。
- 每次 Agent 结论必须记录使用了哪个角色版本和模型版本。
- Prompt 修改必须生成新版本，不覆盖旧版本。
- Prompt 新版本可以先保存为草稿，但必须经过人工确认后才能设为 active。
- MVP 每个角色只配置一个 active 模型，避免早期多模型对照让结论解释复杂化。
- 候选状态变化和投委会评分必须能追溯到当时的 prompt 版本。
- MVP 先做本地版本登记和 Web 展示，后续再做 prompt A/B、回放评估和自动评分对照。

LLM 接入要求：

- DeepSeek 可作为启动默认供应商，因为成本低，适合早期 Agent 分析。
- 首版优先接 DeepSeek，但 provider / model 抽象必须保留，不能写死到业务逻辑里。
- 实验执行、回测和指标计算仍由确定性工具完成，不交给 LLM 编造。
- Web 设置页负责配置 provider、model、API Key、角色启停和默认模型。
- API Key 不应写入前端代码或浏览器本地存储；本地后端通过 `SecretStore` 抽象保存后由后端调用模型。
- MVP 本地优先：优先使用本机安全存储能力；如果暂时采用本地加密文件，也必须在 `.gitignore` 范围内，并在 Web 中只展示 masked 状态。
- Event timeline 只显示模型调用状态、角色、版本和摘要，不泄露密钥或完整敏感配置。

## 运行模型

### 有材料时

```text
读取材料
-> 建立或更新候选
-> 生成假设
-> 设计实验
-> 执行确定性工具
-> 读取结果
-> 多 Agent 分析
-> 投委会评分
-> 更新候选池和记忆
-> 继续下一项材料
```

### 没材料时

```text
进入 idle
-> 每 30 分钟巡检
-> 检查新数据、新导入资产、新失败日志、新待办
-> 有新材料则恢复研究循环
-> 无新材料则继续 idle
```

idle 不是“无意义重复跑”。任何重新实验都必须有新证据、新参数、新数据窗口、新迁移方案或新市场状态。

## 材料池、输出契约和记忆边界

### MVP 材料来源

MVP 默认材料池只包含：

- 旧资产迁移材料。
- 候选池待验证项。
- 失败记录。
- 模拟盘 / paper / testnet 日志。
- 用户手动导入资料。

用户手动导入资料先支持 Web 上传或粘贴文本，类型包括策略说明、因子说明、论文摘要和交易复盘。

MVP 暂不自动抓论文、新闻、社媒或外部网页。外部材料可以由用户主动导入，进入材料池后再由 Agent 判断是否值得研究。

### Agent 输出契约

每轮 Agent 研究必须输出：

- 本轮结论。
- 支持理由。
- 反对理由。
- 关键证据。
- 最大风险。
- 下一步动作。
- 是否需要用户审批。

这份输出是 Web、报告和知识库共同消费的产品契约，不是技术日志。

### 审批类型

MVP 先保留三类人工审批：

- 启用 prompt 版本。
- 让候选进入模拟盘。
- 让候选申请真钱实盘。

其中模拟盘属于验证链路，审批通过后 Agent 可以自动推进；真钱实盘必须停在 `live_approval_required`，等待用户确认准入和资金。

### 模拟盘记录

paper / testnet 是验证阶段，不是真钱交易。

Web 必须展示：

- 每次模拟交易。
- 模拟交易失败原因。
- Agent 对模拟交易结果的复盘。
- 复盘如何影响候选状态或下一轮实验。

### 知识库写入边界

不是所有日志都进入知识库。

MVP 只写入：

- 研究结论。
- 失败原因。
- 候选状态变化。
- 投委会分歧。
- 用户审批记录。

技术日志、逐条模型原文、完整事件流和中间调试信息不直接进入知识库；它们可以留在 event timeline 或原始 artifact 中。

## 研究轮次和防跑偏边界

产品边界确认到本节收敛。后续进入实现拆解和开发，不再无限追加访谈问题。只有遇到真钱实盘、密钥安全、不可逆删除、重大技术路线分叉或用户验收口径冲突时，才重新请求用户确认。

### 单轮研究节奏

MVP 的一轮 Agent 研究最多推进到“给出下一步动作”。

一轮可以包含材料读取、假设、实验计划、确定性验证、Agent 分析、投委会评分和下一步建议，但不能在同一轮里无限递归自我继续。下一轮必须由新的材料、新证据、新用户审批或明确排队任务触发。

### 失败处理

连续两轮同类失败且没有新证据时，候选必须进入 `observe` 或 `retired`。Agent 不能通过重复改参数、重复重跑或换说法来绕过失败结论。

### 候选评分展示

Web 候选池不只展示一个总分。

MVP 默认展示：

- 总评分。
- 研究价值。
- 稳定性。
- 风险。
- 证据质量。
- Agent 分歧。

### 用户可干预点

MVP 允许用户做四类干预：

- 暂停当前主任务。
- 跳过候选。
- 要求补充验证。
- 批准审批事项。

MVP 不做复杂工作流编辑器，避免用户界面先于研究闭环复杂化。

### 事件时间线级别

Event timeline 默认分为五类：

- `info`：普通进展。
- `decision`：Agent 或投委会结论。
- `warning`：风险、证据不足或异常但未中断。
- `approval_required`：等待用户审批。
- `error`：运行失败或需要处理的错误。

### Web 首版验收标准

用户打开 Web 后必须能回答：

- 现在在研究什么。
- 为什么研究它。
- 证据是什么。
- 下一步是什么。
- 哪里需要用户审批。

### 并发边界

MVP 阶段采用 **单主线、多切片** 的并发模型。

同一时间只有一个当前主研究任务，例如一个候选、一个策略迁移主题或一个失败复盘主题。这个主任务可以拆出多个确定性子验证并行执行，例如 BTC / ETH / SOL 对照、不同时间窗口、不同市场状态分组、不同参数切片。

Web 第一版只展示一个当前主任务，避免用户看到多个 Agent 线程同时跳转。后续只有当候选生命周期、事件时间线和人工闸门都稳定后，才评估多个候选同时研究。

## 候选生命周期

候选生命周期是 Agent Supervisor、候选池看板、候选详情页和人工闸门共用的状态模型。

MVP 采用以下主状态：

```text
material_intake
-> migration_review
-> hypothesis
-> experiment_planned
-> validating
-> agent_analysis
-> committee_scoring
-> observe / redesign / simulate / live_approval_required / retired
```

产品口径：

- `material_intake`：材料进入，包括旧策略、旧因子、公开策略、论文、失败记录、模拟盘日志或 Agent 复盘。
- `migration_review`：判断材料能否迁移到 crypto，不允许因为原资产“机构级”就默认有效。
- `hypothesis`：形成可验证假设，必须说明来源和市场机制。
- `experiment_planned`：实验计划已生成，包含数据窗口、资产范围、成功标准和失败标准。
- `validating`：确定性工具正在验证，可以并行跑多币种、多窗口、多切片。
- `agent_analysis`：Agent 读取验证结果，解释失败、异常、有效线索和下一步。
- `committee_scoring`：投委会式评分，允许 Agent 加权和分歧，不只依赖固定公式。
- `observe`：暂不淘汰，等待新证据或新市场状态。
- `redesign`：方向有价值，但需要 crypto 改写或补特征。
- `simulate`：允许进入 dry-run / paper / testnet，不动真钱。
- `live_approval_required`：具备申请实盘资格，但必须等待用户确认准入和资金。
- `retired`：淘汰并沉淀失败原因，避免重复研究。

关键约束：

- Agent 可以自动推进到 `simulate`，因为它仍属于验证链路。
- Agent 不能自动越过 `live_approval_required`。
- 每次状态变化都必须写入 append-only event timeline。
- Web 第一版必须让用户看懂当前状态、状态变化原因、关键证据、反对意见和下一步。

## 旧资产迁移模块定位

旧资产迁移与验证应成为产品模块，而不是一次性工作。

它在 MVP 中的定位是 **验证材料池 / 候选资产准入模块**：

```text
旧策略 / 旧因子 / 外部策略
-> 迁移审查
-> crypto 改写
-> 基线回测
-> 滚动验证
-> Agent 分析评分
-> 进入候选池或淘汰
```

模块最小能力：

- 资产台账。
- 迁移审查。
- 验证记录。
- Agent 复盘。

不做：

- 不把旧策略整包迁移成实盘策略。
- 不因为旧策略机构级就默认可迁移。
- 不先调参后审查机制。

## 当前暂缓项

| 事项 | 暂缓原因 |
---|---|
| 直接引入 LangGraph / CrewAI / ADK 作为运行时依赖 | 产品闭环还在收敛，先借鉴模式，避免框架先行 |
| 分布式任务队列 | MVP 是本地个人常驻软件，单机队列足够 |
| 多用户权限系统 | 本地优先，远程化时再加 |
| A2A / MCP 正式接入 | 先设计安全和工具边界 |
| WebSocket | 当前 Agent 动态主要是单向流，SSE 足够 |
| 实盘执行控制台 | 研究闭环和候选池先完成，交易控制台作为第二阶段 |
| 桌面 App | MVP 先采用本地 Web 服务 + 浏览器；桌面壳后置 |

## 后续技术选型触发条件

| 触发条件 | 再评估什么 |
---|---|
| Agent 状态分支、暂停恢复和人工审批变复杂 | LangGraph 或等价 state machine runtime |
| 需要多个 worker 并发跑实验 | Redis queue / Celery / Dramatiq |
| 本地数据和事件需要远程访问、多用户访问 | Postgres / auth / remote deployment |
| Agent 需要调用外部工具生态 | MCP，但必须先做工具白名单和沙箱策略 |
| 外部 Agent 需要参与研究 | A2A |
| Agent 开始生成或修改策略代码 | OpenHands 式沙箱、审计和安全验证 |

## 文档维护规则

1. 新增 Agent 框架或 Web 框架前，必须先更新本文件。
2. 如果只是借鉴方法论，不能写成运行时依赖。
3. 如果引入新依赖，必须说明它解决哪个当前产品问题。
4. 如果影响用户第一屏，必须同时更新 `docs/PRODUCT_CONTROL_PANEL.md`。
5. 如果影响模块规划，必须同时更新 `docs/MODULE_PLAN_INDEX.md` 和 `TODO.md`。

## 外部资料

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangGraph durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)
- [Google ADK multi-agent systems](https://adk.dev/agents/multi-agents/)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [OpenHands runtime architecture](https://docs.openhands.dev/openhands/usage/architecture/runtime)
- [OpenHands agent architecture](https://docs.openhands.dev/sdk/arch/agent)
- [Dify](https://dify.ai/)
- [A2A Protocol](https://github.com/a2aproject/A2A)
- [MCP specification](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [Freqtrade bot execution logic](https://docs.freqtrade.io/en/stable/bot-basics/)
- [NautilusTrader overview](https://nautilustrader.io/docs/latest/concepts/overview/)
- [Qlib workflow](https://qlib.readthedocs.io/en/latest/component/workflow.html)
- [RD-Agent framework](https://rdagent.readthedocs.io/en/latest/project_framework_introduction.html)
