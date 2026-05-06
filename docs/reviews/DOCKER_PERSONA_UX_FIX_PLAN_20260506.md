# Docker 多画像体验根因修复方案（2026-05-06）

> 来源：`docs/DOCKER_PERSONA_UX_EVALUATION_20260506.md`  
> 目标版本：v0.4.2  
> 范围：修复首次 Docker 体验中的 P0/P1 信任链问题；不新增模拟盘、实盘、Web Docker 化或新策略类型。

## 实施状态

v0.4.2 已按本文逐项修复 P0/P1 信任链问题。后续如果继续扩展 AI 策略创建、历史重放或模拟盘，必须沿用本文原则：用户可见结论绑定当前 run context，sample 数据只代表流程试跑，Docker 命令必须可复制。

## 产品原则

Kronos 的首次体验要先回答交易用户最基本的问题：**我跑了什么、用了什么数据、结论能不能信、下一步做什么。**

因此本轮修复遵守四条原则：

1. **结论绑定当前事实**：所有面向用户的结论必须来自当前 run context，不能写死“90 天”“12 个旧策略”“能不能赚钱”。
2. **sample 只代表流程试跑**：7 天 synthetic 数据只能证明安装、数据读取、策略计算和报告链路可用，不能给策略有效性结论。
3. **第一屏先给交易语言**：报告摘要先说数据、策略、验证结果、失败原因和下一步，再给 artifact 路径。
4. **Docker 命令必须可复制**：Docker 场景输出的下一步命令必须使用容器内路径，避免宿主机 `~` 展开导致失败。

## 修复清单

### P0-1：Agent 输出事实错误

**用户看到的问题**

- 策略列表显示 `这里有 {n} 个策略`。
- 只有 7 天 synthetic 数据，却说“跑了 90 天验证”。
- 只评估 1 个 R-breaker，却说“当前的 12 个旧策略”。

**根因**

- `kronos/common/i18n.py` 中 `conv.strategies_title` 需要 `{n}`，但 `kronos/agent/console.py` 调用时没有传参。
- `conv.strategies_prompt` 和 `conv.research_next` 是固定文案，没有读取当前数据是否 synthetic、实际样本天数、候选数量和本轮评估数量。
- Agent 的候选池文案仍沿用旧 A 股 / 期货迁移阶段的 12 候选语境，没有同步到 v0.4.0 的 R-breaker 用户配置路径。

**产品修复**

- 策略列表标题动态展示真实候选数量。
- 策略列表说明动态区分：
  - synthetic 数据：这是流程试跑，不能判断策略是否赚钱。
  - 真实但少于 90 天：样本偏短，需要补足更长历史。
  - 真实且不少于 90 天：可以说已具备 90 天级别验证样本。
- 研究完成后的下一步根据本轮 `evaluated/promoted` 和数据性质动态生成，禁止出现不真实的“12 个旧策略”。
- 如果是 sample 数据，下一步优先建议同步真实数据，而不是给强策略结论。

**代码位置**

- `kronos/agent/console.py`
- `kronos/common/i18n.py`

**验收标准**

- `agent start` 查看策略列表不再出现 `{n}`。
- 7 天 synthetic 场景不出现“90 天验证”“12 个旧策略”“不能赚钱”。
- 本轮只评估 1 个策略时，结论明确写“1 个策略已评估，0 个通过验证；sample 数据不能作为策略优劣判断”。

### P0-2：`report latest` 摘要不能形成交易判断

**用户看到的问题**

`report latest` 只输出：

```text
本次自动研究已完成工作台和观察名单补证据，当前仍没有候选进入组合或实盘。
```

用户无法知道本次用了什么数据、验证了什么策略、为什么没通过、下一步做什么。

**根因**

- `kronos/reporting/latest.py` 只抽取 Markdown 第一个产品段落。
- 自动研究报告里的“一句话结论”是流程状态，不是交易用户第一屏。
- 完整报告和 `auto_run_summary.json` 已有数据范围、粒度、评估数量、晋升数量等结构化信息，但没有被摘要层组合使用。

**产品修复**

- `summarize_report()` 优先读取同目录 `auto_run_summary.json`，生成固定结构第一屏：
  - 本次结论
  - 数据：symbol、粒度、样本天数、sample/真实边界
  - 策略：评估数量、通过数量
  - 判断：是否能进入观察/组合/模拟盘
  - 下一步命令
- 如果找不到结构化 summary，再回退到 Markdown 段落抽取。

**代码位置**

- `kronos/reporting/latest.py`
- `tests/unit/test_reports_latest.py`

**验收标准**

- `report latest` 前 10 行内能回答“数据、策略、结果、原因、下一步”。
- sample 数据场景必须明确写“流程试跑，不代表策略有效性”。

### P0-3：报告正文 7 天样本与 90 天结论冲突

**用户看到的问题**

报告同一份正文里既写：

```text
BTCUSDT / 1m K线 ... 约 7.0 天
```

又写：

```text
90 天复验已完成
```

**根因**

