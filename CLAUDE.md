# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**默认语言：中文。所有回复、文档、代码注释、commit message 均使用中文。**

## Build & Test Commands

```
uv sync --dev                    # create/update Python 3.12 venv with dev deps
uv run pytest                    # full test suite
uv run pytest -m "not e2e"       # unit + integration only
uv run pytest --cov=kronos --cov-report=term-missing
uv run ruff check . && uv run ruff format .
uv run mypy kronos cli           # strict type checking
uv run kronos data status --config configs/dev.toml
uv run kronos data sync --symbols BTCUSDT,ETHUSDT --since 2024-01-01
```

Web frontend (separate `web/` directory):
```
cd web && npm run dev             # Next.js dev server on :3000? or :3001?
cd web && npm run typecheck       # tsc --noEmit
cd web && npm run lint            # eslint
cd web && PORT=3001 npm run dev   # if 3000 is taken
```

## Architecture Overview

Kronos is a crypto-native quantitative research and trading system. It follows a layered domain architecture:

### Layer 1 — Data (`kronos/data/`)
- **Ingestion:** `kronos/data/loaders/binance_usdm.py` fetches klines, funding rates, OI from Binance USDM futures REST API via `httpx[socks]` (SOCKS proxy support for mainland China environments).
- **Storage:** `kronos/data/storage/parquet_store.py` writes partitioned Parquet files with dedup. Raw API responses saved as NDJSON audit trail.
- **Loading:** `kronos/data/storage/query.py` provides PIT-safe `load()` and `load_universe()` with `as_of` filtering, plus `coverage()` for data status/gap detection.
- **Schemas:** `kronos/data/schemas/` defines standardized Candle, Funding, and OI record types via PyArrow schemas.

### Layer 2 — Factor (`kronos/factor/`)
- **Protocol:** All factors implement `Factor` (from `kronos/common/types.py`): `compute(df) -> pd.Series` with warmup rows outputting NaN, plus `metadata()`.
- **Registry:** Singleton `FactorRegistry` in `kronos/factor/registry.py`. Explicit registration only (no auto-scan). Keyed by (name, version). `compute_all()` does PIT-safe low-frequency joins, per-symbol compute, cross-symbol rank-normalization → long-table output.
- **Bootstrap:** `kronos/factor/bootstrap.py` registers 17 seed factors across 5 families (`TREND_MOMENTUM`, `VOLATILITY_PATH`, `VOLUME_LIQUIDITY`, `MEAN_REVERSION`, `DERIVATIVES`). Only 3 are `set_default=True` (ASI Spread, CMO Momentum, Funding Regime).
- **Implementations:** `kronos/factor/implementations/` — each factor is a class inheriting `BaseFactor` (from `kronos/factor/base.py`).
- **Validation:** `kronos/factor/validation/` includes an Alphalens adapter, IC-based metrics, configurable thresholds, and a pipeline that runs validation + walkforward as dual gates before promotion.
- **Diagnostics:** `kronos/factor/diagnostics/` computes IC/ICIR series, grouped returns, turnover, decay, correlation.

### Layer 3 — Portfolio & Risk (`kronos/portfolio/`, `kronos/risk/`)
- Rule-based allocator: ranking, position cap, leverage cap, strategy-level score mixing, volatility-target scaling.
- Risk engine sits between portfolio construction and execution, emits structured notifications.

### Research (`kronos/research/`)
- **Backtest:** Full backtest engine with config, ranking, weights, returns, costs, trade ledger, metrics, and Freqtrade cross-validation bridge.
- **Walkforward:** Nested walk-forward split engine with parameter search and lookahead audit.
- **Promotion:** Dual-gate factor promotion (validation + walkforward) with batch workflow, preflight checks, decision CSV, and knowledge base capture.
- **Experiments:** `kronos/research/experiments/` — append-only JSONL ledger + DuckDB query layer for cross-run comparison. Standard artifact layout: `experiments/{run_id}/`.
- **Knowledge Base:** SQLite + FTS in `kronos/research/knowledge_base/` for research memory.

