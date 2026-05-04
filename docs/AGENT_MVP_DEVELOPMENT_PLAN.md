# Kronos Agent MVP 完整开发规划

更新时间：2026-04-30

## 当前结论

架构借鉴、技术选型评审、OpenSpec、开发规划、执行级任务拆分和已有资产盘点已经完成，**Batch 1 到 Batch 8 已完成**。当前进入 Agent MVP 产品验收。

后续研发必须沿用这份批次规划，优先复用已有确定性研究工具，不把 Run MVP / 定时器旧口径拉回产品核心。

## 上游约束

本开发规划受以下文档约束：

| 文档 | 用途 |
|---|---|
| `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md` | Agent 类项目只做架构借鉴；基础设施依赖单独处理 |
| `openspec/changes/p0-agent-runtime-web-workbench/` | Agent runtime、Web workbench、日志报告、技术治理的正式 spec |
| `docs/AGENT_MVP_ACCEPTANCE.md` | Agent MVP 的产品验收口径 |
| `docs/PRODUCT_CONTROL_PANEL.md` | 产品经理视角的当前状态和验收入口 |
| `docs/OPEN_SOURCE_INFLUENCE_MAP.md` | 每个能力环节借鉴了哪些项目的哪些架构 |
| `docs/AGENT_MVP_ASSET_INVENTORY.md` | 已有代码、文档、测试和脚本的复用 / 适配 / 延期 / 主线归档边界 |
| `TODO.md` | 当前可执行 backlog |

执行级任务拆分见 `docs/AGENT_MVP_EXECUTION_PLAN.md`。本文件负责路线和批次边界，执行计划负责每个 Batch 内的任务编号、允许文件范围、验收标准和禁止扩展项。

## MVP 北极星

Kronos Agent MVP 不是一个命令行脚本，也不是每天重复跑一次报告。

MVP 交付后，用户应该能打开本地 Web 研究工作台，看见：

1. 当前 Agent 正在研究什么。
2. 为什么研究它。
3. 使用了哪些候选、数据、实验和证据。
4. Agent 的支持理由、反对理由、最大风险和下一步动作。
5. 哪些动作需要用户审批。
6. 如果失败，失败在哪、影响什么、下一步怎么处理。

## 总体开发顺序

```text
0. 开发规划和任务拆分
1. Agent contracts + observability foundation
2. Agent runtime skeleton
3. Prompt / role / LLM provider / SecretStore
4. Deterministic tool executor + reports
5. Local Web API
6. Web research workbench
7. Agent loop integration acceptance
8. Hardening and release readiness
```

顺序原则：

- 先定义数据契约，再写运行逻辑。
- 先定义日志和报告，再做长运行后台。
- 先做后端 API schema，再做前端页面。
- 先让单主研究任务可解释，再考虑多任务并发。
- 先接 DeepSeek provider adapter，不引入 LiteLLM。
- 先自建轻量状态机，不引入 LangGraph / CrewAI / ADK。

## 批次推进硬规则

为避免长期卡在某一个批次，每个 Batch 都必须遵守：

1. **只做本批次范围。** 如果发现新需求，记录到后续批次或 `TODO.md`，不得直接塞进当前批次。
2. **达到退出条件就切换批次。** 不因为“还可以更完善”而继续扩展当前批次。
3. **每批次结束必须更新状态。** 同步 `TODO.md`、`docs/PROJECT_STATUS.md`、`task_plan.md` 和对应 OpenSpec tasks。
4. **每批次只允许一个主目标。** 例如 Batch 1 只做 contracts / observability foundation，不做 runtime、LLM、Web。
5. **跨批次需求必须显式升级。** 如果确实要改变顺序，必须更新本规划并说明原因。

