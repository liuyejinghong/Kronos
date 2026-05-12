# Kronos v0.4.9 多画像模拟用户验收报告

> 日期：2026-05-11
> 验收对象：Kronos v0.4.9 测试网证据与 Web 状态可见性
> 结论：通过。v0.4.9 的测试网模拟盘链路已经能被不同用户角色理解、复核和安全拦截；本结论不代表主网实盘准入或策略盈利能力。

## 验收方法

本轮按“模拟真实用户操作，遇到错误就停，不跳过、不假设”的方式执行。验收不只看一笔 testnet 成交，而是从多个角色检查：

- L1 交易者 / 操作员：能否确认当前版本、看到测试网订单是否真的完成、知道下一步。
- 新环境用户：无历史状态或无凭证时，会不会被清楚拦住。
- 负责人 / 风控 reviewer：证据是否可追溯、是否明确 testnet 边界、是否不泄露密钥。
- Web 验收者：不用读文件时，能否在工作台读到状态和报告。

## 第一屏结论

| 维度 | 结论 |
|---|---|
| 当前版本可自证 | 通过。`kronos --version` 输出 `0.4.9`。 |
| 成功路径可读 | 通过。`paper status` 显示 completed、testnet、order id 和 `FILLED`。 |
| 空状态路径可读 | 通过。隔离空目录下的 `paper status` 明确提示先运行 preflight 或 start。 |
| 无凭证路径安全 | 通过。隔离 SecretStore 下的 `paper preflight` 阻塞在“Binance 测试网 API Key / Secret 尚未配置”。 |
| Web 验收 | 通过。Web 看板首屏优先露出测试网模拟盘状态，报告页可读订单、成交、手续费和实盘边界。 |
| 密钥边界 | 通过。Web API 不读取 raw SecretStore；preflight 只显示掩码；报告不写 raw API Key / Secret。 |
| 实盘边界 | 通过。报告明确 testnet 不等于实盘收益，不自动升级主网。 |

## 画像 1：L1 交易者 / 操作员

用户问题：

- 我现在跑的是不是 v0.4.9？
- 这笔测试网订单到底有没有成交？
- 我下一步应该看哪里？

真实操作：

```bash
uv run kronos --version
uv run kronos paper status --output-path reports/paper
```

观察结果：

- 版本输出：`0.4.9`。
- 状态输出显示：
  - run_id：`20260509T134805Z-paper`
  - status：`completed`
  - environment：`testnet`
  - testnet_order_id：`8693595272`
  - order_status：`FILLED`
  - report：`reports/paper/20260509T134805Z-paper/paper_report.md`

验收判断：通过。用户可以先确认版本，再直接确认 testnet run 已完成，不需要从内部日志里猜。

## 画像 2：新环境用户 / 无凭证用户

用户问题：

- 如果我是新机器或没有配置 API Key，会不会误下单？
- 系统会不会给我一个看得懂的下一步？

真实操作：

```bash
KRONOS_SECRET_STORE_PATH=<isolated-temp-secret-store> \
  uv run kronos paper status \
  --output-path <isolated-empty-paper-output>

KRONOS_SECRET_STORE_PATH=<isolated-temp-secret-store> \
  uv run kronos paper preflight \
  --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md \
  --output-path <isolated-empty-paper-output>
```

观察结果：

- 空状态提示：`No paper trading status found.`，并提示先运行 `kronos paper preflight` 或 `kronos paper start`。
- 无凭证 preflight：状态为“未通过”，环境为 testnet，阻塞项为“Binance 测试网 API Key / Secret 尚未配置”。
- 该分支使用隔离 SecretStore 和隔离输出目录，没有读取本机已配置的测试网凭证。

验收判断：通过。无凭证不会误下单，也不会假装通过；提示能把用户带回正确配置步骤。

## 画像 3：负责人 / 风控 Reviewer

用户问题：

- 这是不是主网或真实资金？
- 证据能不能追溯到研究候选、观察计划、preflight、订单和成交？
- 有没有泄漏密钥？

真实操作：

```bash
uv run kronos paper preflight \
  --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md \
  --output-path reports/paper
```

观察结果：

- preflight 通过，环境为 testnet。
- 成功 run 为 `20260509T134805Z-paper`。
- 订单证据：
  - ETHUSDT BUY 0.01 MARKET
  - Binance testnet order id：`8693595272`
  - trade id：`272130743`
  - price：`2312.9`
  - commission：`0.0092516 USDT`
