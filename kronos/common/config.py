"""Kronos configuration loading via Pydantic + TOML."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from kronos.common.errors import ConfigError
from kronos.common.log import get_logger

log = get_logger("kronos.common.config")

# Directories to search for config files, relative to project root candidates.
_CONFIG_SEARCH_PATHS = (
    "configs/dev.toml",
    "config.toml",
)

# Maximum parent directories to walk upward when searching for config.
_MAX_CONFIG_WALK = 4


class RuntimeConfig(BaseModel):
    """[runtime] section."""

    mode: str = "dev"
    data_path: str = "./data"
    log_level: str = "INFO"
    log_json: bool = True
    lang: str = "zh"


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
    """Load configuration from a TOML file with auto-discovery fallback.

    Resolution order:
    1. Explicit *path* argument
    2. ``KRONOS_CONFIG`` environment variable
    3. ``./configs/dev.toml``
    4. ``../configs/dev.toml`` (walk parent dirs up to {_MAX_CONFIG_WALK} levels)
    5. ``~/.kronos/config.toml``
    6. Built-in defaults (no file needed)

    Returns:
        Parsed KronosConfig.  Never raises for missing files — falls back to
        defaults with a log message instead.

    Raises:
        ConfigError: If a config file exists but contains invalid TOML.
    """
    config_path = Path(path) if path is not None else _discover_config()

    if config_path is None:
        log.info("config.using_defaults")
        return KronosConfig()

    if not config_path.exists():
        if path is not None:
            discovered = _discover_config()
            if discovered is not None:
                log.info("config.explicit_not_found_using_discovered", requested=str(config_path), used=str(discovered))
                config_path = discovered
            else:
                log.info("config.not_found_using_defaults", path=str(config_path))
                return KronosConfig()
        else:
            log.info("config.not_found_fallback", path=str(config_path))
            return KronosConfig()

    try:
        with open(config_path, "rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {config_path}: {e}") from e

    log.debug("config.loaded", path=str(config_path))
    return KronosConfig.model_validate(raw)


def _discover_config() -> Path | None:
    """Walk the filesystem to find an existing config file."""
    env_path = os.environ.get("KRONOS_CONFIG")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    cwd = Path.cwd()
    for level in range(_MAX_CONFIG_WALK + 1):
        base = cwd if level == 0 else Path(*cwd.parts[: -level] if level < len(cwd.parts) else cwd.parts[:1])
        for search_path in _CONFIG_SEARCH_PATHS:
            candidate = base / search_path
            if candidate.exists():
                return candidate

    user_config = Path.home() / ".kronos" / "config.toml"
    if user_config.exists():
        return user_config

    return None