| Batch | 主目标 | 硬退出条件 | 下一批 |
|---|---|---|---|
| 0 | 开发规划、任务拆分和资产盘点 | 本文档、执行计划、资产盘点、TODO、路线图、项目状态已同步 | Batch 1 |
| 1 | Agent contracts + observability foundation | 已完成：schema、event writer、report writer、错误报告接口和单元测试完成 | Batch 2 |
| 2 | Agent runtime skeleton | 已完成：supervisor skeleton、queue、idle scanner、状态机、CLI 状态查询和测试完成 | Batch 3 |
| 3 | Prompt / role / LLM / SecretStore | 已完成：role registry、prompt version、DeepSeek adapter、SecretStore masked status 和测试完成 | Batch 4 |
| 4 | Deterministic tool executor + reports | 已完成：tool executor、artifact_paths、propose / tool execution / conclude 串联、选择性知识库写入规则和 `kronos agent run-once` 完成 | Batch 5 |
| 5 | Local Web API | 已完成：FastAPI app factory、API schema、Agent/candidate/event/settings/material/approval routes、SSE、masked settings 和后端测试完成 | Batch 6 |
| 6 | Web research workbench | 已完成：Next.js 本地前端、候选看板、Agent 时间线、详情页、设置页、材料导入、审批中心和浏览器验收完成 | Batch 7 |
| 7 | Agent loop integration acceptance | 已完成：真实本地数据完成一轮 Agent run，Web 和报告可验收 | Batch 8 |
| 8 | Hardening and release readiness | 已完成：QA、文档、风险、OpenSpec tasks 和验收证据收口 | MVP 验收 |

### Batch 1 防打转边界

Batch 1 只允许交付：

- Agent 相关 schema。
- append-only event timeline writer。
- report writer 的最小接口。
- 成功 / 失败报告模板。
- schema 和 writer 的单元测试。

Batch 1 明确禁止：

- 接 DeepSeek 或任何 LLM。
- 做 Agent Supervisor。
- 做 Web API 或 Web UI。
- 做后台常驻。
- 做工具执行编排。
- 做候选生命周期完整状态机。

如果 Batch 1 过程中发现上述需求，必须放入 Batch 2、3、4、5 或 6，而不是扩展 Batch 1。

## 开发批次

### Batch 0：规划收口、任务拆分和资产盘点

目标：把 OpenSpec 拆成后续开发的执行计划，并明确旧资产复用与归档边界。

产物：

- `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`
- `docs/AGENT_MVP_EXECUTION_PLAN.md`
- `docs/AGENT_MVP_ASSET_INVENTORY.md`
- `docs/ARCHIVE_INDEX.md`
- 更新 `TODO.md`
- 更新 `docs/ROADMAP.md`
- 更新 `docs/PROJECT_STATUS.md`
- 更新 `task_plan.md` / `progress.md`

完成标准：

- 用户能看懂后续开发顺序。
- 每个开发批次都有产品目标、工程范围、验收方式和不做事项。
- 已有代码资产的复用、适配、延期和主线归档边界清楚。
- 没有直接进入产品代码实现。

### Batch 1：Agent Contracts + Observability Foundation

状态：已完成。

目标：先固定 Agent run 的数据契约、事件契约和报告契约。

建议代码范围：

- `kronos/agent/types.py`
- `kronos/agent/events.py`
- `kronos/agent/reports.py`
- `tests/unit/agent/`

核心能力：

- `AgentRun`
- `AgentTask`
- `AgentEvent`
- `AgentRole`
- `PromptVersion`
- `CandidateState`
- `AgentOutput`
- `ApprovalRequirement`

必须产物：

- `agent_events.jsonl`
- `agent_run_summary.json`
- `agent_run_report.md`
- `agent_errors.md`

验收方式：

- 单元测试覆盖 schema 必填字段。
- 报告生成测试覆盖成功和失败两种状态。
- 日志和报告不得包含明文 secret。

不做事项：

- 不接 LLM。
- 不做 Web UI。
- 不做长运行 supervisor。

### Batch 2：Agent Runtime Skeleton

目标：建立可启动、可停止、可查询状态的本地 Agent Supervisor 骨架。

建议代码范围：

- `kronos/agent/supervisor.py`
- `kronos/agent/queue.py`
- `kronos/agent/state_machine.py`
- `kronos/agent/idle.py`
- `cli/main.py`
- `tests/unit/agent/`
- `tests/integration/test_cli.py`

核心能力：

- 本地 supervisor lifecycle。
- 单主研究任务。
- pending research queue。
- idle scanner 框架。
- 候选生命周期状态机。
- 单轮防递归。
- 两轮同类失败后的 observe / retired 收敛规则。

验收方式：

- CLI 可以查看 Agent 当前状态。
- 单主任务运行时，新任务进入队列而不是并发启动。
- 状态变化都会写入 event timeline。
- 失败收敛规则有测试。

不做事项：

- 不做真实后台 daemon 安装。
- 不做多 worker。
- 不做远程访问。

### Batch 3：Prompt / Role / LLM Provider / SecretStore

目标：让 Agent 角色、prompt 版本和 DeepSeek provider 具备可追溯配置能力。

建议代码范围：

