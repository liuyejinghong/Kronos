# Kronos Docker 首次使用体验评测（2026-05-05）

一句话结论：当前 GitHub 版本的 Kronos 还不能通过 Docker 完成交易者首次使用闭环；原始 `docker compose up` 直接因缺少 `Dockerfile` 失败，临时修复后 `quickstart` 也停在缺少运行依赖 `scipy`，最终没有生成 R-breaker 回测报告，因此没有真正帮交易者判断一个策略能不能继续。

## 部署过程记录

评测身份：有 3 年加密货币交易经验的普通交易者，同时从产品体验角度评估首次使用。

评测方式：按用户给定路径从 GitHub 全新部署，不使用本地已有 checkout 作为成功依据。

评测环境：

- 日期：2026-05-05
- 全新目录：`/tmp/kronos-docker-ux-20260505/Kronos`
- GitHub commit：`1574ecba31d73d09cf822c8ac480eaff377cc780`
- Docker：`Docker version 29.3.1`
- Docker Compose：`Docker Compose version v5.1.1`

### 原始命令执行

按要求执行：

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
docker compose up
```

结果：失败。

失败原因：

```text
failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory
```

全新 clone 里有 `docker-compose.yml`，内容使用 `build: .`，但仓库根目录没有 `Dockerfile`。所以 README 虽然写的是 Python + uv 路径，用户指定的 Docker 部署路径在当前 GitHub 版本不可用。

### 修复过程记录

为了继续评估 quickstart，我在临时 clone 中补了一个最小 Dockerfile，只用于本次复现，不作为正式代码变更：

```dockerfile
FROM python:3.12-slim
WORKDIR /kronos
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv
COPY . .
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "--no-dev", "kronos", "quickstart"]
```

修复中遇到两类问题：

1. 如果先只复制 `pyproject.toml` / `uv.lock` 再 `uv sync`，hatchling 构建项目时看不到 `kronos/` 包目录，会报 `Unable to determine which files to ship inside the wheel`。修复方式是先复制完整项目再安装依赖。
2. 如果容器启动命令使用普通 `uv run kronos quickstart`，会额外下载 dev 依赖，包括 pytest、mypy、ruff、alphalens 等。这不是一个交易者期望的生产 Docker 启动体验，所以改为 `uv run --no-dev kronos quickstart`。

修复后 Docker 镜像可以构建并启动，但首次构建耗时很长，主要卡在下载 `pyarrow`、`duckdb`、`numpy`、`pandas` 等依赖。运行依赖准备阶段约 3 分钟以上；如果算上原始失败和修复尝试，整个首次 Docker 体验远远超过“开箱即用”。

## 使用体验记录（按时间线）

### 1. clone 后阅读入口

README 的主路径是：

```bash
uv sync --dev
uv run kronos quickstart
```

从交易者角度看，README 没有告诉我 Docker 怎么跑，也没有解释 `docker compose up` 会启动什么服务、数据和报告放在哪里、如何查看结果。对非工程用户来说，Docker 入口缺少说明。

### 2. 原始 Docker 启动

执行 `docker compose up` 后，系统进入 build，然后直接报缺少 `Dockerfile`。

交易者感受：这一步无法自助修复。错误信息是工程错误，不是产品提示。普通交易者大概率会停在这里。

### 3. 临时修复 Dockerfile 后启动

镜像构建成功，Compose 创建了 3 个卷：

- `kronos_kronos_data`
- `kronos_kronos_reports`
- `kronos_kronos_home`

容器启动后进入 `quickstart`。

### 4. quickstart 前半段成功

容器输出：

```text
⚡ Kronos 快速开始
… 正在检查本地数据…
未找到本地数据，正在生成 7 天 BTCUSDT sample 数据（标记为 synthetic）…
Sample 数据已生成：data/curated/BTCUSDT
[10080 bars, 7d, venue=synthetic]
… 正在注册内置策略…
✅ R-breaker 日内突破 (r_breaker) — mean_reversion
BTCUSDT: 10080 bars, 2026-04-28 11:04 → 2026-05-05 11:03
… 正在运行研究循环（最小窗口，快速验证）…
```

这部分我能理解：系统生成了 7 天 BTCUSDT 1m 合成 K 线，然后注册了一个 R-breaker 示例策略，准备做研究循环。

最困惑的点：

- 它说 R-breaker 是“日内突破”，但注册输出里又标成 `mean_reversion`，交易逻辑定位冲突。
- 数据是 synthetic，不是真实 BTC 行情；对交易判断只能算流程样例，不能算策略证据。
- “研究循环”具体会做什么没有提前说明：是回测、因子验证、参数扫描，还是候选晋升？

### 5. quickstart 失败

研究循环阶段报错：

```text
ModuleNotFoundError: No module named 'scipy'
```

直接原因：`kronos/factor/validation/metrics.py` 运行时导入 `scipy.stats`，但 `pyproject.toml` 的正式运行依赖没有 `scipy`。`scipy` 只通过 dev 依赖里的 `alphalens-reloaded` 间接出现在 lockfile 中。也就是说，干净 Docker 运行环境下 quickstart 的研究部分不可用。

容器最终退出码：`1`。

### 6. 最终留下的产物

数据卷里有 sample 数据：

```text
/data/curated/BTCUSDT/klines_1m/2026/04.parquet: 3656 rows
/data/curated/BTCUSDT/klines_1m/2026/05.parquet: 6424 rows
```

报告卷没有生成任何报告文件。

最终我得到的结果：只有 7 天 BTCUSDT synthetic K 线，没有回测结果，没有收益、胜率、回撤、交易明细，也没有 R-breaker 报告。

这个结果对交易者价值很低。它只能证明“系统能生成一份假数据”，不能证明“策略想法能不能用”。

## “有没有用”的核心判断

作为交易者，我日常关心的问题是：

- 我有个策略想法，不知道行不行。
- 回测结果看着不错，实盘敢不敢上。
- 参数怎么调。
- 这个策略在什么市场环境下会失效。

这次 Docker quickstart 没有解决其中任何一个。

原因不是 R-breaker 本身好坏，而是首次路径没有跑到判断环节。系统没有给我：

- 策略收益率、最大回撤、胜率、盈亏比。
- 交易次数、手续费滑点假设、持仓周期。
- 和买入持有或简单基准的对比。
- 参数敏感性。
- 分市场状态表现，例如趋势、震荡、高波动、低波动。
- 是否适合进入模拟盘的明确结论。

所以我的核心判断是：当前 Docker 首次体验更像一个未完成的工程 demo，不像一个能帮交易者做判断的工具。它展示了数据和研究框架的影子，但没有完成“从想法到可信判断”的产品闭环。

## 交易执行链路完整性检查

Kronos 宣称是策略研究到执行的系统。本次从 Docker quickstart 看到的链路如下：

| 环节 | 本次是否完成 | 证据 | 交易者判断 |
|------|--------------|------|------------|
| 策略定义 | 部分完成 | 注册了 `r_breaker` | 有策略名和因子实现，但不是完整交易策略说明 |
| 历史数据准备 | 部分完成 | 生成 7 天 synthetic BTCUSDT 1m 数据 | 能跑流程，但不能作为真实交易依据 |
| 历史回测 | 未完成 | 研究循环前导入 `scipy` 失败 | 没有收益、胜率、回撤 |
| 结果分析 | 未完成 | 没有报告文件 | 没有任何交易结论 |
| 参数调整 | 未完成 | 没有参数扫描或建议 | 不知道怎么调 |
| 市场环境失效分析 | 未完成 | 没有分环境表现 | 不知道什么时候会失效 |
| 模拟盘 | 未完成 | quickstart 没有进入 paper trading | 无法继续观察 |
| 实盘 | 未完成 | 没有交易所、订单、风控、审批链路 | 不能用于实盘 |

卡点在“历史回测 / 研究循环”之前：数据生成和策略注册完成后，正式研究逻辑因缺少运行依赖中断。

作为交易者，拿到回测结果后我自然想做的是：

1. 看这个策略是不是明显跑输买入持有。
2. 看最大回撤和连续亏损我能不能承受。
3. 看参数稍微变一下会不会完全失效。
4. 看最近几天逐笔交易是否符合直觉。
5. 如果结果还行，放到模拟盘观察一周。

Kronos 这次没有帮我走到这些步骤。

## 产品易用性评分表

| 维度 | 分数（1-5） | 原因 |
|------|-------------|------|
| 安装和启动的顺畅度 | 1 | GitHub 全新 clone 的 `docker compose up` 直接缺 `Dockerfile`；临时修复后首次构建也很慢 |
| 首次使用的引导清晰度 | 2 | quickstart 前半段有中文提示，但 Docker 入口没有说明，研究循环失败后没有面向用户的恢复建议 |
| 输出结果的可理解性 | 1 | 没有生成回测报告；只看到 sample 数据和 Python traceback |
| 完成“跑一个策略”目标的成功率 | 1 | R-breaker 注册成功，但没有跑出回测结果 |
| 系统的实际有用程度 | 1 | 没有回答策略能不能用、参数怎么调、什么时候失效 |
| 交易执行链路完整度 | 1 | 没到回测报告，更没有模拟盘或实盘 |
| 是否会推荐给其他交易者 | 1 | 目前不会推荐给非工程交易者；最多适合开发者继续调试 |

综合评分：`1.1 / 5`。

## 产出内容质量分析

### R-breaker 策略描述是否准确？

只从 quickstart 输出和代码看，描述“R-breaker 日内突破”大方向是可理解的。R-breaker 确实是经典日内突破/反转类策略，使用前一日 OHLC 计算关键价位。

但当前产品表达存在两个问题：

- 注册输出把它标为 `mean_reversion`，而用户看到的中文是“日内突破”。如果我是交易者，会不确定它到底是突破追涨，还是均值回归反转。
- 实现更像一个归一化信号因子，不是完整策略。它没有在 quickstart 输出中解释如何开仓、平仓、止损、仓位、手续费和滑点。

所以描述只能算“方向部分准确”，但还不足以让交易者理解这套策略怎么交易。

### 回测结果是否合理？

无法评估。因为 quickstart 没有生成收益、胜率、回撤、交易次数等任何回测结果。

本次唯一数据结果是 10080 根 1m synthetic K 线。它可以用于演示流程，但不能用于判断策略表现。

### 报告里的结论和建议是否有实际参考价值？

没有报告文件，无法评价报告结论。

从交易者角度，这比“报告结论不好”更严重：系统承诺“一键完成：生成数据 → 注册 R-breaker 策略 → 跑回测 → 出结果”，但实际停在“跑回测”之前。

### 有没有明显错误或误导？

有 4 个明显问题：

1. Docker compose 文件存在，但缺少 Dockerfile，导致 Docker 入口不可用。
2. quickstart 研究循环依赖 `scipy`，但正式运行依赖没有声明 `scipy`。
3. README 承诺 quickstart 会“跑回测 → 出结果”，但本次没有出结果。
4. R-breaker 的产品标签有冲突：中文叫日内突破，注册 family 却是 mean_reversion。

## 最终建议：最需要改进的 3 件事

### 1. 先修 Docker 首次启动闭环

必须让下面命令在全新机器上直接成功：

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
docker compose up
```

