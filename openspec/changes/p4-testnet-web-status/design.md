## Context

v0.4.8 已有 paper CLI 和本地报告产物：

- `reports/paper/current_status.json`
- `reports/paper/<run_id>/paper_run.json`
- `reports/paper/<run_id>/paper_orders.jsonl`
- `reports/paper/<run_id>/paper_fills.jsonl`
- `reports/paper/<run_id>/paper_errors.jsonl`
- `reports/paper/<run_id>/paper_report.md`

这些产物已经能证明 CLI 链路，但 Web 工作台暂时不可见。v0.4.9 需要让用户通过 Web 看懂测试网模拟盘状态，同时保留 v0.4.8 的安全门禁。

## Goals / Non-Goals

### Goals

- Web 显示测试网模拟盘当前状态。
- Web 显示最近订单、成交、错误和报告入口。
- 无 run / 无凭证 / 无合格候选时给出下一步。
- 真实 testnet E2E 验收保留订单和成交证据。
- 全程标记 testnet，输出脱敏。

### Non-Goals

- 不做 Web 凭证录入。
- 不做 Web 一键下单。
- 不做 mainnet / live。
- 不做多策略组合执行。
- 不做长期 daemon 或生产级监控。

## Decisions

### D1: Web 读取 ledger，不读取密钥源

**决策**：Web status API 读取 paper run 产物和 current status，不读取 SecretStore 原始凭证。

**理由**：

- Web 只需要展示状态，不需要知道 API Key / Secret。
- 凭证状态可沿用已有脱敏 status 入口或只展示“未配置 / 已配置”。

### D2: v0.4.9 Web 只读优先

**决策**：v0.4.9 Web 只展示状态和报告，不提供启动真实 testnet 下单按钮。

**理由**：

- 当前最重要的是可见性和验收证据。
- 下单操作仍应走 CLI + 明确人工授权，避免把 Web 误解成交易控制台。

### D3: 空状态是产品状态，不是错误

**决策**：没有 paper run、没有凭证、没有合格观察候选时，Web 必须展示下一步，而不是技术错误。

**理由**：

- v0.4.9 的主要用户价值是让用户知道为什么还不能进入 testnet。
- 2026-05-09 的 E2E 尝试就是一个正确阻塞案例。

## Proposed Architecture

```text
reports/paper/current_status.json
reports/paper/<run_id>/*.json(l), *.md
        |
        v
paper status reader
        |
        v
GET /api/paper/status
GET /api/paper/runs/{run_id}/report
        |
        v
Web Workbench paper status panel
```

## Recommended Modules

- `kronos/execution/paper.py`
  - 如已有 reader 足够，复用；不足时补只读 status/report reader。
- `kronos/web/routes/paper.py`
  - 提供 paper status 和 report API。
- `web/lib/api.ts`
  - 增加 paper API 类型。
- `web/components/paper-status-panel.tsx`
  - 展示状态、最近订单、成交、错误和报告入口。

## API Shape

Recommended endpoints:

- `GET /api/paper/status`
- `GET /api/paper/runs/{run_id}/report`

Response must include:

- environment (`testnet`)
- status
- run id
- updated time
- latest orders
- latest fills
- latest errors
- report path / report body
- next action

## UI Shape

The UI should answer:

1. 现在有没有测试网模拟盘 run？
2. 当前状态是什么？
3. 最近有没有订单 / 成交 / 错误？
4. 报告在哪里？
5. 下一步该做什么？

It should not look like a trading terminal. It is a research validation status panel.

## Safety Rules

- Always label testnet.
- Never expose API Key / Secret.
- Never show a mainnet/live mode switch.
- Never claim testnet profit proves live viability.
- Never offer to bypass preflight.

## Risks / Trade-offs

- **[Web 空状态被误解为坏了]** -> Mitigation：明确展示缺凭证、缺候选、未运行或已停止。
- **[Web 状态滞后]** -> Mitigation：读取 current_status 和 run artifacts，显示更新时间。
- **[报告路径泄漏本地细节]** -> Mitigation：UI 展示报告标题 / run id，技术路径折叠。
- **[范围膨胀成控制台]** -> Mitigation：v0.4.9 只读展示，操作仍走 CLI。
