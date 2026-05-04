# Kronos

> 加密货币量化研究系统 | Crypto-Native Quantitative Research System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Kronos** 是一个本地优先的加密货币量化研究 Agent。它能读取历史研究结果、选择候选策略、提出假设、调用确定性验证工具、输出可审计结论——并在 Web 工作台展示每一步。

**Kronos** is a local-first crypto quantitative research agent. It reads past research results, selects candidate strategies, proposes hypotheses, invokes deterministic validation tools, produces auditable conclusions, and displays every step in a Web workbench.

---

## Quick Start | 快速开始

```bash
# 1. 安装 | Install
git clone <repo-url> && cd Kronos
uv sync --dev

# 2. 一键启动 | One-command bootstrap
uv run kronos quickstart

# 3. 打开 Web 工作台 | Open Web workbench
cd web && npm run dev
# → http://127.0.0.1:3000
```

`kronos quickstart` 会自动生成 sample 数据并验证系统可用。切换到英文：`kronos quickstart --lang en`。

`kronos quickstart` generates sample data and verifies the system is functional. Switch to Chinese: `kronos quickstart --lang zh`.

---

## 这是什么 | What is Kronos

Kronos 的产品定位是 **加密货币策略研究 Agent**。它不像定时任务系统那样每天跑固定报告，也不会自动交易。

Kronos is a **crypto strategy research agent**. It does not run scheduled reports or trade automatically.

**核心能力 | Core capabilities**：
- 读历史研究结果、选候选 → 提出假设 → 调用验证工具 → 读证据 → 写结论 → 沉淀记忆
- Reads past research → selects candidates → proposes hypotheses → invokes validation → reads evidence → writes conclusions → persists memory

**当前状态 | Current status**：
- Agent MVP 完成，支持 DeepSeek-V4 模型驱动研究
- Web 工作台可浏览候选池、时间线、报告
- 12 个旧策略候选已完成 90 天 crypto 复验
- Agent MVP complete, supports DeepSeek-V4 powered research
- Web workbench: candidate pool, timeline, reports
- 12 legacy strategy candidates validated on 90-day crypto data

---

## 文档索引 | Documentation

| 文档 | 说明 |
|------|------|
| [`CLAUDE.md`](CLAUDE.md) | 开发指南（架构、命令、不变量） |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 阶段路线图和优先级 |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | 项目总控面板 |
| [`docs/PRODUCT_CONTROL_PANEL.md`](docs/PRODUCT_CONTROL_PANEL.md) | 产品经理视角总览 |
| [`docs/CODE_REVIEW_20260504.md`](docs/CODE_REVIEW_20260504.md) | 全量代码审查报告 |
| [`docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md`](docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md) | 产品验收报告 |
| [`docs/ONBOARDING_UX_REVIEW.md`](docs/ONBOARDING_UX_REVIEW.md) | 新用户体验审查 |

---

## 常用命令 | Common Commands

```bash
uv run kronos data status                         # 数据覆盖状态
uv run kronos data sync --symbols BTCUSDT,ETHUSDT  # 同步行情
uv run kronos quickstart                           # 快速开始
uv run kronos agent status                         # Agent 运行状态
uv run kronos agent run-once                       # 运行一轮 Agent 研究
uv run pytest -m "not e2e"                         # 跑测试
```
