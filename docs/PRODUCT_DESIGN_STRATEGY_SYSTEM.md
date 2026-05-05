# Kronos 策略系统产品设计

> 版本：0.3.0-draft
> 日期：2026-05-05

## 核心原则

**Kronos 是一个策略研究助手，不是一个策略代码框架。** 用户不应该被要求"先写代码才能用"。

策略的完整生命周期：**体验 → 理解 → 定制 → 创建**。

---

## 1. 用户路径

### 首次使用

```
$ kronos agent start

Kronos Agent

你好！我是 Kronos，一个加密货币策略研究助手。

我可以帮你分析策略的历史表现，或者根据你的想法创建新策略。

你想从哪里开始？

  [1] 先用 R-breaker 策略体验一下 — 这是一个经典的日内突破策略，
      我会在 BTC 上跑一遍，让你看看 Kronos 怎么分析策略
  [2] 我有一个策略想法，帮我实现 — 用自然语言描述你的交易逻辑，
      我会转成可运行的代码
  [3] 先看看有什么功能
```

### 路径 A：体验 R-breaker

```
> 1

好的。R-breaker 是一个经典的日内突破策略，基于前一天的
最高价、最低价和收盘价计算当天的入场和止盈止损位。

📊 当前配置:
  交易品种: BTCUSDT
  时间周期: 15 分钟
  波动率倍数: 1.5x
  止损比例: 2%

——要直接用默认配置跑一次吗？
  [1] 用默认配置，开始分析
  [2] 先调整参数
  [3] 换个策略

> 1

⏳ 加载数据…
⏳ 计算 R-breaker 信号…
⏳ 跑回测验证…

✅ 完成！

📊 R-breaker 在 BTCUSDT 上的表现 (30 天回测):
  · 总收益率: +3.2%
  · 胜率: 52%
  · 最大回撤: -4.1%
  · 夏普比率: 0.68

💡 建议: 当前参数下策略在趋势行情中表现较好，震荡市会频繁止损。
   要不要试试调整波动率倍数？

  [1] 调整参数再跑一次
  [2] 换个品种
  [3] 看看我的其他策略
  [4] 这就够了
```

### 路径 B：AI 创建策略

```
> 2

好的！描述一下你的策略逻辑，越具体越好。

比如："当 5 日均线上穿 20 日均线时做多，下穿时平仓，
      只在 BTC 上交易，每笔仓位不超过 20%"

> 我想做一个简单的动量策略：当最近 10 根 K 线的涨幅超过 2%，
  就做多，持有 5 根 K 线后平仓。只在 BTC 和 ETH 上跑。

好的，让我理解一下你的策略：

📝 策略概要:
  名称: 动量突破策略
  类型: 趋势跟踪
  品种: BTCUSDT, ETHUSDT
  入场条件: 最近 10 根 K 线累计涨幅 > 2% → 做多
  出场条件: 持仓 5 根 K 线后平仓
  仓位: 每笔 20%

——这是不是你想要的？
  [1] 对，就按这个来
  [2] 调整一下参数
  [3] 重新描述

> 1

好的。我已经为你创建了这个策略并注册到系统中。

📋 策略 "动量突破策略" (momentum_breakout_001) 已就绪。

——要现在跑一次验证吗？
  [1] 跑，用最近 30 天 BTC 数据
  [2] 先存着，等会儿再跑
  [3] 再创建一个策略
```

---

## 2. 策略模型

### 策略定义（用户可见）

```toml
# strategies/my_strategy.toml

[strategy]
name = "我的动量策略"
id = "my_momentum_001"           # 唯一标识
description = "基于短期动量的趋势跟踪策略"

[universe]
symbols = ["BTCUSDT", "ETHUSDT"]
timeframe = "1h"

[entry]
condition = "close_pct_change(10) > 0.02"   # 最近 10 根 K 线涨幅 > 2%
direction = "long"                            # long | short | both

[exit]
condition = "bars_held >= 5"                 # 持有 5 根 K 线
stop_loss_pct = 5.0                          # 硬止损 5%

[position]
size_pct = 20.0                              # 每笔仓位 20%
max_positions = 3                            # 最多同时持有 3 笔
```

### 策略存储

```
~/.kronos/
  strategies/
    r_breaker.toml           # 内置 R-breaker（首次自动生成）
    my_strategy.toml          # 用户创建
    momentum_breakout.toml    # 用户创建
  config.toml
```

### 策略注册流程

```
用户描述 → LLM 生成 TOML → 用户确认 → 写入 ~/.kronos/strategies/
→ Agent 启动时自动加载 → 出现在策略池中
```

