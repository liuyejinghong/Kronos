"""Signal diagnostics public API."""

from kronos.factor.diagnostics.core import SignalDiagnosticsResult, analyze_signal_diagnostics
from kronos.factor.diagnostics.reporting import persist_signal_diagnostics_result

__all__ = [
    "SignalDiagnosticsResult",
    "analyze_signal_diagnostics",
    "persist_signal_diagnostics_result",
]
