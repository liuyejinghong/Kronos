"""Factor validation pipeline — thresholds and ValidationOutcome.

ValidationOutcome is a LOCAL three-value enum (separate from FactorStatus).
It represents the conclusion of a single validation run only.

Mapping to FactorStatus (from global-module-contracts):
    pass   → factor can advance from DRAFT to CANDIDATE
    review → factor stays DRAFT, needs human review
    fail   → factor advances to REJECTED

NOTE: pass MUST NOT produce VALIDATED — that requires walk-forward (Phase 2).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, field_validator

from kronos.common.types import FactorStatus


class ValidationOutcome(StrEnum):
    """Single-run validation conclusion (local enum, not from global-module-contracts)."""

    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


# Mapping: ValidationOutcome → target FactorStatus
OUTCOME_TO_STATUS: dict[ValidationOutcome, FactorStatus] = {
    ValidationOutcome.PASS: FactorStatus.CANDIDATE,
    ValidationOutcome.REVIEW: FactorStatus.DRAFT,  # stays DRAFT
    ValidationOutcome.FAIL: FactorStatus.REJECTED,
}


class ValidationConfig(BaseModel):
    """Configuration and thresholds for a factor validation run."""

    # Forward return horizons (in bar counts, not timedeltas — 24/7 crypto)
    periods: list[int] = [1, 3, 5]

    # Number of quantile groups for grouped returns
    quantiles: int = 5

    # Thresholds for pass/review/fail adjudication
    min_mean_rank_ic: float = 0.02
    min_rank_ic_positive_ratio: float = 0.55
    min_top_minus_bottom_return: float = 0.0  # strictly > 0
    max_median_turnover: float = 0.70

    model_config = {"frozen": True}

    @field_validator("periods")
    @classmethod
    def periods_nonempty(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("periods must not be empty")
        return v

    @field_validator("quantiles")
    @classmethod
    def quantiles_min(cls, v: int) -> int:
        if v < 2:
            raise ValueError("quantiles must be >= 2")
        return v
