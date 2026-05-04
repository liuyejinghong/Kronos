"""Kronos shared types — single source of truth for all cross-layer contracts.

This module defines the authoritative versions of all types shared across layers.
Other modules MUST import from here, not redefine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


# === Enums ===

class FactorStatus(StrEnum):
    """Factor lifecycle status."""
    DRAFT = "draft"
    CANDIDATE = "candidate"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class Level(StrEnum):
    """Notification severity level."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class RuntimeMode(StrEnum):
    """System runtime mode."""
    DEV = "dev"
    BACKTEST = "backtest"
    LIVE = "live"


class FactorFamily(StrEnum):
    """Factor family classification."""
    TREND_MOMENTUM = "trend_momentum"
    VOLATILITY_PATH = "volatility_path"
    VOLUME_LIQUIDITY = "volume_liquidity"
    MEAN_REVERSION = "mean_reversion"
    DERIVATIVES = "derivatives"
    MARKET_STRUCTURE = "market_structure"


# === Protocols ===

@runtime_checkable
class Factor(Protocol):
    """Standard factor interface. All factor implementations MUST satisfy this protocol."""
    name: str
    family: str
    version: str
    lookback: int
    warmup_bars: int
    universe: str | list[str]
    required_columns: list[str]
    description: str

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute factor values. Warmup period rows MUST output NaN."""
        ...

    def metadata(self) -> dict[str, Any]:
        """Return factor parameters, computation description, expected direction."""
        ...


class Notifier(Protocol):
    """Notification interface."""
    def send(self, level: Level, title: str, body: str, data: dict[str, Any] | None = None) -> None: ...


# === Data Contracts ===

@dataclass
class CoverageInfo:
    """Data coverage range for a symbol/dataset pair."""
    symbol: str
    dataset: str
    min_event_time: int
    max_event_time: int
    bar_count: int
    gaps: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Constraints:
    """Portfolio construction constraints."""
    max_leverage: float = 3.0
    max_single_weight: float = 0.3
    target_volatility: float | None = None
    min_holding_bars: int = 1
    max_turnover: float = 1.0
    max_long_exposure: float = 1.0
    max_short_exposure: float = 1.0


# === Backtest Results ===

@dataclass
class BacktestMetrics:
    """Structured backtest performance metrics."""
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    total_return: float
    annual_return: float
    win_rate: float
    profit_factor: float
    trade_count: int
    avg_holding_bars: float
    turnover_mean: float
    long_short_ratio: float


@dataclass
class BacktestResult:
    """Unified backtest output."""
    run_id: str
    config_snapshot: dict[str, Any]
    git_commit: str
    data_snapshot_id: str

    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: BacktestMetrics
    factor_scores: pd.DataFrame

    weights: pd.DataFrame
    turnover: pd.DataFrame
    positions: pd.DataFrame

    tearsheet_path: str | None = None


@dataclass
class CrossValidationResult:
    """Freqtrade cross-validation result."""
    run_id: str
    engine_equity: pd.DataFrame
    freqtrade_equity: pd.DataFrame
    max_divergence: float
    mean_divergence: float
    passed: bool
    lookahead_clean: bool


@dataclass
class TargetPortfolio:
    """Target portfolio weights for execution layer."""
    timestamp: int
    positions: dict[str, float]
    metadata: dict[str, Any]
