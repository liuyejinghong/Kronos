# Kronos Docker 多画像首次体验评测（2026-05-06）

> 评测对象：Kronos v0.4.0  
> 评测 commit：`7930ff4`  
> 评测方式：在当前 checkout 使用独立 Docker Compose project `kronospersonaeval` 和全新 volume 模拟新用户首次使用。  
> 评测目的：按 `docs/USER_PERSONAS.md` 的用户画像，记录不同用户在 Docker 首次体验中的理解障碍、产品断点和信任风险。  
> 范围限制：本轮只做产品体验记录，不修复代码；构建层使用本机 Docker cache，重点观察运行后的产品路径。

## 一句话结论

Kronos v0.4.0 的 Docker 主路径已经“能跑通”，但还没有达到“核心交易用户能自助判断下一步”的标准。

对 L3/L5 研究者和工程接手者来说，当前输出足够证明系统有数据、策略、报告和可复现 artifact；对 L1/L2 交易用户来说，体验仍然容易误判：他们会看到“0 通过验证”、`synthetic`、`观察名单`、`候选进入组合`、`90 天复验`、`12 个旧策略` 等混杂信息，却无法稳定回答三个核心问题：

1. 这次只是安装试跑，还是已经证明 R-breaker 不行？
2. 当前用的是 7 天模拟数据、真实数据，还是 90 天验证？
3. 下一步应该读报告、同步数据、改参数、注册策略，还是打开 Agent？

所以本轮产品结论是：**Docker 安装链路合格，首次研究体验仍不合格；v0.4.1+ 应优先修正报告摘要、Agent 文案和 Docker 路径指引，而不是继续堆新功能。**

## 评测画像

本轮用 6 类用户视角复盘同一套 Docker 首次使用流程：

| 画像 | 期望 | 本轮重点观察 |
|---|---|---|
| L0 完全小白 | 知道是否跑起来、结果在哪 | 是否被日志、路径、英文术语吓退 |
| L1 入门交易者 | 看懂策略结果和风险边界 | 是否知道 0 通过验证代表什么 |
| L2 有经验主观/半自动交易者 | 判断策略想法是否值得继续 | 是否知道下一步该同步数据、调参还是放弃 |
| L3 Python 交易研究者 | 数据、粒度、样本、artifact 可追溯 | 输出是否一致、可复现、能定位报告 |
| L4 小型量化团队负责人 | 候选状态、失败原因、下一阶段清晰 | 是否能把结果交给团队做决策 |
| L6 安装小白 / Docker 首次用户 | 一个 Docker 命令后有明确后续命令 | Docker 内外路径是否一致、命令是否可复制 |

## 实际操作记录

### 1. Docker quickstart

执行：

```bash
docker compose -p kronospersonaeval up --build --abort-on-container-exit
```

结果：成功，生成 fresh volume，并完整跑完 quickstart。

关键输出：

```text
Kronos — Docker Quickstart
未找到本地数据，正在生成 7 天 BTCUSDT sample 数据（标记为 synthetic）…
Sample 数据已生成：data/curated/BTCUSDT
[10080 bars, 7d, venue=synthetic]
正在注册内置策略…
R-breaker 日内突破 (r_breaker) — trend_momentum
正在运行最小研究循环（R-breaker × BTCUSDT）…
策略评估结果
市场基准: 使用模拟数据，无法提供可信基准对比。同步真实行情后可查看。
1 个策略已评估
0 通过验证
研究报告: reports/research/experiments/20260506T115008Z-quickstart/auto_run_report.md
直接查看最新报告: kronos report latest
```

正向反馈：

- Docker 能从空 volume 直接跑到报告生成，入口稳定。
- quickstart 明确说明 sample 数据是 synthetic，没有伪造市场基准。
- 终端明确提醒当前版本只输出研究报告，不会启动模拟盘或真实下单。
- v0.3.1 的旧断点“Agent 看不到 quickstart 注册的策略”在本轮没有复现。

主要问题：

