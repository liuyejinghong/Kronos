# Kronos TODO

> 更新：2026-05-09 | 版本：0.4.8 | 下一版本：0.4.9
> 状态：`done` 已完成 · `todo` 待办 · `wip` 进行中

## v0.3.2 已完成

### Agent MVP

| # | 事项 | 证据 |
|---|------|------|
| 1 | Agent 完整闭环（Supervisor / 角色 / Prompt / Secret / LLM / 工具 / 事件） | `kronos/agent/` |
| 2 | DeepSeek V4-Pro / V4-Flash 双模型 | `kronos/agent/roles.py` |
| 3 | Web 工作台（FastAPI + Next.js 16） | `kronos/web/` + `web/` |
| 4 | 对话式 Agent（`kronos agent start`） | `kronos/agent/console.py` |
| 5 | 真实 LLM Agent 运行（`20260504-agent-real-v1`） | `reports/research/experiments/` |

### Onboarding

| # | 事项 | 证据 |
|---|------|------|
| 6 | `kronos quickstart` 一键完成：数据 → R-breaker → 评估 → 报告 | `cli/main.py` |
| 7 | README 中英双语 + HTTPS clone | `README.md` + `README.en.md` |
| 8 | `--lang zh/en` 全局语言切换 | `kronos/common/i18n.py` |
| 9 | 配置自动发现（6 级 fallback） | `kronos/common/config.py` |
| 10 | Sample 数据自动生成 | `kronos/data/seed.py` |
| 11 | Docker 部署（Dockerfile + compose + .dockerignore） | `Dockerfile` + `docker-compose.yml` |

### 内置策略

| # | 事项 | 证据 |
|---|------|------|
| 12 | R-breaker 日内突破策略（Factor 协议实现） | `kronos/strategy/r_breaker.py` |
| 13 | `register_builtin_strategies()` 自动注册 | `kronos/factor/candidates.py` |
| 14 | RBreakerFactor 注册到 FactorRegistry | `kronos/factor/bootstrap.py` |

### 安全 & Bug 修复

| # | 事项 | 证据 |
|---|------|------|
| 15 | Web 路径穿越防护（3 处） | `kronos/web/routes/_mappers.py` |
| 16 | SQL 注入防护 | `kronos/data/storage/query.py` |
| 17 | Secret 脱敏统一 | `kronos/agent/events.py` |
| 18 | 回测 execution_delay_bars / run_id 修复 | `kronos/research/backtest/engine.py` |
| 19 | 其他 8 项 MAJOR bug 修复 | 见 `docs/CODE_REVIEW_20260504.md` |

### 产品文档

| # | 事项 | 证据 |
|---|------|------|
| 20 | 策略系统产品设计（含执行链路） | `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` |
| 21 | Docker 首次部署评测（Codex） | `docs/DOCKER_UX_EVALUATION_20260505.md` |
| 22 | 交易者首次试用记录（Codex） | `docs/EXTERNAL_TRADER_ONBOARDING_REVIEW_20260505.md` |
| 23 | 小白用户 Docker 问题排查日志 | `docs/NOVICE_DOCKER_UX_LOG_20260505.md` |

---

## v0.3.3 已完成

### Codex v0.3.2 评测遗留收口

| # | 事项 | 证据 |
|---|------|------|
| 32 | `done` `kronos report latest` 命令，直接打印最新报告摘要 | `cli/main.py` + `kronos/reporting/latest.py` |
| 33 | `done` 报告指标翻译成交易语言 | `kronos/research/workbench.py` |
| 34 | `done` 数据同步指引补全：数据来源、同步范围、是否需要 API Key | `cli/main.py` + README |
| 35 | `done` 模拟盘边界说明：当前只到研究报告，模拟盘未接入 | quickstart 提示 + 研究报告 |

---

## v0.3.4 已完成

### 审查问题根因修复

