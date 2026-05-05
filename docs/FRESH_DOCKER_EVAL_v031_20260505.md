# Kronos v0.3.1 全新 Docker 首次体验评测（2026-05-05）

一句话结论：v0.3.1 的 Docker quickstart 已经能从零跑通并生成 R-breaker 研究报告，但它目前更像“研究框架演示”而不是交易者能直接拿来判断策略、调参数、进入模拟盘的产品；最明显的断裂在交互式 Agent，quickstart 刚评估完 R-breaker，Agent 却说“你还没有定义任何策略”。

## 评测背景

- 体验身份：有 3 年加密货币交易经验的交易者，同时做产品体验评测。
- 操作方式：从 GitHub 全新 clone，不使用本地开发 checkout。
- 全新目录：`/tmp/kronos-fresh-docker-v031-20260505/Kronos`
- GitHub commit：`4a5ba7cf1e6f874588dbbbd267958977acdeeaee`
- `VERSION`：`0.3.1`
- `pyproject.toml`：`0.3.0`
- README badge：`0.1.0`
- Docker：`Docker version 29.3.1`
- Docker Compose：`Docker Compose version v5.1.1`

版本号不一致不会阻塞使用，但会降低新用户对交付状态的信任：到底我体验的是 0.1.0、0.3.0，还是 0.3.1？

## 安装和首次运行

