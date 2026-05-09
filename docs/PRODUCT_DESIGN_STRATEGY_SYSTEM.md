# Kronos 策略系统产品设计

> 版本：0.4.5
> 日期：2026-05-07

## 当前能力边界

v0.4.5 的已交付能力是：`quickstart` 注册并验证内置 R-breaker，生成研究报告，`report latest` 直接读取最新结果卡；用户还可以用 `kronos strategy draft --prompt "..."` 将 R-breaker 相关想法起草成策略概要、trace 和 TOML 草案，再按“检查配置 → 空跑确认 → 进入候选池”推进，底层仍对应 `validate → smoke-test → register`。这一版新增了关键交易重放报告、市场状态分段下钻、只读观察边界下钻和逐 symbol 烟雾测试。稳定阅读入口分别是 `kronos report replay`、`kronos report regime` 和 `kronos report observation`。

以下能力仍不属于当前已交付范围：

- 任意自然语言生成新策略代码或新策略引擎
- 完整历史重放 / 逐笔或逐分钟回放
- 实时模拟盘

本文前半部分的 Agent 对话脚本仍是目标体验草案；判断当前能不能用，应以本节和下方版本能力矩阵为准。

## 核心原则

**Kronos 是一个策略研究助手，不是一个策略代码框架。** 用户不应该被要求"先写代码才能用"。

策略的完整生命周期：**体验 → 理解 → 定制 → 创建**。当前版本已经覆盖“体验 / 理解 / 手动定制 / R-breaker 模板起草 / 首次结果解释收口 / 关键交易回放起步”的最小链路，“通用 AI 创建 / 完整历史重放 / 模拟盘”进入后续版本。

目标用户不是完全小白，而是已经有交易经验或研究能力、需要把策略想法变成可验证证据的人。完整用户画像见 `docs/USER_PERSONAS.md`。

---

## 1. 目标用户路径（后续体验草案）

### 首次使用

```
$ kronos agent start

Kronos Agent

你好！我是 Kronos，一个加密货币策略研究助手。

我可以帮你把 R-breaker 相关想法起草成配置，也可以分析策略的历史表现。

你想做什么类型的策略？

  [1] 顺势而为 — 在趋势确认后入场（均线、突破），适合 BTC/ETH 大周期
  [2] 日内短线 — 当天进出，吃小波动（R-breaker 等），适合活跃品种
  [3] 我有一个具体的想法 — 描述你的 R-breaker 想法，我来先起草配置
```

### 路径 A：体验日内短线（以 R-breaker 为例）

```
> 2

好的。日内短线策略的特点是当天进场、当天出场，不隔夜。
系统内置了一个经典例子——R-breaker 日内突破策略。

R-breaker 用前一天的 OHLC 数据计算今天的:
· 突破买入价（B-break）
· 突破卖出价（S-break）  
· 参考中枢价（pivot）

当价格突破 B-break 时做多，突破 S-break 时做空。

📊 当前默认配置:
  交易品种: BTCUSDT
  时间周期: 15 分钟
  突破倍数: 1.5x（相对 ATR 波动率）
  止损比例: 2%

——要直接用默认配置跑一次吗？
  [1] 跑，用最近 30 天数据
  [2] 先调整参数
  [3] 看看其他类型的策略

> 1

⏳ 加载数据…
⏳ 计算 R-breaker 信号…
⏳ 跑回测验证…

✅ 完成！

📊 R-breaker 在 BTCUSDT 上的表现 (2026-03-15 ~ 2026-04-14, 30 天):

  策略收益:     +3.2%
  同期持有 BTC: +1.8%  ← 你的策略比持有 BTC 多赚了 1.4%
  胜率:         52% (13 胜 / 12 负)
  最大回撤:     -4.1% (BTC 同期最大回撤 -6.3%)
  盈亏比:       1.4 (平均盈利 / 平均亏损)

📈 市场环境: 这 30 天 BTC 处于上升趋势（+1.8%）。
   策略在趋势行情中表现较好，震荡市会频繁止损。

——接下来想做什么？
  [1] 调整参数再跑一次（比如试试更高的突破倍数）
  [2] 换个品种（ETH 上表现可能不同）
  [3] 加一个震荡过滤器（只在 ADX > 25 时开仓，减少假信号）
  [4] 用历史重放看看关键交易和失败窗口（v0.4.5）
  [5] 这就够了
```