| # | 事项 | 证据 |
|---|------|------|
| 36 | `done` 候选池测试隔离，测试不再读写真实 `~/.kronos/candidates.json` | `kronos/factor/candidates.py` + `tests/conftest.py` |
| 37 | `done` `report latest` 优先使用结构化 run 时间，不再单纯依赖文件 mtime | `kronos/reporting/latest.py` |
| 38 | `done` Web LLM 设置只接受当前支持的 DeepSeek provider | `kronos/web/routes/settings.py` |
| 39 | `done` Agent 工具输入缺字段时提前失败并给出可解释错误 | `kronos/agent/tools.py` |
| 40 | `done` 项目状态和主产品设计文档对齐 current / target / deferred | `docs/PROJECT_STATUS.md` + `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` |

---

## v0.4.0 已完成

### 策略配置入口

| # | 事项 | 证据 |
|---|------|------|
| 45 | `done` TOML 策略配置文件支持（`~/.kronos/strategies/r_breaker.toml`） | `kronos/strategy/config.py` + `kronos strategy init-r-breaker` |
| 46 | `done` 策略配置校验：策略 ID、品种、周期、参数边界 | `kronos/strategy/config.py` + `kronos strategy validate` |
| 47 | `done` 本地烟雾测试：用已有 K 线确认策略逻辑能跑通 | `kronos/strategy/smoke.py` + `kronos strategy smoke-test` |
| 48 | `done` 通过烟雾测试后注册到候选池，Agent/Web 可见 | `kronos strategy register` |
| 49 | `done` 重复注册同一 TOML 策略时按 ID 更新，不产生重复候选 | `upsert_candidate()` |

---

## v0.4.1 已完成

### Docker 多画像体验评测

| # | 事项 | 证据 |
|---|------|------|
| 51 | `done` 基于用户画像模拟 Docker 全新使用流程，记录安装、报告、策略配置、Agent 接力的体验反馈 | `docs/DOCKER_PERSONA_UX_EVALUATION_20260506.md` |
| 52 | `done` 将 v0.4.0 首次体验问题按 P0/P1/P2 和根因归档，作为 v0.4.2 产品体验修复输入 | `docs/DOCKER_PERSONA_UX_EVALUATION_20260506.md` |

---

## v0.4.2 已完成

### Docker 首次体验信任链修复

| # | 事项 | 证据 |
|---|------|------|
| 53 | `done` 修复 Agent 策略列表和研究结论的事实错误：`{n}` 未替换、7 天样本误写 90 天、1 个策略误写 12 个旧策略 | `kronos/agent/console.py` + `kronos/common/i18n.py` |
| 54 | `done` 重做 `kronos report latest` 第一屏摘要：展示 sample/real 数据边界、策略数量、粒度、验证结果和下一步 | `kronos/reporting/latest.py` |
| 55 | `done` 修复自动研究报告中 7 天样本与“90 天复验已完成”的文案冲突 | `kronos/research/auto_runner.py` |
| 56 | `done` Docker 模式下 `strategy init-r-breaker` 输出容器安全的 smoke-test/register 命令，避免宿主机 `~` 路径误导 | `cli/main.py` + README |
| 57 | `done` 解释 quickstart/Agent 1m sample 试跑与 TOML 默认 15m 配置之间的关系 | `cli/main.py` + README |
| 58 | `done` quickstart / agent start 默认隐藏工程调试日志 | `configs/dev.toml` |
| 59 | `done` 将根因、产品逻辑、修复方案和验收标准沉淀为文档 | `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260506.md` |

---

## v0.4.3 已完成

### 自然语言策略起草

| # | 事项 | 证据 |
|---|------|------|
| 60 | `done` AI/自然语言策略创建首版：把 R-breaker 日内突破策略想法转换成策略概要、trace 和 TOML 草案，再走 validate / smoke-test / register 闸门 | `kronos/strategy/authoring.py` + `kronos strategy draft` + `openspec/changes/p4-strategy-authoring/` |
| 61 | `done` 再做一轮 GitHub 全新 clone 的 Docker 首次体验评测，确认 `report latest`、`strategy draft` 和 `agent start` 的承接路径 | `docs/DOCKER_PERSONA_UX_EVALUATION_20260507.md` |

---

