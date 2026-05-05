# 交易者首次试用 Kronos 真实记录

> 试用日期：2026-05-05
> 试用角色：有 3 年加密货币交易经验的 BTC/ETH 现货和合约交易者，会 Python 基础（pandas、matplotlib），没用过量化框架
> 试用方式：从 `git clone https://github.com/liuyejinghong/Kronos.git` 开始，全新目录 `/private/tmp/kronos-trader-trial`，按 README 操作，不跳过错误
> 本机部署要求：尝试使用本地 Docker 做全新部署，但仓库和 README 未提供 Dockerfile 或 compose 文件

## 一句话结论

Kronos 当前对开发者和内部研发验收是可理解的，但对一个普通加密货币交易者来说，还不能形成“clone 后马上跑一个 BTC 策略看看”的闭环。

最直接的卡点不是安装失败，而是：有了样例行情之后，系统没有内置可运行的示例策略；`agent start` 和 `kronos run today` 最终都停在“没有候选策略/因子”，用户不知道下一步该在哪个文件写什么、写完怎么跑。

## 真实操作结果

### 全新 clone

执行：

```bash
git clone https://github.com/liuyejinghong/Kronos.git /private/tmp/kronos-trader-trial
```

第一次失败：

```text
fatal: unable to access 'https://github.com/liuyejinghong/Kronos.git/':
Failed to connect to 127.0.0.1 port 7897 after 0 ms: Couldn't connect to server
```

判断：这是本机代理环境问题，不是 Kronos 仓库问题。关闭沙箱限制后重新 clone 成功。

### 按 README 安装

README 快速开始写的是：

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos agent start
```

执行 `uv sync --dev` 第一次失败：

```text
error: Failed to initialize cache at `/Users/ethan/.cache/uv`
  Caused by: failed to open file `/Users/ethan/.cache/uv/sdists-v9/.git`:
  Operation not permitted (os error 1)
```

判断：这是当前 Codex 沙箱对默认 uv 缓存目录的权限问题，不是 Kronos 依赖本身问题。改用项目内缓存后成功：

```bash
UV_CACHE_DIR=/private/tmp/kronos-trader-trial/.uv-cache uv sync --dev
```

安装结果：

- uv 自动选择 Python 3.14.3，符合 README 的 Python 3.12+。
- 共安装 86 个包。
- 依赖准备耗时约 3 分 37 秒。
- 安装成功，没有 Python 包冲突。

交易者感受：安装能跑通，但等待时间偏长。README 只写 Python 3.12+，没有说明 uv 可能选择更高版本，也没有说明遇到 uv cache 权限问题时可以设置 `UV_CACHE_DIR`。

### 启动 `agent start`

执行：

```bash
UV_CACHE_DIR=/private/tmp/kronos-trader-trial/.uv-cache uv run kronos agent start
```

首次进入后看到：

```text
Kronos Agent

你好！我是 Kronos，一个加密货币量化研究助手。
我可以帮你分析策略的历史表现，回测交易想法，或者让 AI 帮你找到新的研究方向。

正在检查你的环境…

你还没有行情数据。让我帮你准备一下：

  [1] 生成 7 天 BTC 模拟数据，先体验一下
  [2] 连接交易所拉取真实数据
  [3] 先随便看看，等会儿再弄数据
```

这个引导是清楚的。作为交易者，我会选 `[1]`，因为我最想先看到一个最小可运行结果。

但在当前非 TTY 执行环境里，界面显示了输入提示 `>`，实际 stdin 已关闭，无法输入。重新用 TTY 方式启动后，界面变成：

```text
欢迎回来！当前环境: BTCUSDT | AI 模型未配置。

  [1] 继续上次的研究
  [2] 开始一个新方向
  [3] 看看目前的策略池
  [4] 随便看看
```

判断：第一次启动虽然没有成功输入，但系统已经生成了 BTCUSDT 样例数据。第二次启动直接进入“欢迎回来”。这对真实用户会有一点困惑：我还没完成任何选择，为什么状态已经变了？

### 尝试开始第一轮研究

选择 `[2] 开始一个新方向` 后，系统自动选择 BTCUSDT：

```text
好的，我来帮你做一轮策略分析。

