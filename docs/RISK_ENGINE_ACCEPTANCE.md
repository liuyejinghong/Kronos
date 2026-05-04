# Risk Engine Acceptance Mapping

This document records the currently implemented scope of `p3-risk-engine`.

## Current Scope

Primary implementation paths:
- `kronos/risk/engine.py`
- `kronos/risk/__init__.py`

Primary verification path:
- `tests/unit/risk/test_risk_engine.py`

## Requirement Mapping

### Four-Layer Risk Framework

- Implemented as a structured review step through `review_target_portfolio(...)`.
- The current implementation supports factor-level / strategy-level degrade hooks,
  and portfolio-level / account-level hard limits and scaling.

### Max Leverage and Single-Asset Hard Limits

- Implemented in `_apply_hard_limits(...)`.

### Drawdown Reduction and Circuit Breaker

- Implemented in `_apply_drawdown_controls(...)`.

### Funding Cost Budget Monitoring

- Implemented in `_apply_funding_budget(...)`.

### Liquidity-Based Weight Reduction

- Implemented in `_apply_liquidity_scaling(...)`.

### Structured Risk Verdict

- Implemented through `RiskVerdict` with:
  - `status`
  - adjusted `TargetPortfolio`
  - reasons
  - metrics
  - notification level

## Known Limitations

- The current risk engine is still rule-based and intentionally lightweight.
  It does not yet implement a richer account-state model or broker margin
  simulation. It does expose risk-notification emission for meaningful verdicts,
  but does not yet provide a broader runtime event bus.

- The factor-level and strategy-level inputs are currently simple flags rather than
  deeper diagnostics-derived confidence surfaces.