- 产品输出夹杂结构化日志，例如 `config.loaded`、`partition.written`、`query.loaded`。L3/L5 能理解，L0/L1 会认为系统在报错或进入开发模式。
- `bars`、`venue=synthetic`、`data/curated`、`trend_momentum` 仍是工程/研究术语，首次屏缺少交易语言翻译。
- “1 个策略已评估，0 通过验证”是正确风险提示，但没有直接说明“这是安装试跑，不是策略死亡证明”。

### 2. 读取最新报告

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos report latest --max-lines 80
```

结果：成功，但摘要过短。

实际输出：

```text
--- Latest Kronos Report ---
report: reports/research/experiments/20260506T115008Z-quickstart/auto_run_report.md
run_dir: reports/research/experiments/20260506T115008Z-quickstart

本次自动研究已完成工作台和观察名单补证据，当前仍没有候选进入组合或实盘。
```

产品问题：

- `report latest` 已解决“不用 ls 目录”的问题，但没有解决“用户读不懂最新结论”的问题。
- 摘要没有显示数据类型：7 天 synthetic sample。
- 摘要没有显示策略：R-breaker。
- 摘要没有显示粒度：quickstart / Agent 研究均是 1m。
- 摘要没有解释 0 通过验证的原因。
- 摘要没有给可执行下一步。
- “工作台、观察名单、候选、组合、实盘”对 L1/L2 是内部流程词，不是交易判断。

根因定位：

- `kronos/reporting/latest.py` 的 `summarize_report()` 只抽取 Markdown 的第一个产品段落。
- `kronos/research/auto_runner.py` 的 `## 一句话结论` 是固定流程总结，不包含样本类型、策略名、验证失败原因和下一步。
- 完整日报里已经有数据周期、粒度、是否同步、评估数量等信息，但 `report latest` 没有把它们组成用户第一屏。

### 3. 数据状态

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos data status --symbols BTCUSDT
```

结果：成功。

实际输出：

```text
config.loaded path=configs/dev.toml
Data Coverage:
Symbol       Dataset      From                   To                           Bars
BTCUSDT      klines_1m    2026-04-29 11:50       2026-05-06 11:49            10080
```

画像反馈：

- L3/L5：这份输出可用，能确认数据覆盖。
- L1/L2：`Dataset`、`klines_1m`、`Bars` 可猜，但仍偏研究者语言。
- L0/L6：`config.loaded` 会被误解成异常或调试残留。

产品建议：

- 默认输出先给交易语言：`BTCUSDT 1分钟K线：7天，10080根，sample数据`。
- `--debug` 或配置打开时再展示 `config.loaded`。

### 4. 策略配置初始化

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos strategy init-r-breaker
```

结果：成功。

实际输出：

```text
--- Strategy Config Created ---
path: /root/.kronos/strategies/r_breaker.toml
strategy: R-breaker 日内突破 (r_breaker)
symbols: BTCUSDT, ETHUSDT
timeframe: 15m
next: kronos strategy smoke-test /root/.kronos/strategies/r_breaker.toml
```

正向反馈：

- Docker 内路径是正确的 `/root/.kronos/...`。
- 输出有明确下一步 `smoke-test`。
- `symbols` 和 `timeframe` 对 L2/L3 有价值。

产品问题：

- Docker 用户看到的 `next` 命令不是 Docker 可直接复制命令；他需要自己补 `docker compose run --rm kronos uv run`。
- quickstart 刚刚研究的是 1m 数据，`init-r-breaker` 生成的策略配置默认是 15m。两个都叫 R-breaker，但用户不知道“刚刚评估的”和“我现在生成的配置”是不是同一个研究对象。

根因定位：

- CLI 策略配置入口输出的是容器内命令，不知道当前命令来自 Docker entrypoint 包装。
- quickstart / Agent 研究链路硬编码使用 1m；TOML 配置默认 15m；缺少产品解释把二者区分开。

### 5. 策略 smoke test：容器路径成功，宿主机 `~` 路径失败

容器路径执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos strategy smoke-test /root/.kronos/strategies/r_breaker.toml
```

结果：成功。

关键输出：

```text
--- Strategy Smoke Test ---
status: 通过
strategy: r_breaker
symbol: BTCUSDT
timeframe: 15m
rows: 673
valid_signals: 420
strong_signals: 242
reason: ok
message: 策略能读取本地数据并产生强突破信号, 可进入研究验证。
trading_enabled: no; smoke test only checks research logic
```

这条输出对 L2/L3 是有价值的：它说明策略逻辑能跑通，但不会交易。

宿主机 `~` 路径执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos strategy smoke-test ~/.kronos/strategies/r_breaker.toml
```