### 路径 B：策略起草（v0.4.3 已交付子集）

```
> 2

好的！描述一下你的策略逻辑，越具体越好。

比如："当 5 日均线上穿 20 日均线时做多，下穿时平仓，
      只在 BTC 上交易，每笔仓位不超过 20%"

> 我想做 BTCUSDT 和 ETHUSDT 的 R-breaker 日内突破，15m 周期。

好的，让我理解一下你的策略：

📝 策略概要:
  名称: R-breaker 日内突破
  类型: 日内突破
  品种: BTCUSDT, ETHUSDT
  周期: 15m
  默认参数: atr_period=14, volatility_multiplier=1.5
  未确定项: 无

——这是不是你想要的？
  [1] 对，就按这个来
  [2] 调整一下参数
  [3] 重新描述

> 1

好的。我先写入草案，不会注册策略，也不会启动模拟盘。

下一步:
  1. kronos strategy validate ~/.kronos/strategy_drafts/<draft>.toml
  2. kronos strategy smoke-test ~/.kronos/strategy_drafts/<draft>.toml
  3. kronos strategy register ~/.kronos/strategy_drafts/<draft>.toml
```

---

## 2. 策略模型

### 策略定义（v0.4.3 已交付子集，用户可见）

```toml
# ~/.kronos/strategies/r_breaker.toml

[strategy]
id = "r_breaker"
name = "R-breaker 日内突破"
description = "基于前一日 OHLC 计算突破价位, 适合日内短线研究。"
kind = "r_breaker"

[universe]
symbols = ["BTCUSDT", "ETHUSDT"]
timeframe = "15m"

[params]
atr_period = 14
volatility_multiplier = 1.5
```

当前 v0.4.3 只支持 `kind = "r_breaker"`。`kronos strategy draft` 可以把 R-breaker 相关自然语言想法起草成同一份 TOML 结构；通用 entry/exit 表达式、仓位配置、止损配置和任意策略代码生成仍是后续版本目标。

### 策略存储（v0.4.3 已交付）

```
~/.kronos/
  strategy_drafts/
    draft_r_breaker_*.summary.md
    draft_r_breaker_*.trace.json
    draft_r_breaker_*.toml      # 自然语言起草输出
  strategies/
    r_breaker.toml           # R-breaker 配置模板
    my_r_breaker.toml        # 用户复制/改名后的 R-breaker 配置
  config.toml
```

### 策略注册流程（v0.4.3 已交付）

```
draft 起草概要和 TOML →
init-r-breaker 生成 TOML → validate 校验字段和参数 → smoke-test 用本地 K 线试算
→ register 写入候选池 → Agent/Web 可见
```

`register` 默认要求烟雾测试通过；如果数据暂时不可用，用户可以显式加 `--skip-smoke`，但这只适合高级用户。当前烟雾测试验证“能读取本地 K 线并产生有效信号”，不等于通过回测验证，也不代表可以进入模拟盘。

---

## 3. R-breaker — 内置参考策略

### 为什么是 R-breaker

- 经典策略，交易者普遍知道
- 逻辑清晰（3 个价格位 + 突破信号），适合作为示例
- 参数少，易于理解和调整
- 有实际交易价值

### 默认配置

```toml
[strategy]
id = "r_breaker"
name = "R-breaker 日内突破"
description = "基于前一日 OHLC 计算突破价位, 适合日内短线研究。"
kind = "r_breaker"

[universe]
symbols = ["BTCUSDT", "ETHUSDT"]
timeframe = "15m"

[params]
atr_period = 14
volatility_multiplier = 1.5
```

### 用户可调参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `symbols` | BTCUSDT, ETHUSDT | 交易品种 |
| `timeframe` | 15m | K 线周期 |
| `atr_period` | 14 | 波动率平滑周期 |
| `volatility_multiplier` | 1.5x | 突破阈值乘数 |

---

## 4. AI 策略创建器（v0.4.3 已交付子集）

v0.4.3 不是通用策略代码生成器，而是一个受模板约束的策略起草器：

- 支持：R-breaker / 日内突破相关自然语言描述。
- 输出：策略概要、澄清问题或拒绝原因、trace JSON、可编辑 TOML 草案。
- 闸门：草案必须继续走 `validate → smoke-test → register`。
- 边界：不支持均线、RSI、网格、套利、任意 entry/exit 表达式和自动下单。
- 解析：默认使用确定性规则；用户显式加 `--use-ai` 时才尝试本地 DeepSeek 辅助解析。

