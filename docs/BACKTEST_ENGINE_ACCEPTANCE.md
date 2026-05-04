# Backtest Engine Acceptance Mapping

This document records how `p1-backtest-engine` maps its SHALL/MUST requirements
to the current implementation.

## Scope

Module: `p1-backtest-engine`

Primary implementation paths:
- `kronos/research/backtest/config.py`
- `kronos/research/backtest/engine.py`
- `kronos/research/backtest/validators.py`
- `kronos/research/backtest/ranking.py`
- `kronos/research/backtest/weights.py`
- `kronos/research/backtest/returns.py`
- `kronos/research/backtest/costs.py`
- `kronos/research/backtest/trades.py`
- `kronos/research/backtest/metrics.py`
- `kronos/research/backtest/reporting.py`
- `kronos/research/backtest/freqtrade_bridge.py`

Primary verification paths:
- `tests/unit/research/backtest/test_backtest_engine.py`
- `tests/unit/research/backtest/test_backtest_metrics.py`
- `tests/unit/research/backtest/test_freqtrade_bridge.py`
- `tests/integration/research/backtest/test_backtest_integration.py`

## Requirement Mapping

### Backtest Engine Spec

- Main engine entry:
  Implemented in `engine.py` via `Engine(config).run(signals, data) -> BacktestResult`.

- Input contract and PIT enforcement:
  Implemented in `validators.py`.

- Standard pipeline `signal -> ranking -> target weights -> executed weights -> pnl`:
  Implemented across `ranking.py`, `weights.py`, `returns.py`, and `engine.py`.

- Delay-one-bar anti-lookahead rule:
  Implemented in `engine.py`; verified in `test_backtest_engine.py` and `test_backtest_integration.py`.

- Costs and funding hook:
  Implemented in `costs.py` and `engine.py`.

- BacktestResult output contract:
  Implemented in `types.py` and returned by `engine.py`.

### Backtest Metrics Spec

- Core return/risk metrics:
  Implemented in `metrics.py`.

- Holding/turnover stats:
  Implemented in `metrics.py`.

- Tail risk stats:
  Implemented in `metrics.py`.

- JSON-compatible tearsheet payload:
  Implemented in `reporting.py`; verified in `test_backtest_metrics.py`.

### Freqtrade Bridge Spec

- Signal export:
  Implemented in `freqtrade_bridge.py::export_signals`.

- Minimal config generation:
  Implemented in `freqtrade_bridge.py::build_freqtrade_config`.

- Lookahead-analysis workflow encapsulation:
  Implemented in `freqtrade_bridge.py::build_lookahead_analysis_command` and
  integrated into `run_cross_validation`.

- Equity comparison and threshold verdict:
  Implemented in `compare_with_freqtrade` and `run_cross_validation`.

## Known Limitations

- The lookahead-analysis workflow is encapsulated, but not executed from inside
  the module. The current bridge builds the command and expects the caller to
  provide the lookahead result payload.

- The cost model is still a parameterized approximation:
  fee + slippage + optional funding hook. It is suitable for research speed,
  not execution realism.

- The current engine is research-only:
  it does not implement order lifecycle simulation, matching, queue position,
  partial fills, or production order management.

- Shared-type cleanup remains for a later pass:
  this module currently uses its own `types.py` result objects while the repo
  still carries older shared placeholders in `kronos/common/types.py`.
