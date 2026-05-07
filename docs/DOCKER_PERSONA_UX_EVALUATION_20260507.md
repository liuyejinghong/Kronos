# Kronos Docker 多画像首次体验评测（2026-05-07）

> 评测对象：Kronos v0.4.3
> 评测 commit：`a6e5d38`
> 评测方式：在 GitHub 全新 clone 的独立目录里，用 Docker 从零跑通 quickstart，再检查 `report latest`、`strategy draft` 和 `agent start` 的承接路径。
> 评测目的：继续用交易者视角判断“第一次安装后，用户能不能顺着系统给出的下一步继续做对的事”。

## 一句话结论

Kronos v0.4.3 的 Docker 首次体验已经从“能跑通”推进到“能继续做事”了，但还没到“新用户能稳定理解下一步”的程度。

这次最明显的变化有两点：

1. `report latest` 现在真的能把最新结论翻成交易语言。
2. `agent start` 里新增的“描述一个策略想法，先起草配置”可以把自然语言想法接到 `strategy draft`，再继续 `validate → smoke-test → register`。

但首次体验里仍然有几个卡点：

- quickstart 的首屏还是有一些工程术语，对完全小白不够友好。
- `docker compose up` 输出的构建/依赖下载信息依然很重，容易让人误解为故障。
- `agent start` 进入策略起草后，用户如果输入了不完整内容，系统会拒绝，这是对的，但提示仍可以更像交易助手而不是内部校验器。
- Docker 里的路径和命令虽然已经可复制，但新用户仍需要一点心智转换，才能知道“现在该读报告、起草配置，还是同步真实数据”。

## 评测画像

| 画像 | 期望 | 本轮观察 |
|---|---|---|
| L0 完全小白 | 跑起来、知道结果在哪 | 能跑，但仍会被构建日志和术语吓到 |
| L1 入门交易者 | 看懂策略是否值得继续 | `report latest` 已经能看懂，但还缺市场状态解释 |
| L2 有经验的主观交易者 | 把想法变成可验证草案 | `agent start` → `strategy draft` 已经顺了 |
| L3 Python 研究者 | 可复现、可追溯 | 结果和路径都清楚，能继续验证 |
| L6 Docker 首次用户 | 一个命令后知道下一步 | 主链路已通，但仍需更少工程噪音 |

## 实际操作记录

### 1. Docker quickstart

执行：

```bash
docker compose up --build
```

结果：成功。

关键输出：

```text
策略评估结果
1 个策略已评估
0 通过验证
当前没有策略通过验证。这在首次运行中很常见

研究报告: reports/research/experiments/20260507T095540Z-quickstart/auto_run_report.md
直接查看最新报告: kronos report latest

Docker 环境下，下一步：
  · 查看最新报告: docker compose run --rm kronos uv run kronos report latest
  · 起草策略配置: docker compose run --rm kronos uv run kronos strategy draft --prompt "我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期"
```

正向反馈：

- 结论现在能直接看懂，不再只是“0 通过验证”。
- 新增 `report latest` 的交易语言摘要非常关键。
- `strategy draft` 已经进入 Docker 下一步，路径闭环更完整。

问题：

- 构建日志仍然很重，第一次看会分不清是在下载、安装还是报错。
- quickstart 里的“最小研究循环”对 L0/L1 仍偏内部术语。
- 1m sample 数据和 15m TOML 配置的关系仍需要用户自己理解。

### 2. `report latest`

执行：

```bash
docker compose run --rm kronos uv run kronos report latest
```

结果：这次是本轮最好的改进之一。

实际输出：

```text
本次结论：当前没有策略通过验证，不建议进入组合或模拟盘。
数据：BTCUSDT / 1m K线 / 约 7.0 天 / sample 数据。
策略：1 个已评估，0 个通过，1 个未通过。
判断：这是安装和流程试跑，不能证明策略有效或无效。
下一步：先运行 `docker compose run --rm kronos uv run kronos data sync --symbols BTCUSDT --since 2026-01-01` 同步真实行情，再重新验证。
```

产品判断：

- 这已经是交易者能用的结论了。
- 它明确区分了 sample 试跑和真实行情验证。
- 它把下一步直接翻译成可执行命令。

