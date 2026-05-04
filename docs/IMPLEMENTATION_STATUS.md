# Kronos Implementation Status

## Summary

This document tracks the **actual implementation status** of the repository against the OpenSpec task files. It exists because task files and implementation reality can drift over time.

Status precedence for this file:

1. Current code in `kronos/`, `cli/`, and `tests/`
2. Git history in this repository
3. OpenSpec task definitions

`tasks.md` remains the design source for scope, but not the source of truth for completion.

## Module Status

### `p1-data-layer`

**Implemented**
- Project/toolchain skeleton, config loading, logging, and error hierarchy are present in [pyproject.toml](/Users/ethan/Kronos/pyproject.toml), [config.py](/Users/ethan/Kronos/kronos/common/config.py), [log.py](/Users/ethan/Kronos/kronos/common/log.py), and [errors.py](/Users/ethan/Kronos/kronos/common/errors.py).
- Data schemas, dedup keys, exchange metadata loader, partitioned Parquet store, DuckDB query layer, Binance USDM adapter, sync pipeline, and CLI are implemented under [kronos/data](/Users/ethan/Kronos/kronos/data) and [cli/main.py](/Users/ethan/Kronos/cli/main.py).
- Unit and integration coverage exists in [tests/unit](/Users/ethan/Kronos/tests/unit) and [tests/integration](/Users/ethan/Kronos/tests/integration).

**Partially implemented**
- Schema validation covers OHLC consistency and PIT timestamps, but not all requested checks such as monotonic timestamp ordering and minute-boundary alignment.
- Acceptance-style validation in `tasks.md` is not tracked as completed, even though mock end-to-end coverage exists.

**Not implemented or not yet evidenced**
- No evidence yet of live verification against Binance native 1h/4h/1d responses.
- Real Binance E2E now passes in the current environment after adding reproducible SOCKS proxy support through `httpx[socks]`.
- The E2E fetch tests are bounded to recent windows so full-suite validation does not accidentally pull unbounded historical data.

**Current status note**
- `p1-data-layer/tasks.md` has been backfilled for evidenced work, but `TODO.md` remains the live execution source of truth.

### `p1-factor-platform`

**Implemented**
- Shared factor contracts and enums exist in [types.py](/Users/ethan/Kronos/kronos/common/types.py).
- Factor metadata schema, base class, registry, materialization, bootstrap, three seed factors, validation metrics/pipeline, and factor tests exist under [kronos/factor](/Users/ethan/Kronos/kronos/factor) and [tests/unit/factor](/Users/ethan/Kronos/tests/unit/factor).

**Partially implemented**
- The shared contract exists, but the exact file layout differs from the task file: `Factor` lives in [types.py](/Users/ethan/Kronos/kronos/common/types.py), not `kronos/factor/protocol.py`.
- Validation result persistence in [reporting.py](/Users/ethan/Kronos/kronos/factor/validation/reporting.py) now writes metrics and report images under the fixed `reports/factor_validation/{factor_name}/{version}/` shape; `run_id` is stored as metadata rather than a path segment.
- Registry `status()` now exposes cache coverage and latest materialization timestamps, but the registry summary surface is still not fully aligned with the spec naming and metadata expectations.
- 基础报告元信息已经能写入版本、timeframe、universe 和 thresholds，且 Alphalens 适配与 tear sheet 图片导出已经落地。

**Current status note**
- `p1-factor-platform/tasks.md` has been backfilled for evidenced work, but `TODO.md` remains the live execution source of truth.

### `p1-backtest-engine`

**Implemented**
- The backtest module now exists under [backtest](/Users/ethan/Kronos/kronos/research/backtest) with config, engine, validators, ranking, weights, returns, costs, trades, metrics, reporting, and bridge helpers.
- The backtest path is covered by [test_backtest_engine.py](/Users/ethan/Kronos/tests/unit/research/backtest/test_backtest_engine.py), [test_backtest_metrics.py](/Users/ethan/Kronos/tests/unit/research/backtest/test_backtest_metrics.py), [test_freqtrade_bridge.py](/Users/ethan/Kronos/tests/unit/research/backtest/test_freqtrade_bridge.py), and [test_backtest_integration.py](/Users/ethan/Kronos/tests/integration/research/backtest/test_backtest_integration.py).
- A module-level acceptance mapping and known-limit document now exists at [BACKTEST_ENGINE_ACCEPTANCE.md](/Users/ethan/Kronos/docs/BACKTEST_ENGINE_ACCEPTANCE.md).

