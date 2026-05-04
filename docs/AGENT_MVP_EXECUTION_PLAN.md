# Kronos Agent MVP 执行级开发计划

更新时间：2026-04-30

## 用途

这份文档把 `docs/AGENT_MVP_DEVELOPMENT_PLAN.md` 的 8 个 Batch 拆到可执行任务级。

它的目标是让后续开发可以按任务推进，而不是每次重新解释方向。

本文件回答：

1. 每个 Batch 内具体做哪些任务。
2. 每个任务允许改哪些文件。
3. 每个任务产出什么。
4. 每个任务怎么验收。
5. 每个 Batch 什么时候必须停止并进入下一批。
6. 哪些需求必须放到后续批次，不允许塞进当前批次。

## 使用规则

1. **按任务编号推进。** 任务编号格式为 `B{batch}.T{task}`。
2. **每次只认当前任务范围。** 如果发现相邻需求，记录到后续任务，不扩大当前任务。
3. **每个任务完成后更新 TODO。** 执行面板仍然以 `TODO.md` 为 live backlog。
4. **每个 Batch 完成后更新项目状态。** 同步 `docs/PROJECT_STATUS.md`、`task_plan.md`、`progress.md` 和 OpenSpec tasks。
5. **每个代码任务都要有测试。** 不允许只写实现不补测试。
6. **每个 Batch 有硬退出条件。** 达到退出条件后必须进入下一批。

## 任务模板

每个任务默认包含：

| 字段 | 含义 |
|---|---|
| 任务 ID | 例如 `B1.T3` |
| 目标 | 这项任务要完成的单一目标 |
| 允许文件范围 | 本任务允许新增或修改的文件 |
| 输入 | 依赖的上游文档、schema 或已有代码 |
| 输出 | 必须产出的代码、测试、文档或 artifact |
| 验收 | 判断完成的条件 |
| 禁止扩展 | 本任务不能顺手做的事 |

## 全局完成定义

任一代码任务完成时，至少满足：

- 相关单元测试或集成测试通过。
- `ruff` 覆盖改动文件通过。
- `mypy` 覆盖改动模块通过。
- `git diff --check` 通过。
- 新增 schema、状态、artifact 或 report 字段时，同步文档或测试 fixture。

完整批次完成时，至少满足：

```bash
UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run ruff check kronos tests cli
UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run mypy kronos cli
UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run pytest -q -m "not e2e"
git diff --check
```

Web 批次还必须加浏览器验收。

## Batch 0：规划收口和任务拆分

状态：已完成。

硬退出条件：

- 架构借鉴评审完成。
- OpenSpec 完成。
- 总开发规划完成。
- 本执行级开发计划完成。
- 已有资产复用和归档边界完成。
- TODO、项目状态、路线图和规划文件同步。

### B0.T1：架构借鉴评审

状态：已完成。

输出：

- `docs/AGENT_MVP_TECH_SELECTION_REVIEW.md`

验收：

- 明确 Agent 类项目是 architecture-reference，不是直接复制或接入。
- 明确基础设施依赖和 Agent 项目架构借鉴的区别。

### B0.T2：OpenSpec 准入

状态：已完成。

输出：

- `openspec/changes/p0-agent-runtime-web-workbench/`

验收：

- 覆盖 `agent-runtime`、`agent-workbench`、`agent-observability`、`agent-technology-governance`。

### B0.T3：开发批次规划

状态：已完成。

输出：

- `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`

验收：

- 0-8 全批次都有目标、退出条件和不做事项。

### B0.T4：执行级任务拆分

状态：已完成。

输出：

- `docs/AGENT_MVP_EXECUTION_PLAN.md`

验收：

- 每个 Batch 都有任务级拆分。
- Batch 1 有防打转边界。
- 后续开发可以直接从 B1.T1 开始。

### B0.T5：已有资产盘点和归档边界

状态：已完成。

输出：

