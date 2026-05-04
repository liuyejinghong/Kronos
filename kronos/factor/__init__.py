"""Kronos Factor Platform — Layer 2.

Public API surface:

    from kronos.factor.base import BaseFactor
    from kronos.factor.registry import registry
    from kronos.factor.schemas import FactorMeta
    import kronos.factor.bootstrap  # registers seed factors
"""

from __future__ import annotations

from kronos.factor.base import BaseFactor
from kronos.factor.registry import FactorRegistry, registry
from kronos.factor.schemas import FactorMeta

__all__ = ["BaseFactor", "FactorMeta", "FactorRegistry", "registry"]