## v0.4.4 已完成

### Docker 首次体验语义收口

| # | 事项 | 证据 |
|---|------|------|
| 62 | `done` 将 v0.4.3 Docker fresh clone 评测问题沉淀为修复方案，明确用户看到的问题、根因、产品逻辑和验收标准 | `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260507.md` |
| 63 | `done` `quickstart` / `report latest` 共用结果卡口径：数据来源、样本范围、评估对象、结论、可信度、下一步 | `kronos/reporting/latest.py` + `cli/main.py` |
| 64 | `done` 策略起草后的 `validate / smoke-test / register` 对外翻译成检查配置、空跑确认、进入候选池 | `kronos/strategy/authoring.py` + `kronos/agent/console.py` |
| 65 | `done` Docker entrypoint 和 quickstart 下一步收敛为先读最新报告，再进入策略起草 / 真实数据 / Agent | `docker-entrypoint.sh` + `kronos/common/i18n.py` |
| 66 | `done` OpenSpec 约束、README、项目状态、路线图和策略系统设计同步 v0.4.4 边界 | `openspec/changes/p4-docker-first-use-result-card/` + README + `docs/PROJECT_STATUS.md` + `docs/ROADMAP.md` |

---

## v0.4.5 已完成

| # | 事项 | 证据 |
|---|------|------|
| 67 | 关键交易重放入口 | `kronos report replay` + `kronos/research/backtest/reporting.py` |
| 68 | 市场状态分段入口 | `kronos report regime` + `kronos/research/watchlist_evidence.py` |
| 69 | 只读观察边界入口 | `kronos report observation` + `kronos/research/workbench.py` |
| 70 | 多品种 smoke-test 覆盖所有声明品种 | `kronos/strategy/smoke.py` + `tests/integration/test_cli.py` |

## v0.4.6 已完成

| # | 事项 | 证据 |
|---|------|------|
| 71 | `done` Docker 模拟用户测试与修复方案 | `docs/DOCKER_PERSONA_UX_EVALUATION_20260508.md` + `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260508.md` |
| 72 | `done` fresh Docker 依赖准备根因修复：移除 `uv sync --no-cache` | `Dockerfile` + `tests/unit/test_dockerfile.py` |
| 73 | `done` quickstart / report latest / agent start 首屏继续压缩为更短的试跑结论和下一步 | `kronos/reporting/latest.py` + `kronos/common/i18n.py` |

## v0.4.7 已完成

| # | 事项 | 证据 |
|---|------|------|
| 74 | `done` 只读观察计划版本需求与 OpenSpec 立项 | `docs/RELEASE_0.4.7_PAPER_OBSERVATION_PLAN.md` + `openspec/changes/p4-paper-observation-plan/` |
| 75 | `done` 从研究报告生成只读观察计划 | `kronos report observation-plan` + `kronos/reporting/observation_plan.py` |
| 76 | `done` 观察计划明确虚拟订单、延迟、滑点和人工闸门，不启动模拟盘或真实订单 | `paper_observation_plan.md` |

## v0.4.8 已完成

> 产品目标：在只读观察计划之后，推进 Binance 模拟盘 / 测试网真实成交最小闭环。允许使用模拟盘 API Key 在测试网提交真实测试订单，但必须隔离真实资金、拒绝主网、保留人工闸门。

| # | 事项 |
|---|------|
| 77 | `done` v0.4.8 Binance 模拟盘真实成交版本需求与 OpenSpec 立项 |
| 78 | `done` Binance 测试网凭证配置：本地保存 API Key / Secret，全程脱敏 |
| 79 | `done` `paper preflight`：确认测试网环境、观察计划 metadata、凭证、账户和风控限额 |
| 80 | `done` `paper start/status/stop`：从合格观察计划启动受限测试网模拟盘，停止后必须显式 reset 才能重启 |
| 81 | `done` 测试网订单 / 成交 / 错误 ledger：记录 Binance testnet order id、trade 明细、成交时间、手续费、失败原因和停止动作 |
| 82 | `done` 模拟盘报告：明确测试网成交不等于实盘收益，不能自动升级实盘 |
| 83 | `done` Docker fresh 验证：无凭证时给清晰下一步，mock testnet 安全路径可用 |
| 84 | `done` `paper credentials set` 移除 argv secret，支持环境变量和隐藏输入，减少 shell history 暴露 |