- `docs/AGENT_MVP_ASSET_INVENTORY.md`
- `docs/ARCHIVE_INDEX.md`

验收：

- 直接复用、包一层复用、延期保留、主线归档和生成物清理候选都有明确分类。
- `research auto-run`、`kronos run today`、定时脚本和 Run MVP 验收口径不再被当成 Agent MVP 产品核心。
- 后续 Batch 1 开发有明确的旧资产复用边界。

## Batch 1：Agent Contracts + Observability Foundation

目标：固定 Agent 的数据契约、事件契约、报告契约和错误报告契约。

硬退出条件：

- Agent schema 定义完成。
- event timeline writer 完成。
- report writer 最小接口完成。
- success / failure report fixture 完成。
- 单元测试通过。
- 未接 LLM、未做 supervisor、未做 Web、未做 tool executor。

### B1.T1：建立 `kronos/agent` 模块骨架

状态：已完成。

目标：建立 Agent 模块的最小包结构和 public exports。

允许文件范围：

- `kronos/agent/__init__.py`
- `tests/unit/agent/__init__.py`
- `tests/unit/agent/test_imports.py`

输入：

- `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`
- `openspec/changes/p0-agent-runtime-web-workbench/specs/agent-runtime/spec.md`

输出：

- 可 import 的 `kronos.agent` 包。

验收：

- `import kronos.agent` 无副作用。
- 包内不启动后台、不读写本地数据、不调用网络。

禁止扩展：

- 不定义完整业务 schema。
- 不接 CLI。

### B1.T2：定义 Agent 基础枚举和 ID 类型

状态：已完成。

目标：统一 Agent 事件、状态、角色和审批的枚举值。

允许文件范围：

- `kronos/agent/types.py`
- `tests/unit/agent/test_types.py`

输出：

- `AgentRunStatus`
- `AgentTaskStatus`
- `AgentEventLevel`
- `AgentEventType`
- `CandidateLifecycleState`
- `ApprovalType`
- `AgentRoleKind`

验收：

- 枚举值覆盖 OpenSpec 要求。
- 枚举值稳定、可序列化、使用 snake_case。

禁止扩展：

- 不写状态机转换逻辑。
- 不写 supervisor。

### B1.T3：定义核心 Agent schema

状态：已完成。

目标：定义 Agent run / task / event 的结构化数据模型。

允许文件范围：

- `kronos/agent/types.py`
- `tests/unit/agent/test_types.py`

输出：

- `AgentRun`
- `AgentTask`
- `AgentEvent`
- `AgentArtifactRef`
- `AgentErrorRef`

验收：

- 必填字段包含 `run_id`、`task_id`、`event_id`、`event_type`、`level`、`status`、`artifact_paths`。
- `AgentEvent` 可以 JSON 序列化。
- 缺少关键字段的对象不能通过测试 fixture。

禁止扩展：

- 不写文件 writer。
- 不写报告模板。

### B1.T4：定义角色、prompt 和输出契约 schema

状态：已完成。

目标：固定 Agent 输出契约和 prompt 版本追踪字段。

允许文件范围：

- `kronos/agent/types.py`
- `tests/unit/agent/test_types.py`

输出：

- `AgentRole`
- `PromptVersionRef`
- `ModelInvocationRef`
- `AgentOutput`
- `ApprovalRequirement`

验收：

- `AgentOutput` 至少包含 `conclusion`、`support_reasons`、`opposition_reasons`、`key_evidence`、`max_risk`、`next_action`、`approval_required`。
- `ModelInvocationRef` 包含 provider、model、prompt_version。
- key evidence 必须能引用 artifact path 或 run_id。

禁止扩展：

- 不做 prompt registry。
- 不接 DeepSeek。

### B1.T5：实现 append-only event timeline writer

状态：已完成。

目标：提供最小事件流写入能力。

允许文件范围：

- `kronos/agent/events.py`
- `tests/unit/agent/test_events.py`

