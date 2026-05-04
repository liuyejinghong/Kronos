# Kronos Implementation Gap Analysis

## Purpose

This document reconciles three sources of truth:

1. `openspec/changes/*/tasks.md`
2. current repository code and tests
3. recent git history

Use this file to decide what is actually done, what is only partially done, and what remains backlog work. Do not rely on raw OpenSpec checkboxes alone; many are stale.

## Verification Snapshot

- `UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run pytest -q`: `385 passed`
- `UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run pytest -q -m "not e2e"`: `380 passed, 5 deselected`
- `UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run pytest -q -m e2e`: `5 passed, 380 deselected`
- `UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run mypy kronos cli`: passes, 82 source files
- `UV_CACHE_DIR=/Users/ethan/Kronos/.uv-cache uv run ruff check kronos tests cli`: passes

The former SOCKS proxy blocker is resolved by declaring `httpx[socks]` in project dependencies. Real-network E2E tests are now bounded to recent windows to avoid unbounded historical downloads.

## Status Sync Decision

- On 2026-04-09, the repository backfilled `openspec/changes/p1-data-layer/tasks.md` and `openspec/changes/p1-factor-platform/tasks.md` for items with clear code/test evidence.
- `TODO.md` remains the live execution backlog; OpenSpec task files are now coarse status mirrors, not the primary planning surface.

## Module Status

### `p1-data-layer`

Status: mostly implemented, OpenSpec task state is stale.

Evidence:
- code exists under `kronos/data/`, `kronos/common/`, `cli/`
- tests cover schemas, storage, query, sync, CLI, and sync pipeline
- git commits `a9d5082`, `d214fd7`, `f8eca6e`, `008f657` map directly to P1 data-layer milestones

Implemented:
- project skeleton, config, logging, errors, toolchain
- candle / funding / OI schemas
- exchange info loader and symbol validation
- partitioned parquet storage
- DuckDB query layer, resampling, universe load, coverage, gap detection
- Binance USDM adapter, raw NDJSON capture, incremental sync, CLI sync/status
- unit + integration coverage

Partial / divergent from tasks:
- `kronos.data.load()` and `load_universe()` exist in `kronos/data/storage/query.py`, but are not re-exported from `kronos/data/__init__.py`
- schema validators cover core OHLC and timestamp ordering, but task-level checks like minute-boundary alignment and monotonic timestamp validation are not obviously centralized at schema level
- CLI prints summaries, but explicit per-dataset progress output is still thin
- real-network E2E now passes in the current environment

Doc action:
- `openspec/changes/p1-data-layer/tasks.md` was backfilled on 2026-04-09; keep using `TODO.md` for remaining execution work

### `p1-factor-platform`

Status: core implemented, but several task items are still missing and the OpenSpec file is stale.

Evidence:
- code exists under `kronos/factor/`
- factor test suite passes under `tests/unit/factor/`

Implemented:
- shared factor protocol lives in `kronos/common/types.py`
- `BaseFactor`, `FactorMeta`, registry, materialization, cache identity
- seed factors: `asi_spread`, `cmo_momentum`, `funding_regime`
- validation metrics, thresholds, persistence
- bootstrap registration
- strong unit coverage for protocol, registry, materialization, metrics, and seed factors

Partial / divergent from tasks:
- no `kronos/factor/protocol.py`; protocol was folded into `kronos/common/types.py`
- registry API uses `list_factors()` instead of task name `list()`
- registry `status()` now exposes cache coverage and latest materialization time, but `list_factors()` still does not surface the same cache summary
- low-frequency PIT join exists through `low_freq_data`, but there is no end-to-end loader/integration layer proving funding/OI joins from real data flow
- validation persistence now writes metrics and Alphalens images under the fixed `reports/factor_validation/{factor_name}/{version}/` shape; `run_id` is kept as report metadata rather than a path segment
- test coverage is now green, and PIT-safe low-frequency join, metadata-hash isolation, base report metadata, Alphalens adaptation, and tear sheet export all have direct unit-test evidence

Doc action:
- keep P1 factor platform as `partially implemented`
- split remaining work into `signal diagnostics` and `experiment management` where appropriate, instead of leaving everything under P1
- `openspec/changes/p1-factor-platform/tasks.md` was backfilled on 2026-04-09; use `TODO.md` for the remaining gaps

