# Kronos — 加密货币量化研究系统

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-informational.svg)](CHANGELOG.md)

[English](README.en.md)

**Kronos** 是一个本地优先的加密货币量化研究 Agent。它能读取历史研究结果、选择候选策略、提出假设、调用确定性验证工具、输出可审计结论——并在 Web 工作台展示每一步。

> 它不是定时任务系统，不会自动交易，也没有每日固定报告。它是一个**研究员**——提出问题、设计实验、验证假设、沉淀结论。

---

## 快速开始

```bash
git clone git@github.com:liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos quickstart
```

`quickstart` 会自动生成 sample 数据、验证系统可用，并告诉你下一步怎么做。

---

## 这是什么

Kronos 把传统 A 股/期货的量化策略资产重新适配到加密货币市场。当前 12 个旧策略候选已完成 90 天 crypto 复验。

**工作方式**：读历史研究结果 → 选候选 → 提出假设 → 调用验证工具 → 读证据 → 写结论 → 沉淀记忆

**当前能力**：
- Agent MVP 完成，支持 DeepSeek-V4 双模型驱动研究
- Web 工作台可浏览候选池、时间线、报告
- 完整回测引擎、因子验证管线、滚动窗口验证、信号诊断

---

## 命令速查

```bash
uv run kronos data status                          # 数据覆盖状态
uv run kronos data sync --symbols BTCUSDT,ETHUSDT   # 同步行情
uv run kronos quickstart                            # 一键快速开始
uv run kronos agent run-once                        # 运行一轮 Agent 研究
uv run kronos agent status                          # 查看 Agent 状态
uv run pytest -m "not e2e"                          # 跑测试
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 阶段路线图和优先级 |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | 项目总控面板 |
| [`CLAUDE.md`](CLAUDE.md) | 开发指南（架构、命令、关键约束） |
| [`docs/CODE_REVIEW_20260504.md`](docs/CODE_REVIEW_20260504.md) | 全量代码审查报告 |
| [`docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md`](docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md) | 产品验收报告 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本变更记录 |