---

## 3. R-breaker — 内置参考策略

### 为什么是 R-breaker

- 经典策略，交易者普遍知道
- 逻辑清晰（3 个价格位 + 突破信号），适合作为示例
- 参数少（4 个），易于理解和调整
- 有实际交易价值

### 默认配置

```toml
[strategy]
name = "R-breaker 日内突破"
id = "r_breaker"
description = "经典日内突破策略，基于前一日高低点和收盘价计算今日入场位"
builtin = true

[universe]
symbols = ["BTCUSDT", "ETHUSDT"]
timeframe = "15m"

[params]
volatility_multiplier = 1.5
stop_loss_pct = 2.0

[r_breaker]
# 前一日 OHLC 作为基准
lookback_days = 1
# 波动率用 ATR(14) 计算
atr_period = 14
```

### 用户可调参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `symbols` | BTCUSDT, ETHUSDT | 交易品种 |
| `timeframe` | 15m | K 线周期 |
| `volatility_multiplier` | 1.5x | 突破阈值乘数 |
| `stop_loss_pct` | 2.0% | 止损比例 |
| `position_size_pct` | 20% | 每笔仓位 |

---

## 4. AI 策略创建器

### LLM Prompt 设计

```
你是一个加密货币量化策略专家。用户会用自然语言描述交易想法，
你需要将其转化为结构化的策略定义。

策略定义格式（TOML）：
[strategy] name / id / description
[universe] symbols / timeframe
[entry] condition / direction
[exit] condition / stop_loss_pct
[position] size_pct / max_positions

规则：
- condition 使用类自然语言的表达式，比如 "close_pct_change(10) > 0.02"
  或 "ma_cross(5, 20, 'up')"
- 如果用户没有明确指定品种，默认用 ["BTCUSDT"]
- 如果用户没有指定时间周期，根据策略类型推荐（日内→15m，趋势→1h）
- 检查逻辑一致性：做多策略不应该在下跌时入场

输出：先输出策略概要让用户确认，确认后再输出完整 TOML。
```

### 策略模板库

LLM 可以从以下模板中选择最接近的作为基础，然后根据用户描述调整：

| 模板 | 类型 | 适用场景 |
|------|------|----------|
| 趋势跟踪 | `ma_cross` | 用户提到"均线""金叉""趋势" |
| 动量突破 | `pct_change` | 用户提到"涨幅""动量""突破" |
| 均值回归 | `rsi` / `bollinger` | 用户提到"超买""回归""震荡" |
| 波动率过滤 | `atr` / `volatility` | 用户提到"波动率""缩量" |
| R-breaker | `r_breaker` | 用户提到"日内""突破""开盘" |

---

## 5. 交易执行链路

策略回测通过只是第一步。用户真正关心的是：**这个策略能不能帮我赚钱？** 这需要完整的执行链路。

### 完整生命周期

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  定义    │ →  │  验证    │ →  │  模拟    │ →  │  执行    │ →  │  迭代    │
│ 策略     │    │ 回测     │    │ 纸交易   │    │ 实盘     │    │ 优化     │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
  R-breaker      30天历史       实时行情        交易所 API      根据实盘结果
  AI 创建        信号质量       延迟模拟        仓位管理        调整参数
  手动编写       收益/风险      不涉及真钱      风控执行        或淘汰策略
```

### 各阶段 Agent 对话

#### 阶段 1: 验证（已实现）

```
Agent: R-breaker 在 BTCUSDT 上 30 天回测:
       收益 +3.2%, 夏普 0.68, 最大回撤 -4.1%
       
       ——想进一步验证吗？
         [1] 换个品种跑跑
         [2] 上模拟盘，用实时数据观察
         [3] 调整参数
```

#### 阶段 2: 模拟盘

```
> 2

Agent: 好的，启动模拟盘。

       模拟盘用实时行情生成虚拟订单，不涉及真实资金。
       你需要配置一个交易所连接来获取实时数据。

       当前可用:
         [1] Binance（需要 API Key，只读权限即可）
         [2] 用本地已有数据模拟（离线模式，非实时）

> 1

Agent: 请在 Web 设置页配置 Binance API Key（只需读取权限）。
       然后我会:
       · 每分钟拉取最新行情
       · R-breaker 生成信号时记录虚拟订单
       · 按当前市价模拟成交
       · 每日生成模拟盘报告

       配置好后回复"开始"。
```

#### 阶段 3: 实盘执行

```
（模拟盘跑了 2 周，收益 +2.1%，信号稳定）