- `kronos/agent/roles.py`
- `kronos/agent/prompts.py`
- `kronos/agent/llm.py`
- `kronos/agent/secrets.py`
- `configs/`
- `tests/unit/agent/`

核心能力：

- 角色注册。
- prompt draft / active 版本。
- prompt 新版本人工确认后才能 active。
- DeepSeek-first provider adapter。
- provider / model / base_url 可配置。
- SecretStore masked status。
- LLM 调用事件记录。

验收方式：

- API Key 不进入日志、报告、event timeline 或前端响应。
- 每次 LLM 调用记录 role、prompt_version、provider、model、latency、status。
- DeepSeek 连接测试可在无真实 key 时返回明确待配置状态。

不做事项：

- 不引入 LiteLLM。
- 不做多模型 A/B。
- 不做自动 prompt 优化。

### Batch 4：Deterministic Tool Executor + Agent Reports

状态：已完成。

目标：把 Agent 的计划、确定性工具执行、结果读取和报告串成一个最小闭环。

建议代码范围：

- `kronos/agent/tools.py`
- `kronos/agent/planner.py`
- `kronos/agent/analyzer.py`
- `kronos/research/agent_planner.py` 的兼容迁移或包装
- `tests/unit/agent/`
- `tests/integration/test_cli.py`

核心能力：

- 工具白名单。
- 工具输入参数记录。
- 工具运行状态记录。
- artifact_paths 记录。
- 工具失败转成 `agent_errors.md`。
- `propose -> execute tools -> conclude -> next_action` 串联。

验收方式：

- 用现有本地研究 artifact 跑一轮 Agent run。
- 报告能说明当前研究目标、原因、证据、结论、下一步和审批。
- Agent 结论必须引用确定性工具 artifact。

不做事项：

- 不让 LLM 直接写策略代码。
- 不自动进入组合或实盘。
- 不做 Freqtrade 真实外部执行，除非单独计划启动。

### Batch 5：Local Web API

状态：已完成。

目标：在后端提供 Web 研究工作台需要的稳定 API。

建议代码范围：

- `kronos/web/app.py`
- `kronos/web/schemas.py`
- `kronos/web/routes/`
- `tests/integration/web/`

API 范围：

- candidate pool。
- candidate detail。
- Agent current status。
- Agent event timeline。
- approval items。
- LLM settings masked status。
- prompt versions。
- material import。
- report/artifact references。

验收方式：

- FastAPI app 可启动。
- API schema 测试通过。
- SSE endpoint 能从 `agent_events.jsonl` 重建时间线。
- Web API 不返回明文 secret。

不做事项：

- 不做用户登录。
- 不做远程部署。
- 不做复杂权限系统。

### Batch 6：Web Research Workbench

状态：已完成。

目标：让产品经理通过浏览器验收 Kronos，而不是读 CLI 输出。

建议代码范围：

- `web/` 或等价前端目录。
- Next.js App Router + TypeScript。
- shadcn/ui + Tailwind + Radix。
- TanStack Query / Table。
- Apache ECharts。

第一版页面：

- 候选资产看板。
- Agent 工作流时间线。
- 候选详情页。
- LLM / Agent 设置页。
- 材料导入页。
- 审批中心。

验收方式：

- 浏览器第一屏能回答：现在研究什么、为什么、证据是什么、下一步是什么、哪里需要审批。
- 候选表格支持基础筛选、排序和状态查看。
- Agent 时间线能实时或准实时更新。
- 设置页只展示 API Key masked 状态。

不做事项：

- 不做营销落地页。
- 不做桌面 App。
- 不做复杂工作流编辑器。

### Batch 7：Agent Loop Integration Acceptance

状态：已完成。

目标：跑通一轮完整 Agent MVP 验收批次。

完成证据：

- 验收批次：`20260430-agent-acceptance-v1`
- Agent run report：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_report.md`
- Agent run summary：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_summary.json`
- Agent events：`reports/research/experiments/20260430-agent-acceptance-v1/agent_events.jsonl`
- Web runtime events：`reports/agent_runtime/20260430-agent-acceptance-v1/agent_events.jsonl`
- Web run summary API：`/api/agent/runs/20260430-agent-acceptance-v1/summary`

输入：

- 旧策略迁移材料。
- 候选池待验证项。
- 失败记录。
- 上一轮研究摘要。
- 用户手动导入材料。

输出：

