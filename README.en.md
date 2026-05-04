# Kronos — Crypto-Native Quantitative Research System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-informational.svg)](CHANGELOG.md)

[中文](README.md)

**Kronos** is a local-first crypto quantitative research agent. It reads past research results, selects candidate strategies, proposes hypotheses, invokes deterministic validation tools, produces auditable conclusions, and displays every step in a Web workbench.

> It does not run scheduled reports, trade automatically, or generate daily briefings. It is a **researcher** — asking questions, designing experiments, validating hypotheses, persisting conclusions.

---

## Quick Start

```bash
git clone git@github.com:liuyejinghong/Kronos.git && cd Kronos
uv sync --dev
uv run kronos quickstart
```

`quickstart` generates sample data, verifies the system works, and tells you what to do next. For Chinese output: `kronos quickstart --lang zh`.

---

## What is Kronos

Kronos re-adapts legacy A-share / futures quantitative strategies for crypto markets. Currently, 12 legacy strategy candidates have completed 90-day crypto backtesting.

**How it works**: read past research → select candidates → propose hypotheses → invoke validation → read evidence → write conclusions → persist memory.

**Current capabilities**:
- Agent MVP complete, powered by DeepSeek-V4 dual models
- Web workbench: candidate pool, timeline, reports
- Full backtest engine, factor validation pipeline, walkforward validation, signal diagnostics

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

## Documentation

| Document | Description |
|------|------|
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phase roadmap and priorities |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | Project status dashboard |
| [`CLAUDE.md`](CLAUDE.md) | Developer guide (architecture, commands, invariants) |
| [`docs/CODE_REVIEW_20260504.md`](docs/CODE_REVIEW_20260504.md) | Comprehensive code review |
| [`docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md`](docs/ACCEPTANCE_20260504_AGENT_MVP_PRODUCT_REVIEW.md) | Product acceptance report |
| [`CHANGELOG.md`](CHANGELOG.md) | Version changelog |