### 执行命令

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
docker compose up
```

### 构建和启动过程

这次 Docker 路径可以跑通，原先缺 Dockerfile / 缺 scipy 的问题已经修复。

总耗时：

```text
real 185.29
```

也就是约 3 分 5 秒。

前 2 分多主要是在下载 Python 科学计算依赖：

- `pyarrow`
- `scipy`
- `duckdb`
- `numpy`
- `pandas`
- `matplotlib`
- `pillow`

作为交易者，我能理解“第一次安装比较慢”，但构建日志里大量包名、sha、layer、wheel、manifest、attestation 对我没有业务意义。我只知道系统好像还活着，因为下载进度一直在变化。如果网络慢一点，这里很容易让人以为卡住。

### quickstart 终端输出逐行体验

#### 能理解的内容

```text
Kronos — Docker Quickstart
```

能理解：这是 Docker 里的快速开始。

```text
Kronos 快速开始
正在检查本地数据
未找到本地数据，正在生成 7 天 BTCUSDT sample 数据（标记为 synthetic）
```

能理解：系统没有发现本地行情，所以生成一份 7 天 BTCUSDT 样例数据。`synthetic` 我理解为模拟/假数据。

```text
Sample 数据已生成：data/curated/BTCUSDT
[10080 bars, 7d, venue=synthetic]
```

基本能理解：10080 根 1 分钟 K 线，刚好 7 天。但 `data/curated` 对非工程用户不直观。

```text
正在注册内置策略
R-breaker 日内突破 (r_breaker) — trend_momentum
```

部分能理解：R-breaker 是内置日内突破策略。`trend_momentum` 对交易者也算能猜到是趋势动量，比之前 `mean_reversion` 清晰。

```text
BTCUSDT: 10080 bars, 2026-04-28 15:15 → 2026-05-05 15:14
```

能理解：这是数据范围。

```text
正在运行最小研究循环（R-breaker × BTCUSDT）
```

能理解大意：要用 R-breaker 跑 BTCUSDT。但“研究循环”仍偏内部术语，不如“正在验证 R-breaker 在 BTCUSDT 上是否值得继续”。

```text
策略评估结果
市场基准: 使用模拟数据，无法提供可信基准对比。同步真实行情后可查看。
1 个策略已评估
0 通过验证
```

这部分是本次最有价值的输出。至少我知道：系统没有乱给假基准，也明确告诉我 sample 数据不能形成可信市场基准。

```text
当前没有策略通过验证。这在首次运行中很常见：
策略需要足够长的真实数据才能形成可信结论。sample 数据只是演示流程，建议用 kronos data sync 拉取真实行情后重跑。
```

这句很好，交易者能看懂。它把“0 通过验证”解释成“样例流程，不是策略死亡证明”。

```text
研究报告: reports/research/experiments/20260505T151511Z-quickstart/auto_run_report.md
```

有用，但路径对 Docker 新用户不够直接。后面 entrypoint 追加了 Docker 查看命令，补上了这一点。

#### 看不懂或容易困惑的内容

```text
config.loaded path=configs/dev.toml
partition.written dataset=klines_1m month=4 rows=3405 symbol=BTCUSDT year=2026
seed.klines_generated bars=10080 partitions=2 symbol=BTCUSDT venue=synthetic
query.loaded rows=10080 symbol=BTCUSDT timeframe=1m
```

这些对开发者有用，但对交易者属于噪音。第一次体验里我只需要知道“样例数据已生成，7 天，BTCUSDT，模拟数据”。现在日志和产品输出混在一起，降低了可读性。

```text
0 通过验证
```

这句话本身能懂，但还缺关键交易解释：验证标准是什么？是收益不行、预测力不行、回撤太大，还是交易次数不够？

## 按 entrypoint 继续操作

quickstart 提示：

```bash
docker compose run --rm kronos ls /kronos/reports/research/experiments/
docker compose run --rm kronos uv run kronos agent start
```

### 查看报告目录

执行：

```bash
docker compose run --rm kronos ls /kronos/reports/research/experiments/
```

成功，输出：

```text
20260505T151511Z-quickstart
20260505T151511Z-quickstart-evidence-r_breaker
20260505T151511Z-quickstart-workbench
20260505T151511Z-quickstart-workbench-r_breaker
ledger.duckdb
ledger.jsonl
```

从交易者视角：

- 我能猜到 `quickstart` 是主报告。
- `evidence_r_breaker` 可能是 R-breaker 证据。
- `workbench`、`ledger.duckdb`、`ledger.jsonl` 都偏工程内部概念。

如果产品目标是交易者使用，下一步不应该只让我 `ls` 目录，而应该直接告诉我：

```bash
docker compose run --rm kronos cat /kronos/reports/research/experiments/.../auto_run_report.md
```

或者提供一个 `kronos report latest` 命令。

### 读取报告后的感受

主报告一句话结论：

```text
本次自动研究已完成工作台和观察名单补证据，当前仍没有候选进入组合或实盘。
```

这句话有价值，我能理解：R-breaker 不能进入组合或实盘。

工作台报告一句话结论：

```text
本批没有候选达到下一阶段标准，暂不建议进入组合或实盘。
```

也有价值，比单纯说“0 通过验证”更像交易判断。

R-breaker 专项报告一句话结论：

```text
补证据后仍未看到稳定支持，建议转入退休评审。
```

这已经接近我想要的结论：不要继续拿这个 R-breaker demo 当可交易策略。

但报告里也有我看不懂或不确定怎么用的指标：

- `mean_rank_ic`
- `top_minus_bottom`
- `median_turnover`
- `walkforward_validation_mean`
- `walkforward_positive_test_window_ratio`
- `leak_audit_passed`

作为交易者，我知道这些可能和因子预测力、换手、走步验证、防偷看未来有关，但普通交易者不会知道阈值怎么解读。报告应该把关键指标翻译成交易语言，例如：

- 预测力为负，说明信号方向不稳定。
- 高波动状态下只有弱信号，不能单独交易。
- 没有稳定优势，所以不建议调参数硬救。

## 策略评估结果

### “1 个策略已评估，0 通过验证”有用吗？

有一点用，但不够。

有用的地方：

- 它明确告诉我本次不是系统崩了，而是真的评估了 1 个策略。
- 它没有把 demo 策略包装成成功案例。
- 它明确阻止我把 sample 数据当实盘依据。

不够的地方：

- 没有在终端直接告诉我“失败原因是基础预测力未达标”。
- 没有给收益率、回撤、胜率、交易次数。
- 没有解释“验证”到底验证什么。
- 没有告诉我“如果我想继续，是应该同步真实数据，还是换策略，还是调参数”。

所以这个结论目前更像风险提示，不像完整交易决策。

### benchmark 是否有参考价值？

本次没有给具体 benchmark 数字，而是输出：

```text
使用模拟数据，无法提供可信基准对比。同步真实行情后可查看。
```

这个处理是正确的。sample 数据是 synthetic，给出买入持有收益会误导交易者。没有 benchmark 数字反而比给一个假数字更可信。

但我希望下一步同步真实数据后，benchmark 至少包括：

- 同期 BTC 买入持有收益。
- R-breaker 策略收益。
- 最大回撤对比。
- 手续费和滑点假设。
- 是否跑赢风险调整后的基准。

### “下一步”是否清晰可执行？

终端给出的 Docker 下一步是清晰的：

```text
查看报告
交互式 Agent
同步真实数据
```

但它有两个问题：

1. “查看报告”只是 `ls` 目录，不是直接读报告。交易者执行完以后还是不知道该打开哪个文件。
2. “交互式 Agent”看起来是最自然下一步，但实际体验会断裂，见下一节。

## 交互式 Agent 体验

执行：

```bash
docker compose run --rm kronos uv run kronos agent start
```

启动成功，没有重新下载 dev 依赖，也没有报错。菜单如下：

```text
Kronos Agent