**Known limitations**
- The bridge builds the Freqtrade lookahead-analysis workflow and command, but does not execute the external tool from inside the module.
- Global config wiring and repo-wide shared-type cleanup remain future cleanup items, not blockers for the current module scope.

**Current status note**
- `p1-backtest-engine/tasks.md` is now aligned with the implemented Phase 1 scope.

### `p2-experiment-management`

**Implemented**
- The experiment management module now exists under [experiments](/Users/ethan/Kronos/kronos/research/experiments).
- It provides `run_id` generation, schema validation, append-only JSONL storage, DuckDB query rebuilding, artifact directory helpers, and recording workflows for backtest and factor validation runs.
- Standard artifact roots under `experiments/{run_id}/` are now used by the recording helpers.
- A module-level acceptance document now exists at [EXPERIMENT_MANAGEMENT_ACCEPTANCE.md](/Users/ethan/Kronos/docs/EXPERIMENT_MANAGEMENT_ACCEPTANCE.md).

**Implemented core; orchestration pending**
- Signal diagnostics and walk-forward now have shared `run_id` recording workflows. Broader cross-module adoption remains a workflow/orchestration task, not a missing ledger primitive.

**Known limitations**
- This module intentionally does not provide a remote tracking server, dashboard, or distributed scheduler.
- The current surface is still local file + DuckDB based and does not yet provide a higher-level project dashboard.

### `p2-factor-families`

**Implemented**
- The repo now has additional factor-family coverage beyond the Phase 1 seeds:
  `body_energy`, `bar_close_pressure`, `midpoint_power`, `range_chop_filter`,
  `taker_buy_ratio`, `volume_drought`, `move_density`,
  `oi_momentum`, `liquidation_flow`, `signal_persistence_density`,
  `band_position_conditioning`, `trend_pullback_tolerance`,
  `trend_pullback_entry`, and `multi_timeframe_confirmation`.
- Layer 1 now exposes public funding, OI, and liquidation-loading entrypoints for family expansion work.
- The new factors are registered as non-default candidates in bootstrap.
- The registry now exposes a validated-only default score path for downstream consumers.
- The 12 mined legacy candidates are now fully mapped to runnable or directly-backed implementations.

**Partially implemented**
- `liquidation_flow` is currently a platform scaffold and still depends on future Layer 1 liquidation data ingestion.

### `p2-signal-diagnostics`

**Implemented**
- The signal diagnostics module now exists under [diagnostics](/Users/ethan/Kronos/kronos/factor/diagnostics).
- It computes IC / ICIR time-series, grouped returns, turnover, decay, correlation matrix, and crypto-specific diagnostics.
- Its outputs can be persisted and recorded into the experiment ledger.
- A module-level acceptance document now exists at [SIGNAL_DIAGNOSTICS_ACCEPTANCE.md](/Users/ethan/Kronos/docs/SIGNAL_DIAGNOSTICS_ACCEPTANCE.md).

**Known limitations**
- Visual output is still lightweight compared with the richer validation-report style.
- Some crypto-specific diagnostics remain bounded by current Layer 1 data availability.

### `p2-walkforward`

