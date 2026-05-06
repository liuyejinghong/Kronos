# Kronos TODO

> 更新：2026-05-06 | 版本：0.4.0 | 下一版本：0.4.1
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

## 下一版本 (v0.4.1+) — 待办

> 产品目标：让用户能创建或配置一个策略，并在历史重放 / 模拟盘前看到足够清晰的风险边界和研究证据。
> 设计文档：`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`

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

### P2 — v0.4.x 主线

| # | 事项 |
|---|------|
| 41 | AI 自然语言策略创建 |
| 42 | 实时模拟盘（需 Binance 只读 API Key） |
| 43 | 历史重放（关键交易回放） |
| 44 | 按市场状态分段评估（牛/熊/震荡） |
| 50 | 多品种策略配置逐 symbol smoke-test，避免只验证首个品种 |

---

## 产品文档索引

| 文档 | 说明 |
|------|------|
| `docs/USER_PERSONAS.md` | **用户画像**：核心用户、非核心用户、功能排序和文案原则 |
| `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` | **主设计文档**：策略系统 + 执行链路 + 实现计划 |
| `docs/PRODUCT_DESIGN_REVIEW_20260505.md` | 设计自审（CC 产品经理 + 交易者视角） |
| `docs/DOCKER_UX_EVALUATION_20260505.md` | Codex Docker 部署评测 |
| `docs/EXTERNAL_TRADER_ONBOARDING_REVIEW_20260505.md` | Codex 交易者首次试用 |
| `docs/NOVICE_DOCKER_UX_LOG_20260505.md` | CC 小白用户 Docker 问题排查（含 6 项根因修复） |
| `docs/PROJECT_STATUS.md` | 项目总控面板 |
| `docs/ROADMAP.md` | 阶段路线图 |
| `CHANGELOG.md` | 版本变更记录 |
