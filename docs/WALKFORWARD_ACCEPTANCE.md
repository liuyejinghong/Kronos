# Walkforward Acceptance Mapping

This document records the currently implemented scope of `p2-walkforward`.

## Current Scope

Primary implementation paths:
- `kronos/research/walkforward/core.py`
- `kronos/research/walkforward/reporting.py`
- `kronos/research/walkforward/__init__.py`
- `kronos/research/promotion.py`
- `cli/main.py`

Primary verification path:
- `tests/unit/research/walkforward/test_walkforward.py`
- `tests/unit/research/test_promotion.py`
- `tests/integration/test_cli.py`

## Requirement Mapping

### Nested Walk-Forward Splits

- Implemented through `generate_nested_splits(...)`.

### Window-local Parameter Search

- Implemented through `run_walkforward_validation(...)` using a lightweight
  evaluator-driven search loop.

### Parameter-Neighbourhood Stability

- Implemented through per-window `stability` summaries comparing the best trial
  with nearby candidates.

### Lookahead Leak Audit

- Implemented through `audit_lookahead_inputs(...)`.

### Cross-Window Decay

- Implemented through `cross_window_decay` in `WalkforwardResult`.

### Persistable Walk-Forward Artifacts

- Implemented through `persist_walkforward_result(...)`, which writes:
  - `summary.json`
  - `windows.csv`
  - `best_trials.json`
  - `stability.json`

### Experiment-Management Consumption

- Implemented through:
  - `write_walkforward_artifacts(...)`
  - `record_walkforward_run(...)`

This means walk-forward results can now be written into the experiment ledger
with a shared `run_id`.

### Candidate Promotion Orchestration

- Implemented through `kronos.research.promotion`.
- The workflow consumes a factor validation result and a walk-forward result
  under one `run_id`.
- A catalog-level batch entrypoint can apply the shared workflow across
  candidate specs and record skipped candidates when implementation or evidence
  is missing.
- A market-data-backed entrypoint can load or receive PIT-safe market data,
  compute factor values, derive validation and walk-forward evidence, and then
  call the catalog batch workflow.
- The CLI command `kronos research promote-candidates` runs the local-data-backed
  promotion batch using the configured curated data path.
- The same command supports `--preflight-only` to check local data readiness
  before spending time on a full run.
- It writes validation evidence, walk-forward evidence, and
  `promotion_decision.json` into the experiment artifact tree.
- It writes `promotion_batch_summary.json` for batch-level review.
- It also writes `promotion_batch_report.md` and
  `promotion_batch_decisions.csv` for human review and spreadsheet use.
- It appends ledger rows for `factor_validation`, `walkforward`, and
  `factor_promotion`.
- It records promotion decisions, rejected gates, and skipped candidate reasons
  into the research knowledge base.
- It updates the registry to `validated` only when validation and
  walk-forward gates both pass.
- A first real local-data batch was run on BTCUSDT, ETHUSDT, and SOLUSDT 1m
  data from 2026-04-24 to 2026-04-26. It evaluated 12 candidates, promoted 0,
  and skipped 0.

## Known Limitations

- The current parameter search is a lightweight in-repo equivalent and not yet
  a full Optuna integration.

- The first real-data batch is a short-window smoke result, not enough history
  for durable factor selection.