你好！我是 Kronos，一个加密货币量化研究助手。
我可以帮你分析策略的历史表现，回测交易想法，或者让 AI 帮你找到新的研究方向。

正在检查你的环境…
你已经有一些数据了（BTCUSDT 等），可以直接开始。
  [BTCUSDT: synthetic [模拟数据]]
AI 模型未配置

  [1] 帮我分析一下这些策略的表现
  [2] 先看看有什么策略
  [3] 怎么配置 AI 模型？
```

作为交易者，我知道该选什么：选 `[1] 帮我分析一下这些策略的表现`。因为我刚刚跑完 quickstart，想继续看 R-breaker 表现。

之后系统问：

```text
你有什么特别想研究的吗？（回车跳过）
[看看哪些策略值得继续关注]:
```

这个默认值是好的，我按回车接受。

然后出现关键断裂：

```text
开始分析…
加载数据…
计算信号…
验证结果…

你还没有定义任何策略。让我先告诉你怎么创建一个。
```

这一步让我想放弃。

原因：quickstart 明明刚刚注册并评估了 R-breaker，报告目录里也有 R-breaker 结果，但 Agent 却告诉我“你还没有定义任何策略”。作为交易者，我会怀疑：

- 刚才的 R-breaker 不算策略吗？
- quickstart 的结果和 Agent 不是同一个系统吗？
- 我是不是进错入口了？
- 我是不是必须会 Python 才能用？

继续选择示例后，Agent 给出 Python 代码：

```python
from kronos.factor.candidates import CandidateFactorSpec, register_candidate