输出：

- `AgentEventWriter`
- `write_event(event)`
- `read_events(run_dir)`

验收：

- 写入 `agent_events.jsonl`。
- 多次写入只追加，不覆盖。
- 读回顺序与写入顺序一致。
- 写入前做 secret-like 字段拦截或脱敏测试。

禁止扩展：

- 不做 SSE。
- 不做 Web API。
- 不做跨进程锁。

### B1.T6：实现报告 writer 最小接口

状态：已完成。

目标：生成 PM 可读报告、机器摘要和错误报告。

允许文件范围：

- `kronos/agent/reports.py`
- `tests/unit/agent/test_reports.py`

输出：

- `write_agent_run_summary`
- `write_agent_run_report`
- `write_agent_errors`

验收：

- 输出 `agent_run_summary.json`。
- 输出 `agent_run_report.md`。
- 失败时输出 `agent_errors.md`。
- Markdown 第一屏包含研究目标、原因、证据、结论、下一步和审批要求。
- secret-like 字段不出现在报告中。

禁止扩展：

- 不写完整 UI 文案系统。
- 不接知识库。

### B1.T7：补测试 fixture 和文档映射

状态：已完成。

目标：为后续批次提供稳定测试样例。

允许文件范围：

- `tests/unit/agent/fixtures/`
- `tests/unit/agent/test_reports.py`
- `docs/AGENT_MVP_DEVELOPMENT_PLAN.md`
- `TODO.md`

输出：

- success run fixture。
- failed run fixture。
- event timeline fixture。

验收：

- fixture 可被后续 Batch 2-5 复用。
- TODO 标记 Batch 1 可关闭项。

禁止扩展：

- 不跑真实 Agent run。
- 不改研究业务逻辑。

### B1.T8：Batch 1 收口

状态：已完成。

目标：关闭 Batch 1，切换到 Batch 2。

允许文件范围：

- `TODO.md`
- `docs/PROJECT_STATUS.md`
- `task_plan.md`
- `progress.md`
- `openspec/changes/p0-agent-runtime-web-workbench/tasks.md`

验收：

- Batch 1 所有任务完成。
- 项目级验证通过。
- 文档明确下一批是 Batch 2。

禁止扩展：

- 不因为发现 runtime 需求而继续扩 Batch 1。

## Batch 2：Agent Runtime Skeleton

目标：建立可启动、可停止、可查询状态的本地 Agent Supervisor 骨架。

状态：已完成（2026-04-30）。

完成证据：

- `kronos/agent/supervisor.py` 和 `tests/unit/agent/test_supervisor.py`
- `kronos/agent/queue.py` 和 `tests/unit/agent/test_queue.py`
- `kronos/agent/state_machine.py` 和 `tests/unit/agent/test_state_machine.py`
- `kronos/agent/idle.py` 和 `tests/unit/agent/test_idle.py`
- `kronos agent status` CLI 状态查询和集成测试

硬退出条件：

- supervisor lifecycle 完成。
- research queue 完成。
- idle scanner skeleton 完成。
- candidate lifecycle transition 完成。
- CLI 状态查询完成。
- 单主任务约束有测试。

### B2.T1：Supervisor lifecycle

状态：已完成。

允许文件范围：

- `kronos/agent/supervisor.py`
- `tests/unit/agent/test_supervisor.py`

输出：

- `AgentSupervisor`
- `start_run`
- `stop_run`
- `get_status`

验收：

- 可以创建 run。
- 可以停止 run。
- 状态查询返回当前 run、task、last_event。

禁止扩展：

- 不做 daemon。
- 不做 launchd。

### B2.T2：Research queue

状态：已完成。

允许文件范围：

- `kronos/agent/queue.py`
- `tests/unit/agent/test_queue.py`

输出：

- pending queue。
- single-main-task guard。

验收：