- 报告明确写明：这是 Binance testnet，不是实盘收益证明，不能自动升级实盘。
- raw SecretStore 不进入 Web API；密钥不进入 Markdown 记忆和项目控制文档。

验收判断：通过。负责人可以复核完整证据链，同时不会把 testnet fill 误判为主网准入。

## 画像 4：Web 验收者

用户问题：

- 不打开本地文件，只看 Web 工作台能不能理解状态？
- 移动窄屏下报告能不能读？

真实操作：

- 启动本地后端和 Web 前端。
- 打开工作台首页，查看“测试网模拟盘”卡片。
- 点击“读取报告”。
- 用桌面和 390px 宽度检查报告页。

观察结果：

- 初始问题：测试网模拟盘面板在通用 Agent 卡片和操作区之后，模拟用户第一眼更容易先看到旧批次语义，而不是 v0.4.9 testnet 验收对象。
- 已修复：将测试网模拟盘面板提升到今日看板内容区最前面，并把状态标签从 `completed` 改成“已完成”。
- 桌面首屏显示只读测试网模拟盘状态、已完成、testnet、run id、下一步和报告入口。
- 390px 移动视口首屏已能看到“测试网模拟盘”和 testnet 边界文案；报告按钮在首屏底部附近，轻微滚动即可点击。
- 报告页显示 environment、run id、order id、`FILLED`、成交价、数量、手续费、成交时间和实盘边界。
- 当前页面 console error / warning 为 0。

验收判断：通过。Web 已能作为 v0.4.9 的只读验收面板。

## 暴露问题与处理

| 优先级 | 问题 | 处理结果 |
|---|---|---|
| P1 | 用户第一步无法从 CLI 确认当前安装版本 | 已修复：新增 `kronos --version` / `kronos -V`，并补回归测试。 |
| P1 | Web 看板第一屏先出现旧 Agent 批次和通用操作卡，测试网模拟盘位置偏下 | 已修复：测试网模拟盘面板提升到今日看板内容区最前面；桌面首屏可见，390px 移动首屏露出核心模块和边界文案。 |
| P2 | Web 全局 header 仍显示旧 Agent 批次语义，而不是 v0.4.9 testnet 验收对象 | 不阻塞 v0.4.9。建议放入 v0.4.10 记忆与交接控制台：顶部展示当前版本、验收对象和来源文档。 |
| P2 | 本轮不是 fresh clone Docker 全流程验收 | 不阻塞 v0.4.9。v0.4.9 目标是测试网证据和 Web 状态可见性；fresh clone Docker 已有独立画像验收记录，后续发外部包时再做完整新装验收。 |

## 产品结论

v0.4.9 可以按“测试网证据与 Web 状态可见性”验收通过：

- 它证明 Kronos 能从真实研究候选走到观察计划、preflight、testnet 订单、成交记录和 Web 只读展示。
- 它证明无凭证 / 空状态会安全阻塞，而不是绕过闸门。
- 它证明 Web 能给非工程用户看到“发生了什么、是不是测试网、证据在哪、下一步是什么”。

但 v0.4.9 仍不应该被包装为：

- 主网实盘能力。
- 策略盈利证明。
- 自动交易控制台。
- 对外分发安装包的最终 fresh install 验收。

## 建议进入后续版本的事项

1. v0.4.10 顶部状态区应该显示当前版本、当前验收对象、最近成功 run、下一步和来源文档，避免用户被旧批次号干扰。
2. v0.4.10 Agent 记忆与交接控制台应复用本报告的多画像验收口径，把“当前事实源”和“不能误解的边界”做成第一屏。
3. 后续准备外部分发前，需要单独跑 fresh clone / Docker / 无历史数据 / 无凭证 / mock testnet / 有凭证 testnet 的完整新装验收。

## 验证记录

- `uv run kronos --version`
- `uv run kronos paper status --output-path reports/paper`
- `uv run kronos paper preflight --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md --output-path reports/paper`
- `KRONOS_SECRET_STORE_PATH=<isolated-temp-secret-store> uv run kronos paper status --output-path <isolated-empty-paper-output>`
- `KRONOS_SECRET_STORE_PATH=<isolated-temp-secret-store> uv run kronos paper preflight --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md --output-path <isolated-empty-paper-output>`
- Web 工作台桌面与 390px 窄屏浏览器验收。
- 2026-05-11 Web 看板专项验收：桌面首屏可见测试网模拟盘；390px 移动首屏露出测试网模块和边界文案；点击“读取报告”可打开 Binance 测试网模拟盘报告；console error / warning 为 0。
