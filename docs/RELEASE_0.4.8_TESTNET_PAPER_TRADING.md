# Kronos v0.4.8 版本需求：Binance 模拟盘真实成交

> 状态：首版已完成
> 版本目标：0.4.8
> 约束来源：用户明确边界、`docs/PROJECT_STATUS.md`、`docs/RELEASE_0.4.7_PAPER_OBSERVATION_PLAN.md`、`docs/USER_PERSONAS.md`

## 版本目标

v0.4.7 已经把研究报告转换成只读观察计划。v0.4.8 的目标是把这份计划推进到 **Binance 模拟盘 / 测试网真实成交**：Kronos 可以使用用户提供的 Binance 模拟盘 API Key，在测试网环境提交真实测试订单，并记录测试网成交结果。

这不是“本地虚拟成交”，也不是实盘交易。它的产品定义是：

1. 订单真的提交到 Binance 模拟盘 / 测试网。
2. 成交真的来自测试网撮合。
3. 资金是测试资金，不影响真实账户资金。
4. 所有入口都必须明确当前环境是 `testnet`。
5. 系统不得自动切换到主网或实盘。

## 为什么要做

交易用户读完研究报告后，下一步自然不是直接实盘，而是想看策略在一个真实撮合环境中能否按预期运行。只读观察计划解决了“能不能观察、按什么边界观察”，但没有解决“下单链路是否能跑通”。

v0.4.8 要补齐的是执行链路信任：

- API Key 能不能安全配置；
- 系统是否真的只连测试网；
- 策略信号能否转成受限测试订单；
- 订单和成交能否被记录、复盘、停止；
- 用户能否一眼确认没有碰真实资金。

## 产品承诺

1. 用户可以配置 Binance 模拟盘 / 测试网 API Key。
2. 用户可以从一个合格的只读观察计划启动测试网模拟盘。
3. 系统只允许连接 Binance 测试网，不允许连接 Binance 主网。
4. 系统可以在测试网提交真实测试订单，并读取测试网订单 / 成交状态。
5. 所有订单、成交、错误和停止动作必须落成本地日志和报告。
6. 默认只支持最小仓位、单策略、单品种、短时运行。
7. 用户必须手动启动，系统不能因为研究报告通过就自动开跑。
8. 用户必须能一键停止模拟盘运行。

## 产品边界

### In Scope

- `kronos paper credentials status/set/delete`：本地配置和查看 Binance 测试网凭证状态。
- `kronos paper preflight`：检查凭证、测试网连接、账户类型、观察计划、策略和风控限额。
- `kronos paper start`：启动一轮受限测试网模拟盘。
- `kronos paper status`：查看当前模拟盘运行状态、最近信号、订单和成交。
- `kronos paper stop`：停止本地模拟盘循环，不再提交新订单。
- 测试网订单记录：信号、下单请求、订单 ID、成交状态、成交价、手续费、错误原因。
- 模拟盘报告：每轮结束后生成用户可读 Markdown 和机器可读 JSON。
- Docker 路径：允许用户通过环境变量或本地密钥文件注入测试网 API Key，但不得写入镜像。

### Out of Scope

- Binance 主网实盘。
- 任意真实资金交易。
- 多策略组合执行。
- 自动加仓、自动调参、自动升级实盘。
- 高级订单类型和复杂仓位管理。
- Web 工作台完整交易控制台。
- 长时间守护进程和生产级容灾。

## 用户流程

### 首次配置

1. 用户在 Binance 模拟盘 / 测试网创建 API Key。
2. 用户运行 `kronos paper credentials set` 保存 API Key 和 Secret。
3. 系统只返回脱敏状态，不在控制台、报告、日志、Web API 中输出原始密钥。
4. 用户运行 `kronos paper preflight`。
5. 系统确认：
   - 当前环境是测试网；
   - 凭证可用；
   - 账户是测试网账户；
   - 观察计划存在；
   - 策略已通过准入；
   - 默认仓位和订单限额在安全范围内。

### 启动模拟盘

1. 用户运行 `kronos paper start --plan <paper_observation_plan.md>`。
2. 系统再次展示确认卡：
   - 环境：Binance 测试网；
   - 资金：测试资金；
   - 真实资金：不会触碰；
   - 策略：单策略；
   - 品种：单品种；
   - 最大订单金额；
   - 最长运行时间；
   - 停止命令。