### LLM Prompt 设计

```
你是一个加密货币量化策略专家。用户会用自然语言描述交易想法，
你需要将其转化为结构化的策略定义。

策略定义格式（TOML）：
[strategy] id / name / description / kind = "r_breaker"
[universe] symbols / timeframe
[params] atr_period / volatility_multiplier

规则：
- 只允许 R-breaker 模板。
- 如果用户没有明确指定品种，返回 needs_clarification。
- 如果用户没有指定时间周期，返回 needs_clarification。
- 如果用户描述的是均线 / RSI / 网格 / 套利等不支持模板，返回 unsupported_template。

输出：先输出策略概要和未确定项；只有 status=ready 时才写出完整 TOML。
```

### 策略模板库

后续模板库目标如下。v0.4.3 只开放 R-breaker：

| 模板 | 类型 | 适用场景 |
|------|------|----------|
| 趋势跟踪 | `ma_cross` | 用户提到"均线""金叉""趋势" |
| 动量突破 | `pct_change` | 用户提到"涨幅""动量""突破" |
| 均值回归 | `rsi` / `bollinger` | 用户提到"超买""回归""震荡" |
| 波动率过滤 | `atr` / `volatility` | 用户提到"波动率""缩量" |
| R-breaker | `r_breaker` | 用户提到"日内""突破""开盘"（v0.4.3 已支持） |

---

## 5. 交易执行链路

策略回测通过只是第一步。用户真正关心的是：**这个策略能不能帮我赚钱？** 这需要完整的执行链路。

### 完整生命周期

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  定义    │ →  │  验证    │ →  │  重放    │ →  │  模拟    │ →  │  执行    │
│ 策略     │    │ 回测     │    │ 历史回放 │    │ 纸交易   │    │ 实盘     │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
  R-breaker      30天历史       观看每日买卖    实时行情         交易所 API
  AI 创建        信号质量       不需要 API     虚拟订单         仓位+风控
  手动编写       收益/风险      本地数据即可    Binance行情      人工闸门

  ←—— 迭代: 每一步都可以回到前面调整参数或策略逻辑 ——
```

### 版本当前能力

| 阶段 | v0.4.5 | 说明 |
|------|--------|------|
| 定义策略 | 部分具备 | 内置 R-breaker 可注册和验证；TOML 配置、校验、烟雾测试已交付；R-breaker 自然语言起草已交付 |
| 验证回测 | 具备 | quickstart / 研究工作台可输出研究报告和可信度结论 |
| 最新报告 | 具备 | `kronos report latest` 可直接读取最新结果卡和产品报告路径 |
| 策略配置烟雾测试 | 具备 | `kronos strategy smoke-test` 验证本地数据和信号计算可用 |
| 历史重放 | v0.4.5 起步 | 当前提供关键交易重放报告，不做逐笔或逐分钟回放 |
| Binance 模拟盘真实成交 | v0.4.8 | 需要 Binance 模拟盘 / 测试网 API Key，只连接测试网 |
| 实盘执行 | v0.5.0+ | 需要交易 API Key、风控配置和人工闸门 |

### 各阶段 Agent 对话

#### 阶段 1: 验证（v0.4.0 已交付）

```
Agent: R-breaker 近 30 天 BTC:
       策略 +3.2% vs 持有 +1.8%, 夏普 0.68, 最大回撤 -4.1%
       
       ——想进一步验证吗？
         [1] 换个品种跑跑（ETH 上表现可能不同）
         [2] 用历史重放看看关键交易和失败窗口（v0.4.5）
         [3] 调整参数
```

#### 阶段 2: 历史重放（v0.4.5 起步，不需要 API Key）

##### 可读入口

- `kronos report replay`：关键交易重放
- `kronos report regime`：市场状态分段
- `kronos report observation`：只读观察边界

```
> 2

