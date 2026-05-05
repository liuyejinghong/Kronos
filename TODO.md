# Kronos TODO

> 更新：2026-05-05 | 版本：0.2.0 | 下一版本：0.3.0
> 状态：`done` 已完成 · `todo` 待办 · `wip` 进行中

## 当前版本 (v0.2.0) — 已完成

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

## 下一版本 (v0.3.0) — 待办

> 产品目标：让一个非开发交易者在 10 分钟内判断 R-breaker 是否值得进入模拟盘观察。
> 设计文档：`docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md`

### P0 — R-breaker 可信度评估闭环

| # | 事项 | 关联文档 |
|---|------|----------|
| 24 | `todo` 可信度报告：收益（含手续费）+ 最大回撤 + 最大连续亏损 + 盈亏比 + vs 持有基准 + 交易笔数 | 产品设计 §6 Phase 1 |
| 25 | `todo` 关键交易复盘：列出最大盈利/最大亏损/最长持仓的交易 | 同上 |
| 26 | `todo` 可信度结论：每次回测后输出"不建议 / 可以观察 / 值得模拟盘" | 同上 |
| 27 | `todo` 参数调整 + 即时重跑（对话中修改 volatility_multiplier、stop_loss_pct 等） | 同上 |

### P1 — 产品体验打磨

| # | 事项 | 关联文档 |
|---|------|----------|
| 28 | `todo` matplotlib 模块级 import 改为惰性加载 | `NOVICE_DOCKER_UX_LOG` #4 |
| 29 | `todo` quickstart 输出去重：去掉通用的"npm run dev"提示，Docker 用 entrypoint 覆盖 | `NOVICE_DOCKER_UX_LOG` #5 |
| 30 | `todo` Web 全新 clone 空状态：无历史 run 时不显示不存在的默认批次 | Codex 实测反馈 |
| 31 | `todo` 策略池空状态引导："你还没有策略，要创建一个吗？" | 产品设计 §1 |

### P2 — v0.4.0 预留

| # | 事项 |
|---|------|
| 32 | AI 自然语言策略创建 |
| 33 | 实时模拟盘（需 Binance 只读 API Key） |
| 34 | 历史重放（关键交易回放） |
| 35 | 按市场状态分段评估（牛/熊/震荡） |

---

## 产品文档索引

| 文档 | 说明 |
|------|------|
| `docs/PRODUCT_DESIGN_STRATEGY_SYSTEM.md` | **主设计文档**：策略系统 + 执行链路 + 实现计划 |
| `docs/PRODUCT_DESIGN_REVIEW_20260505.md` | 设计自审（CC 产品经理 + 交易者视角） |
| `docs/DOCKER_UX_EVALUATION_20260505.md` | Codex Docker 部署评测 |
| `docs/EXTERNAL_TRADER_ONBOARDING_REVIEW_20260505.md` | Codex 交易者首次试用 |
| `docs/NOVICE_DOCKER_UX_LOG_20260505.md` | CC 小白用户 Docker 问题排查（含 6 项根因修复） |
| `docs/PROJECT_STATUS.md` | 项目总控面板 |
| `docs/ROADMAP.md` | 阶段路线图 |
| `CHANGELOG.md` | 版本变更记录 |