3. 系统启动最小运行循环。
4. 如果产生信号，系统提交测试网订单。
5. 系统轮询订单状态并记录成交。
6. 用户可随时运行 `kronos paper stop`。

### 结束与复盘

1. 停止后系统生成模拟盘报告。
2. 报告必须展示：
   - 启动环境；
   - 凭证状态（脱敏）；
   - 运行时长；
   - 信号数量；
   - 测试网订单数量；
   - 成交数量；
   - 未成交 / 取消 / 失败原因；
   - 是否存在真实资金风险；
   - 下一步建议。

## 功能需求

### 需求 1：测试网环境必须不可绕过

系统 SHALL 只允许 v0.4.8 的 paper trading 连接 Binance 模拟盘 / 测试网。

#### 验收点

- 默认环境必须是 `testnet`。
- CLI、配置、日志和报告必须显示当前是测试网。
- 任何主网 URL、主网订单端点或 live mode 都必须被拒绝。
- 没有显式测试网配置时，系统不得启动。

### 需求 2：凭证必须本地保存、全程脱敏

系统 SHALL 使用本地 SecretStore 或等价本地密钥存储保存 Binance 测试网 API Key 和 Secret。

#### 验收点

- 原始密钥不得进入 git、报告、事件日志、控制台普通输出或 Web 响应。
- `credentials status` 只能显示 configured / masked suffix。
- 空密钥、缺 secret、疑似主网凭证或格式异常必须被拒绝。
- 删除凭证后，`preflight` 必须失败。

### 需求 3：启动前必须通过 preflight

系统 SHALL 在任何测试网下单前执行 preflight。

#### 验收点

- 无观察计划时失败。
- sample / 短样本 / 证据不足 / 未通过策略的观察计划不能启动。
- 无测试网凭证时失败。
- 测试网连接失败时失败。
- 风控限额缺失或超过默认上限时失败。
- preflight 结果必须落成本地报告。

### 需求 4：订单必须是真实测试网订单

系统 SHALL 在测试网模拟盘运行时提交 Binance 测试网订单，而不是本地虚拟成交。

#### 验收点

- 每个订单必须记录 Binance 测试网订单 ID。
- 成交状态必须来自测试网查询结果。
- 订单和成交必须标记为 `testnet`。
- 失败订单必须记录失败原因，不得静默吞掉。
- 没有测试网订单 ID 的记录不得被称为成交。

### 需求 5：运行必须受限、可停止、可复盘

系统 SHALL 限制 v0.4.8 模拟盘的运行范围，并提供停止和复盘能力。

#### 验收点

- 默认单策略、单品种、最长运行时间、最大订单金额。
- `paper stop` 后不得再提交新订单。
- 异常退出后再次 `status` 应能看到最后状态。
- 运行报告必须区分信号、下单、成交、失败和停止。

### 需求 6：不得自动升级实盘

系统 SHALL 保留人工闸门，不得把测试网表现自动转换为实盘动作。

#### 验收点

- 报告不得出现“已证明可实盘”。
- 即使测试网盈利，也只能建议继续观察或人工评审。
- 任何 live / mainnet 入口必须另走后续版本需求和审批。

## 开发边界

### 推荐模块边界

- `kronos/execution/`：测试网客户端、订单模型、运行状态和模拟盘循环。
- `kronos/agent/secrets.py`：复用或扩展本地 SecretStore，避免单独写密钥文件逻辑。
- `cli/main.py`：新增 `paper` 命令组，不把执行逻辑塞进 CLI。
- `reports/paper/`：模拟盘运行日志和报告目录。
- `tests/unit/execution/`：测试网客户端适配器、风控门禁、状态机和报告。
- `tests/integration/test_cli.py`：CLI 成功 / 失败路径。

### 不应做的事

- 不要把真实 API Key 写进配置样例。
- 不要在测试中真实调用 Binance 网络。
- 不要在默认 quickstart 中自动启动模拟盘。
- 不要把测试网成交包装成策略有效性证明。
- 不要新增和 v0.4.8 无关的策略生成能力。

## 测试与验证

至少需要覆盖：