Agent: R-breaker 模拟盘表现良好。要上实盘吗？

       ⚠️ 实盘涉及真实资金。在此之前需要配置:
       · 交易所 API Key（需交易权限）
       · 单笔最大仓位（当前建议: 账户的 5%）
       · 每日最大亏损限额
       · 人工确认每笔交易，还是自动执行？

       ——你想怎么配置？
         [1] 帮我设置安全参数（推荐首次使用）
         [2] 我先看看需要什么
         [3] 暂时不上实盘
```

### 执行配置模型

```toml
# ~/.kronos/execution.toml

[exchange]
provider = "binance"              # 交易所
api_key = "ENV:BINANCE_API_KEY"   # 从环境变量读取
testnet = true                    # 先用测试网

[risk]
max_position_pct = 5.0            # 单笔最大仓位
max_daily_loss_pct = 2.0          # 每日最大亏损
max_concurrent = 3                # 最多同时持有
require_approval = true           # 每笔需要人工确认

[execution]
mode = "paper"                    # paper | live
order_type = "limit"              # market | limit
slippage_pct = 0.1               # 预估滑点
```

### Agent 执行时的安全检查

```
每次生成交易信号时:
  1. ✅ 仓位 < max_position_pct?
  2. ✅ 今日亏损 < max_daily_loss_pct?
  3. ✅ 并发持仓 < max_concurrent?
  4. ✅ 用户已确认（如果 require_approval = true）?

全部通过 → 发送订单 → 记录 → 监控
任一失败 → 跳过 → 通知用户原因
```

### 执行后监控

```
Agent 每日摘要（终端或 Web）:
  
  📊 今日摘要
  R-breaker (BTCUSDT)
    · 今日信号: 做多 @ 67,200
    · 当前持仓: 1 笔
    · 未实现盈亏: +$340 (1.2%)
    · 已实现盈亏: +$120
    · 风险使用: 15% (安全线内)
