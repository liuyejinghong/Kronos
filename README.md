# Kronos — 加密货币量化研究系统

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.4.5-informational.svg)](CHANGELOG.md)

[English](README.en.md)

Kronos 是一个本地优先的加密货币量化研究系统。它提供从数据采集到策略验证的完整研究工具链，并内置了一个能主动推进研究的 AI Agent。

---

## 快速开始

**前置条件**：Python 3.12+、[uv](https://docs.astral.sh/uv/)、git

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos quickstart
uv run kronos report latest
```

一键完成：生成数据 → 注册 R-breaker 策略 → 跑回测 → 出结果。`kronos report latest` 会先给一张结果卡：用了什么数据、评估了什么、这次结论能不能信、下一步做什么。策略想法可以用 `kronos strategy draft --prompt "..."` 起草成 TOML，再按三步推进：检查配置、空跑确认、进入候选池。英文：`kronos quickstart --lang en`。

进阶使用：`kronos agent start`（交互式对话 Agent）。
Docker 用户：`docker compose up`。

---

## 能做什么

| 能力 | 说明 |
|------|------|
| **数据管线** | Binance USDM 数据拉取（K 线/Funding/OI）、Parquet 分区存储、PIT-safe 查询 |
| **因子平台** | 17 个内置因子、5 个家族、自定义因子注册、完整验证管线、Alphalens 集成 |
| **回测引擎** | 信号调度、成本模型、Freqtrade 交叉验证 |
| **AI Agent** | 多角色 LLM 驱动研究（DeepSeek-V4）、自动假设生成、工具执行、结论沉淀 |
| **Web 工作台** | 候选池看板、Agent 时间线、报告阅读、模型配置、审批中心 |
| **实验管理** | run_id 贯穿全链路、JSONL 账本、DuckDB 查询、知识库（SQLite + FTS） |

---

## 命令速查（本地 uv）

```bash
uv run kronos data status                          # 数据覆盖状态
uv run kronos data sync --symbols BTCUSDT,ETHUSDT --since 2026-01-01  # 同步公开行情，不需要 API Key
uv run kronos quickstart                            # 一键快速开始
uv run kronos report latest                         # 直接查看最新报告摘要
uv run kronos strategy draft --prompt "我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期"  # 起草策略 TOML
uv run kronos strategy init-r-breaker               # 生成 R-breaker TOML 策略配置
uv run kronos strategy smoke-test ~/.kronos/strategies/r_breaker.toml  # 用本地数据空跑确认信号能算出来
uv run kronos strategy register ~/.kronos/strategies/r_breaker.toml    # 空跑通过后进入候选池
uv run kronos agent run-once                        # 运行一轮 Agent 研究
uv run kronos agent status                          # 查看 Agent 状态
uv run pytest -m "not e2e"                          # 跑测试
```

## Docker 命令速查

Docker 内部的策略配置路径是 `/root/.kronos/...`，不要把本地 `~/.kronos/...` 路径直接套进 `docker compose run`。

```bash
docker compose up
docker compose run --rm kronos uv run kronos report latest
docker compose run --rm kronos uv run kronos strategy draft --prompt "我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期"
docker compose run --rm kronos uv run kronos strategy init-r-breaker
docker compose run --rm kronos uv run kronos strategy smoke-test /root/.kronos/strategies/r_breaker.toml
docker compose run --rm kronos uv run kronos strategy register /root/.kronos/strategies/r_breaker.toml
docker compose run --rm kronos uv run kronos agent start
```

Docker 首次构建时会出现依赖下载和安装输出。只要最后出现结果卡，就是正常流程；第一次建议先运行 `report latest`，读懂结论后再进入 Agent。

当前版本只产出研究报告、Agent 复盘、策略草案和策略配置试算，不会启动模拟盘或真实下单。实时模拟盘将在后续版本接入 Binance 实时行情和只读 API Key。

---

## 架构

```
数据层 (kronos/data)     → 行情采集、存储、PIT-safe 查询
因子层 (kronos/factor)   → 因子定义、注册、计算、验证、诊断
研究层 (kronos/research) → 回测、滚动窗口、实验管理、知识库
Agent 层 (kronos/agent)  → 多角色 LLM、工具执行、事件时间线
组合层 (kronos/portfolio) → 仓位构建、风险控制
Web 层  (kronos/web)     → FastAPI 后端、Next.js 前端
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [`CLAUDE.md`](CLAUDE.md) | 开发指南（命令、架构、不变量） |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 路线图 |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | 项目状态 |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更记录 |