- 单元测试：凭证脱敏、测试网 URL 门禁、preflight 失败原因、订单状态映射、停止状态。
- 集成测试：`paper credentials status/set/delete`、`paper preflight`、`paper start` dry-run 或 mocked testnet、`paper status`、`paper stop`。
- 安全测试：报告和事件日志不包含 API Key / Secret 原文。
- Docker 验证：fresh Docker 下未配置凭证时给出清晰下一步；配置测试凭证环境变量时能通过 mocked/safe preflight。
- 文档验证：README、TODO、PROJECT_STATUS、ROADMAP、CHANGELOG 与 v0.4.8 边界一致。

## 完成标准

v0.4.8 完成时，必须满足：

1. 有完整的产品需求文档和 OpenSpec 约束。
2. 用户能配置 Binance 测试网凭证并看到脱敏状态。
3. 用户能通过 preflight 确认当前只会连接测试网。
4. 系统能在测试网提交一笔受限订单并记录测试网订单 ID，或在无真实凭证环境下用 mock adapter 验证同等流程。
5. 用户能查看状态、停止运行、读取模拟盘报告。
6. 所有报告都明确测试网资金不等于真实资金，不能自动升级实盘。
7. 全量测试、类型、lint、前端构建和 Docker fresh 验证通过。

## v0.4.8 实现结果

首版实现已经把“只读观察计划之后的一步”推进到 Binance 测试网模拟盘入口：

- 新增 `kronos paper credentials status/set/delete`，测试网 API Key / Secret 保存在本地 SecretStore，移除 argv secret，支持环境变量和隐藏输入，控制台和报告只显示脱敏状态。
- 新增 `kronos paper preflight`，检查只读观察计划 metadata、来源报告 / summary hash、凭证和 Binance testnet 账户连通性；`--mock-testnet` 只用于本地 / CI / Docker 安全验证。
- 新增 `kronos paper start/status/stop`，默认单品种、最小数量、订单金额上限；停止后再次启动必须显式 `--reset-stopped`；生成订单账本、成交账本、错误账本、状态 JSON 和 Markdown 报告。
- 真实 testnet 成交证据来自 Binance testnet trade 明细，而不是订单摘要推导；成交账本记录 trade id、成交价、数量、手续费、手续费资产和成交时间。
- 所有 `paper start` 失败都会落账：参数非法、停止后未显式 reset、preflight 未通过、行情读取失败、金额超过上限、下单失败和成交查询失败都会写入 failed 状态、错误账本和用户可读报告。
- 执行客户端只允许 `https://testnet.binancefuture.com`，拒绝 Binance mainnet endpoint。
- 报告固定提示：测试网资金不影响真实账户，测试网成交不能自动升级实盘。

## v0.4.8 仍保留的边界

- 默认 quickstart 不会启动模拟盘，也不会自动下单。
- 没有测试网凭证时，preflight 和 start 必须失败并给出下一步。
- Web 工作台暂不提供交易控制台，只能通过 CLI 使用模拟盘入口。
- 真实 Binance testnet 端到端需要用户显式提供测试网 API Key 后手动执行；自动化测试使用 mock testnet，不真实调用 Binance 网络。

## v0.4.9 建议

- 用用户测试网凭证跑一次真实 Binance testnet 手动验收，保留订单 ID、成交状态和报告截图 / 文本证据。
- 在 Web 工作台增加模拟盘状态、最近订单和报告入口。

## 关键风险

| 风险 | 根因 | 必须怎么控 |
|---|---|---|
| 误连主网 | 测试网 / 主网配置混用 | 客户端层硬编码环境枚举，paper 命令拒绝 mainnet |
| 密钥泄漏 | 控制台、日志、报告直接打印 payload | SecretStore + redact + 测试覆盖 |
| 用户误以为模拟盘盈利等于实盘可用 | 测试网成交看起来太像真实成交 | 报告固定提示测试网资金和真实资金隔离 |
| 策略未通过也被启动 | 执行层绕过研究闸门 | start 必须读取观察计划状态和 preflight 结果 |
| 停止后继续下单 | 本地状态和循环控制不一致 | stop 写状态，循环每轮检查停止标记 |

## OpenSpec 约束

v0.4.8 的实现必须先满足 `openspec/changes/p4-testnet-paper-trading/`。在 OpenSpec 没有通过前，不进入代码实现。