Agent: 好的。我会用过去 30 天的数据模拟实时交易——就像你坐在屏幕前
       看行情、等信号、下单一样，只是这一切发生在历史数据上。

       开始重放 3月15日…
       [09:00] BTC 68720 → 无信号
       [09:01] BTC 68680 → 无信号
       [09:15] BTC 69100 → R-breaker 做多信号 → 虚拟买入 0.02 BTC @ 69110
       [13:45] BTC 69450 → 达到止盈 2% → 虚拟卖出 0.02 BTC @ 69440
       │ 这笔交易: +$66 (+1.9%)
       ...
       
       ═══ 30 天重放完成 ═══
       总交易: 25 笔
       盈利: 13 笔 | 亏损: 12 笔
       总收益: +$340
       
       ——想怎么做？
         [1] 这是我想用的策略，上实时模拟盘
         [2] 有些买卖点不满意，调整一下
         [3] 看看别的策略
```

#### 阶段 3: Binance 模拟盘真实成交（v0.4.8，需要 Binance 测试网 API Key）

```
> 1

Agent: 好的。下一步会进入 Binance 模拟盘 / 测试网。系统会用测试网 API Key
       提交真实测试订单并读取测试网成交，但不会触碰真实资金或主网实盘。

       请先配置 Binance 测试网 API Key，然后运行 preflight。

> kronos paper preflight

Agent: preflight 通过。当前环境: Binance testnet。
       资金: 测试资金，不影响真实账户。
       策略: R-breaker 日内突破。
       停止命令: kronos paper stop。

> kronos paper start

Agent: 测试网模拟盘已启动。我会:
       · 只连接 Binance testnet
       · R-breaker 生成信号 → 提交受限测试网订单
       · 记录 testnet order id、成交状态和错误原因
       · 停止后生成模拟盘报告
       
       你可以在终端看到实时动态，也可以随时问我"现在什么情况"。