### `p2-factor-families`

Status: well underway, with the current legacy candidate catalog now fully mapped.

Evidence:
- new family implementations exist under `kronos/factor/implementations/`
- public data loading entrypoints now expose funding and OI through `kronos/data/__init__.py`
- factor and query tests pass after the new family additions

Implemented:
- multiple new `volatility_path` factors (`body_energy`, `bar_close_pressure`, `midpoint_power`, `range_chop_filter`)
- multiple new `volume_liquidity` factors (`taker_buy_ratio`, `volume_drought`, `move_density`)
- multiple `trend_momentum` / `mean_reversion` candidates (`signal_persistence_density`, `band_position_conditioning`, `trend_pullback_tolerance`, `trend_pullback_entry`, `multi_timeframe_confirmation`)
- multiple `derivatives` factors (`oi_momentum`, `liquidation_flow` scaffold)
- bootstrap registration for the new factors as non-default `candidate` entries
- public Layer 1 loading entrypoints for funding, OI, and liquidation flow
- validated-only default score filtering for downstream consumers
- structured legacy candidate catalog with all 12 entries now mapped to runnable or directly-backed implementations

Partial / divergent from module intent:
- `liquidation_flow` is still only a platform scaffold until the underlying liquidation dataset is ingested by Layer 1
- the candidate catalog is now mapped, but the remaining work is promotion and validation rather than cataloging

Doc action:
- keep `p2-factor-families` as the active Layer 2 expansion module until liquidation data ingestion and later candidate promotion requirements are handled

### `p2-signal-diagnostics`

Status: core implemented.

Evidence:
- code now exists under `kronos/factor/diagnostics/`
- experiment-management wiring now accepts signal diagnostics artifacts and run records
- targeted signal diagnostics tests pass

Implemented:
- IC / Rank IC / ICIR time-series diagnostics
- grouped return monotonicity summaries
- turnover and decay diagnostics
- factor correlation matrix
- crypto-specific diagnostics for funding drag, liquidity filter, and regime split
- persistable diagnostics artifacts
- experiment-ledger recording workflow for diagnostics runs

Known limitations:
- current report outputs are structured and lightweight, not yet a richer multi-panel visual report set
- liquidation-aware diagnostics still depend on future liquidation data ingestion

### `p2-walkforward`

Status: initial validation core implemented and ledger-integrated.

Evidence:
- code now exists under `kronos/research/walkforward/`
- targeted walk-forward tests pass

Implemented:
- nested train / validation / test split generation
- lightweight parameter-search workflow for per-window evaluation
- best-trial tracking, stability summary, and cross-window decay summary
- automated lookahead input audit
- artifact persistence and experiment-ledger recording workflow
- factor-registry dual-gate promotion entrypoint requiring validation + walk-forward evidence
- higher-level candidate promotion workflow consuming validation + walk-forward evidence under one `run_id`
- catalog-level promotion batch workflow with skipped-candidate reporting
- market-data-backed promotion runner that computes factor, validation, and walk-forward evidence before calling the batch workflow
- CLI command `kronos research promote-candidates` for running a local-data-backed candidate batch
- CLI preflight, Markdown report, decision CSV, and knowledge-base recording for promotion outcomes and skipped candidates
- first short-window local-data promotion batch on BTCUSDT/ETHUSDT/SOLUSDT 1m data

Known limitations:
- the current parameter search is a lightweight in-repo equivalent, not full Optuna integration
- the first real-data promotion batch used only a short 2026-04-24 to 2026-04-26 window; longer history is needed before treating rejection results as durable factor conclusions

### `p3-portfolio-construction`

Status: first rule-based allocator implemented.

Evidence:
- code now exists under `kronos/portfolio/`
- targeted portfolio unit tests pass

Implemented:
- standard `construct(scores, current_positions, constraints)` Layer 3 entrypoint
- rule-based allocator with sign-based ranking, position cap, leverage cap, exposure control
- strategy-level score mixing
- optional volatility-target scaling
- `TargetPortfolio` contract aligned to `timestamp + positions + metadata`
- portfolio acceptance mapping document

Known limitations:
- current rebalance handling is still metadata-level and helper-level; it does not yet consume diagnostics / walk-forward outputs automatically
- a helper-level risk-engine review step exists between allocator output and execution, but no fuller production workflow is attached yet

