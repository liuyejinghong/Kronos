# Signal Diagnostics Acceptance Mapping

This document records the currently implemented scope of `p2-signal-diagnostics`.

## Current Scope

Primary implementation paths:
- `kronos/factor/diagnostics/core.py`
- `kronos/factor/diagnostics/reporting.py`
- `kronos/factor/diagnostics/__init__.py`

Primary verification path:
- `tests/unit/factor/test_signal_diagnostics.py`

## Requirement Mapping

### IC / ICIR Time-Series Diagnostics

- Implemented through `analyze_signal_diagnostics(...)`:
  the diagnostics output includes timestamped IC / Rank IC series, rolling mean,
  rolling std, ICIR, and rolling positive ratio.

### Grouped Return Monotonicity

- Implemented through grouped return summaries for quintile and decile style
  buckets with top-minus-bottom spread and monotonicity flags.

### Turnover / Decay Diagnostics

- Implemented through:
  - quantile-membership turnover summaries
  - decay summary by holding period

### Correlation Matrix

- Implemented through factor correlation matrix generation for bundled signals.

### Crypto-Specific Diagnostics

- Funding drag:
  implemented when `funding_rate` is present in the price frame.

- Liquidity filter:
  implemented through high/low-liquidity rank-IC split.

- Regime split:
  implemented through high/low volatility regime rank-IC split.

### Persistable Structured Artifacts

- Implemented through `persist_signal_diagnostics_result(...)`, which writes:
  - `summary.json`
  - `ic_timeseries.csv`
  - `decay.csv`
  - `correlation_matrix.csv`
  - `correlation_heatmap.png`

### Experiment-Management Consumption

- Implemented through:
  - `write_signal_diagnostics_artifacts(...)`
  - `record_signal_diagnostics_run(...)`

This means diagnostics results can now be written into the experiment ledger
with a shared `run_id`.

## Known Limitations

- The current diagnostics module is focused on structured quantitative outputs
  and a basic heatmap artifact. It does not yet generate a richer multi-panel
  report comparable to the Alphalens-backed validation report style.

- Crypto-specific diagnostics currently rely on fields already present in the
  input price frame. They do not yet consume a dedicated liquidation dataset or
  more advanced regime classifiers.
