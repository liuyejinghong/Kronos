# Kronos v0.4.8 Testnet E2E Attempt：授权后真实验收记录

> 日期：2026-05-09
> 结论：未提交 Binance testnet 订单。原因不是执行失败，而是 v0.4.8 的产品闸门正确阻止了不合格下单。

## 背景

用户已授权进行 Binance testnet 真实成交验收。验收目标是：在不触碰主网、不触碰真实资金的前提下，用测试网 API Key 跑通 `paper preflight -> paper start -> status/report`，并保留订单 ID、trade 明细和报告证据。

## 实际检查结果

### 1. 测试网凭证状态

命令：

```bash
uv run kronos paper credentials status
```

首次验收时的结果：

```text
configured: no
api_key: -
api_secret: -
storage: .kronos-secrets/agent_secrets.json
```

后续用户已重新提供 Binance testnet 凭证，并已通过隐藏输入写入本机
`.kronos-secrets/agent_secrets.json`。该路径被 `.gitignore` 忽略，不应进入
Git 或打包产物。当前凭证状态为：

```text
configured: yes
api_key: ************************************************************SXb7
api_secret: ************************************************************daSD
storage: .kronos-secrets/agent_secrets.json
```

无下单连通性校验也已通过：

```text
account_ping: ok
can_trade: True
BTCUSDT ticker: ok
```

### 2. 本地真实数据存在，但没有通过验证的候选

本地数据覆盖：

- BTCUSDT / 1m K线：2026-01-27 00:00 -> 2026-04-27 03:23，约 90.14 天
- ETHUSDT / 1m K线：2026-01-27 00:00 -> 2026-04-27 03:25，约 90.14 天
- SOLUSDT / 1m K线：2026-01-27 00:00 -> 2026-04-27 03:27，约 90.14 天

真实数据研究验收命令：

```bash
uv run kronos research auto-run \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --timeframe 1m \
  --since 2026-01-27 \
  --run-id 20260509T0415Z-v048-real-data-gate-check \
  --skip-sync-data \
  --skip-watchlist-evidence
```

结果：

```text
readiness: no_candidate_ready
evaluated: 4
promoted: 0
not_promoted: 4
skipped: 0
```

研究报告：

```text
reports/research/experiments/20260509T0415Z-v048-real-data-gate-check/auto_run_report.md
```

### 3. 观察计划正确判定为“暂不观察”

命令：

```bash
uv run kronos report observation-plan \
  reports/research/experiments/20260509T0415Z-v048-real-data-gate-check/auto_run_report.md
```

结果：

```text
状态: 暂不观察
判断: 当前没有策略通过验证，不建议进入模拟盘或只读观察。
```

观察计划：

```text
reports/research/experiments/20260509T0415Z-v048-real-data-gate-check/paper_observation_plan.md
```

### 4. Preflight 正确阻止下单

命令：

```bash
uv run kronos paper preflight \
  --plan reports/research/experiments/20260509T0415Z-v048-real-data-gate-check/paper_observation_plan.md \
  --mock-testnet
```

结果：

```text
状态: 未通过
环境: testnet
结论: 启动前还有阻塞项。
阻塞项:
- 观察计划还不是只读观察候选，不能启动测试网模拟盘。
- Binance 测试网 API Key / Secret 尚未配置。
```

preflight 报告：

```text
reports/paper/20260509T041553Z-preflight/paper_preflight_report.md
```

## 产品结论

本次没有提交 Binance testnet 订单，这是正确结果。v0.4.8 的设计目标不是“用户一授权就下单”，而是“只有测试网凭证 + 合格观察候选同时存在时，才允许 testnet 下单”。

当前阻塞项属于真实产品闸门：

1. 真实 90 天数据研究没有产生 promoted 候选，因此观察计划不是“只读观察候选”。
2. preflight 正确拒绝使用“暂不观察”计划启动测试网模拟盘。

如果为了完成演示而绕过候选、观察计划或 preflight，就会破坏 v0.4.8 刚建立的研究证据链。

## 下一步

v0.4.9 的真实 testnet E2E 应按以下顺序推进：

1. 先产出一个真实数据、非 sample、promoted > 0 的观察候选。
2. 用该观察候选运行 `paper preflight`。
3. preflight 通过后再运行一笔最小数量、受限金额的 Binance testnet 订单。
4. 保留订单 ID、trade 明细、成交时间、手续费、状态 JSON 和 Markdown 报告。

## 后续结果

v0.4.9 已完成上述后续步骤，详见
`docs/TESTNET_E2E_ACCEPTANCE_20260509.md`。

关键变化：

- `signal_persistence_density` 在 ETHUSDT / BTCUSDT / SOLUSDT 横截面、
  4h 重采样、真实 90.14 天数据上自然产生 `promoted=1`。
- 观察计划变为“只读观察候选”，`paper preflight` 通过。
- 首次 ETHUSDT 0.001 testnet 下单因 Binance `MIN_NOTIONAL=20` 被拒绝；
  v0.4.9 已补本地下单前最小名义金额检查。
- 第二次 ETHUSDT 0.01 testnet 下单成功，run id
  `20260509T134805Z-paper`，订单 `8693595272`，状态 `FILLED`，
  trade id `272130743`。
- Web 工作台已能展示真实 testnet paper 状态、订单、成交、手续费和报告。
