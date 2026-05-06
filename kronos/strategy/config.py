"""TOML strategy configuration for user-defined Kronos strategies."""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any, Literal

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kronos.agent.types import CandidateLifecycleState
from kronos.common.errors import ConfigError
from kronos.data.storage.query import TIMEFRAME_MINUTES
from kronos.factor.candidates import CandidateFactorSpec, upsert_candidate

_STRATEGIES_ENV_VAR = "KRONOS_STRATEGIES_PATH"
_DEFAULT_STRATEGY_DIR = Path.home() / ".kronos" / "strategies"
_SAFE_STRATEGY_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$")
_SAFE_SYMBOL = re.compile(r"^[A-Z0-9]{3,20}$")

SUPPORTED_STRATEGY_KINDS = ("r_breaker",)


class StrategyInfo(BaseModel):
    """Human-facing strategy identity."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable strategy id used by CLI/Agent.")
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=500)
    kind: Literal["r_breaker"] = "r_breaker"

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _SAFE_STRATEGY_ID.match(value):
            raise ValueError(
                "strategy.id must start with a letter and contain only letters, "
                "numbers, underscores, or hyphens"
            )
        return value


class StrategyUniverse(BaseModel):
    """Market universe for a strategy config."""

    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT"])
    timeframe: str = "15m"

    @field_validator("symbols")
    @classmethod
    def _validate_symbols(cls, value: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in value if symbol.strip()]
        if not normalized:
            raise ValueError("universe.symbols must contain at least one symbol")
        invalid = [symbol for symbol in normalized if not _SAFE_SYMBOL.match(symbol)]
        if invalid:
            raise ValueError(f"invalid symbols: {invalid}")
        return list(dict.fromkeys(normalized))

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, value: str) -> str:
        if value not in TIMEFRAME_MINUTES:
            valid = ", ".join(TIMEFRAME_MINUTES)
            raise ValueError(f"universe.timeframe must be one of: {valid}")
        return value


class RBreakerParams(BaseModel):
    """R-breaker parameters exposed to non-developer users."""

    model_config = ConfigDict(extra="forbid")

    atr_period: int = Field(14, ge=2, le=1000)
    volatility_multiplier: float = Field(1.5, gt=0.0, le=20.0)


class StrategyConfig(BaseModel):
    """Canonical TOML strategy config model."""

    model_config = ConfigDict(extra="forbid")

    strategy: StrategyInfo
    universe: StrategyUniverse = Field(default_factory=StrategyUniverse)
    params: RBreakerParams = Field(
        default_factory=lambda: RBreakerParams(atr_period=14, volatility_multiplier=1.5)
    )

    @model_validator(mode="after")
    def _validate_kind_params(self) -> StrategyConfig:
        if self.strategy.kind not in SUPPORTED_STRATEGY_KINDS:
            raise ValueError(f"unsupported strategy kind: {self.strategy.kind}")
        return self


def default_strategy_dir() -> Path:
    """Return the user strategy config directory."""
    override = os.environ.get(_STRATEGIES_ENV_VAR)
    if override and override.strip():
        return Path(override).expanduser()
    return _DEFAULT_STRATEGY_DIR


def default_r_breaker_config(
    *,
    strategy_id: str = "r_breaker",
    name: str = "R-breaker 日内突破",
    symbols: list[str] | None = None,
    timeframe: str = "15m",
) -> StrategyConfig:
    """Build the default R-breaker strategy config."""
    return StrategyConfig(
        strategy=StrategyInfo(
            id=strategy_id,
            name=name,
            description="基于前一日 OHLC 计算突破价位, 适合日内短线研究。",
            kind="r_breaker",
        ),
        universe=StrategyUniverse(symbols=symbols or ["BTCUSDT", "ETHUSDT"], timeframe=timeframe),
        params=RBreakerParams(atr_period=14, volatility_multiplier=1.5),
    )


def strategy_file_path(strategy_id: str, directory: Path | None = None) -> Path:
    """Return the canonical TOML path for a strategy id."""
    if not _SAFE_STRATEGY_ID.match(strategy_id):
        raise ConfigError(f"Invalid strategy id for file path: {strategy_id!r}")
    return (directory or default_strategy_dir()) / f"{strategy_id}.toml"


def load_strategy_config(path: str | Path) -> StrategyConfig:
    """Load and validate one TOML strategy config."""
    config_path = Path(path).expanduser()
    try:
        with config_path.open("rb") as file:
            raw: dict[str, Any] = tomllib.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"Strategy config not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc
    return StrategyConfig.model_validate(raw)


def write_strategy_config(
    config: StrategyConfig,
    *,
    directory: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a validated strategy config to TOML."""
    output_dir = Path(directory).expanduser() if directory is not None else default_strategy_dir()
    path = strategy_file_path(config.strategy.id, output_dir)
    if path.exists() and not overwrite:
        raise ConfigError(f"Strategy config already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json")
    path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    return path


def candidate_spec_from_strategy_config(
    config: StrategyConfig,
    *,
    migration_rank: int = 50,
) -> CandidateFactorSpec:
    """Convert a validated strategy config into the shared candidate registry shape."""
    return CandidateFactorSpec(
        candidate_id=config.strategy.id,
        family="trend_momentum",
        title=config.strategy.name,
        source_strategies=tuple(config.universe.symbols),
        migration_rank=migration_rank,
        implementation_name=config.strategy.kind,
        origin="user_config",
        lifecycle_state=CandidateLifecycleState.OBSERVE,
    )


def register_strategy_config(config: StrategyConfig, *, migration_rank: int = 50) -> CandidateFactorSpec:
    """Register or update a strategy config in the candidate registry."""
    spec = candidate_spec_from_strategy_config(config, migration_rank=migration_rank)
    upsert_candidate(spec)
    return spec
