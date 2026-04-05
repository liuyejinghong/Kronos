"""Kronos configuration loading via Pydantic + TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from kronos.common.errors import ConfigError


class RuntimeConfig(BaseModel):
    """[runtime] section."""
    mode: str = "dev"
    data_path: str = "./data"
    log_level: str = "INFO"
    log_json: bool = True


class DataConfig(BaseModel):
    """[data] section."""
    base_path: str = "./data"
    raw_format: str = "ndjson"
    curated_format: str = "parquet"
    default_exchange: str = "binance"
    request_interval_ms: int = 200
    max_retries: int = 5


class FactorConfig(BaseModel):
    """[factor] section."""
    cache_enabled: bool = True
    default_forward_periods: list[int] = Field(default_factory=lambda: [1, 5, 20])


class BacktestConfig(BaseModel):
    """[backtest] section — placeholder, detailed in P1-BT."""
    fee_bps: float = 4.0
    slippage_bps: float = 5.0


class KronosConfig(BaseModel):
    """Root configuration model."""
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    factor: FactorConfig = Field(default_factory=FactorConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)


def load_config(path: Path | str | None = None) -> KronosConfig:
    """Load configuration from a TOML file.

    Args:
        path: Path to TOML config file. If None, returns defaults.

    Returns:
        Parsed KronosConfig.

    Raises:
        ConfigError: If the file cannot be read or parsed.
    """
    if path is None:
        return KronosConfig()

    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {config_path}: {e}") from e

    return KronosConfig.model_validate(raw)
