# Kronos — Crypto-Native Quantitative Research System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-informational.svg)](CHANGELOG.md)

[中文](README.md)

Kronos is a local-first crypto quantitative research system. It provides a complete research toolchain — from data ingestion to strategy validation — plus an AI agent that actively drives the research process forward.

---

## Quick Start

**Prerequisites**: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos agent start
```

The Agent checks your environment, shows available data, and guides you through your first research cycle. Chinese: `kronos agent start --lang zh`.

---

## What It Does

| Capability | Description |
|------|------|
| **Data Pipeline** | Binance USDM ingestion (Klines/Funding/OI), Parquet storage, PIT-safe queries |
| **Factor Platform** | 17 built-in factors across 5 families, custom factor registration, full validation pipeline, Alphalens integration |
| **Backtest Engine** | Signal scheduling, cost modeling, Freqtrade cross-validation |
| **AI Agent** | Multi-role LLM-driven research (DeepSeek-V4), automated hypothesis generation, tool execution, conclusion persistence |
| **Web Workbench** | Candidate pool dashboard, agent timeline, report reader, model settings, approval center |
| **Experiment Management** | run_id threading, JSONL ledger, DuckDB queries, knowledge base (SQLite + FTS) |

---

## Common Commands

```bash
uv run kronos data status                          # Data coverage
uv run kronos data sync --symbols BTCUSDT,ETHUSDT   # Sync market data
uv run kronos quickstart                            # One-command bootstrap
uv run kronos agent run-once                        # Run one Agent research cycle
uv run kronos agent status                          # Check Agent status
uv run pytest -m "not e2e"                          # Run tests
```

---

## Architecture

```
Data Layer  (kronos/data)     → Market data ingestion, storage, PIT-safe queries
Factor Layer (kronos/factor)  → Factor definition, registration, computation, validation
Research Layer (kronos/research) → Backtesting, walkforward, experiments, knowledge base
Agent Layer (kronos/agent)    → Multi-role LLM, tool execution, event timeline
Portfolio Layer (kronos/portfolio) → Position sizing, risk management
Web Layer  (kronos/web)       → FastAPI backend, Next.js frontend
```

---

## Documentation

| Document | Description |
|------|------|
| [`CLAUDE.md`](CLAUDE.md) | Developer guide (commands, architecture) |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Roadmap |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | Project status |
| [`CHANGELOG.md`](CHANGELOG.md) | Changelog |
