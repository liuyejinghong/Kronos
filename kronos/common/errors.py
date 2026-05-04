"""Kronos unified exception hierarchy."""


class KronosError(Exception):
    """Base exception for all Kronos errors."""


class DataError(KronosError):
    """Errors related to data loading, validation, or storage."""


class SchemaError(DataError):
    """Data schema validation failures."""


class IngestionError(DataError):
    """Data ingestion/sync failures."""


class FactorError(KronosError):
    """Errors related to factor computation or validation."""


class FactorInputError(FactorError):
    """Factor input validation failures (missing columns, wrong types)."""


class FactorRegistryError(FactorError):
    """Factor registry errors (duplicate registration, not found)."""


class FactorVersionError(FactorRegistryError):
    """Factor version not found or default version not configured."""


class BacktestError(KronosError):
    """Errors related to backtesting."""


class ConfigError(KronosError):
    """Configuration loading or validation errors."""


class ExecutionError(KronosError):
    """Errors related to order execution."""