- `run_watchlist_evidence_review()` 返回的 `history_status == "enough_history"` 只代表达到调用方传入的 `min_history_days`。
- quickstart / Agent 为了体验速度把 `min_history_days` 降到 1 或 7，但 `_next_step()` 固定把 `enough_history` 翻译成“90 天复验已完成”。

**产品修复**

- `_next_step()` 必须读取当前覆盖天数。
- 只有实际 K 线覆盖不少于 90 天时，才允许出现“90 天复验”。
- 小于 90 天时写“当前样本约 N 天，只能做流程试跑/短样本观察，不能形成 90 天复验结论”。

**代码位置**

- `kronos/research/auto_runner.py`
- `tests/integration/test_cli.py`

**验收标准**

- 7 天 sample 报告不再出现“90 天复验已完成”。
- 90 天真实数据报告仍可保留 90 天复验表达。

### P1-1：Docker 策略路径容易误导

**用户看到的问题**

- 容器内正确路径：`/root/.kronos/strategies/r_breaker.toml`。
- 本地 README 常见路径：`~/.kronos/strategies/r_breaker.toml`。
- Docker 用户把本地路径套进 `docker compose run` 后，宿主机 shell 会展开成 `/Users/ethan/...`，容器内找不到。

**根因**

- 本地命令和 Docker 命令没有分栏。
- `strategy init-r-breaker` 输出的 `next:` 不知道当前在 Docker 内，导致 Docker 用户需要自己补命令。
- `strategy smoke-test/register` 报错只说文件不存在，没有识别明显宿主机路径。

**产品修复**

- Docker 模式下 `strategy init-r-breaker` 输出可复制的 Docker 命令：
  - `docker compose run --rm kronos uv run kronos strategy smoke-test /root/.kronos/strategies/r_breaker.toml`
  - `docker compose run --rm kronos uv run kronos strategy register /root/.kronos/strategies/r_breaker.toml`
- README 命令速查拆成本地版和 Docker 版。
- 当配置路径以 `/Users/`、`/home/` 等宿主机路径形态传入且文件不存在时，补一句 Docker 路径提示。

**代码位置**

- `cli/main.py`
- `README.md`
- `README.en.md`
- `tests/integration/test_cli.py`

**验收标准**

- Docker 内 `strategy init-r-breaker` 输出的下一步命令可直接复制成功。
- 宿主机路径失败时提示 Docker 用户使用 `/root/.kronos/...`。

### P1-2：quickstart / Agent 1m 与 TOML 默认 15m 关系不清楚

**用户看到的问题**

- quickstart / Agent 研究显示 `timeframe=1m`。
- `init-r-breaker` 生成 TOML 显示 `timeframe: 15m`。
- 用户无法判断刚才研究的是不是自己生成的配置。

**根因**

- demo 研究路径和用户 TOML 策略路径是两条流程。
- CLI 输出没有解释“quickstart 是 1m 流程试跑，TOML 是你可编辑的新配置”。

**产品修复**

- `init-r-breaker` 输出补充说明：quickstart 默认 1m 只用于安装试跑；当前 TOML 默认 15m，需要 `smoke-test/register` 后才进入用户策略池。
- Agent 研究结论显示本轮实际使用的 timeframe。

**代码位置**

- `cli/main.py`
- `kronos/agent/console.py`

**验收标准**

- 用户从输出中能区分“刚才的 quickstart 试跑”和“当前生成的 15m TOML 配置”。

### P1-3：工程日志泄露到产品首屏

**用户看到的问题**

- `config.loaded`
- `query.loaded`
- `partition.written`
- ANSI 彩色 structlog 输出

**根因**

- `configs/dev.toml` 默认 `log_level = "DEBUG"`。
- CLI 用户输出和结构化日志都走 stdout。
- quickstart / agent start 使用 dev config 时没有降低日志级别。

**产品修复**

- 把 `configs/dev.toml` 默认日志级别降为 `WARNING`。
- 保留 `log_json = false`，避免开发本地输出大段 JSON。
- 后续需要调试时通过配置或 `KRONOS_CONFIG` 使用 DEBUG，不在首次体验默认暴露。

**代码位置**

- `configs/dev.toml`
- 相关测试只做输出回归和 Docker 复测。

**验收标准**

- `docker compose up` quickstart 输出不再出现 `config.loaded/query.loaded/partition.written`。
- `agent start` 首屏不再夹杂 `query.loaded`。

## 实施顺序

1. 先补 `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260506.md`，锁定根因、产品逻辑和验收标准。
2. 修 Agent 动态文案和样本上下文。
3. 修 `report latest` 结构化摘要。
4. 修 auto report 下一步的 90 天判断。
5. 修 Docker 策略路径提示和 README 命令分栏。
6. 调整默认日志级别。
7. 补单元/集成测试。
8. 跑针对性 CLI + Docker 复测。
9. 同步版本、CHANGELOG、TODO、PROJECT_STATUS。

## 不做的事

- 不把 Web 服务塞进默认 Docker Compose。
- 不新增实时模拟盘或 Binance 只读 API Key。
- 不把 sample 数据包装成任何策略有效性结论。
- 不在本轮重构 Agent runtime 或策略系统架构。