只有 BTCUSDT 有数据，那我就分析这个。
  → BTCUSDT

你有什么特别想研究的吗？（回车跳过）
  [看看哪些策略值得继续关注]:
```

直接回车后：

```text
开始分析…
    加载数据…
    计算信号…
    验证结果…

你还没有定义任何策略。让我先告诉你怎么创建一个。
```

这就是首次试用的核心断点。

交易者感受：

- 我以为系统会帮我跑一个示例策略，结果告诉我还没有策略。
- 我有 BTCUSDT 数据，但没有任何东西可以跑。
- “看看哪些策略值得继续关注”这个默认文案让我期待会有候选策略，实际没有。

### 查看示例代码

选择“给我看示例代码”后，系统输出：

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

然后提示：

```text
把这段代码放到启动脚本里，每次 Kronos 启动时自动注册。
实现因子逻辑后，Kronos 就能帮你验证这个策略了。
```

交易者感受：

- “启动脚本”是哪一个文件？README 没说，界面也没给路径。
- `implementation_name="my_strategy_impl"` 对应的函数要写在哪里？
- 因子逻辑的入参、返回值、数据格式是什么？
- 写完以后应该运行 `agent start`、`quickstart`、`run today`，还是其他命令？
- 这段代码更像内部开发接口，不像交易者可直接复制运行的示例策略。

结果：我不能继续。

### 尝试 `kronos quickstart`

README 命令速查里有：

```bash
uv run kronos quickstart
```

执行后输出：

```text
⚡ Kronos 快速开始

… 正在检查本地数据…
  已找到本地数据，跳过生成。

  BTCUSDT: 10080 bars, 2026-04-28 10:18 → 2026-05-05 10:17

✅ 快速开始完成！

下一步：
  1. 启动 Web 工作台：cd web && npm run dev
  2. 打开浏览器：http://127.0.0.1:3000
  3. 配置 DeepSeek API Key 以启用 Agent 研究
  4. 同步真实数据：kronos data sync --symbols BTCUSDT,ETHUSDT
  5. 运行完整研究：kronos run today