- `agent_run_report.md`
- `agent_run_summary.json`
- `agent_events.jsonl`
- `agent_errors.md` 如失败
- Web 上可见的候选状态变化和审批项

验收方式：

- 真实本地数据跑一轮 Agent run。
- Web 第一屏可读。
- 知识库只写入研究结论、失败原因、候选状态变化、投委会分歧和审批记录。
- `ruff`、`mypy`、`pytest -m "not e2e"`、`git diff --check` 通过。

不做事项：

- 不自动真钱交易。
- 不安装定时器作为 MVP 主线。
- 不做多候选同时研究。

### Batch 8：Hardening and Release Readiness

目标：把 MVP 从“能跑”提升到“可验收、可排查、可继续迭代”。

重点：

- 错误分类补全。
- 报告模板打磨。
- Web 第一屏产品 QA。
- Secret 脱敏复查。
- 事件时间线重放。
- OpenSpec tasks 回填。
- TODO 和项目状态同步。

验收方式：

- 产品经理能通过 Web 和报告完成一次验收。
- 开发者能通过 run_id 定位到事件、工具、报告、错误和知识库条目。
- 所有剩余风险写入 `docs/PROJECT_STATUS.md`。

## 模块边界

| 模块 | 职责 | 不负责 |
|---|---|---|
| `kronos/agent` | Agent runtime、角色、状态机、事件、工具执行、报告 | Web UI、交易所直接执行 |
| `kronos/web` | FastAPI app、API schema、SSE、Web 后端访问层 | 量化研究逻辑本身 |
| `web/` | Next.js 产品界面 | 直接读本地文件、保存密钥 |
| `kronos/research` | 现有确定性研究工具 | Agent 角色和审批逻辑 |
| `kronos/research/knowledge_base` | 研究结论和失败记忆 | 原始技术日志归档 |
| `kronos/research/experiments` | run_id、ledger、artifact 串联 | Web 产品展示 |

## 日志和报告标准

任何批次只要引入长运行、Agent 决策、LLM 调用或工具执行，都必须同时考虑：

- structured log。
- `agent_events.jsonl`。
- `agent_run_summary.json`。
- `agent_run_report.md`。
- `agent_errors.md`。
- secret 脱敏。
- `run_id` 和 `artifact_paths` 串联。

## 开发验收命令

每个代码批次至少运行：

```bash
UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run ruff check kronos tests cli
UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run mypy kronos cli
UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run pytest -q -m "not e2e"
git diff --check
```

Web 批次额外要求：

- 本地后端可启动。
- 本地前端可启动。
- 使用浏览器验证第一屏、候选看板、Agent 时间线、候选详情、设置页和审批中心。

## 当前不做

- 不自动真钱交易。
- 不接执行层。
- 不引入 LangGraph / CrewAI / Google ADK 作为运行时依赖。
- 不引入 LiteLLM。
- 不接 OpenTelemetry。
- 不开放 MCP 任意本地工具。
- 不做 A2A 外部 Agent 网络。
- 不做桌面 App。
- 不做多用户权限。

## 下一步执行建议

下一步应从 **Agent MVP 产品验收** 开始。

原因：

- Batch 1 已经把 Agent run、事件、报告和错误这些长期骨架定下来。
- Batch 2 已经让这些契约支撑一个可启动、可停止、可查询状态的本地运行主体。
- Batch 3 已接入 Agent 角色、prompt 版本、DeepSeek provider 配置和 SecretStore。
- Batch 4 已把已有确定性研究工具纳入 Agent runtime，让 Agent 计划、执行和结论能形成一轮最小闭环。
- Batch 5 已为 Web 研究工作台提供稳定后端 API。
- Batch 6 已完成本地浏览器工作台，让候选池、Agent 时间线、设置、材料导入和审批中心进入产品第一屏。
- Batch 7 已完成真实本地 Agent loop 集成验收，让 Web 和报告读取同一批次结果。
- Batch 8 已完成 release readiness，让 Web 默认读取 `20260430-agent-mvp-delivery-v1`，并补齐错误分类、时间线恢复、DeepSeek 配置状态检查、secret 脱敏复查和交付验收文档。

第一批最小任务：

1. 产品验收 `docs/AGENT_MVP_DELIVERY.md` 和 Web 默认交付批次 `20260430-agent-mvp-delivery-v1`。
2. 验收通过后，进入候选评分维度和失败记忆约束。
3. 围绕 `trend_pullback_entry` 做 crypto-native 改造 proposal。
4. 补真实实验图表。