剩余问题：

- `1m K线`、`sample 数据` 这些词仍然偏研究者，但已经可接受。
- `组合` 和 `模拟盘` 对核心交易者能懂，对 L0 仍然偏抽象。

### 3. `strategy draft`

执行：

```bash
docker compose run --rm kronos uv run kronos strategy draft --prompt "我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期"
```

结果：成功。

实际输出：

```text
--- Strategy Draft ---
status: 已生成草案
intent: 我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期
template: R-breaker 日内突破
symbols: BTCUSDT
timeframe: 15m
key_parameters: atr_period=14, volatility_multiplier=1.5
...
next: docker compose run --rm kronos uv run kronos strategy validate /root/.kronos/strategy_drafts/....toml
then: docker compose run --rm kronos uv run kronos strategy smoke-test /root/.kronos/strategy_drafts/....toml
then: docker compose run --rm kronos uv run kronos strategy register /root/.kronos/strategy_drafts/....toml
```

正向反馈：

- 这是把“自然语言想法 → 可继续验证的草案”真正接起来了。
- Docker 内路径是容器路径，能直接复制。
- 没有把草案包装成盈利承诺。

产品问题：

- 对完全小白来说，`R-breaker`、`TOML`、`validate`、`smoke-test` 还是有学习门槛。
- `strategy draft` 成功后虽然有下一步，但用户仍需知道为什么要先 `validate` 再 `smoke-test`。

### 4. `agent start`

执行：

```bash
docker compose run --rm kronos uv run kronos agent start
```

结果：这次承接得比旧版明显更顺。

第一屏已经变成了：

```text
我可以帮你把策略想法起草成配置，分析历史表现，或者继续推进新的研究方向。
...
[4] 描述一个策略想法，先起草配置
```

进入 `[4]` 后：

```text
请描述你的策略想法。
当前首版支持 R-breaker 日内突破。请说清楚品种和周期，例如：我想做 BTCUSDT 的 R-breaker 日内突破，15m 周期。
```

输入标准策略想法后：

```text
--- Strategy Draft ---
status: 已生成草案
...
next: kronos strategy validate ...
then: kronos strategy smoke-test ...
then: kronos strategy register ...
```

这说明：

- `agent start` 已经不再把用户甩回 Python 示例。
- 自然语言策略入口已经能在对话里闭环。
- 新用户在“我有个想法”之后，不需要先知道 `CandidateFactorSpec`。

我也试了一个不完整输入，系统明确拒绝并要求补齐，这个行为是对的。

## 主要问题，按优先级排序

### P0：quickstart 和 `report latest` 之间的“结果解释”还可以再短一点

现在已经能看懂，但第一次用户仍要多读几句才能理解“这是试跑，不是结论”。

根因：系统还在同时兼顾研究者和交易者两种阅读方式。

### P1：`strategy draft` 已打通，但术语负担还偏重

对 L2/L6 来说，`validate` / `smoke-test` / `register` 还是工程词。

根因：产品主线已经接上了，但文案还没完全翻译成交易行为。

### P1：`agent start` 的首屏已经对了，但还可以更像“助手”而不是“入口菜单”

现在菜单是清晰的，但还是偏命令面板。

根因：Agent 还没有完全按画像重写成“先看结论，再做下一步”的叙事。

### P2：Docker 首次构建日志仍太重

构建成功，但第一次看到大量依赖下载的人，还是容易怀疑卡住。

根因：这是 Docker / Python 科学栈的客观成本，但产品还可以做更明确的“正在安装 / 预计多久 / 已完成什么”提示。

## 结论

如果按“Docker 全新首次使用”这个标准来打分，Kronos 现在已经从“不合格”往“可用”跨了一大步：

- `quickstart` 能跑完。
- `report latest` 能读懂。
- `strategy draft` 能把想法接成草案。
- `agent start` 能把用户带进同一条路径。

但它还不是完全小白友好型产品，下一轮优先级应该继续放在：

1. 报告语言进一步交易化。
2. Docker 首屏减少工程噪音。
3. `agent start` 把“继续做什么”说得更短更直白。