```

---

## 6. 实现计划

### Phase 1: 策略存储和加载（v0.3.0）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| `kronos/strategy/spec.py` | `StrategySpec` 数据模型 | P0 |
| `kronos/strategy/store.py` | 加载 `~/.kronos/strategies/*.toml` | P0 |
| `kronos/strategy/r_breaker.py` | R-breaker 因子实现 | P0 |
| 内置 `r_breaker.toml` | 首次启动自动写入 | P0 |

### Phase 2: Agent 对话流重写（v0.3.0）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 重写欢迎流 | 三入口: R-breaker / AI 创建 / 浏览 | P0 |
| `_r_breaker_flow()` | 参数展示 → 确认 → 回测 → 结果 | P0 |
| `_ai_create_flow()` | 自然语言 → LLM → TOML → 确认 | P0 |
| `_param_tuning_flow()` | 对话中调整策略参数并重跑 | P1 |

### Phase 3: AI 策略生成（v0.3.0）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| `kronos/agent/strategy_prompts.py` | LLM system prompt | P0 |
| `kronos/agent/strategy_generator.py` | 调用 LLM 生成 TOML | P0 |
| 对话集成 | 描述 → 确认 → 注册 闭环 | P0 |

### Phase 4: 模拟盘（v0.4.0）

借鉴 AItrading 的 `OneMinuteExecutionEngine` 和 `EventBus` 架构。

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 事件总线 | `bar_closed` / `order_filled` / `position_changed` 事件类型 | P1 |
| 模拟盘引擎 | 1m 实时行情 + 虚拟订单匹配，执行优先级: reverse > SL > TP > exit > entry | P1 |
| 运行时状态持久化 | SQLite 存储 StrategyRuntime（trailing tier, TP1 标记, 冷却规则） | P1 |
| 信号引擎共享 | 同一份策略代码用于回测和模拟盘（`importlib` 动态加载） | P1 |
| 模拟盘报告 | 日/周报，信号记录，盈亏统计 | P1 |
| 交易所连接 | Binance WebSocket 实时行情（只读，不需要交易权限） | P1 |

### Phase 5: 实盘执行（v0.5.0+）

借鉴 AItrading 的 `StrategyExecutor` + `RiskGuard` + 分层风控。

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 策略级风控 | reentry gate、规则冷却、入场次数限制 | P2 |
| 执行前置检查 | 实盘开关、同向加仓阻止、FLAT 信号入场规则绑定 | P2 |
| 全局仓位风控 | 总敞口上限（USDC 计价） | P2 |
| 订单发送 | Binance REST API 下单（market/limit），时间同步，recvWindow 安全 | P2 |
| 止盈止损同步 | TP/SL stop-limit 订单创建 + 自动修复 | P2 |
| 仓位监控 | 实时持仓、P&L、风险敞口，WebSocket fill 事件 + 定期快照对账 | P2 |
| 每日摘要 | Agent 推送当日交易摘要（信号、成交、盈亏、风险使用率） | P2 |
| 尾随止损 | 借鉴 AItrading 的 trailing tier 模式 | P3 |

---

## 7. 从 AItrading 借鉴的架构设计

> 参考项目：`/Users/ethan/AItrading`，生产级 1h-信号 + 1m-执行的 Binance 量化系统。

### 7.1 信号引擎共享

AItrading 的 `strategy_signal.py` 同时被回测引擎（通过 `live_strategy_adapter.py` 的 `importlib` 动态加载）和实盘网关（直接 import）使用。**保证信号一致性**——回测结果和实盘行为严格对齐。

**Kronos 采用**：策略的 `compute(df) → pd.Series` 接口在回测和模拟盘中调用同一份代码。策略定义文件和因子实现绑定，确保"你在回测里看到的，就是实盘会执行的"。

### 7.2 执行优先级

AItrading 的 `OneMinuteExecutionEngine` 每根 1m K 线按固定优先级处理：

```
reverse（反向开仓） > SL（止损） > TP（止盈） > exit（出场信号） > entry（入场信号）
```

**Kronos 采用**：模拟盘和实盘引擎按相同优先级处理。这是一个经过生产验证的顺序——先处理风险（reverse/SL/TP），再处理新机会（entry）。

### 7.3 风险分层

AItrading 有 4 层风险检查，从细到粗：

| 层级 | 检查内容 | 位置 |
|------|----------|------|
| 1. 策略级 | reentry gate、规则冷却、入场次数限制 | `strategy_instance.py:360-398` |
| 2. 执行前置 | 实盘开关、同向加仓阻止 | `strategy_executor.py:435` |
| 3. 出场绑定 | FLAT 信号校验入场规则 | `strategy_executor.py:668` |
| 4. 全局仓位 | 总敞口上限 | `risk_engine.py:36` |

**Kronos 采用**：扩展当前简单的风控引擎，加入分层检查。Kronos 已有 `risk/engine.py` 的基础框架，需要补充策略级和全局级的检查逻辑。

### 7.4 策略 YAML 配置

AItrading 的策略配置清晰简洁：

```yaml
strategies:
  - strategy_id: "eth_v2_main"
    strategy_class: "v2"
    symbol: "ETHUSDT"
    kline_interval: "1h"
    tp1_pct: 0.011
    base_sl_pct: 0.04
    trailing_tiers: [[0.02, 0.005], [0.06, 0.015], ...]
```

每个策略自包含，参数有明确含义和默认值。**Kronos 采用 TOML 格式**（与现有配置体系一致），但结构借鉴这个风格。

### 7.5 运行时状态持久化

AItrading 的 `StrategyRuntime` 在每次重启时从 DB 恢复：trailing tier、TP1 标记、入场方向、冷却规则、split-SL 状态。

**Kronos 采用**：模拟盘/实盘的运行时状态写入 SQLite（Kronos 已有 `knowledge_base/store.py` 的 SQLite 基础），重启后恢复，避免因进程重启丢失订单上下文。

### 7.6 事件驱动架构

AItrading 使用 `EventBus` pub/sub：`bar_closed`、`fill`、`mark_price_tick`、`account_snapshot`。每个 `StrategyInstance` 按 symbol 订阅。

**Kronos 采用**：Kronos 已有 `agent/events.py` 的 append-only 事件时间线。模拟盘/实盘引擎复用同一事件模型，增加 `bar_closed`、`order_filled`、`position_changed` 等交易事件类型。

### 7.7 单标的策略实例

AItrading 每个 `StrategyInstance` 只管理一个 symbol。多个标的 = 多个实例。

**Kronos 采用**：策略配置中 `symbols` 允许列表，但运行时为每个 symbol 创建独立的执行实例。这样每个标的的状态（持仓、冷却、止损位）独立管理，互不干扰。

---

## 8. 不变更

- **不预装用户的个人策略** — R-breaker 是唯一的 builtin 示例策略
- **策略存储为用户本地文件** — 不上传、不同步、不依赖网络
- **AI 生成的策略代码由用户审核** — 不自动执行未确认的代码
- **模拟盘不涉及真实资金** — 仅用实时行情生成虚拟订单
- **实盘执行有人工闸门** — 首次执行、参数变更、风控触发时强制确认
- **不自动加仓、不网格、不马丁** — 只执行策略定义的信号
