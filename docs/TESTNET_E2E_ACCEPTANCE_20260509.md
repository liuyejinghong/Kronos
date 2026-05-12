# Kronos v0.4.9 真实 Testnet E2E 产品验收报告

> 日期：2026-05-09
> 结论：通过。Kronos 已在 Binance USD-M Futures testnet 上完成一笔人工授权、受限金额、非主网的真实测试网订单，并能在 Web 工作台只读展示订单、成交、手续费和报告。

## 第一屏结论

- 环境：Binance testnet，不是 mainnet，不影响真实资金。
- 观察候选：`signal_persistence_density` / ETHUSDT-BTCUSDT-SOLUSDT / 4h 横截面研究候选。
- 研究闸门：通过。真实 90.14 天 1m K 线重采样为 4h，`promoted=1`。
- 观察计划：通过。状态为“只读观察候选”。
- Preflight：通过。测试网凭证、计划 metadata、来源 hash 和 testnet 账户连通性均通过。
- 测试网订单：通过。ETHUSDT BUY 0.01 MARKET，Binance testnet 返回 `FILLED`。
- Web 验收：通过。工作台显示 completed、testnet、订单、成交、手续费、报告入口；报告页可读。

## 关键证据

### 1. promoted 候选自然生成

命令：

```bash
uv run kronos research auto-run \
  --symbols ETHUSDT,BTCUSDT,SOLUSDT \
  --candidates signal_persistence_density \
  --skip-watchlist-evidence \
  --timeframe 4h \
  --since 2026-01-27 \
  --periods 20 \
  --train-size 60 \
  --validation-size 30 \
  --test-size 30 \
  --step-size 60 \
  --run-id 20260509T-v049-signal-persistence-4h-cross-section \
  --output-path reports/research \
  --config configs/dev.toml
```

结果：

```text
readiness: ready_for_deeper_research
evaluated: 1
promoted: 1
not_promoted: 0
skipped: 0
```

关键指标：

- validation_outcome：`pass`
- mean_rank_ic：`0.32183091741659936`
- top_minus_bottom：`0.04330783442286999`
- walkforward_test_mean：`0.001116149258429149`
- walkforward_positive_test_window_ratio：`0.875`
- leak_audit_passed：`true`

产物：

- `reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/auto_run_report.md`
- `reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/auto_run_summary.json`

### 2. 观察计划和 preflight 通过

命令：

```bash
uv run kronos report observation-plan \
  reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/auto_run_report.md

uv run kronos paper preflight \
  --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md
```

结果：

```text
状态: 只读观察候选
状态: 通过
结论: 可以启动 Binance 测试网模拟盘。
```

产物：

- `reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md`
- `reports/paper/20260509T134600Z-preflight/paper_preflight_report.md`

### 3. 首次真实 testnet 下单被最小名义金额挡住

命令：

```bash
uv run kronos paper start \
  --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md \
  --symbol ETHUSDT \
  --quantity 0.001 \
  --max-notional-usdt 100 \
  --reset-stopped
```

结果：

- Binance testnet 返回 HTTP 400。
- 查询交易所规则后确认：ETHUSDT `MIN_NOTIONAL=20`，0.001 ETH 满足最小数量但名义金额不足。
- v0.4.9 已补本地交易规则检查：后续会在提交订单前提示 `below Binance testnet minimum`，避免用户只看到交易所 400。

失败产物：

- `reports/paper/20260509T134612Z-paper/paper_report.md`
- `reports/paper/20260509T134612Z-paper/paper_errors.jsonl`

### 4. 第二次真实 testnet 下单成功

命令：

```bash
uv run kronos paper start \
  --plan reports/research/experiments/20260509T-v049-signal-persistence-4h-cross-section/paper_observation_plan.md \
  --symbol ETHUSDT \
  --quantity 0.01 \
  --max-notional-usdt 100 \
  --reset-stopped
```

结果：

```text
run_id: 20260509T134805Z-paper
状态: completed
环境: testnet
testnet_order_id: 8693595272
order_status: FILLED
```

成交明细：

- symbol：ETHUSDT
- side：BUY
- quantity：0.01
- order_id：`8693595272`
- trade_id：`272130743`
- price：`2312.9`
- commission：`0.0092516 USDT`
- fill_time：`2026-05-09T13:48:06.730000+00:00`

产物：

- `reports/paper/current_status.json`
- `reports/paper/20260509T134805Z-paper/paper_run.json`
- `reports/paper/20260509T134805Z-paper/paper_orders.jsonl`
- `reports/paper/20260509T134805Z-paper/paper_fills.jsonl`
- `reports/paper/20260509T134805Z-paper/paper_report.md`

### 5. Web 工作台验收通过

Web API：

- `GET /api/paper/status` 返回 completed、testnet、run id、订单、成交、手续费和报告路径。
- `GET /api/paper/runs/20260509T134805Z-paper/report` 返回 Markdown 报告正文。

浏览器验收：

- 首页“测试网模拟盘”面板显示 `completed`、`testnet`、run id、ETHUSDT BUY / FILLED。
- 最近成交显示 ETHUSDT 和 trade id。
- 点击“读取报告”后，报告页显示订单 ID、成交价、成交数量、手续费和成交时间。
- 当前页面无新增 console error。

截图：

- `reports/paper/20260509T134805Z-paper/web-report-screenshot.png`

## 本轮产品发现

1. **单标的 validation 的 `rank_ic_positive_ratio` 不应被当成失败证据。** 该指标在单标的场景不可计算，v0.4.9 已改为“不可用则跳过该稳定性门槛”，但仍要求 IC、top-minus-bottom、turnover 过线。
2. **研究命令应该允许直接选择内置因子。** v0.4.9 已支持 `--candidates signal_persistence_density` 直接作为一次性研究候选，不要求用户先写入候选池。
3. **重采样周期的覆盖记录需要解释来源。** v0.4.9 已把 4h 报告中的数据覆盖写成“1m K线（重采样为 4h）”，避免误导用户以为缺少 4h 文件。
4. **测试网下单前应检查交易所最小名义金额。** v0.4.9 已补 `MIN_NOTIONAL` 检查，避免低于规则时只看到 Binance HTTP 400。

## 验收判断

v0.4.9 可以进入模拟用户产品验收结论：

- 真实 testnet E2E 已通过。
- Web 状态可见性已通过。
- 凭证未进入 Git，Web 不读 raw SecretStore。
- 失败路径被产品化记录，且已新增交易规则前置检查。
- 测试套件已隔离本机真实凭证：`KRONOS_SECRET_STORE_PATH` 指向临时测试目录。
- 仍然不能把 testnet 成交解释为实盘收益或实盘准入。

## 验证补充

- 2026-05-11 模拟用户复验：`kronos --version` 输出 `0.4.9`；`paper status` 可读 completed/testnet/order/FILLED；`paper preflight` 通过且 API Key 只显示掩码。
- 2026-05-11 Web 复验：首页“测试网模拟盘”卡片可读，只读展示和 testnet 边界明确；点击“读取报告”后，桌面和 390px 窄屏均能读到订单 ID、FILLED、成交价、数量、手续费和实盘边界；当前页面 console error/warning 为 0。
- `uv run pytest -m "not e2e"`：591 passed, 5 deselected。
- `uv run mypy kronos cli`：通过。
- `npm --prefix web run typecheck`：通过。
- `npm --prefix web run lint`：通过。
- `npm --prefix web run build`：通过。
- `python3 scripts/harness_memory_check.py`：通过。
- `git diff --check`：通过。
