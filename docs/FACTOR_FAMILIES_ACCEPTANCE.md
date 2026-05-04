# Factor Families Expansion Acceptance Mapping

This document records the currently implemented scope of `p2-factor-families`.

## Current Scope

Primary implementation paths:
- `kronos/data/__init__.py`
- `kronos/factor/candidates.py`
- `kronos/factor/implementations/trend.py`
- `kronos/factor/implementations/volatility.py`
- `kronos/factor/implementations/liquidity.py`
- `kronos/factor/implementations/derivatives.py`
- `kronos/factor/implementations/mean_reversion.py`
- `kronos/factor/bootstrap.py`
- `kronos/factor/registry.py`

Primary verification paths:
- `tests/unit/factor/test_body_energy.py`
- `tests/unit/factor/test_bar_close_pressure.py`
- `tests/unit/factor/test_midpoint_power.py`
- `tests/unit/factor/test_range_chop_filter.py`
- `tests/unit/factor/test_taker_buy_ratio.py`
- `tests/unit/factor/test_volume_drought.py`
- `tests/unit/factor/test_move_density.py`
- `tests/unit/factor/test_oi_momentum.py`
- `tests/unit/factor/test_liquidation_flow.py`
- `tests/unit/factor/test_signal_persistence_density.py`
- `tests/unit/factor/test_band_position_conditioning.py`
- `tests/unit/factor/test_trend_pullback_tolerance.py`
- `tests/unit/factor/test_trend_pullback_entry.py`
- `tests/unit/factor/test_multi_timeframe_confirmation.py`
- `tests/unit/factor/test_candidates.py`
- `tests/unit/factor/test_registry.py`

## Requirement Mapping

### Four Core Families

- `trend_momentum`:
  covered by Phase 1 seeds and expanded with
  `signal_persistence_density`, `band_position_conditioning`,
  `trend_pullback_tolerance`, and `multi_timeframe_confirmation`.

- `volatility_path`:
  expanded with `body_energy`, `bar_close_pressure`, and `midpoint_power`.

- `volume_liquidity`:
  expanded with `taker_buy_ratio`, `volume_drought`, and `move_density`.

- `derivatives`:
  expanded with `oi_momentum` and a first `liquidation_flow` scaffold alongside
  the existing funding factor.

- `mean_reversion`:
  now covered by `trend_pullback_entry`.

### Legacy Hypotheses as Structured Candidates

- Structured candidate catalog:
  implemented in `kronos/factor/candidates.py` with 12 mined hypothesis entries.

- Candidate-first discipline:
  newly added family factors are registered as non-default `candidate` entries
  in bootstrap.

- Runnable or directly-backed implementations:
  all 12 current legacy candidates now point to a concrete implementation name
  or to an already-backed Phase 1 seed factor.

### Crypto-native Input Paths

- `load_funding()`, `load_oi()`, and `load_liquidations()` public Layer 1 entrypoints:
  implemented in `kronos/data/__init__.py`.

- OI-based crypto-native factor:
  implemented through `oi_momentum`.

- Taker-flow factor:
  implemented through `taker_buy_ratio`.

### Default Downstream Filtering

- Validated-only downstream score path:
  implemented in `FactorRegistry.compute_validated(...)`.

## Remaining Gaps

- `liquidation_flow` is only a scaffold because the current Layer 1 ingestion
  flow does not yet persist liquidation data.

- The remaining work is no longer cataloging. It is validation and promotion:
  these candidate factors still need later IC / walk-forward evidence before
  they can graduate beyond `candidate`.
- `validated` state still depends on later modules (`walk-forward`) to become
  fully meaningful for default downstream consumption.