- 当前主任务 running 时，新任务进入 pending。
- 当前主任务完成后，下一个 pending 可以被取出。

禁止扩展：

- 不做 Redis / Celery。
- 不做多 worker。

### B2.T3：Candidate lifecycle state machine

状态：已完成。

允许文件范围：

- `kronos/agent/state_machine.py`
- `tests/unit/agent/test_state_machine.py`

输出：

- allowed transitions。
- invalid transition errors。

验收：

- 覆盖 material_intake -> migration_review -> hypothesis -> experiment_planned -> validating -> agent_analysis -> committee_scoring。
- 终态覆盖 observe / redesign / simulate / live_approval_required / retired。
- live_approval_required 不得自动进入 live。

禁止扩展：

- 不做真实候选数据库。

### B2.T4：Idle scanner skeleton

状态：已完成。

允许文件范围：

- `kronos/agent/idle.py`
- `tests/unit/agent/test_idle.py`

输出：

- scanner interface。
- material detector placeholders。

验收：

- 能返回 no_material / material_found。
- 不会无意义重复开启同一任务。

禁止扩展：

- 不自动抓新闻、论文、社媒。

### B2.T5：Failure convergence guard

状态：已完成。

允许文件范围：

- `kronos/agent/state_machine.py`
- `tests/unit/agent/test_state_machine.py`

输出：

- same-class failure counter。
- observe / retired recommendation。

验收：

- 连续两轮同类失败且无新证据时，返回 observe 或 retired。

禁止扩展：

- 不做复杂评分模型。

### B2.T6：CLI status surface

状态：已完成。

允许文件范围：

- `cli/main.py`
- `tests/integration/test_cli.py`

输出：

- `kronos agent status` 或等价入口。

验收：

- CLI 输出当前 run、task、status、last_event、pending_count。
- 无 active run 时输出用户可读状态。

禁止扩展：

- 不做完整 run command。

### B2.T7：Batch 2 收口

状态：已完成。

验收：

- 单主任务、状态机、CLI status 测试通过。
- 文档状态更新。
- 下一批切到 Batch 3。

## Batch 3：Prompt / Role / LLM Provider / SecretStore

目标：让 Agent 角色、prompt 版本和 DeepSeek provider 具备可追溯配置能力。

状态：已完成（2026-04-30）。

完成证据：

- `kronos/agent/roles.py` 和 `tests/unit/agent/test_roles.py`
- `kronos/agent/prompts.py` 和 `tests/unit/agent/test_prompts.py`
- `kronos/agent/secrets.py` 和 `tests/unit/agent/test_secrets.py`
- `kronos/agent/llm.py` 和 `tests/unit/agent/test_llm.py`
- `.gitignore` 已保护本地 `.kronos-secrets/`
- `configs/dev.toml` 和 `configs/backtest.toml` 已预留 DeepSeek provider 配置位

硬退出条件：

- role registry 完成。
- prompt draft / active 完成。
- SecretStore masked status 完成。
- DeepSeek provider adapter 完成。
- LLM 调用事件记录完成。
- 无真实 key 时有明确待配置状态。

### B3.T1：Role registry

状态：已完成。

允许文件范围：

- `kronos/agent/roles.py`
- `tests/unit/agent/test_roles.py`

输出：

- default roles。
- enable / disable role。

验收：

- 默认角色覆盖研究员、反方审查、风控审查、投委会裁决、执行记录分析。

禁止扩展：

- 不做多模型 A/B。

### B3.T2：Prompt version store

状态：已完成。

允许文件范围：

- `kronos/agent/prompts.py`
- `tests/unit/agent/test_prompts.py`

输出：

- draft prompt。
- active prompt。
- immutable prompt history。

验收：

- 修改 prompt 生成新版本，不覆盖旧版本。
- active 需要确认动作。

禁止扩展：

- 不做自动 prompt 优化。

### B3.T3：SecretStore

状态：已完成。

允许文件范围：

