# Kronos v0.4.9 版本需求：测试网证据与 Web 状态可见性

> 状态：已完成；真实 testnet E2E 与 Web 状态验收均已通过
> 版本目标：0.4.9
> 优先级：P0 / P1
> 约束来源：`docs/RELEASE_0.4.8_TESTNET_PAPER_TRADING.md`、`docs/TESTNET_E2E_ATTEMPT_20260509.md`、`TODO.md`、`docs/PROJECT_STATUS.md`、`docs/ROADMAP.md`

## 版本定位

v0.4.8 已经完成 Binance testnet paper trading 最小闭环：凭证、preflight、start/status/stop、订单 / 成交 / 错误 ledger 和 Markdown 报告。

v0.4.9 的目标不是扩展交易能力，而是补齐两个验收缺口：

1. **真实 testnet E2E 证据**：在用户提供测试网凭证且存在合格观察候选时，跑一次人工授权的最小 testnet 订单，保留订单 ID、trade 明细、成交时间、手续费、状态 JSON 和报告证据。
2. **Web 状态可见性**：Web 工作台能展示测试网模拟盘状态、最近订单、最近成交 / 错误和报告入口，让用户不用只靠 CLI 读文件。

这版仍然不是实盘版本，不允许主网、不允许真实资金、不允许自动升级 live。

## 为什么要做

v0.4.8 已证明“系统结构可以安全地进入测试网模拟盘”，但 2026-05-09 的真实验收尝试没有提交订单。原因是产品闸门正确阻止了不合格下单：

- 初始验收时本地没有 Binance testnet API Key / Secret；后续用户已重新提供并写入本机 ignored SecretStore，且无下单 account ping / ticker 校验通过；
- 真实 90 天数据研究没有 promoted 候选；
- 观察计划状态为“暂不观察”；
- preflight 正确失败。

这说明 v0.4.8 的安全门禁有效，但产品验收仍差两步：

- 用户有合格候选后，需要一次真实 testnet 证据；
- Web 需要能看见 paper run 状态和报告，否则模拟盘能力仍像 CLI 内部功能。

## 产品承诺

1. 系统只在测试网凭证和合格观察候选同时存在时允许真实 testnet 下单。
2. 真实 testnet 订单必须记录交易所返回的 order id。
3. 真实 testnet 成交必须记录 trade id、成交价、数量、手续费、手续费资产和成交时间。
4. 所有真实 testnet 验收必须保留本地 Markdown / JSON / JSONL 证据。
5. Web 工作台必须展示当前 paper 状态、最近 run、最近订单 / 成交 / 错误和报告入口。
6. Web 必须清楚标记 `testnet`，并明确测试网资金不等于真实收益。
7. Web 不提供主网实盘启动入口。
8. Web 不显示 API Key / Secret 原文。

## 产品边界

### In Scope

- 真实 Binance testnet E2E 手动验收流程和证据记录。
- Web API 读取 `reports/paper/current_status.json` 和最近 paper run 产物。
- Web 工作台展示测试网模拟盘状态。
- Web 工作台展示最近订单、成交、错误和报告入口。
- Web 工作台在无凭证、无合格观察候选、无 paper run 时给出清晰下一步。
- 文档化 v0.4.9 手动验收流程和阻塞条件。

### Out of Scope

- Binance mainnet / live trading。
- Web 直接输入或保存 API Key / Secret。
- Web 一键启动真实 testnet 下单。
- 多策略组合执行。
- 长时间 daemon / 生产级容灾。
- 自动放宽观察计划、promoted 候选或 preflight 闸门。
- 自动把 testnet 盈利升级为实盘建议。

## 用户流程

### A. 真实 testnet E2E 验收

1. 用户通过环境变量或隐藏输入配置 Binance testnet API Key / Secret。
2. 系统确认凭证状态，只显示脱敏结果。
3. 系统使用真实数据产出合格观察候选；如果没有 promoted 候选，必须停止。
4. 系统从合格报告生成只读观察计划。
5. 系统运行 `paper preflight`。
6. preflight 通过后，用户明确授权最小订单。
7. 系统运行一笔受限 testnet 订单。
8. 系统记录 order id、trade 明细、成交时间、手续费、状态和报告。
9. 用户可在 CLI 和 Web 中查看状态和报告。

### B. Web 查看模拟盘状态

1. 用户打开 Web 工作台。
2. 进入“测试网模拟盘”或现有 Agent / 报告页面中的 paper 状态区。
3. 系统展示：
   - 当前环境：testnet；
   - 当前状态：未配置 / 阻塞 / 运行中 / 已停止 / 失败 / 完成；
   - 最近 run id；
   - 最近订单和成交；
   - 最近错误；
   - 报告入口；
   - 下一步。