```

#### 阶段 4: 实盘执行（v0.5+）

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

> 2026-05-05 修订：根据 Codex (GPT 5.5) 产品评估，**v0.3.0 范围大幅收缩**。
> 核心原则：先把"判断一个策略值不值得信任"做透，再做 AI 创建和多策略。
> v0.3.x 产品目标：**让一个非开发交易者在 10 分钟内判断 R-breaker 是否值得进入模拟盘观察。**
> v0.4.0 产品目标：**让用户能手动配置一个 R-breaker 策略，并在历史重放 / 模拟盘前经过明确的本地烟雾测试和注册闸门。**
> v0.4.3 产品目标：**让用户用自然语言起草 R-breaker TOML，并保留澄清、拒绝和验证闸门。**
> v0.4.4 产品目标：**让 Docker 首次体验先回答结果是什么、能不能信、下一步做什么。**
> v0.4.5 产品目标：把结果卡推进成解释卡，补齐关键交易重放、市场状态分段、只读观察边界和逐 symbol smoke-test。
> v0.4.x 后续目标：历史重放、市场状态分段、只读观察边界、更多策略模板和实时模拟盘。

### Phase 1: R-breaker 可信度评估闭环（v0.3.0）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| `kronos/strategy/spec.py` | `StrategySpec` 数据模型 + TOML 解析 | P0 |
| `kronos/strategy/store.py` | 加载 `~/.kronos/strategies/*.toml` | P0 |
| `kronos/strategy/r_breaker.py` | R-breaker 因子实现（遵循 `Factor` 协议） | P0 |
| 内置 `r_breaker.toml` | 首次启动自动写入，策略自描述 | P0 |
| 一键回测 | `agent start` → 选"日内短线" → 默认参数跑 30 天回测 | P0 |
| **可信度报告** | 收益 + 手续费后收益 + 最大回撤 + 最大连续亏损 + 盈亏比 + vs 持有基准 + 交易笔数 | P0 |
| 手续费/滑点扣除 | 每笔交易自动扣除 fee_bps + slippage_bps | P0 |
| 参数调整 + 重跑 | 对话中修改波动率倍数、止损比例、品种，即时重跑 | P0 |
| 关键交易复盘 | 列出最大盈利/最大亏损/最长持仓的交易，每笔有入场理由和出场理由 | P0 |
| 可信度结论 | 回测结束后给明确判断："不建议" / "可以观察" / "值得模拟盘"，附理由 | P0 |

### v0.3.3 产品体验收口

本轮不新增模拟盘引擎，先把 v0.3.x 用户判断链路补完整：

- `kronos report latest`：直接打印最新产品报告摘要，用户不需要进入 `reports/research/experiments/` 手动找目录。
- 报告保留 `mean_rank_ic` 等技术字段，但在候选结果中追加交易语言解读：预测方向是否稳定、多空分层是否拉开、样本外是否足够支持模拟盘观察。
- `kronos data sync` 明确数据来源、同步范围和 API Key 边界：当前使用 Binance USDM 公开行情，拉 K 线 / funding / OI，不需要 API Key；无 `--since` 时沿用增量同步或交易所最早可用历史。
- 当前版本只到研究报告、Agent 复盘和策略配置试算；实时模拟盘属于后续 v0.4.x，未通过验证的策略不建议进入 paper trading。

### Phase 2: 多策略 + AI 创建（v0.4.3 已启动，后续扩展）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| AI 自然语言 → TOML | R-breaker 模板起草已交付；更多模板后续扩展 | P1 |
| 策略池浏览和对比 | 多个策略并排比较回测结果 | P1 |
| 多品种/多周期 | 用户选择品种和时间框架组合 | P1 |
| 按市场状态分段 | 牛市/熊市/震荡市分别出结果 | P1 |
| 参数稳健性热力图 | 展示参数邻域的稳定性 | P2 |

### Phase 2.5: 策略解释与观察路径（v0.4.5）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 关键交易重放 | 从最新报告继续下钻，解释关键入场 / 出场 / 失败窗口 | P0 |
| 市场状态分段评估 | 牛市 / 熊市 / 震荡市 / 高波动环境分别给结论 | P0 |
| 只读观察边界 | 先定义虚拟订单、延迟、滑点和人工闸门，再考虑更强执行层 | P0 |
| 多品种 smoke-test | 每个 symbol 单独验证，避免只看第一个品种 | P0 |

### Phase 3: 历史重放 + 实时模拟盘（后续 v0.4.x）

（原 v0.3.0 的历史重放合并至此版本）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 历史重放（关键交易回放） | 只回放关键交易（入场/出场节点），不做逐分钟流水 | P0 |
| Binance 模拟盘真实成交 | Binance testnet 行情 + 受限测试网订单 + testnet 成交记录，需要测试网 API Key | P1 |
| 事件总线 | `bar_closed` / `order_filled` / `position_changed` 事件类型 | P1 |
| 运行时状态持久化 | SQLite 存储 StrategyRuntime | P1 |

### Phase 4: 实盘执行（v0.5.0+）

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

## 8. 评审记录

### 2026-05-05: CC 自审 → 修订

见 `docs/PRODUCT_DESIGN_REVIEW_20260505.md`。核心修订：入口改为交易风格、回测结果加基准、AI 策略加烟雾测试、新增关键交易重放模式。

### 2026-05-05: Codex (GPT 5.5) 产品评估 → v0.3.0 范围收缩

**关键意见**：当前 v0.3.0 范围太大（R-breaker + AI 创建 + 历史重放 + Agent 对话重写），每一项都够独立踩坑。建议砍成一个明确可验收的闭环。

**采纳的修改**：
- v0.3.0 聚焦：R-breaker 单一策略 → BTCUSDT 15m → 一键回测 → 可信度报告 → 参数调整 → 关键交易复盘
- AI 策略创建后移至 v0.4.x（等基础评估框架可信了再做）
- 历史重放先做关键交易复盘，不做逐分钟流水；逐分钟流水仍后移至后续版本。
- 新增可信度结论：每次回测后给出"不建议/可以观察/值得模拟盘"的明确判断
- 新增手续费/滑点扣除：收益数字扣费后展示
- 新增参数稳健性热力图（v0.4.x）

**未采纳**：
- R-breaker 名称保留（公认经典策略名，交易者普遍知道）
- 模拟盘需要 API Key（这是必备的前置条件，不是门槛问题）

---

## 9. 不变更

- **不预装用户的个人策略** — R-breaker 是唯一的 builtin 示例策略
- **策略存储为用户本地文件** — 不上传、不同步、不依赖网络
- **AI 生成的策略代码由用户审核** — 不自动执行未确认的代码
- **模拟盘不涉及真实资金** — v0.4.8 只允许 Binance testnet 订单和测试资金，不允许 mainnet/live
- **实盘执行有人工闸门** — 首次执行、参数变更、风控触发时强制确认
- **不自动加仓、不网格、不马丁** — 只执行策略定义的信号