- `kronos/agent/secrets.py`
- `.gitignore`
- `tests/unit/agent/test_secrets.py`

输出：

- local secret storage abstraction。
- masked status。

验收：

- 明文 API Key 不出现在日志、报告、event、测试快照中。
- 本地 secret 文件在 `.gitignore` 保护范围。

禁止扩展：

- 不接远程 KMS。
- 不做多用户权限。

### B3.T4：LLM provider interface

状态：已完成。

允许文件范围：

- `kronos/agent/llm.py`
- `tests/unit/agent/test_llm.py`

输出：

- provider protocol。
- request / response schema。
- timeout / retry 配置字段。

验收：

- provider 可 mock。
- 缺 key 返回 waiting_configuration。

禁止扩展：

- 不接 LiteLLM。

### B3.T5：DeepSeek adapter

状态：已完成。

允许文件范围：

- `kronos/agent/llm.py`
- `configs/`
- `tests/unit/agent/test_llm.py`

输出：

- DeepSeek OpenAI-compatible adapter。

验收：

- 不写死具体模型名。
- 网络调用在测试中 mock。
- 连接测试可返回 masked provider status。

禁止扩展：

- 不做真实付费调用测试作为默认测试。

### B3.T6：LLM invocation events

状态：已完成。

允许文件范围：

- `kronos/agent/llm.py`
- `kronos/agent/events.py`
- `tests/unit/agent/test_llm.py`

输出：

- LLM 调用事件。

验收：

- 记录 role_id、prompt_version、provider、model、latency、status、artifact_paths。
- 不记录 secret。

## Batch 4：Deterministic Tool Executor + Agent Reports

状态：已完成。

目标：把 Agent 计划、确定性工具执行、结果读取和报告串成一个最小闭环。

硬退出条件：

- tool registry 完成。
- 工具输入输出和 artifact_paths 记录完成。
- propose / execute / conclude 串联完成。
- 报告引用确定性 artifact。

### B4.T1：Tool registry

状态：已完成。

允许文件范围：

- `kronos/agent/tools.py`
- `tests/unit/agent/test_tools.py`

输出：

- tool whitelist。
- tool metadata。

验收：

- 只有白名单工具可执行。
- 每个工具有 name、purpose、input_schema、output_schema。

禁止扩展：

- 不开放任意 shell。
- 不开放 MCP。

### B4.T2：Existing research tool adapters

状态：已完成。

允许文件范围：

- `kronos/agent/tools.py`
- `kronos/research/agent_planner.py`
- `tests/unit/agent/test_tools.py`

输出：

- workbench / evidence / conclude adapter。

验收：

- 能包装现有确定性研究 artifact。
- 不重写研究工具本身。

### B4.T3：Tool execution records

状态：已完成。

允许文件范围：

- `kronos/agent/tools.py`
- `kronos/agent/events.py`
- `tests/unit/agent/test_tools.py`

输出：

- tool_start / tool_finish / tool_error events。

验收：

- 每次工具执行记录输入摘要、状态、artifact_paths、error_code。

### B4.T4：One-cycle orchestrator

状态：已完成。

允许文件范围：

- `kronos/agent/planner.py`
- `kronos/agent/analyzer.py`
- `tests/unit/agent/test_planner.py`
- `tests/integration/test_cli.py`

输出：

- propose -> execute tools -> conclude -> next_action。

验收：

- 使用本地 fixture 可跑完一轮。
- 不自动递归开启第二轮。

### B4.T5：Knowledge base selective write

状态：已完成。

允许文件范围：

- `kronos/agent/analyzer.py`
- `kronos/research/knowledge_base/`
- `tests/unit/agent/`

输出：

- 只写研究结论、失败原因、状态变化、投委会分歧、审批记录。

验收：

- 原始技术日志不写入知识库。

### B4.T6：CLI Agent run command

状态：已完成。

允许文件范围：

