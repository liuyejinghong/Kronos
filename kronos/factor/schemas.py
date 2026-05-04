"""Factor metadata schema.

FactorMeta is the Pydantic model that validates and carries all static
factor metadata required by the Factor Protocol.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from kronos.common.types import FactorFamily  # noqa: TC001 — needed at runtime by Pydantic


class FactorMeta(BaseModel):
    """Static metadata for a registered factor.

    Every field maps directly to an attribute required by the Factor Protocol
    (kronos.common.types.Factor).  Instances are created once per factor class
    and treated as immutable after construction.
    """

    name: str
    family: FactorFamily
    version: str
    lookback: int
    warmup_bars: int
    universe: str | list[str]
    required_columns: list[str]
    description: str

    model_config = {"frozen": True}

    @field_validator("lookback")
    @classmethod
    def lookback_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("lookback must be > 0")
        return v

    @field_validator("warmup_bars")
    @classmethod
    def warmup_gte_lookback(cls, v: int, info: object) -> int:
        data = getattr(info, "data", {})
        lookback = data.get("lookback", 0)
        if v < lookback:
            raise ValueError(f"warmup_bars ({v}) must be >= lookback ({lookback})")
        return v

    @field_validator("version")
    @classmethod
    def version_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("version must not be empty")
        return v