```

判断：`quickstart` 比 README 主路径里的 `agent start` 更像新手入口，但当前它只是完成了样例数据准备，没有跑出最小研究结果。CLI help 写的是：

```text
quickstart  One-command bootstrap: generate sample data and run a minimal research cycle.
```

实际体验与描述不一致：没有生成最小研究循环结果。

### 尝试 Web 工作台

按 quickstart 提示执行：

```bash
cd web && npm run dev
```

原样失败：

```text
sh: next: command not found
```

原因：README 和 quickstart 提示没有写 `npm install`。

补充执行 `npm install` 后安装成功，耗时约 6 秒，但 npm 报告 2 个 moderate severity vulnerabilities。

再启动前端时，默认端口也遇到占用。最终用避让端口启动：

```bash
PORT=3017 NEXT_PUBLIC_KRONOS_API_BASE_URL=http://127.0.0.1:8017/api npm run dev
```

后端也需要单独启动，README 没写。手动启动：

```bash
UV_CACHE_DIR=/private/tmp/kronos-trader-trial/.uv-cache uv run python -c \
"import uvicorn; from kronos.web.app import create_app; uvicorn.run(create_app(), host='127.0.0.1', port=8017)"
```

Web 页面可以打开，标题是 `Kronos Agent Workbench`，API 健康检查正常：

```json
{"status":"ok","service":"kronos-web-api"}
```

浏览器控制台持续出现 Next.js HMR WebSocket 错误。关闭前端服务时看到原因：

```text
Blocked cross-origin request to Next.js dev resource /_next/webpack-hmr from "127.0.0.1".
Cross-origin access to Next.js dev resources is blocked by default for safety.
```

判断：这是因为前端提示打开 `127.0.0.1`，而 Next.js dev server 默认按 `localhost` 起服务。功能页面仍能打开，但控制台连续报错会影响开发者和试用者信任。

但默认批次不存在：

```json
{"detail":"No Agent summary found for run: 20260430-agent-mvp-delivery-v1"}
```

全新 clone 中没有 `reports/` 目录。页面首屏仍显示“批次 20260430-agent-mvp-delivery-v1”，并写着“本轮结论来源”，但实际上没有本轮结论。

### 尝试 `kronos run today`

按 quickstart 的第 5 步执行：

```bash
UV_CACHE_DIR=/private/tmp/kronos-trader-trial/.uv-cache uv run kronos run today --skip-sync-data --config configs/dev.toml
```

结果失败：

```text
No matching candidate factors.
```

这确认了核心问题：样例数据有了，但没有样例策略/候选因子，所以“跑一个策略看看”无法完成。

### 尝试本地 Docker 全新部署

本机 Docker 可用：

```text
Docker version 29.3.1
Docker Compose version v5.1.1
```

但全新 clone 仓库中没有发现 Docker 部署入口：

- 没有 Dockerfile。
- 没有 `docker-compose.yml` / `compose.yml`。
- README 没有 Docker 部署说明。
- docs 中也没有可执行的 Docker 快速部署路径。

结论：当前无法按“本地 Docker，全新部署”完成试用。不是 Docker 本机不可用，而是 Kronos 没提供 Docker 化部署资产和文档。

## 对 7 个问题的直接回答

### 1. 安装过程顺利吗？有报错吗？

不完全顺利。

项目依赖本身可以安装成功，但真实过程中遇到两个环境类问题：

- clone 第一次因为本机代理端口不可用失败。
- `uv sync --dev` 第一次因为 uv 默认缓存目录权限失败，改用项目内 `UV_CACHE_DIR` 后成功。

如果只看 Kronos 依赖质量，安装是可恢复的；如果按 README 对新手承诺，缺少常见失败处理提示。

### 2. 启动 `agent start` 后，你知道该做什么吗？

一开始知道：没有数据时给了 3 个选项，我会选“生成 7 天 BTC 模拟数据”。

但进入“开始新方向”后就不知道了。系统默认说“看看哪些策略值得继续关注”，但最后告诉我“你还没有定义任何策略”。这和我的预期冲突。

### 3. 整个过程有没有让你困惑的地方？

有，主要是 5 个：

- `agent start` 首次没有完成输入，但第二次已经变成“欢迎回来”，状态变化不透明。
- `quickstart` 说是一键最小研究循环，实际只准备了数据。
- 示例策略只注册 metadata，不告诉我因子逻辑怎么写、写在哪里、怎么运行。
- Web 默认批次在全新 clone 中不存在。
- README 没有说明 Web 需要后端、前端依赖安装、API 地址和端口冲突处理。

### 4. 最想做的事做到了吗？

没有。

我最想做的是“跑一个 BTC 策略看看结果”。实际只做到了：

- 生成 7 天 BTCUSDT 样例数据。
- 打开 Agent 交互。
- 打开 Web 工作台空壳。

没有做到：

- 跑出一个示例策略。
- 看到收益曲线、胜率、回撤、交易次数。
- 看到一个我能判断“值得继续研究吗”的结果。

### 5. 如果不能继续了，卡在哪里？

卡在“没有候选策略/因子”：

```text
你还没有定义任何策略。
```

以及：

```text
No matching candidate factors.
```

要继续就必须写代码注册策略和实现因子逻辑，但文档没有给出交易者可照抄的最小完整示例。

### 6. 作为交易者，你觉得这个系统有用吗？实际价值在哪？

有潜在价值，但当前价值还没有通过 onboarding 展示出来。

我能看出的潜在价值：

- 本地优先，适合不想把策略和数据上传到云端的人。
- 有数据、因子、研究、Agent、Web 工作台的完整方向。
- 如果后续能把策略验证、报告、候选池和 Agent 建议打通，会适合做策略研究台。

但当前首次体验没有让我看到“它比我自己写 pandas 回测强在哪里”。因为最关键的第一件事：跑出一个策略结果，没有完成。

### 7. 还会再用吗？为什么？

如果我是普通交易者，我大概率暂时不会继续。

原因：

- clone 后 20 分钟内没有看到任何可判断的策略结果。
- 需要理解候选因子、注册接口、启动脚本、Agent run、Web 后端这些工程概念。
- 缺少一个完整、可复制、可运行的 BTC 示例策略。

如果我是愿意参与开发的量化工程用户，我会继续，因为系统的方向和模块边界有价值。但它还不像给交易者直接用的开源产品。

## 需要落实的产品修复建议

### P0：`quickstart` 必须真的跑完一个最小策略

目标：全新用户执行下面三步后，必须看到一份策略结果：

```bash
git clone https://github.com/liuyejinghong/Kronos.git
cd Kronos
uv sync --dev
uv run kronos quickstart
```

最低可接受结果：

- 自动生成或下载 BTCUSDT 样例数据。
- 自动注册一个内置示例策略，例如 BTC 均线趋势或突破策略。
- 输出收益、最大回撤、交易次数、胜率、样例报告路径。
- 告诉用户“这是模拟数据 / 示例策略，不能用于实盘”。

### P0：README 主路径应改为 `quickstart`，不是 `agent start`

当前 README 把 `agent start` 放在快速开始主路径，但真实体验中 `agent start` 很快会卡在“没有策略”。

建议主路径：

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos quickstart
```