结果：失败。

实际输出：

```text
Strategy config invalid: Strategy config not found: /Users/ethan/.kronos/strategies/r_breaker.toml
config.loaded path=configs/dev.toml
```

产品问题：

- README 的本地命令使用 `~/.kronos/strategies/r_breaker.toml`，Docker 用户很容易把它套进 `docker compose run`。
- 在 shell 里 `~` 会先被宿主机展开成 `/Users/ethan/...`，容器内当然找不到。
- 这个失败对 L6 是典型“我照着文档做了但报错”的体验，且错误没有解释“这是 Docker 内外路径不同”。

根因定位：

- 本地路径和 Docker 路径使用了同一套文档口径，没有在 Docker 场景做路径翻译。
- CLI 报错只说明文件不存在，没有识别 `/Users/...` 这类明显宿主机路径并给 Docker 专用提示。

### 6. 策略注册

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos strategy register /root/.kronos/strategies/r_breaker.toml
```

结果：成功。

实际输出：

```text
--- Strategy Registered ---
candidate_id: r_breaker
title: R-breaker 日内突破
symbols: BTCUSDT, ETHUSDT
origin: user_config
visible_to_agent: yes
```

正向反馈：

- `visible_to_agent: yes` 对用户很关键，说明 Agent 能看到。
- v0.3.1 的候选池持久化断裂在本轮已经修复。

产品问题：

- `candidate_id`、`origin` 仍是内部词。
- 对 L2 更有用的表达应该是：`R-breaker 已加入你的策略池，下一次 Agent 分析会看到它。`

### 7. Agent 首屏

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos agent start
```

结果：成功进入交互模式。

首屏关键输出：

```text
Kronos Agent

你好！我是 Kronos，一个加密货币量化研究助手。
我可以帮你分析策略的历史表现，回测交易想法，或者让 AI 帮你找到新的研究方向。

正在检查你的环境…
query.loaded rows=10080 symbol=BTCUSDT timeframe=1m

你已经有一些数据了（BTCUSDT 等），可以直接开始。
  [BTCUSDT: synthetic [模拟数据]]
AI 模型未配置

  [1] 帮我分析一下这些策略的表现
  [2] 先看看有什么策略
  [3] 怎么配置 AI 模型？
```

正向反馈：

- Agent 能识别 BTCUSDT 数据。
- Agent 能明确 AI 模型未配置。
- Agent 不再说“你还没有定义任何策略”。

产品问题：

- `query.loaded` 调试日志仍插在对话里。
- `BTCUSDT: synthetic [模拟数据]` 同时出现英文 synthetic 和中文模拟数据，表达重复。
- 菜单说“这些策略”，但还没有先告诉用户当前有哪些策略、是否包括刚注册的 R-breaker。

### 8. Agent 查看策略列表

选择菜单 `2`。

实际输出：

```text
这里有 {n} 个策略，按关注度排列：

值得关注的:
  #50 R-breaker 日内突破  [观察]

这些策略在 crypto 上跑了 90 天验证，但没有一个能直接赚钱——这是正常的，好的策略需要反复打磨。
```

这是本轮最高优先级的产品缺陷之一。

影响：

- `{n}` 未替换会让用户认为 Agent 文案没有完成。
- 当前环境只有 7 天 synthetic 数据，却说“跑了 90 天验证”，直接破坏可信度。
- “没有一个能直接赚钱”是强交易结论，但当前数据不足以支持这个说法。
- `#50` 和 `[观察]` 对 L2 用户不如“R-breaker 已加入策略池，当前只在 sample 数据上试跑过”有价值。

根因定位：

- `kronos/common/i18n.py` 中 `conv.strategies_title` 需要 `{n}`，但 `kronos/agent/console.py` 调用时没有传入 `n`。
- `conv.strategies_prompt` 是固定的“90 天 crypto 验证”文案，没有读取当前数据天数、数据是否 synthetic、实际候选数量。
- Agent 菜单把历史迁移候选池文案沿用到 v0.4.0 的 R-breaker 用户配置路径，产品上下文没有同步。

