# Kronos — Crypto-Native Quantitative Research System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.4.10-informational.svg)](CHANGELOG.md)

[中文](README.md)

Kronos is a local-first crypto quantitative research system. It provides a complete research toolchain — from data ingestion to strategy validation — plus an AI agent that actively drives the research process forward.

---

## Quick Start

**Prerequisites**: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos quickstart
uv run kronos report latest
```

One command: generate data → register R-breaker → run backtest → see results. `kronos report latest` now starts with a result card: data used, strategy evaluated, whether the conclusion is reliable, and the next step. `kronos strategy draft --prompt "..."` can draft R-breaker ideas into TOML, then guide you through three gates: check config, dry run, and enter the candidate pool. Chinese: `kronos quickstart --lang zh`.

Advanced: `kronos agent start` (interactive conversational Agent).

---

## What It Does

| Capability | Description |
|------|------|
| **Data Pipeline** | Binance USDM ingestion (Klines/Funding/OI), Parquet storage, PIT-safe queries |
| **Factor Platform** | 17 built-in factors across 5 families, custom factor registration, full validation pipeline, Alphalens integration |
| **Backtest Engine** | Signal scheduling, cost modeling, Freqtrade cross-validation |
| **AI Agent** | Multi-role LLM-driven research (DeepSeek-V4), automated hypothesis generation, tool execution, conclusion persistence |
| **Web Workbench** | Candidate pool dashboard, agent timeline, report reader, testnet paper status, Agent memory control, model settings, approval center |
| **Experiment Management** | run_id threading, JSONL ledger, DuckDB queries, knowledge base (SQLite + FTS) |

---

## Common Commands (local uv)

```bash
uv run kronos data status                          # Data coverage
uv run kronos data sync --symbols BTCUSDT,ETHUSDT --since 2026-01-01  # Sync public market data, no API key
uv run kronos quickstart                            # One-command bootstrap
uv run kronos report latest                         # Read latest report summary
uv run kronos report observation-plan               # Generate a read-only observation plan from a research report
uv run kronos paper credentials status              # Inspect Binance testnet credential status
uv run kronos paper credentials set --api-key "$BINANCE_TESTNET_API_KEY"  # Secret comes from BINANCE_TESTNET_API_SECRET or hidden prompt
uv run kronos paper preflight --mock-testnet        # Safely check the paper-trading path
uv run kronos paper start --mock-testnet            # Verify the testnet order flow locally
uv run kronos strategy draft --prompt "I want BTCUSDT R-breaker intraday breakout on 15m"  # Draft strategy TOML
uv run kronos strategy init-r-breaker               # Create R-breaker TOML strategy config
uv run kronos strategy smoke-test ~/.kronos/strategies/r_breaker.toml  # Dry-run local strategy logic
uv run kronos strategy register ~/.kronos/strategies/r_breaker.toml    # Enter candidate pool after dry run passes
uv run kronos agent run-once                        # Run one Agent research cycle
uv run kronos agent status                          # Check Agent status
uv run pytest -m "not e2e"                          # Run tests
```

## Docker Commands

Inside Docker, strategy configs live under `/root/.kronos/...`. Do not paste the local `~/.kronos/...` path into `docker compose run`.

```bash
docker compose up
docker compose run --rm kronos uv run kronos report latest
docker compose run --rm kronos uv run kronos report observation-plan
docker compose run --rm kronos uv run kronos paper credentials status
docker compose run --rm -e BINANCE_TESTNET_API_KEY -e BINANCE_TESTNET_API_SECRET kronos uv run kronos paper credentials set
docker compose run --rm kronos uv run kronos paper preflight --mock-testnet
docker compose run --rm kronos uv run kronos strategy draft --prompt "I want BTCUSDT R-breaker intraday breakout on 15m"
docker compose run --rm kronos uv run kronos strategy init-r-breaker
docker compose run --rm kronos uv run kronos strategy smoke-test /root/.kronos/strategies/r_breaker.toml
docker compose run --rm kronos uv run kronos strategy register /root/.kronos/strategies/r_breaker.toml
docker compose run --rm kronos uv run kronos agent start
```

The first Docker build may show dependency download and install output. If the run ends with a result card, the flow is normal. On first use, read `report latest` before entering the Agent.

This version adds Agent Memory Control after the testnet paper Web status release: the Web workbench "Memory" view shows the current version, acceptance target, latest successful run, source documents, recent decisions, lessons, a copyable handoff pack, and memory drift checks. v0.4.9 completed one real Binance testnet end-to-end acceptance run, and the Web workbench still shows paper status, recent orders, fills, and reports in read-only mode. Real Binance testnet orders require explicit testnet credentials and an eligible observation candidate; fill evidence comes from testnet trade details, and failures write local status, reports, and error ledgers. Kronos still avoids real funds and mainnet live trading. `paper` only accepts observation-plan metadata generated by Kronos, and restarting after `paper stop` requires explicit `--reset-stopped`.

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
