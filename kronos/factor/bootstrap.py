"""Bootstrap: central registration of all P1 seed factors.

Import this module to populate the module-level registry singleton:

    import kronos.factor.bootstrap  # noqa: F401
    from kronos.factor.registry import registry
"""

from __future__ import annotations

from kronos.common.types import FactorStatus
from kronos.factor.implementations.derivatives import (
    FundingRegimeFactor,
    LiquidationFlowFactor,
    OIMomentumFactor,
)
from kronos.factor.implementations.liquidity import (
    MoveDensityFactor,
    TakerBuyRatioFactor,
    VolumeDroughtFactor,
)
from kronos.factor.implementations.mean_reversion import TrendPullbackEntryFactor
from kronos.factor.implementations.trend import (
    ASISpreadFactor,
    BandPositionConditioningFactor,
    CMOMomentumFactor,
    MultiTimeframeConfirmationFactor,
    SignalPersistenceDensityFactor,
    TrendPullbackToleranceFactor,
)
from kronos.factor.implementations.volatility import (
    BarClosePressureFactor,
    BodyEnergyFactor,
    MidpointPowerFactor,
    RangeChopFilterFactor,
)
from kronos.factor.registry import registry
from kronos.strategy.r_breaker import RBreakerFactor

# Register seed factors with their defaults
_SEED_FACTORS = [
    (ASISpreadFactor(), True),
    (CMOMomentumFactor(), True),
    (FundingRegimeFactor(), True),
    (BodyEnergyFactor(), False),
    (BarClosePressureFactor(), False),
    (MidpointPowerFactor(), False),
    (RangeChopFilterFactor(), False),
    (TakerBuyRatioFactor(), False),
    (VolumeDroughtFactor(), False),
    (MoveDensityFactor(), False),
    (OIMomentumFactor(), False),
    (LiquidationFlowFactor(), False),
    (SignalPersistenceDensityFactor(), False),
    (BandPositionConditioningFactor(), False),
    (TrendPullbackToleranceFactor(), False),
    (TrendPullbackEntryFactor(), False),
    (MultiTimeframeConfirmationFactor(), False),
    (RBreakerFactor(), False),
]

for _factor, _as_default in _SEED_FACTORS:
    registry.register(_factor, set_default=_as_default)
    if not _as_default:
        registry.update_status(_factor.name, _factor.version, FactorStatus.CANDIDATE)

__all__ = ["registry"]