### 9. Agent 跑一轮分析

继续选择策略分析并回车跳过研究目标。

关键输出：

```text
开始分析…
    加载数据…
    计算信号…
    验证结果…

query.loaded rows=10080 symbol=BTCUSDT timeframe=1m
query.loaded rows=10080 symbol=BTCUSDT timeframe=1m
分析完成！
  1 个策略已评估, 0 个通过验证
  完整报告: reports/research/experiments/20260506T115402Z-console/auto_run_report.md

当前的 12 个旧策略在 crypto 上表现都不够好——这很正常。好的策略需要反复迭代。下一步建议关注 liquidation 数据和市场状态过滤，而不是继续调参数。
```

产品问题：

- 明明只评估了 1 个策略，却说“当前的 12 个旧策略”。
- 数据仍是 7 天 synthetic，却给出“旧策略在 crypto 上表现不够好”的泛化判断。
- 分析过程显示的是 1m，刚才创建的 TOML 配置是 15m，用户会困惑“我到底验证了哪个 R-breaker”。
- “liquidation 数据”是高级方向，但当前版本 onboarding 没有说明 liquidation 数据如何接入。
- 推荐按钮里又出现“调整 R-breaker 参数再跑一次”，与“而不是继续调参数”互相冲突。

根因定位：

- `kronos/agent/console.py` 的 `_research_flow()` 固定传 `timeframe="1m"`，没有读取用户刚生成的 TOML 策略配置。
- `conv.research_next` 是固定文案，没有根据本轮 `evaluated`、候选数量、synthetic 状态、样本天数动态生成。
- Agent 的研究路径和策略配置路径仍是两条并行流程，没有形成同一个“用户策略资产”的连续体验。

### 10. 完整日报内部也有 90 天错配

读取 Agent 生成的完整日报：

```bash
docker compose -p kronospersonaeval run --rm --entrypoint sed kronos -n 1,180p /kronos/reports/research/experiments/20260506T115402Z-console/auto_run_report.md
```

报告正文同时出现：

```text
研究数据样本
- BTCUSDT / 1m K线：2026-04-29 11:50 -> 2026-05-06 11:49，10080 条，约 7.0 天

建议下一步
- 90 天复验已完成但只看到局部弱信号；保留弱信号候选为观察或状态过滤评估，暂不进入组合层。
```

影响：

- 报告正文前后自相矛盾。
- L3 会质疑报告生成逻辑；L2 会直接失去策略结论信任。

根因定位：

- `kronos/research/auto_runner.py` 的 `_next_step()` 只看 `history_status == "enough_history"`，但文案固定写“90 天复验已完成”。
- quickstart / Agent 配置中 `min_history_days` 可低到 1 或 7，导致“enough_history”和“90 天”不等价。

## 分画像体验结论

### L0 完全小白

能完成安装，但不能独立判断结果。

主要障碍：

- 终端里有太多日志和英文缩写。
- 不知道 `bars`、`synthetic`、`candidate`、`workbench` 是什么。
- 容器路径 `/root/.kronos/...` 和宿主机路径 `~/.kronos/...` 容易混淆。

产品要求：

- quickstart 最后一屏要只保留 3 个动作：读报告、同步真实数据、进入 Agent。
- 报错要直接说明“你用了宿主机路径，Docker 里请用 `/root/.kronos/...`”。

### L1 入门交易者

能理解 BTCUSDT、R-breaker、0 通过验证，但不知道这个结果是否有交易意义。

主要障碍：

- `report latest` 没有说明 sample 数据不代表策略有效性。
- “没有候选进入组合或实盘”不是交易语言。
- 没有看到收益、回撤、交易次数、手续费假设，也没有看到“样本太短”的明确解释。

产品要求：

- 报告第一屏用“当前不能判断策略优劣，因为只用了 7 天模拟数据”之类的结论。
- 指标可以保留，但必须先给交易判断。

### L2 有经验主观/半自动交易者

这是 Kronos 的核心用户之一，但当前体验会让他在策略路径上迷路。

