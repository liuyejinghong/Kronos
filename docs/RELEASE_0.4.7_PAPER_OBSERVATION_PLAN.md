# Kronos v0.4.7 版本需求：只读观察计划

> 状态：已完成
> 版本目标：0.4.7
> 约束来源：`docs/PROJECT_STATUS.md`、`TODO.md`、`docs/USER_PERSONAS.md`、`openspec/changes/p4-research-interpretation-path/`

## 版本目标

v0.4.6 已经把 fresh Docker 新用户体验和研究报告第一屏压到可读状态。v0.4.7 不急着接实时模拟盘，而是先补一层更稳的产品过渡：把研究报告转换成一份**只读观察计划**。

这份计划回答四个问题：

1. 当前策略是否值得进入只读观察。
2. 如果进入观察，观察对象、样本和前提是什么。
3. 虚拟订单、延迟和滑点按什么假设记录。
4. 什么条件必须人工确认，不能自动升级到实盘。

## 版本承诺

1. 用户可以从最新研究报告生成只读观察计划。
2. 计划必须显式说明不会发送真实订单。
3. 计划必须记录虚拟订单、延迟、滑点和人工闸门假设。
4. sample 试跑、短样本和未通过策略不会被包装成可观察结论。
5. 系统仍不连接真实交易、不启动实时模拟盘、不自动下单。

## 产品边界

### In Scope

- `report observation-plan`：从最新报告或指定报告生成只读观察计划。
- 观察计划 Markdown 产物：可被用户、Agent 和后续 Web 工作台读取。
- 从自动研究摘要里提取数据来源、样本范围、评估对象和通过数量。
- 根据 sample / 短样本 / 通过数量给出观察准入判断。
- 固定的虚拟订单假设：只记录虚拟信号，不发真实订单；默认 1 根 bar 延迟；默认 5 bps 滑点；人工确认才能进入更强执行态。

### Out of Scope

- 实时行情订阅。
- Binance API Key 接入。
- 真实模拟盘撮合。
- 虚拟 PnL 曲线。
- 自动下单。
- 实盘执行。
- 任意策略自动生成。

## 用户流程

### 默认路径

1. 用户运行 `kronos quickstart` 或 `kronos research auto-run`。
2. 用户运行 `kronos report latest` 阅读结果卡。
3. 用户运行 `kronos report observation-plan` 生成只读观察计划。
4. 系统告诉用户当前是：
   - 不建议观察；
   - 需要补数据后再观察；
   - 可以进入只读观察候选；
   - 仍需人工确认，不能进入实盘。

### Docker 路径

Docker 用户使用：

```bash
docker compose run --rm kronos uv run kronos report observation-plan
```

输出路径必须是容器内可读路径，并且报告正文必须继续说明当前不会启动模拟盘或真实订单。

## 功能需求

### 需求 1：只读观察计划必须来自真实报告

系统 SHALL 从最新研究报告或用户指定报告生成观察计划，不得凭空生成。

#### 验收点

- 没有报告时，命令失败并提示先运行 quickstart 或研究工作台。
- 有报告时，计划记录来源报告路径。
- 自动研究报告优先读取结构化摘要。

### 需求 2：计划必须给出准入判断

系统 SHALL 明确告诉用户当前是否适合进入只读观察。

#### 验收点

- sample 试跑只能得到“不建议观察，先同步真实行情”。
- 短样本只能得到“先补数据，再观察”。
- 没有策略通过验证时，不能建议进入模拟盘。
- 有策略通过时，也只能进入只读观察候选，不能进入实盘。

### 需求 3：计划必须记录虚拟订单假设

系统 SHALL 在计划中记录虚拟订单、延迟和滑点假设。

#### 验收点

- 明确“不发送真实订单”。
- 明确“虚拟成交必须标记为虚拟”。
- 明确默认延迟和滑点。
- 明确后续可以由真实模拟盘替换这些假设。

### 需求 4：计划必须保留人工闸门

系统 SHALL 在只读观察和更强执行态之间保留人工确认。

#### 验收点

- 计划中必须写明“人工确认前不能进入实盘”。
- 即使观察结果未来看起来很好，也不能自动升级。
- 报告语言不得出现“已证明可交易”。

## 版本完成标准

v0.4.7 完成时，必须满足：

1. `kronos report observation-plan` 可以生成 Markdown 计划。
2. 计划能清楚区分 sample、短样本、通过策略和未通过策略。
3. README、TODO、PROJECT_STATUS、ROADMAP、CHANGELOG 与版本边界一致。
4. OpenSpec 约束已落地。
5. 测试覆盖成功路径、无报告路径和 sample 边界路径。

## 已完成验证

- 目标回归：`uv run pytest tests/unit/test_observation_plan.py tests/integration/test_cli.py::TestReportCLI -q` 通过，覆盖 sample 阻断、短样本阻断、缺历史覆盖阻断、未通过策略、指定报告、缺失报告和默认最新报告。
- 质量门禁：`uv run ruff check .`、`uv run mypy kronos cli`、`uv run pytest -m "not e2e"`、`cd web && npm run typecheck`、`cd web && npm run build` 已通过。
- Docker 验证：`docker compose -p kronosv047 up --build --abort-on-container-exit` 和 `docker compose -p kronosv047 run --rm kronos uv run kronos report observation-plan` 已通过，容器内输出“不建议观察 / 先同步真实行情”，未启动模拟盘或真实订单。

## 测试与验证

至少需要覆盖：

- 单元测试：观察计划生成、sample 阻断、短样本判断、通过策略判断。
- 集成测试：`report observation-plan` 默认最新报告、指定报告、无报告失败。
- 文档验证：版本需求、OpenSpec、TODO、PROJECT_STATUS、ROADMAP 同步。
- 发布验证：ruff、pytest、mypy、前端 typecheck/build、Docker quickstart。

## OpenSpec 约束

v0.4.7 的正式实现约束由 `openspec/changes/p4-paper-observation-plan/` 提供。后续围绕实时模拟盘继续开发时，必须先保留本版本确立的只读观察边界和人工闸门。