**Implemented**
- The walk-forward module now exists under [walkforward](/Users/ethan/Kronos/kronos/research/walkforward).
- It provides nested train / validation / test split generation, lightweight per-window parameter search, cross-window decay summaries, and lookahead input audit helpers.
- Its outputs can now be persisted and recorded into the experiment ledger.
- The candidate promotion workflow in [promotion.py](/Users/ethan/Kronos/kronos/research/promotion.py) now consumes validation + walk-forward evidence under one `run_id` and updates registry status only when both gates pass.
- The same module also provides a catalog-level promotion batch entrypoint that writes skipped-candidate reporting and `promotion_batch_summary.json`.
- It also provides a market-data-backed runner that can compute candidate factor values, validation evidence, and walk-forward evidence before calling the batch workflow.
- [main.py](/Users/ethan/Kronos/cli/main.py) exposes `kronos research promote-candidates` so the local curated-data batch can be run from the CLI.
- The CLI includes a preflight mode to check candidate selection and local `klines_1m` availability before running the batch.
- Promotion batches now write a JSON summary, a human-readable Markdown report, and a decision CSV.
- Promotion outcomes, rejected decisions, and skipped candidate reasons are recorded into the research knowledge base for later search.
- A module-level acceptance document now exists at [WALKFORWARD_ACCEPTANCE.md](/Users/ethan/Kronos/docs/WALKFORWARD_ACCEPTANCE.md).

**Known limitations**
- The current search flow is a lightweight built-in equivalent rather than a full Optuna integration.
- This checkout currently has no curated local `data/` directory, so the CLI-backed market-data runner has not yet been run on local real data.

### `p3-portfolio-construction`

**Implemented**
- The portfolio-construction module now exists under [portfolio](/Users/ethan/Kronos/kronos/portfolio).
- It provides the standard `construct(...)` interface, a rule-based allocator, strategy-level score mixing, exposure control, and optional volatility-target scaling.
- A module-level acceptance document now exists at [PORTFOLIO_CONSTRUCTION_ACCEPTANCE.md](/Users/ethan/Kronos/docs/PORTFOLIO_CONSTRUCTION_ACCEPTANCE.md).

**Known limitations**
- Rebalance policy is still lightweight and not yet driven automatically by diagnostics / walk-forward outputs.
- A helper-level risk review chain now exists through the portfolio workflow, but there is not yet a fuller production workflow that consumes live diagnostics and account state.

### `p3-risk-engine`

**Implemented**
- The risk-engine module now exists under [risk](/Users/ethan/Kronos/kronos/risk).
- It provides a standalone review step with hard limits, drawdown controls, funding budget scaling, liquidity scaling, and structured risk verdicts.
- A module-level acceptance document now exists at [RISK_ENGINE_ACCEPTANCE.md](/Users/ethan/Kronos/docs/RISK_ENGINE_ACCEPTANCE.md).

**Known limitations**
- The current implementation is still a lightweight rule engine.
- It is connected to portfolio output and risk notification at helper-workflow level, but not yet to a broader execution/runtime event bus.

### `p3-notification-system`

**Implemented**
- The notification module now exists under [notify](/Users/ethan/Kronos/kronos/notify).
- It provides a structured event formatter, an in-memory notifier, a Telegram notifier, and risk-verdict notification emission.
- A module-level acceptance document now exists at [NOTIFICATION_SYSTEM_ACCEPTANCE.md](/Users/ethan/Kronos/docs/NOTIFICATION_SYSTEM_ACCEPTANCE.md).

**Known limitations**
- The current implementation focuses on the risk path and first Telegram channel only.

### `p4-knowledge-base`

**Implemented**
- The knowledge-base module now exists under [knowledge_base](/Users/ethan/Kronos/kronos/research/knowledge_base).
- It provides SQLite + FTS storage and retrieval for experiment and failure memories.
- A module-level acceptance document now exists at [KNOWLEDGE_BASE_ACCEPTANCE.md](/Users/ethan/Kronos/docs/KNOWLEDGE_BASE_ACCEPTANCE.md).

**Known limitations**
- The current implementation is still FTS-only and not yet semantic-search aware.

## Immediate Recommendation

1. Update active work tracking in `TODO.md` using this file as the factual baseline.
2. Treat `p1-data-layer` as mostly done with verification/document-sync debt.
3. Treat `p1-factor-platform` as partially done with clear spec-alignment gaps.
4. Treat `p1-backtest-engine` and `p2-experiment-management` as the next real implementation backlog.