## 功能需求

### 需求 1：真实 testnet E2E 仍必须受 preflight 闸门约束

系统 SHALL 只有在凭证、观察计划、研究证据和风控限额都通过 preflight 后，才允许真实 testnet 下单。

#### 验收点

- 无测试网凭证时，不得启动。
- 无 promoted 候选时，不得启动。
- 观察计划为“暂不观察”时，不得启动。
- preflight 未通过时，不得启动。
- 用户未明确授权时，不得提交真实 testnet 订单。

### 需求 2：真实 testnet 证据必须可追溯

系统 SHALL 保留真实 testnet 订单和成交证据。

#### 验收点

- 订单记录必须有 Binance testnet order id。
- 成交记录必须来自 testnet trade 明细。
- 成交记录必须包含 trade id、价格、数量、手续费、手续费资产和时间。
- 状态 JSON、订单 JSONL、成交 JSONL、错误 JSONL 和 Markdown 报告必须能互相指向。
- 报告必须说明 testnet 不代表实盘收益。

### 需求 3：Web 必须展示 paper 状态

系统 SHALL 在 Web 工作台展示测试网模拟盘状态。

#### 验收点

- 显示当前 paper status。
- 显示环境为 testnet。
- 显示最近 run id 和更新时间。
- 显示停止状态和失败状态。
- 无 run 时显示下一步，不显示空白或工程错误。

### 需求 4：Web 必须展示最近订单、成交、错误和报告入口

系统 SHALL 在 Web 工作台展示最近 paper run 的关键证据。

#### 验收点

- 最近订单显示 symbol、side、quantity、status、order id、时间。
- 最近成交显示 price、quantity、fee、trade id、时间。
- 最近错误显示错误类型、可读原因和发生时间。
- 报告入口能打开或读取 Markdown 报告。
- 长列表首版可截断，但必须说明还有更多记录。

### 需求 5：Web 不得泄漏凭证或变成实盘控制台

系统 SHALL 保持 Web 展示脱敏和只读优先。

#### 验收点

- Web API 不返回 API Key / Secret 原文。
- Web 不提供 mainnet / live 切换。
- Web 不提供绕过 preflight 的启动按钮。
- 任何“启动 testnet 下单”的 Web 能力必须另走后续需求和审批。

## 推荐模块边界

- `kronos/execution/paper.py`：继续作为 paper run 状态和 ledger 的事实源。
- `kronos/web/routes/paper.py`：新增 paper status/report API。
- `web/lib/api.ts`：新增 paper API client 类型。
- `web/components/`：新增测试网模拟盘状态、订单、成交、错误和报告入口组件。
- `tests/unit/execution/`：补充状态读取和报告索引测试。
- `tests/integration/web/`：补充 paper status API 测试。

## 数据与产物

读取已有产物：

- `reports/paper/current_status.json`
- `reports/paper/<run_id>/paper_run.json`
- `reports/paper/<run_id>/paper_orders.jsonl`
- `reports/paper/<run_id>/paper_fills.jsonl`
- `reports/paper/<run_id>/paper_errors.jsonl`
- `reports/paper/<run_id>/paper_report.md`

新增可选产物：

- `docs/TESTNET_E2E_ACCEPTANCE_<date>.md`：真实 testnet 验收成功后补充。

## 安全规则

- v0.4.9 仍只允许 Binance testnet。
- Web 只读展示，不写凭证。
- Web 不展示完整 secret-like 字符串。
- testnet 成交不能被描述成实盘收益。
- 未通过研究 / 观察 / preflight 闸门，不得为了演示强行下单。

## 测试与验证

至少需要覆盖：

- 单元测试：paper status 读取、缺文件、空 run、失败 run、停止 run、报告路径解析。
- 集成测试：Web paper status API。
- 前端验证：桌面和窄屏展示状态、订单、成交、错误和报告入口。
- 安全测试：Web API 不返回 API Key / Secret。
- E2E 手动验收：在用户提供 testnet 凭证且存在合格观察候选时，提交一笔最小 testnet 订单并保存证据。
- 文档验证：TODO、PROJECT_STATUS、ROADMAP、PRODUCT_CONTROL_PANEL 均索引 v0.4.9 文档和 OpenSpec。

## 完成标准

v0.4.9 完成时，必须满足：

