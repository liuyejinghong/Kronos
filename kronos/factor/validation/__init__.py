"""Factor validation package.

Public API:
    validate_factor()          — run full validation pipeline
    ValidationResult           — result dataclass
    ValidationOutcome          — pass / review / fail enum
    ValidationConfig           — thresholds + periods config
    OUTCOME_TO_STATUS          — maps ValidationOutcome → FactorStatus
    load_prices_for_alphalens   — load multi-asset price data for Alphalens
    prepare_alphalens_factor_data — adapt factor/price data for Alphalens
    export_alphalens_report    — write tear sheet image artifacts
    persist_validation_result  — write result to disk
"""

from kronos.factor.validation.alphalens_adapter import (
    load_prices_for_alphalens,
    prepare_alphalens_factor_data,
)
from kronos.factor.validation.pipeline import ValidationResult, validate_factor
from kronos.factor.validation.reporting import export_alphalens_report, persist_validation_result
from kronos.factor.validation.thresholds import (
    OUTCOME_TO_STATUS,
    ValidationConfig,
    ValidationOutcome,
)

__all__ = [
    "OUTCOME_TO_STATUS",
    "ValidationConfig",
    "ValidationOutcome",
    "ValidationResult",
    "export_alphalens_report",
    "load_prices_for_alphalens",
    "persist_validation_result",
    "prepare_alphalens_factor_data",
    "validate_factor",
]