最低要求：

- 提交正式 `Dockerfile`。
- Dockerfile 构建时安装完整运行依赖。
- 容器启动命令不要拉 dev 依赖。
- quickstart 失败时不要直接抛 traceback，要输出用户能理解的失败原因和下一步。

### 2. quickstart 必须真的产出一份交易者能读懂的策略报告

报告至少要包括：

- 使用的数据是真实还是 synthetic。
- 策略逻辑：什么时候买、什么时候卖、什么时候空仓。
- 收益率、最大回撤、胜率、交易次数、手续费/滑点假设。
- 和基准的对比。
- 一句话结论：不建议继续、建议观察、还是可以进入模拟盘。

没有这些，quickstart 不应该宣传为“跑回测 → 出结果”。

### 3. 把下一步从“工程命令”改成“交易决策路径”

交易者跑完一个策略后，下一步不是看目录结构，而是做判断。Kronos 应该在报告末尾给出清晰路径：

- 结果不行：为什么不行，应该放弃还是改造。
- 结果一般：优先调哪个参数，为什么。
- 结果还行：如何进入模拟盘，观察哪些风险指标。
- 结果很好：实盘前还缺哪些验证和审批。

当前系统有研究平台的雏形，但 Docker 首次体验还没有让交易者感到“它能帮我做交易判断”。下一步应优先修复首次闭环，而不是继续扩展更多模块。
