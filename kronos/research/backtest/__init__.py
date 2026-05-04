"""Research backtest engine public API.

Phase 1 scope:
- vectorised research engine only
- no execution/order-management semantics
- no portfolio optimisation
"""

from kronos.research.backtest.config import BacktestConfig, CrossValidationConfig
from kronos.research.backtest.engine import Engine
from kronos.research.backtest.freqtrade_bridge import (
    build_freqtrade_config,
    build_lookahead_analysis_command,
    compare_with_freqtrade,
    export_signals,
    run_cross_validation,
)
from kronos.research.backtest.types import BacktestMetrics, BacktestResult, CrossValidationResult

__all__ = [
    "BacktestConfig",
    "BacktestMetrics",
    "BacktestResult",
    "CrossValidationConfig",
    "CrossValidationResult",
    "Engine",
    "build_freqtrade_config",
    "build_lookahead_analysis_command",
    "compare_with_freqtrade",
    "export_signals",
    "run_cross_validation",
]
