## Why

v0.4.7 已经把研究报告推进到只读观察计划，但用户真正想验证的是“这条策略能不能在不碰真实资金的环境里跑通下单链路”。

v0.4.8 要把观察计划推进到 Binance 模拟盘 / 测试网真实成交：允许使用测试网 API Key 提交测试网订单，读取测试网成交，并生成可复盘报告。它不是本地虚拟成交，也不是实盘。

## What Changes

- 新增 `paper` 命令组：credentials、preflight、start、status、stop。
- 新增 Binance 测试网执行边界：只允许 testnet，不允许 mainnet/live。
- 新增测试网订单和成交记录。
- 新增模拟盘运行报告。
- 新增凭证脱敏、preflight、停止开关和人工闸门约束。

## Capabilities

### New Capabilities

- `testnet-paper-credentials`: 本地保存和查看 Binance 测试网凭证状态。
- `testnet-paper-preflight`: 启动前确认测试网、凭证、观察计划和风控边界。
- `testnet-paper-run`: 在 Binance 测试网提交受限订单并记录测试网成交。
- `testnet-paper-report`: 生成模拟盘运行报告。

### Modified Capabilities

- `paper-observation-plan`: 从只读计划升级为测试网模拟盘的启动前置条件。
- `report-latest`: 后续可以提示用户进入测试网模拟盘，而不是只停留在观察计划。

## Impact

- **新增用户路径**：`report observation-plan -> paper preflight -> paper start -> paper status/stop -> paper report`。
- **新增产物**：测试网订单日志、成交日志、模拟盘报告。
- **安全边界**：测试网真实成交允许；主网实盘、真实资金、自动升级实盘禁止。
