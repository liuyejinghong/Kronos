# Kronos Docker 多画像模拟用户测试（2026-05-08）

> 评测对象：Kronos v0.4.5
> 评测方式：在 fresh Docker 环境里模拟不同成熟度用户，观察 `quickstart`、`report latest`、`strategy draft`、`report regime`、`report observation` 和 `agent start` 的首次体验。
> 评测目的：判断当前版本是否已经把“安装 -> 结果 -> 理解 -> 下一步”这条主线讲清楚，并找出最影响继续使用的产品问题。
> 范围限制：只做产品体验评测，不把本轮结论写成修复方案，不引入模拟盘、实盘或新策略类型。

## 一句话结论

v0.4.5 在 fresh Docker 复测里已经能把新用户带到一份可读的研究结果，也能把策略想法起草成草案，但它还没有完全把“我现在该做什么”讲到足够短、足够直白。

这轮测试最明显的进步是：

1. `report latest` 现在是一张稳定的结果卡，不再只是目录摘要。
2. `strategy draft` 能把自然语言想法压成可继续验证的草案。
3. `report regime` 和 `report observation` 终于把“为什么表现好/差”和“当前只到研究边界”讲出来了。

但仍有几个影响产品判断的点：

- 首次安装时，L0/L6 仍会在“数据、研究、草案、下一步”之间停顿一会儿。
- `agent start` 已经像助手，但在某些路径上仍偏菜单式引导。
- `report replay` 只有在已有回放报告时才有内容；缺少回放时的解释仍略硬。
- sample 数据和真实行情边界虽然有了，但完全小白仍需要重复确认一次。
- 首次构建慢的直接根因已定位到 Dockerfile 禁用 `uv` 缓存；去掉 `--no-cache` 后，fresh build 里的依赖准备从 15 分钟级恢复到约 12 秒级，剩余问题是首次等待阶段仍需要更清楚的阶段提示。

## 评测画像

| 画像 | 关注点 | 本轮结果 |
|---|---|---|
| L0 完全小白 | 能不能跑起来、结果在哪、下一步是什么 | 能跑，但需要更少选择题 |
| L1 入门交易者 | 这次结果值不值得继续看 | 能看懂结果卡，但还不够短 |
| L2 有经验交易者 | 能不能把想法变成可验证草案 | 已经可以 |
| L3 研究者 | 是否能追溯数据、解释和边界 | 已经能用 |
| L4 小团队负责人 | 是否能拿来做分层决策 | 够用，但还可再压缩表达 |

## 实际操作记录

### 1. fresh Docker quickstart

执行：

```bash
docker compose -p kronosfreshv046test3 up --build --abort-on-container-exit
docker compose -p kronosfreshv046test4 up --build --abort-on-container-exit
```

结果：成功。

观察到的产品信号：

- 首次运行会明确说出 sample 数据、研究报告和下一步。
- `report latest`、`report observation`、`agent start` 都能在 fresh 容器里接住。
- `report replay` 在没有回放报告时，会明确告诉用户先有回放再看。
- `quickstart` 的结果已经不只是“跑完了”，而是能把“这是试跑，不是结论”讲清楚。
- 修复后 fresh Docker 构建里 `uv sync` 的依赖准备阶段从 `kronosfreshv046test3` 的 15m49s 降到 `kronosfreshv046test4` 的 11.99s。

主要问题：

- 首次构建慢的工程根因已经修复；剩余体验问题是用户仍需要知道当前处在“准备依赖 / 生成 sample / 分析报告”的哪个阶段。
- `quickstart` 末尾与 entrypoint 末尾仍有一点重复收尾感。

### 2. `report latest`

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos report latest
```

结果：成功。

观察到的产品信号：

- 第一屏已经是稳定的结果卡。
- 数据来源、样本范围、评估对象、结论、可信度和下一步都在前面。
- sample / 真实边界没有被混掉。

主要问题：

- 对 L1 来说，`mean_rank_ic` 这类指标仍需要一句交易语言解释。
- `report latest` 已经能用，但还可以更短。

### 3. `strategy draft`

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos strategy draft --prompt "我想做 BTCUSDT 的 R-breaker 策略, 15m 周期"
```

结果：成功。

观察到的产品信号：

- 自然语言策略想法已经能进草案。
- 输出里明确写了 `validate → smoke-test → register` 的下一步。
- 没有把草案包装成可交易策略。

主要问题：

- 对完全小白来说，R-breaker 这个专有策略名、TOML、validate 仍是学习门槛。
- 这条路径更适合 L2/L3，不适合作为 L0 的默认第一步。

### 4. `report regime`

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos report regime
```

结果：成功。

观察到的产品信号：

- 不同市场状态被拆开讲了。
- 有弱正向和不支持的分段结论，不再只看总均值。

主要问题：

- 术语层仍偏研究者，但已经比上一版好很多。

### 5. `report replay`

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos report replay
```

结果：没有可用回放报告。

观察到的产品信号：

- 系统能明确说出当前没有回放报告，而不是假装给出结果。
- 这条路径本身是对已有研究报告的下钻，不是默认首屏。

主要问题：

- 缺少内容时提示虽然正确，但还可以更像“先有回放，再看解释”的产品提醒。

### 6. `report observation`

执行：

```bash
docker compose -p kronospersonaeval run --rm kronos uv run kronos report observation
```

结果：成功。

观察到的产品信号：

- 当前版本只到研究报告和 Agent 复盘，这个边界说得很清楚。
- 虚拟订单、延迟、滑点和人工闸门被明确留在后面。

主要问题：

- 对 L0 来说，这一段还是偏产品说明，需要配合更短的主结论一起看。

### 7. `agent start`

在新装 Docker 环境里打开 `agent start` 时，首屏先说“我会先帮你判断当前结果能不能信，再给一个最合适的下一步”，然后明确提示“你还没有行情数据”，并给出生成 sample 数据、连接交易所、先看看三条路。

观察到的产品信号：

- 这已经像一个助手了，不只是命令菜单。
- L0 在无数据时不会被直接丢进内部流程。
- 生成 sample 数据后，系统能继续往草案和研究方向推进。

主要问题：

- 某些分支仍然略像“选项面板”，不是完全自然语言对话。
- 对完全小白来说，数据、策略、研究三个概念还会在脑子里打架一次。

## 主要问题，按优先级排序

### P0：L0/L6 仍需要重复确认“这次到底是不是结论”

根因：
产品主线已经清楚了，但首次安装后的叙事还不够短，用户需要在 sample、结果、草案、下一步之间自己再拼一次。

### P1：`agent start` 还没完全从“菜单”变成“助手”

根因：
入口已经正确，但表达还没有完全压缩到交易用户可直接继续的程度。

### P1：`report replay` 在没有回放报告时的解释还不够顺手

根因：
这条路径是升级入口，不是默认入口；缺少内容时的提示更像工具报错，不像产品引导。

### P2：构建和首次等待对小白仍偏重

根因：
直接根因不是 Docker 本身慢，而是 Dockerfile 在 `uv sync` 阶段使用了 `--no-cache`，导致 fresh build 不能复用依赖缓存，等待被反复放大。产品层剩余问题是首次运行时用户只看到大量安装日志，不一定知道这属于正常准备阶段。

## 结论

如果按“新用户能不能从安装一路走到可读结果”来评估，v0.4.5 已经合格。

如果按“完全小白能不能不反复停顿地知道下一步”来评估，它还差半步：

1. 结果卡已经够用。
2. 解释卡已经补上。
3. 还需要把首次入口再压短一点。
