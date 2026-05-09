## Context

Kronos 当前已经能生成研究报告和只读观察计划。下一步应该验证执行链路，而不是继续停留在纸面计划。

用户已经具备 Binance 模拟盘 API Key。产品上应允许在模拟盘 / 测试网里真实下单和成交，因为这不会影响真实资金。但这也引入了新的风险：只要环境边界写错，模拟盘功能就可能被误解为实盘能力。

## Goals / Non-Goals

### Goals

- 支持 Binance 模拟盘 / 测试网 API Key。
- 启动前强制 preflight。
- 在测试网提交真实测试订单并读取测试网成交。
- 记录订单、成交、错误、停止和报告。
- 保留人工闸门，禁止自动升级实盘。

### Non-Goals

- 不做 Binance 主网实盘。
- 不做多策略组合执行。
- 不做生产级长期 daemon。
- 不做高级订单类型。
- 不做 Web 完整交易控制台。

## Decisions

### D1: 测试网成交是真成交，但不是实盘

**决策**：v0.4.8 的 paper trading 使用 Binance 测试网真实订单和测试网成交，不再叫本地虚拟成交。

**理由**：

- 用户已经提供模拟盘 API Key，真实测试网撮合更接近交易体验。
- 测试网资金与真实资金隔离，适合作为实盘前的执行链路验证。

### D2: paper 命令永远拒绝 mainnet

**决策**：`kronos paper ...` 命令组只能连接 testnet endpoint。

**理由**：

- v0.4.8 不是实盘版本。
- mainnet/live 是另一个产品阶段，需要单独审批和更强风控。

### D3: preflight 是启动前硬门槛

**决策**：任何 `paper start` 都必须先通过 preflight。

**理由**：

- 执行层不能绕过研究报告和观察计划。
- 用户需要在下单前看到环境、凭证、策略、品种和限额。

### D4: 订单证据以交易所返回为准

**决策**：只有拿到 Binance 测试网订单 ID 的记录才能称为测试网订单；只有查询到测试网成交结果的记录才能称为成交。

**理由**：

- 这版要验证真实测试网链路，而不是本地假设。
- 报告必须可追溯。

### D5: 停止优先于继续观察

**决策**：`paper stop` 写入停止状态后，运行循环每轮都必须检查并停止提交新订单。

**理由**：

- 模拟盘虽然不影响真实资金，但仍然会产生测试网订单和用户心理负担。
- 停止动作必须简单可信。

## Proposed Architecture

```text
Observation Plan
      |
      v
paper preflight
      |
      v
Testnet Credentials + Risk Limits
      |
      v
paper start
      |
      v
Signal -> Testnet Order -> Testnet Fill Query
      |
      v
Local JSONL Ledger + Markdown Report
```

## Data Artifacts

- `reports/paper/<run_id>/paper_run.json`
- `reports/paper/<run_id>/paper_orders.jsonl`
- `reports/paper/<run_id>/paper_fills.jsonl`
- `reports/paper/<run_id>/paper_report.md`
- `reports/paper/current_status.json`

## Safety Rules

- Paper mode endpoint must be testnet.
- Credentials are local-only and redacted.
- Reports must never contain raw API Key or Secret.
- Start requires an observation plan and preflight result.
- Default order size and runtime are capped.
- Stop status is checked before every signal and before every order submission.

## Risks / Trade-offs

- **[测试网和主网混用]** -> Mitigation：environment enum + endpoint allowlist + tests.
- **[密钥泄漏]** -> Mitigation：reuse SecretStore, redact logs, add regression tests.
- **[测试网成交被误读为实盘收益]** -> Mitigation：report copy always states testnet funds are isolated.
- **[实现范围膨胀]** -> Mitigation：single strategy, single symbol, limited runtime, basic order type only.
