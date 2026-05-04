# Portfolio Construction Acceptance Mapping

This document records the currently implemented scope of `p3-portfolio-construction`.

## Current Scope

Primary implementation paths:
- `kronos/portfolio/allocator.py`
- `kronos/portfolio/mixing.py`
- `kronos/portfolio/rebalance.py`
- `kronos/portfolio/__init__.py`

Primary verification path:
- `tests/unit/portfolio/test_allocator.py`

## Requirement Mapping

### Standard Layer 2 -> Layer 3 Interface

- Implemented through `construct(scores, current_positions, constraints) -> TargetPortfolio`.

### Rule-based Allocator

- Implemented through `allocator.py` with:
  - score ranking
  - sign-based long / short bucket construction
  - position cap
  - leverage cap
  - exposure control
  - optional volatility-target scaling

### Strategy-Level Mixing

- Implemented through `mix_scores(...)` in `mixing.py`.

### Rebalance Frequency Control

- Implemented at the policy-helper level through `should_rebalance(...)`.
- The allocator now carries `rebalance_frequency_ms` and `decay_hint` through
  metadata when provided by upstream callers.

### TargetPortfolio Contract

- Implemented using the shared `TargetPortfolio` dataclass with:
  - `timestamp`
  - `positions`
  - `metadata`

## Known Limitations

- The current allocator is still intentionally rule-based and simple.
  It does not implement optimisation, covariance-aware sizing, or richer
  multi-strategy hierarchical allocation.

- Rebalance frequency is represented and can be carried through metadata, but
  the allocator itself does not yet compute the rebalance cadence from
  diagnostics or walk-forward outputs automatically.

- Portfolio construction is connected to the risk-engine review step at
  helper-workflow level through `construct_with_risk_review(...)`. A fuller
  production workflow that consumes diagnostics / walk-forward outputs is still
  future work.