### `p3-risk-engine`

Status: first rule-based risk review layer implemented.

Evidence:
- code now exists under `kronos/risk/`
- targeted risk-engine tests pass

Implemented:
- standalone risk review entrypoint
- hard leverage and single-asset limit enforcement
- drawdown de-risk and circuit-breaker behavior
- funding budget scaling
- liquidity-based weight reduction
- structured risk verdict output

Known limitations:
- the current engine is still lightweight and rule-based
- portfolio-construction and notification integration exist at helper-workflow level; richer runtime integration remains future work

### `p4-knowledge-base`

Status: initial memory layer implemented.

Evidence:
- code now exists under `kronos/research/knowledge_base/`
- targeted knowledge-base tests pass

Implemented:
- SQLite-backed research memory store
- FTS-based text search
- experiment-memory and failure-memory entry writing

Known limitations:
- semantic retrieval is not implemented
- automatic feeding from every experiment path is not yet attached

### `p3-notification-system`

Status: initial notification layer implemented.

Evidence:
- code now exists under `kronos/notify/`
- notifier and risk-notification tests pass

Implemented:
- shared notifier surface
- Telegram first channel
- structured event formatter
- risk-verdict notification emission

Known limitations:
- event coverage is still narrow and mostly centered on the risk-engine path
- no multi-channel routing beyond Telegram + in-memory test notifier

### `p1-backtest-engine`

Status: implemented for Phase 1 scope, with explicit known limitations.

Evidence:
- code now exists under `kronos/research/backtest/`
- unit tests exist under `tests/unit/research/backtest/`
- targeted verification passes for backtest unit tests, ruff, and mypy

Implemented:
- module skeleton, config model, result types, and public exports
- input validators and lookahead guard
- ranking, weight generation, delay-one-bar execution logic, drift handling
- bar returns, linear cost model, funding toggle hook, trade ledger generation
- metrics payload and JSON-compatible tearsheet payload
- Freqtrade bridge workflow: signal export, config generation, lookahead-workflow encapsulation, result comparison, threshold verdict
- unit + integration tests covering validators, engine path, mode constraints, bridge verdicts, and data-layer/factor-layer integration
- module acceptance mapping doc and known-limit documentation

Known limitations:
- the bridge encapsulates the Freqtrade lookahead-analysis workflow, but does not execute external Freqtrade itself; callers still provide the lookahead result payload
- no explicit config loader wiring from the global config layer yet
- current result objects remain module-local, while repo-wide shared-type cleanup can be handled later

Doc action:
- treat `openspec/changes/p1-backtest-engine/tasks.md` as completed for the current Phase 1 module scope

### `p2-experiment-management`

Status: core implemented; broader orchestration pending.

Evidence:
- code now exists under `kronos/research/experiments/`
- experiment tests exist under `tests/unit/research/experiments/`
- backtest and factor-validation artifact writers now produce standard experiment roots and ledger records

Implemented:
- run ledger schema and `run_id` generation
- append-only JSONL ledger and DuckDB rebuild/query layer
- standard artifact root under `experiments/{run_id}/`
- backtest and factor validation recording workflows
- cross-run comparison projection and unit tests

Partial / divergent from tasks:
- signal diagnostics and walk-forward are now wired into the shared `run_id` flow
- acceptance mapping and known-limit documentation are present, but broader cross-module adoption still depends on later orchestration modules

Doc action:
- keep `openspec/changes/p2-experiment-management/tasks.md` active only for the remaining cross-module integrations

## Practical Conclusions

- The current codebase is strongest in Layer 1 data ingestion/storage/query and Layer 2 factor infrastructure.
- A first usable research loop now exists across factor validation, signal diagnostics, walk-forward, backtest, and the experiment ledger.
- The remaining gap is operational use: candidate factors still need curated local market data, then a real batch run through `kronos research promote-candidates` to produce promotion/rejection decisions.
- `docs/DEVELOPMENT_PLAN.md` remains useful as a design roadmap, but live progress should be read through `PROJECT_STATUS.md`, `TODO.md`, and evidence-backed implementation docs.

## Source-of-Truth Order

When statuses disagree, use this order:

1. live code and passing tests
2. git history
3. OpenSpec tasks checkboxes
4. narrative status summaries in planning docs
