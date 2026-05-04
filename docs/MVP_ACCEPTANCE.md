# Kronos Run MVP 验收定义

更新时间：2026-04-27

> 2026-04-28 更新：本文件只保留 `Run MVP / 工具入口` 的验收口径。当前整体产品 MVP 已切换为 `Agent MVP`，验收定义见 `docs/AGENT_MVP_ACCEPTANCE.md`。`kronos run today` 是 Agent 可调用的工具底座，不再代表产品终点。

## 当前结论

Kronos Run MVP V0.1 已经跑通，进入产品验收。

这次不再只是“研究工作台 / 自动研究任务”子模块跑通，而是已经有了一个系统级默认入口：

```bash
kronos run today
```

它会先检查数据，再调用内部默认研究任务，最后输出一份系统级状态报告，告诉用户本轮有没有正常跑、用了什么数据、产出了什么结论、失败时卡在哪里。

它仍然不是实盘交易产品，也不代表已经有可交易策略。

## 最新 Run MVP 验收批次

- 批次：`20260427-run-mvp-v1`
- 默认入口：`kronos run today`
- 运行结果：成功
- 程序耗时：9 分 49 秒
- 数据：BTCUSDT、ETHUSDT、SOLUSDT，1m K 线，约 90.14 天
- 数据量：每个币种约 13 万根 1m K 线
- 研究候选：12 个旧策略候选因子
- 评估完成：12
- 通过晋升：0
- 跳过：0
- 观察名单补证据：2 份
- 阻塞：0
- 系统状态报告：`reports/research/experiments/20260427-run-mvp-v1/kronos_run_status.md`
- 系统状态 JSON：`reports/research/experiments/20260427-run-mvp-v1/kronos_run_status.json`
- 自动研究日报：`reports/research/experiments/20260427-run-mvp-v1-research/auto_run_report.md`

## MVP 不再怎么定义

以下能力只能算子模块进展，不能算整体 MVP 完成：

- 某个因子验证能跑。
- 某个候选策略能出报告。
- 某个 `research` 命令能运行。
- 某个定时脚本能调用研究任务。
- 某批真实数据能产出一次实验结果。

这些能力有价值，但如果用户还不知道“我怎么启动整个 Kronos、启动后看哪里、失败了怎么办”，项目就还没有进入可用 MVP。

## Run MVP 的正确定义

Run MVP 包含七件事：

1. **一个默认入口**
   - 用户不需要理解 research、factor、walk-forward 这些技术模块。
   - 用户只需要知道“运行今天的 Kronos”。

2. **一个默认运行方案**
   - 默认币种、默认数据窗口、默认研究任务、默认报告位置都由系统给出。
   - 不要求产品经理每次拼参数。

3. **数据新鲜度检查**
   - 系统先告诉用户数据是否足够、是否新鲜、是否有缺口。
   - 不能把程序运行时间误写成研究样本长度。

4. **一轮默认研究任务**
   - 研究工作台 / 自动研究任务作为 Run MVP 的内部步骤存在。
   - 它负责产出候选验证、观察名单和下一步建议。

5. **一个人能看懂的状态总览**
   - 第一屏回答：本轮是否成功、用了多少历史数据、生成了哪些报告、结论是什么。
   - 先给产品结论，再给技术路径。

6. **失败时有明确原因**
   - 数据不足、网络失败、数据不新鲜、报告未生成、候选全失败，都要有可读解释。
   - 失败不能只留下技术报错。

7. **验收通过后再定时运行**
   - 定时器是 Run MVP 的放大器，不是 MVP 本身。
   - 手动运行和状态总览没有验收前，不安装每日无人值守运行。

## 明确不包含

Run MVP 不包含：

- 自动下单。
- 实盘交易。
- 交易执行层。
- RD-Agent 自主提出和改写策略。
- 承诺已经找到可交易策略。
- 把旧 A 股 / 期货策略直接迁移成 crypto 策略。
- 让未通过验证的候选进入组合或风控。

## 当前已有能力

这些是已经跑通的子能力：

- 可以同步 BTCUSDT、ETHUSDT、SOLUSDT 的真实 Binance USDM 数据。
- K 线和资金费率已经补到 90 天以上。
- OI 历史受交易所接口限制，不能作为 90 天级别结论依据。
- 可以通过 `kronos research auto-run` 跑一次自动研究循环。
- 可以生成 `auto_run_report.md` 和 `auto_run_summary.json`。
- 可以对 `range_chop_filter` 和 `body_energy` 生成观察名单补证据报告。
- 已有本地脚本 `scripts/run_mvp_auto_research.sh` 和 launchd 模板，适合作为后续定时入口。

最新研究批次：

- 批次：`20260427-mvp-90d-auto-run`
- 数据：BTCUSDT、ETHUSDT、SOLUSDT，1m K 线，约 90.14 天
- 研究候选：12 个旧策略候选因子
- 评估完成：12
- 通过晋升：0
- 跳过：0
- 观察名单补证据：2 份
- 补证据阻塞：0

## Run MVP V0.1 已补上的能力

当前已经补上：

- 顶层“运行 Kronos”的产品入口：`kronos run today`。
- 默认运行配置：BTC/ETH/SOL、1m K 线、90 天最低历史、本地数据优先、不自动交易。
- 系统级状态页：`kronos_run_status.md`。
- 数据检查：展示每个币种的数据起止时间、样本条数、历史天数和阻塞原因。
- 失败状态：缺数据时会生成失败状态报告，而不是只返回技术报错。
- 手动验收批次：`20260427-run-mvp-v1` 已成功跑完。

仍然待产品确认：

- 第一屏状态报告是否足够好懂。
- 是否接受 `research auto-run` 作为 Run MVP 的默认内部研究任务。
- 是否需要安装本地定时器，形成每日无人值守运行。

## 产品验收方式

Run MVP 的验收不应该从技术命令开始，而应该从这三个问题开始：

1. 我是否知道怎么启动整个 Kronos。
2. 我是否能在第一屏看懂它这次有没有正常跑。
3. 我是否能看懂下一步应该做什么。

通过标准：

- 一个默认入口能完成一轮运行。
- 状态总览能说清楚成功或失败。
- 报告能说明研究样本窗口，而不是只说程序跑了多久。
- 本轮产物路径清晰。
- 没有可交易候选时，系统能明确说“没有”，而不是包装成策略成果。
- 失败时能给出产品经理能理解的原因。

不通过标准：

- 用户必须理解多个内部模块才能运行。
- 运行成功但不知道看哪个报告。
- 报告只给技术指标，不给产品判断。
- 把局部研究任务运行成功当成整体系统完成。
- 定时器跑起来了，但失败、数据缺口或结论不可读。

## 报告如何使用

产品验收时先看系统状态报告：

1. 系统状态报告：`reports/research/experiments/20260427-run-mvp-v1/kronos_run_status.md`
2. 自动研究日报：`reports/research/experiments/20260427-run-mvp-v1-research/auto_run_report.md`
3. `body_energy` 补证据报告：`reports/research/experiments/20260427-run-mvp-v1-research-evidence-body_energy/watchlist_evidence_report.md`
4. `range_chop_filter` 补证据报告：`reports/research/experiments/20260427-run-mvp-v1-research-evidence-range_chop_filter/watchlist_evidence_report.md`

验收顺序：

1. 先看系统状态报告，判断本轮是否跑通。
2. 再看自动研究日报，判断研究结论是否能理解。
3. 最后只在需要时打开专项报告，复查候选退休或观察证据。