- `cli/main.py`
- `tests/integration/test_cli.py`

输出：

- `kronos agent run-once` 或等价入口。

验收：

- 输出 report、summary、events。
- 失败时输出 errors。

## Batch 5：Local Web API

状态：已完成。

目标：为 Web 工作台提供稳定后端 API。

硬退出条件：

- FastAPI app factory 完成。
- API schemas 完成。
- candidate / event / settings / material / approval routes 完成。
- SSE endpoint 完成。
- 后端测试通过。

### B5.T1：FastAPI app factory

状态：已完成。

允许文件范围：

- `kronos/web/app.py`
- `kronos/web/__init__.py`
- `tests/integration/web/test_app.py`

输出：

- `create_app()`

验收：

- app 可在测试中启动。
- health endpoint 返回状态。

### B5.T2：Web API schemas

状态：已完成。

允许文件范围：

- `kronos/web/schemas.py`
- `tests/integration/web/test_schemas.py`

输出：

- Candidate list/detail schema。
- Agent status schema。
- Event schema。
- Settings schema。
- Approval schema。
- Material schema。

验收：

- schema 不暴露 secret。

### B5.T3：Agent status and candidate routes

状态：已完成。

允许文件范围：

- `kronos/web/routes/agent.py`
- `kronos/web/routes/candidates.py`
- `tests/integration/web/`

输出：

- status endpoint。
- candidate pool endpoint。
- candidate detail endpoint。

### B5.T4：Event timeline SSE

状态：已完成。

允许文件范围：

- `kronos/web/routes/events.py`
- `tests/integration/web/test_events.py`

输出：

- SSE endpoint。

验收：

- 可从 `agent_events.jsonl` 重建事件流。

### B5.T5：Settings / material / approval routes

状态：已完成。

允许文件范围：

- `kronos/web/routes/settings.py`
- `kronos/web/routes/materials.py`
- `kronos/web/routes/approvals.py`
- `tests/integration/web/`

验收：

- API Key masked。
- 材料导入不会直接绕过 migration_review。
- 审批动作记录事件。

## Batch 6：Web Research Workbench

状态：已完成。

目标：提供本地浏览器产品界面。

硬退出条件：

- 首页布局完成。
- 候选看板完成。
- Agent 时间线完成。
- 候选详情完成。
- 设置页完成。
- 材料导入和审批中心完成。
- 浏览器验收通过。

### B6.T1：Frontend scaffold

状态：已完成。

允许文件范围：

- `web/`
- frontend config files。

验收：

- 本地前端可启动。
- 不做营销页。

### B6.T2：Design system foundation

状态：已完成。

输出：

- layout。
- navigation。
- common components。
- empty / loading / error states。

验收：

- 风格是研究工作台，不是营销站。

### B6.T3：API client and query layer

状态：已完成。

输出：

- typed API client。
- TanStack Query hooks。

验收：

- candidate / events / settings / approvals 可读取。

### B6.T4：Candidate board

状态：已完成。

输出：

- TanStack Table 候选看板。

验收：

- 展示状态、评分、证据、最大问题、下一步。

### B6.T5：Agent timeline

状态：已完成。

输出：

- SSE timeline。

验收：

- 事件级别可识别：info / decision / warning / approval_required / error。

### B6.T6：Candidate detail

状态：已完成。

输出：

- 迁移审查、验证证据、Agent 分歧、投委会结论、状态变化。

### B6.T7：Settings, material import, approvals

状态：已完成。

输出：

- LLM 设置页。
- 材料导入页。
- 审批中心。

验收：

- API Key 仅 masked。
- prompt activation / simulation admission / live application 可展示。

### B6.T8：Browser QA

状态：已完成。

验收：

- 桌面和窄屏都可读。
- 无明显文本溢出。
- 第一屏能回答五个产品问题。

## Batch 7：Agent Loop Integration Acceptance

状态：已完成（2026-04-30）。