主要障碍：

- quickstart 跑 R-breaker，策略配置也叫 R-breaker，但一个是 1m、一个是 15m。
- Agent 说“90 天验证”和“12 个旧策略”，与实际 7 天 1 个策略矛盾。
- 推荐“别调参”和按钮“调整 R-breaker 参数”互相打架。

产品要求：

- 建立唯一主路径：生成配置 -> smoke-test -> register -> Agent 分析 -> report latest。
- 每一步都说明“这一步验证的是逻辑能跑，还是历史表现值得继续”。

### L3 Python 交易研究者

基础设施可信，但产品表述会降低研究结论可信度。

正向体验：

- 数据路径、report artifact、run id、粒度、样本条数都能定位。
- smoke-test 给出 rows、valid_signals、strong_signals，有助于快速判断信号是否跑通。

主要障碍：

- 报告正文数据样本是 7 天，但建议下一步写 90 天。
- Agent 研究硬编码 1m，没有和 TOML 策略配置对齐。
- 结构化日志默认打到用户终端，影响 CLI 可读性。

产品要求：

- 把 run summary 作为 report latest 的结构化来源。
- 报告里所有“90 天”文案必须来自实际样本长度或配置阈值，不能固定写死。

### L4 小型量化团队负责人

当前 Docker 流程还不能支撑团队决策。

主要障碍：

- Docker Compose 默认不启动 Web 工作台，`docker-compose.yml` 里 Web 被注释，需要宿主机 Node 环境。
- Agent 和报告能说没有晋升，但不能清晰分组失败原因。
- “观察名单”“候选进入组合”是流程状态，但缺少面向决策者的摘要。

产品要求：

- Docker 体验要么明确“CLI-only quickstart”，要么提供 Web 工作台启动路径。
- report latest 应输出候选状态、失败原因、下一步 owner。

### L6 Docker 首次用户

安装路径比 v0.3.1 稳定，但命令复制体验仍有坑。

主要障碍：

- entrypoint 底部提供的命令能用，但 `strategy init-r-breaker` 之后给出的 `next` 不是 Docker 命令。
- README 的 `~/.kronos/...` 本地路径和 Docker 内 `/root/.kronos/...` 没有并排说明。
- `docker compose run` 自带 `Container ... Creating/Created` 噪音，叠加 Kronos 调试日志后很难读。

产品要求：

- Docker 模式下每个 CLI 下一步都打印 Docker 可复制命令。
- 文档中本地命令和 Docker 命令分栏，不混用 `~` 路径。

## 优先级问题清单

### P0-1：Agent 输出事实错误，直接破坏信任

现象：

- `这里有 {n} 个策略`
- 7 天 synthetic 数据下说“跑了 90 天验证”
- 1 个策略评估后说“当前的 12 个旧策略”

用户影响：

- L1/L2 会认为产品文案是假的。
- L3/L5 会怀疑研究结论没有绑定真实 run context。

根因：

- i18n 模板未传变量。
- Agent 文案大量固定写死，没有读取当前数据窗口、候选数量和数据类型。

建议修复方向：

- Agent 所有结论文案都从 `result.summary()`、数据覆盖和候选列表动态生成。
- 禁止在 sample/synthetic 数据上输出“赚钱/不赚钱”的泛化结论。

### P0-2：`report latest` 仍不是交易用户可读的最新结论

现象：

- 只输出一句“工作台和观察名单补证据”。
- 不显示样本、策略、失败原因和下一步。

用户影响：

- 用户仍然需要打开深层报告才能理解结果。
- v0.3.3 解决了“找不到报告”，但没有解决“读懂报告”。

根因：

- 当前摘要抽取 Markdown 段落，不基于结构化 run summary 生成产品第一屏。

建议修复方向：

- `report latest` 默认输出一个固定结构：
  - 本次是不是 sample/synthetic
  - 策略名和交易品种
  - 数据范围和粒度
  - 是否通过验证
  - 为什么不能继续
  - 下一步推荐命令

### P0-3：报告正文出现 7 天数据和 90 天结论冲突

现象：

- 报告样本写约 7 天。
- 建议下一步写“90 天复验已完成”。

用户影响：