register_candidate(CandidateFactorSpec(
    candidate_id="my_first_strategy",
    family="trend_momentum",
    title="我的第一个策略",
    source_strategies=("BTCUSDT",),
    migration_rank=1,
    implementation_name="my_strategy_impl",
))
```

这对开发者有用，但对普通交易者不友好。我不是来写 `CandidateFactorSpec` 的，我是想知道“R-breaker 能不能用、下一步怎么验证、能不能进模拟盘”。

### Agent 流程是否顺畅？

启动和菜单是顺畅的，文案也比普通 CLI 友好。但主路径断裂严重：菜单承诺“分析这些策略表现”，实际却转向“你还没有定义策略，去写 Python”。

### 我知道每步该选什么吗？

前两步知道：

1. 选分析策略表现。
2. 接受默认研究问题。

第三步不知道，因为系统突然否定已有策略，转向开发者教程。

### 哪个操作让我想放弃？

就是“你还没有定义任何策略”这句。它和 quickstart 的“1 个策略已评估”直接冲突。

## 整体评价：这次体验让我觉得 Kronos 有用吗？

有用的部分：

- Docker 现在能从零跑起来。
- quickstart 能生成数据、评估 R-breaker、写报告。
- 系统会明确说 sample 数据不是可信基准。
- 报告会阻止未通过策略进入组合或实盘，这一点很重要。
- R-breaker 专项报告能告诉我高波动有弱信号、整体不支持继续加码研究。

不足的部分：

- quickstart 的结论还没有转化成交易者最熟悉的回测语言：收益、回撤、胜率、交易次数、成本假设。
- Agent 没有承接 quickstart 结果，反而把我带到写 Python。
- 报告目录和产物命名仍偏工程内部。
- “同步真实数据后重跑”是正确方向，但没有告诉我会花多久、拉多长数据、是否需要代理、是否会请求 Binance。
- 还没有模拟盘路径。作为交易者，我自然下一步想“先 paper trading 观察”，但系统目前只说“不进入组合或实盘”，没有给模拟盘观察方案。

所以我的判断是：Kronos v0.3.1 已经不是玩具了，它开始像一个本地量化研究原型；但它还不是普通交易者可顺畅使用的产品。它能回答“这个 demo 策略暂时不要上”，但还不能完整解决“我有个策略想法，不知道行不行、参数怎么调、什么时候失效、下一步能不能模拟盘观察”。

## 是否推荐给其他交易者？

暂时不会推荐给普通交易者。

我会推荐给两类人：

- 会 Docker、Python、愿意看 Markdown/JSON 的量化开发者。
- 想搭建本地策略研究框架、愿意自己补策略实现的人。

不会推荐给：

- 只想快速验证一个交易想法的主观/半自动交易者。
- 不会写 Python 的交易者。
- 想直接从回测走到模拟盘/实盘的人。

## 最需要补的东西

### 1. Agent 必须承接 quickstart 的 R-breaker 结果

用户跑完 quickstart 后进入 Agent，第一屏应该是：

```text
我看到你刚跑完 R-breaker quickstart：
- 1 个策略已评估
- 0 个通过验证
- 主要原因：基础预测力未达标
- 但高波动切片有弱正向信号

你想：
[1] 看 R-breaker 详细报告
[2] 同步真实 BTC 数据后重跑
[3] 调整 R-breaker 参数
[4] 创建自己的策略
```

不要在此时说“你还没有定义任何策略”。

### 2. 增加 `kronos report latest`

现在让用户 `ls` 一个 Docker volume 目录，只能证明报告存在，不能帮助阅读。建议提供：

```bash
docker compose run --rm kronos uv run kronos report latest
```

直接打印最新报告摘要，并给出主报告、工作台报告、专项报告的阅读顺序。

### 3. 把指标翻译成交易语言

报告里可以保留 `mean_rank_ic` 等专业指标，但必须追加交易者解释：

- 这个信号方向是否稳定？
- 有没有跑赢买入持有？
- 最大回撤大不大？
- 交易次数够不够？
- 哪种市场环境下表现最好/最差？
- 为什么不能进模拟盘？

### 4. 给出同步真实数据后的明确路径

当前提示：

```bash
docker compose run --rm kronos uv run kronos data sync --symbols BTCUSDT
```

还缺：

- 默认同步多久？
- 数据来自哪里？
- 需要 API key 吗？
- 失败时怎么办？
- 同步后用什么命令重跑同一个 R-breaker？

### 5. 明确模拟盘边界

Kronos 说自己是“策略研究到执行”的系统，但本次体验没有模拟盘入口。至少应该说明：

- 当前 Docker quickstart 只到研究报告。
- 模拟盘尚未接入，或如何接入。
- 未通过验证的策略为什么不能进入 paper trading。

## 最终结论

v0.3.1 的进步很明显：Docker 能跑通，quickstart 有报告，benchmark 不再误导，下一步提示也切到了 Docker 场景。但从交易者体验看，Kronos 仍卡在“研究框架能产出证据”到“用户能顺畅做交易判断”的中间地带。真正的 P0 不再是 Docker 能不能启动，而是 Agent 和报告要围绕同一个用户问题闭环：这个策略能不能继续，为什么，下一步怎么验证。
