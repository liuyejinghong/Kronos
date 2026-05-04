"""BaseFactor: abstract base class for all Kronos factor implementations.

This class satisfies the Factor Protocol defined in kronos.common.types.
It does NOT redefine the protocol — it provides concrete helpers so that
individual factor implementations stay focused on their computation logic.

All factor implementations MUST subclass BaseFactor.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, ClassVar

from kronos.common.errors import FactorInputError
from kronos.common.types import (  # noqa: F401 (re-exported for implementers)
    Factor,
    FactorFamily,
    FactorStatus,
)
from kronos.factor.schemas import FactorMeta

if TYPE_CHECKING:
    import pandas as pd

# Required columns that every input DataFrame must have regardless of factor
_MANDATORY_COLUMNS = {"event_time", "available_at", "symbol"}


class BaseFactor(abc.ABC):
    """Abstract base class implementing the Factor Protocol.

    Subclasses MUST define:
      - Class-level attributes: name, family, version, lookback, warmup_bars,
        universe, required_columns, description
      - _compute(df): the actual computation logic (returns raw Series)
      - metadata(): dict of parameters that affect computation output

    Subclasses SHOULD NOT touch time semantics — input is already PIT-safe.
    """

    # --- Protocol attributes (declared here for type-checker satisfaction) ---
    name: str
    family: str | FactorFamily
    version: str
    lookback: int
    warmup_bars: int
    universe: str | list[str]
    required_columns: ClassVar[list[str]]
    description: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Validate metadata completeness at class definition time (not instance).
        # Abstract subclasses (intermediate ABCs) are allowed to skip this.
        if abc.ABC not in cls.__bases__ and not getattr(cls, "__abstractmethods__", None):
            _check_class_attrs(cls)

    # --- Public API required by Factor Protocol ---

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute factor values for the given PIT-safe DataFrame.

        Validates input, delegates to _compute(), then enforces output contract:
        - Same length and index as input
        - Warmup rows set to NaN
        """
        self.validate_input(df)
        result = self._compute(df)
        result = self._enforce_warmup(result)
        if len(result) != len(df) or not result.index.equals(df.index):
            raise ValueError(
                f"Factor {self.name} returned a Series with mismatched length or index"
            )
        return result

    @abc.abstractmethod
    def _compute(self, df: pd.DataFrame) -> pd.Series:
        """Implement the actual factor computation.

        Input df is already validated and PIT-safe.
        Warmup enforcement happens after this method returns.
        """

    @abc.abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Return a dict of parameters that affect computation output.

        Used to generate params_hash for cache identity.
        MUST be deterministic: same parameters → identical dict every call.
        MUST NOT include universe, time ranges, or other external conditions.
        """

    # --- Helpers ---

    def validate_input(self, df: pd.DataFrame) -> None:
        """Raise FactorInputError if df is missing required columns."""
        required = _MANDATORY_COLUMNS | set(self.required_columns)
        missing = required - set(df.columns)
        if missing:
            raise FactorInputError(
                f"Factor '{self.name}' is missing required columns: {sorted(missing)}"
            )

    def _enforce_warmup(self, series: pd.Series) -> pd.Series:
        """Set the first (warmup_bars - 1) rows to NaN.

        Uses warmup_bars as the canonical warm-up length.
        """
        n = self.warmup_bars - 1
        if n <= 0:
            return series
        result = series.copy()
        if len(result) > 0:
            result.iloc[:n] = float("nan")
        return result

    @property
    def meta(self) -> FactorMeta:
        """Return a validated FactorMeta instance for this factor."""
        return FactorMeta(
            name=self.name,
            family=FactorFamily(self.family),
            version=self.version,
            lookback=self.lookback,
            warmup_bars=self.warmup_bars,
            universe=self.universe,
            required_columns=self.required_columns,
            description=self.description,
        )


# ---- runtime Protocol compliance check ----

def _check_class_attrs(cls: type) -> None:
    """Verify that a concrete factor class has all required protocol attributes."""
    required_attrs = (
        "name", "family", "version", "lookback",
        "warmup_bars", "universe", "required_columns", "description",
    )
    missing = [attr for attr in required_attrs if not hasattr(cls, attr)]
    if missing:
        raise TypeError(
            f"Factor class '{cls.__name__}' is missing required attributes: {missing}. "
            "All Factor implementations must declare these as class-level attributes."
        )


# Ensure BaseFactor itself satisfies the Factor Protocol at import time
def _assert_protocol() -> None:
    assert issubclass(BaseFactor, Factor), "BaseFactor does not satisfy Factor Protocol"  # type: ignore[misc]