1. 有完整版本需求文档和 OpenSpec 约束。
2. 真实 testnet E2E 阻塞条件被保留，不绕过凭证 / promoted 候选 / observation plan / preflight。
3. 有一次成功真实 testnet E2E 证据，或有明确阻塞报告说明为什么不能执行。
4. Web 工作台能展示 paper 状态、最近订单、最近成交 / 错误和报告入口。
5. Web 输出全程标记 testnet，不泄漏密钥，不暗示实盘收益。
6. 测试、类型检查、前端构建和文档索引验证通过。

## 关键风险

| 风险 | 根因 | 必须怎么控 |
|---|---|---|
| 为了完成 E2E 绕过闸门 | testnet 证据压力 | 保留 v0.4.8 preflight 和 observation plan 硬门槛 |
| Web 被误解成交易控制台 | 展示订单和成交后用户以为能实盘 | 明确 testnet，只读展示，不提供 live/mainnet 入口 |
| 密钥泄漏 | Web API 读取状态时带出 credential payload | API 只读 ledger/status，不读 raw SecretStore |
| 空状态体验差 | 无凭证或无 run 时只有技术错误 | 输出下一步：配置 testnet 凭证、产出 promoted 候选、运行 preflight |
| v0.4.10 抢跑 | 记忆控制台已规划 | v0.4.9 完成后再进入 v0.4.10 |

## OpenSpec 约束

实现前必须先满足 `openspec/changes/p4-testnet-web-status/`。在 OpenSpec 没有通过前，不进入代码实现。

## v0.4.9 实现结果

已完成：

- 新增 `kronos/web/routes/paper.py`，提供 `GET /api/paper/status` 和 `GET /api/paper/runs/{run_id}/report`。
- Web API 从 `reports/paper/current_status.json`、`paper_orders.jsonl`、`paper_fills.jsonl`、`paper_errors.jsonl` 和 `paper_report.md` 读取证据。
- 缺 run、失败 run、停止 run 都返回产品化状态和下一步，不返回工程空白。
- 新增 `web/components/paper-status-panel.tsx`，在 Web 工作台首页展示 testnet paper 状态、最近订单、成交、错误、报告入口和本地证据路径。
- 报告阅读器支持 paper run 报告；Dashboard 不再在无真实 run id 时请求 `latest` Agent 报告。
- Web API 不读取 raw SecretStore；错误原因和 paper 报告正文中的 `api_key`、`api_secret`、`signature`、`token` 和带 query 的 URL 会在返回前脱敏。

保留阻塞：

- 无。真实 Binance testnet E2E 已在 2026-05-09 完成。

真实 testnet 证据：

- 验收报告：`docs/TESTNET_E2E_ACCEPTANCE_20260509.md`
- 多画像模拟用户验收：`docs/KRONOS_V049_PERSONA_ACCEPTANCE_20260511.md`
- 研究候选：`20260509T-v049-signal-persistence-4h-cross-section`，`promoted=1`。
- 观察计划：`reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md`，状态为“只读观察候选”。
- Preflight：`reports/paper/20260509T134600Z-preflight/paper_preflight_report.md`，状态通过。
- 成功 run：`20260509T134805Z-paper`。
- 订单：ETHUSDT BUY 0.01 MARKET，Binance testnet order id `8693595272`，状态 `FILLED`。
- 成交：trade id `272130743`，成交价 `2312.9`，数量 `0.01`，手续费 `0.0092516 USDT`。
- 失败学习：首次 ETHUSDT 0.001 被 testnet `MIN_NOTIONAL=20` 阻止，v0.4.9 已补交易所最小名义金额前置检查和可读错误。
- 安全边界仍成立：不允许绕过凭证、promoted 候选、观察计划、preflight 或用户明确授权；testnet 成交不能被描述为实盘收益。
- 模拟用户验收：2026-05-11 按 L1 操作员、新环境用户、负责人 / 风控 reviewer、Web 验收者四个画像复核；成功路径、空状态、无凭证阻塞和 Web 桌面 / 窄屏均通过。

验证：

- `uv run pytest tests/integration/web/test_routes.py tests/unit/execution/test_paper.py tests/unit/factor/test_validation_metrics.py`
- `uv run ruff check kronos/web/app.py kronos/web/schemas.py kronos/web/routes/paper.py kronos/execution/paper.py kronos/factor/validation/metrics.py kronos/factor/validation/pipeline.py cli/main.py tests/integration/web/test_routes.py tests/unit/execution/test_paper.py tests/unit/factor/test_validation_metrics.py tests/integration/test_cli.py`
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run build`
- 浏览器验证：Web 展示真实 completed paper 状态、订单、成交和报告入口；点击“读取报告”可看到订单 ID、成交价、成交数量、手续费和成交时间；当前页面无新增错误。
