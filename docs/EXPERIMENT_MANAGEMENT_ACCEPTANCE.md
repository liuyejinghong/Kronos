# Experiment Management Acceptance Mapping

This document records how `p2-experiment-management` maps its SHALL/MUST
requirements to the current implementation.

## Scope

Module: `p2-experiment-management`

Primary implementation paths:
- `kronos/research/experiments/schema.py`
- `kronos/research/experiments/ledger.py`
- `kronos/research/experiments/artifacts.py`
- `kronos/research/experiments/query.py`
- `kronos/research/experiments/workflow.py`

Primary verification path:
- `tests/unit/research/experiments/test_experiments.py`

## Requirement Mapping

### Unified Experiment Ledger Entry

- Standard ledger schema:
  Implemented in `schema.py` via `ExperimentRunRecord`.

- Minimum reproducibility triplet enforcement:
  Implemented in `ExperimentRunRecord.validate_minimum_fields()`.

- Structured `results` storage:
  Implemented in `build_run_record(...)`; results are stored as structured key/value data.

### Standardized `run_id`

- `timestamp + short hash` run identifier:
  Implemented in `generate_run_id(...)`.

- Same-second uniqueness:
  Verified in `test_generate_run_id_is_unique_with_same_second`.

### JSONL + DuckDB Ledger

- Append-only JSONL source of truth:
  Implemented in `append_run_record(...)`.

- DuckDB rebuild from JSONL:
  Implemented in `rebuild_ledger_index(...)`.

- Query interface:
  Implemented in `query_runs(...)` and `compare_runs(...)`.

### Standard Artifact Paths

- `experiments/{run_id}/` root:
  Implemented in `experiment_root(...)`.

- Backtest artifact path contract:
  Implemented in `write_backtest_artifacts(...)` for `metrics.json`,
  `config_snapshot.toml`, `equity.parquet`, and `trades.parquet`.

- Validation artifact path contract:
  Implemented in `write_validation_artifacts(...)` for `metrics.json`,
  `config_snapshot.toml`, and detailed validation report directory.

### Cross-Module `run_id` Propagation

- Backtest output chain:
  Implemented in `record_backtest_run(...)`.

- Factor validation output chain:
  Implemented in `record_validation_run(...)` and `write_validation_artifacts(...)`.

- Signal diagnostics / walk-forward shared run_id:
  Implemented in `record_signal_diagnostics_run(...)`,
  `record_walkforward_run(...)`, `write_signal_diagnostics_artifacts(...)`,
  and `write_walkforward_artifacts(...)`.

- Factor promotion shared run_id:
  Implemented in `run_factor_promotion_workflow(...)`, which records
  validation, walk-forward, and promotion-decision evidence under one run.

### Cross-Run Comparison

- Query by factors / universe / split_dates / reproducibility keys:
  Implemented in `query_runs(...)`.

- Comparison-friendly projection:
  Implemented in `compare_runs(...)`.

## Known Limitations

- Experiment management is wired for backtest, factor validation, signal
  diagnostics, walk-forward, and factor-promotion outputs. Broader adoption by
  future execution or governance workflows is still pending.

- Query filtering by result metrics currently supports ordering through
  stored numeric result summaries, but does not yet expose a richer
  dashboard-style comparison surface.

- The ledger uses local JSONL + DuckDB only. This module intentionally does
  not provide a remote tracking server, dashboard, or distributed scheduler.
