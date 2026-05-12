## Why

v0.4.8 已经完成测试网模拟盘最小闭环，但真实 testnet 验收在 2026-05-09 被正确阻止：没有测试网凭证，也没有真实 90 天数据下 promoted 的观察候选。

v0.4.9 要补齐两个产品验收缺口：

1. 当凭证和合格候选都具备时，跑一次真实 testnet E2E 并保存证据。
2. Web 工作台展示测试网模拟盘状态、最近订单、成交 / 错误和报告入口。

## What Changes

- 新增 v0.4.9 测试网证据与 Web 状态可见性约束。
- 新增 Web paper status/report API。
- 新增 Web 测试网模拟盘状态展示。
- 新增真实 testnet E2E 验收流程文档化要求。

## Capabilities

### New Capabilities

- `testnet-e2e-acceptance`: 在所有闸门通过后保留真实 testnet 订单和成交证据。
- `paper-web-status`: Web 展示当前 paper 状态和最近 run。
- `paper-web-evidence`: Web 展示最近订单、成交、错误和报告入口。

### Modified Capabilities

- `testnet-paper-run`: 继续沿用 v0.4.8 的 preflight / stop / report 边界。
- `web-workbench`: 增加测试网模拟盘可见性，但不变成实盘控制台。

## Impact

- **新增用户路径**：`Web 工作台 -> 测试网模拟盘状态 -> 最近订单 / 成交 / 报告`。
- **新增验收路径**：`credentials -> promoted candidate -> observation plan -> preflight -> testnet order -> Web status/report`。
- **不变安全边界**：testnet only、无凭证不启动、无合格观察候选不启动、Web 不泄漏 secrets、不升级实盘。