- 这是研究可信度问题，不只是文案问题。
- 用户会怀疑门禁是否真的按配置运行。

根因：

- `history_status == enough_history` 被翻译成固定“90 天复验已完成”，但 quickstart / Agent 的最低样本要求不是 90 天。

建议修复方向：

- 文案改成实际天数：`当前样本约 7 天，只能做流程试跑`。
- 只有真实覆盖超过 90 天时才允许出现“90 天复验”。

### P1-1：Docker 策略路径容易误导

现象：

- `/root/.kronos/...` 能通过。
- `~/.kronos/...` 被宿主机展开后失败。

用户影响：

- Docker 首次用户会觉得照文档执行也报错。

根因：

- 本地文档和 Docker 文档没有分栏。
- CLI 没有识别宿主机路径并给 Docker 专用纠错。

建议修复方向：

- Docker 模式下 `init-r-breaker` 直接输出：
  `docker compose run --rm kronos uv run kronos strategy smoke-test /root/.kronos/strategies/r_breaker.toml`
- README 命令速查拆成本地版和 Docker 版。

### P1-2：1m quickstart / 15m TOML 配置没有解释关系

现象：

- quickstart 和 Agent 研究输出 `timeframe=1m`。
- `init-r-breaker` 默认 `timeframe: 15m`。

用户影响：

- L2 会误以为自己刚生成的配置已经被 Agent 验证。
- L3 会质疑实验可复现性。

根因：

- 内置 demo 策略研究路径和用户 TOML 策略路径分离。

建议修复方向：

- quickstart 后如果生成 TOML，应提示“这是新的可编辑配置，尚未进入刚才的 1m quickstart 报告”。
- Agent 分析优先读取已注册的 user_config，并展示其 timeframe。

### P1-3：工程日志泄露到产品首屏

现象：

- `config.loaded`
- `query.loaded`
- `partition.written`
- ANSI 彩色 structlog 输出

用户影响：

- L0/L1 可能误判为报错。
- L2 读产品结论被打断。

根因：

- CLI 用户输出和结构化日志共用 stdout。
- dev 配置默认日志级别对 Docker quickstart 不够克制。

建议修复方向：

- 产品 CLI 默认 INFO 以下日志走 stderr 或隐藏。
- quickstart / agent start 默认关闭 debug logs，提供 `--debug` 打开。

### P2-1：Web 工作台在 Docker 体验中仍是断开的

现象：

- Agent 建议“打开 Web 工作台看完整报告”。
- `docker-compose.yml` 中 Web 服务被注释，README 让用户宿主机 `cd web && npm run dev`。

用户影响：

- L4 团队负责人无法用 Docker 一键体验 Web 控制台。
- L6 Docker 用户可能没有 Node 环境。

根因：

- 当前 Docker 定位是 CLI quickstart，不是完整工作台。
- 文案没有明确区分 CLI-only Docker 和 Web 本地开发。

建议修复方向：

- Docker quickstart 明确写“本镜像只跑 CLI 研究流程”。
- 如果要让 L4 体验 Web，需要提供 profile 或单独 compose 文件。

## 本轮建议的下一步

按产品优先级，不建议先做实时模拟盘或更多策略类型。应先把首次体验的信任链修好：

1. 修 Agent 文案事实错误：`{n}`、90 天、12 旧策略。
2. 重做 `report latest` 第一屏摘要，让它成为交易用户真正能读懂的最新结论。
3. 修 auto report 的样本天数和 90 天文案冲突。
4. 给 Docker 模式输出容器安全命令，避免 `~` 路径踩坑。
5. 统一 R-breaker demo 研究和 TOML 配置的 timeframe 解释。

## 验收标准

下一轮体验如果要判定合格，应满足：

- 新用户运行 `docker compose up` 后，首屏没有 debug 日志。
- `report latest` 前 10 行内能回答：用了什么数据、什么策略、是否通过、为什么、下一步是什么。
- Agent 不再输出未替换模板、不真实样本天数、不真实策略数量。
- Docker 用户复制 `strategy init-r-breaker` 后的下一步命令可以直接成功。
- sample 数据上的所有结论都明确标注为“流程试跑，不是交易有效性判断”。