目标：跑通一轮完整 Agent MVP 验收。

完成证据：

- 验收批次：`20260430-agent-acceptance-v1`
- Agent run report：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_report.md`
- Agent run summary：`reports/research/experiments/20260430-agent-acceptance-v1/agent_run_summary.json`
- Agent events：`reports/research/experiments/20260430-agent-acceptance-v1/agent_events.jsonl`
- Web runtime events：`reports/agent_runtime/20260430-agent-acceptance-v1/agent_events.jsonl`
- Web run summary API：`/api/agent/runs/20260430-agent-acceptance-v1/summary`

硬退出条件：

- 真实本地数据完成 Agent run。
- Web 可读取结果。
- 报告可给产品经理验收。
- 知识库写入符合边界。

### B7.T1：Acceptance fixture preparation

状态：已完成。

输出：

- 选择真实上一轮研究摘要：`reports/research/experiments/20260427-run-mvp-v1-research/auto_run_summary.json`。
- 选择真实专项证据：`trend_pullback_entry` 和 `multi_timeframe_confirmation` evidence review。

### B7.T2：Run full local Agent cycle

状态：已完成。

输出：

- `agent_run_report.md`
- `agent_run_summary.json`
- `agent_events.jsonl`
- `agent_errors.md` 如失败。

### B7.T3：Web acceptance read

状态：已完成。

验收：

- Web 首页显示当前研究目标、原因、证据、下一步和审批。
- Playwright 验证桌面和 390px 窄屏能读取 `20260430-agent-acceptance-v1`，且无整页横向溢出。

### B7.T4：Knowledge base verification

状态：已完成。

验收：

- 只写允许的知识类型。
- 可通过 run_id 追溯。
- 本轮保留 2 条 Agent 研究记忆：`agent_research_plan` 和 `agent_research_decision`。

### B7.T5：Acceptance documentation

状态：已完成。

输出：

- 更新 `docs/AGENT_MVP_ACCEPTANCE.md`。
- 更新 `docs/PROJECT_STATUS.md`。

## Batch 8：Hardening and Release Readiness

状态：已完成。

目标：把 MVP 收口成可验收状态。

硬退出条件：

- QA 通过。
- 文档同步。
- 风险清单明确。
- OpenSpec tasks 回填。
- MVP 验收入口明确。

### B8.T1：Error taxonomy hardening

状态：已完成。

输出：

- 已新增 `AgentErrorCategory`。
- `agent_errors.md` 已展示错误分类、直接影响、用户可处理性和下一步动作。

### B8.T2：Secret and safety audit

状态：已完成。

验收：

- 日志、报告、Web、event timeline 不泄露 secret。
- 交付批次 report/event/runtime secret 扫描无命中。

### B8.T3：Timeline replay and recovery

状态：已完成。

验收：

- Web 可从 event timeline 重建最近状态。
- Supervisor 快照缺失时可从最近 `agent_events.jsonl` 恢复状态。

### B8.T4：Performance and UX QA

状态：已完成。

验收：

- 首屏可读。
- 候选看板、timeline、详情页无明显卡顿或布局问题。
- Playwright 桌面和 390px 窄屏均验证无整页横向溢出。

### B8.T5：Docs and OpenSpec sync

状态：已完成。

输出：

- OpenSpec tasks 回填。
- TODO 同步。
- Project status 同步。
- Roadmap 同步。
- 新增 `docs/AGENT_MVP_DELIVERY.md`。

### B8.T6：MVP acceptance package

状态：已完成。

输出：

- 验收批次 run_id：`20260430-agent-mvp-delivery-v1`。
- 报告路径：`reports/research/experiments/20260430-agent-mvp-delivery-v1/agent_run_report.md`。
- Web 访问方式：`http://127.0.0.1:3000`。
- 已知风险和下一阶段建议已写入 `docs/AGENT_MVP_DELIVERY.md`。
