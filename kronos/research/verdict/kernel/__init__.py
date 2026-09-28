"""Freqtrade kernel integration package (P08).

Only this package knows about freqtrade; the rest of kronos sees the
:class:`~kronos.research.verdict.contracts.ExecutionLedger` produced by
:mod:`kronos.research.verdict.backtest_adapter`.  The GPL dependency stays
inside the pinned venv subprocess (ruling D-20260928-003).
"""

from __future__ import annotations

from kronos.research.verdict.kernel.freqtrade_runner import (
    DEFAULT_TIMEOUT_S,
    FREQTRADE_PIN,
    FREQTRADE_VERSION,
    DataStagingError,
    FreqtradeEnvBootstrapError,
    FreqtradeEnvMissingError,
    FreqtradeKernelError,
    FreqtradeRunError,
    FreqtradeTimeoutError,
    FundingDataError,
    ResultParseError,
    RunSpec,
    ensure_freqtrade_env,
    expand_15m_to_1m,
    freqtrade_binary,
    resolve_venv,
)
from kronos.research.verdict.kernel.strategy_template import (
    STRATEGY_NAME,
    TEMPLATE_VERSION,
    render_strategy_source,
)

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "FREQTRADE_PIN",
    "FREQTRADE_VERSION",
    "STRATEGY_NAME",
    "TEMPLATE_VERSION",
    "DataStagingError",
    "FreqtradeEnvBootstrapError",
    "FreqtradeEnvMissingError",
    "FreqtradeKernelError",
    "FreqtradeRunError",
    "FreqtradeTimeoutError",
    "FundingDataError",
    "ResultParseError",
    "RunSpec",
    "ensure_freqtrade_env",
    "expand_15m_to_1m",
    "freqtrade_binary",
    "render_strategy_source",
    "resolve_venv",
]