## 下一版本 (v0.4.9+) — 待办

| # | 事项 |
|---|------|
| 85 | `blocked` 用用户提供的 Binance testnet API Key 跑一次人工授权的端到端真实测试网下单验证：2026-05-09 已授权尝试，但当前缺测试网凭证且真实 90 天数据没有 promoted 候选，不能绕过闸门 |
| 86 | Web 工作台展示测试网模拟盘状态和报告 |

---

## 历史已完成补充

### P0 — R-breaker 可信度评估闭环（✅ 完成）

| # | 事项 | 证据 |
|---|------|------|
| 24 | `done` 可信度报告：vs 持有基准 + 市场周期 + 评估数量 + 通过数量 | quickstart 输出 |
| 25 | `done` 明确结论："当前没有策略通过验证" + 原因解释 | quickstart verdict |
| 26 | `done` 参数调整引导：控制台研究完成后展示可调参数 + TOML 路径 + 常见调整建议 | console.py `_show_tuning_guide()` |
| 27 | `done` 惰性加载 matplotlib | `diagnostics/reporting.py` |

### P1 — 产品体验打磨

| # | 事项 | 状态 |
|---|------|------|
| 28 | Web 全新 clone 空状态：无历史 run 时隐藏批次号 + 更新产品描述 | `done` |
| 29 | Docker entrypoint 覆盖 quickstart 的通用下一步提示 | `done` |
| 30 | 策略池空状态引导："你还没有策略" + 示例代码 | `done` |

---

## 产品文档索引

| 文档 | 说明 |
|------|------|
| `docs/USER_PERSONAS.md` | **用户画像**：核心用户、非核心用户、功能排序和文案原则 |
| `docs/DOCKER_PERSONA_UX_EVALUATION_20260506.md` | **Docker 多画像体验评测**：按用户画像记录 v0.4.0 首次体验问题和修复优先级 |
| `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260506.md` | **Docker 体验修复方案**：P0/P1 问题根因、产品逻辑、修复方案和验收标准 |
| `docs/DOCKER_PERSONA_UX_EVALUATION_20260507.md` | **Docker fresh clone 复测**：验证 v0.4.3 的 report latest、strategy draft 和 Agent 接力问题 |
| `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260507.md` | **Docker 体验语义收口方案**：v0.4.4 结果卡、策略闸门翻译和 Docker 首屏修复 |
| `docs/DOCKER_PERSONA_UX_EVALUATION_20260508.md` | **Docker 模拟用户测试**：fresh Docker 新装路径、L0-L4 画像和首轮产品结论 |
| `docs/reviews/DOCKER_PERSONA_UX_FIX_PLAN_20260508.md` | **Docker 模拟用户测试修复方案**：针对首次入口再压缩的一轮产品修复指引 |
| `openspec/changes/p4-docker-first-use-result-card/` | **v0.4.4 OpenSpec**：首次体验结果卡、策略闸门翻译和 Docker 默认入口验收要求 |
| `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` | **主设计文档**：策略系统 + 执行链路 + 实现计划 |
| `docs/PRODUCT_DESIGN_REVIEW_20260505.md` | 设计自审（CC 产品经理 + 交易者视角） |
| `docs/DOCKER_UX_EVALUATION_20260505.md` | Codex Docker 部署评测 |
| `docs/EXTERNAL_TRADER_ONBOARDING_REVIEW_20260505.md` | Codex 交易者首次试用 |
| `docs/NOVICE_DOCKER_UX_LOG_20260505.md` | CC 小白用户 Docker 问题排查（含 6 项根因修复） |
| `docs/PROJECT_STATUS.md` | 项目总控面板 |
| `docs/ROADMAP.md` | 阶段路线图 |
| `CHANGELOG.md` | 版本变更记录 |