然后再提示：

- 想对话式继续研究：`uv run kronos agent start`
- 想打开 Web：先启动后端和前端
- 想接真实数据：`uv run kronos data sync --symbols BTCUSDT,ETHUSDT`

### P0：提供一个完整策略文件，而不是只给注册片段

需要一个交易者可以复制运行的文件，例如 `examples/btc_ma_demo.py`。

它应该包含策略名字、数据频率、入场逻辑、出场逻辑、手续费假设、如何注册到 Kronos、运行命令和预期报告。不要只展示 `CandidateFactorSpec`。这对没用过量化框架的人不够。

### P1：Web 全新打开时不要默认指向不存在批次

全新 clone 没有 `reports/` 时，Web 应该进入“首次使用”状态，而不是展示 `20260430-agent-mvp-delivery-v1`。

建议首屏：

- “你还没有研究结果。”
- “先运行 `uv run kronos quickstart` 生成第一个示例报告。”
- “如果你已经有报告，选择报告目录。”
- “如果要启用 Agent，请配置 DeepSeek API Key。”

### P1：补齐 Web 本地启动说明

README 或 quickstart 输出需要明确后端、前端、`npm install`、`NEXT_PUBLIC_KRONOS_API_BASE_URL` 和端口冲突处理。还需要统一推荐访问域名，避免 Next.js dev server 因 `localhost` / `127.0.0.1` 不一致持续报 HMR WebSocket 错误。

### P1：补 Docker 部署资产

用户要求本地 Docker 全新部署时，当前无路可走。

需要至少提供根目录 Dockerfile 或后端/前端分离 Dockerfile、`docker-compose.yml`、`.env.example`、README Docker 快速启动命令和健康检查地址。

### P2：把“候选/因子/研究循环”翻译成交易者语言

交易者更关心：

- 这个策略交易什么？
- 什么条件开仓？
- 什么条件平仓？
- 过去 7 天/1 年赚不赚钱？
- 最大亏损多少？
- 和买入持有 BTC 比怎么样？
- 下一步该优化什么？

## 当前可用性判断

| 模块 | 当前状态 | 对交易者的影响 |
|---|---|---|
| 安装 | 可完成，但有环境坑 | 需要补常见失败说明 |
| 样例数据 | 可生成 BTCUSDT 7 天 1m 数据 | 有了起点 |
| Agent CLI | 能引导，但无法完成第一轮策略结果 | 容易失望 |
| quickstart | 能准备数据，但没有最小研究结果 | 名称承诺过高 |
| Web 工作台 | 可手动启动，但全新 clone 默认无报告 | 看不到实际价值 |
| Docker 部署 | 暂不可用 | 无法满足本地 Docker 试用 |
| 示例策略 | 缺失 | 最大阻塞点 |

最终判断：Kronos 已经有研究系统的骨架，但首次体验还缺“第一口饭”。对交易者来说，第一口饭不是 Agent 架构，也不是候选池，而是一个能跑完的 BTC 示例策略和一份看得懂的结果报告。