### Agent (`kronos/agent/`)
- **Types:** NewType string identifiers (`AgentRunId`, `AgentTaskId`, etc.) and StrEnum status types in `kronos/agent/types.py`.
- **Supervisor:** `kronos/agent/supervisor.py` manages local research queue, idle scanner, single-main-task lifecycle, candidate state machine.
- **Roles:** Versioned prompt registry with active/draft states and append-only history.
- **LLM:** DeepSeek OpenAI-compatible provider adapter (`kronos/agent/llm.py`), mockable, no hardcoded model name.
- **Secrets:** `kronos/agent/secrets.py` — local backend secret store, masked status, no frontend persistence.
- **Tools:** Deterministic tool execution interface for workbench/evidence tools.
- **Events:** Append-only event timeline with levels: info, decision, warning, approval_required, error.
- **CLI:** `kronos agent propose`, `kronos agent run-once`, `kronos agent conclude`, `kronos agent status`.

### Web API (`kronos/web/`)
- FastAPI app factory (`create_app()`) with `WebAppContext` dataclass for filesystem root config.
- Routes: agent, candidates, events, settings, materials, approvals — all read from local research artifacts.
- SSE endpoint for real-time agent timeline streaming.

### CLI (`cli/main.py`)
- Typer with 4 subcommand groups: `kronos data`, `kronos research`, `kronos run`, `kronos agent`.
- Configuration loaded via `load_config()` from TOML files in `configs/`.

### Web Frontend (`web/`)
- Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, TanStack Query + Table, ECharts, Radix UI primitives.
- `web/lib/api.ts` — typed API client for the local FastAPI backend.
- Key components: `workbench-app.tsx` (shell), `candidate-table.tsx`, `agent-timeline.tsx`, `settings-panel.tsx`, `approval-center.tsx`, `materials-panel.tsx`, `run-brief-panel.tsx`.

## Critical Invariants

- **PIT-safe everywhere:** Data must be accessed with `as_of` timestamps. Never read the "latest" data directly — use the query layer's `as_of` parameter. Factor compute must not peek into future bars.
- **Factor warmup:** `compute()` must output NaN for the first `warmup_bars` rows. This is enforced by the protocol and tests.
- **run_id threading:** Every research artifact (backtest, validation, diagnostics, walkforward) must carry a `run_id` that traces back to a single experiment.
- **No auto-registration:** Factors are registered explicitly in `bootstrap.py`. Do not use `__init_subclass__` or `importlib` scanning.
- **Agent event timeline is append-only:** Never mutate or delete events after they're written. Replacements (same-run reruns) are done by `run_id` overwrite, not event-level mutation.
- **Commit trailers:** Logical decisions in commits must include structured trailers: `Constraint:`, `Rejected:`, `Directive:`, `Confidence:`, `Scope-risk:` — see global CLAUDE.md for format.

## Common Patterns

- **Config flow:** `configs/dev.toml` → `load_config()` → `KronosConfig` Pydantic model → accessed via typed attributes (`cfg.data.base_path`, `cfg.runtime.log_level`).
- **Data loading for factors:** `kronos.data.load()` or `load_universe()` → PIT-safe DataFrame → `registry.compute_all(df)` → long-table scores.
- **Experiments:** Create `experiment_root(run_id)` → write artifacts inside → append to ledger JSONL.
- **Error handling:** Use the typed exception hierarchy from `kronos/common/errors.py` — `DataError`, `FactorInputError`, `FactorRegistryError`, `BacktestError`, `ConfigError`. CLI commands catch `DataError` and translate to `typer.Exit(code=1)`.
- **Logging:** `structlog` via `kronos/common/log.py` — `get_logger("kronos.module")` returns a bound logger. Call `setup_logging()` once at entry points.

## Config

- `configs/dev.toml` — local development (DEBUG logging, local data paths)
- `configs/backtest.toml` — backtest-specific overrides
- Config sections: `[runtime]`, `[data]`, `[factor]`, `[backtest]`, `[agent.llm.deepseek]`

## OpenSpec & Planning

- `openspec/changes/` — design specs organized by priority (P0–P6). Each change has `proposal.md`, `tasks.md`, and optional `design.md`.
- `TODO.md` — the maintained execution backlog (source of truth over OpenSpec checkbox state).
- `docs/` — planning documents, acceptance criteria, architecture reviews, product control panel.
