"""Candidate factor registry — users define their own research candidates.

No strategies are pre-loaded. New users start with an empty candidate pool and
define their own candidates via ``register_candidate()`` or a config file.
"""

from __future__ import annotations

from dataclasses import dataclass

from kronos.agent.types import CandidateLifecycleState


@dataclass(frozen=True)
class CandidateFactorSpec:
    """Structured description of a candidate factor hypothesis.

    Users create these to define what strategies they want Kronos to research.
    """

    candidate_id: str
    family: str
    title: str
    source_strategies: tuple[str, ...]
    migration_rank: int
    implementation_name: str | None = None
    origin: str = "user"
    initial_status: str = "candidate"
    lifecycle_state: CandidateLifecycleState | None = None


# Module-level registry — populated by the user at startup.
_registry: list[CandidateFactorSpec] = []


def register_candidate(spec: CandidateFactorSpec) -> None:
    """Register one candidate strategy for Kronos to research.

    Example::

        from kronos.factor.candidates import CandidateFactorSpec, register_candidate
        register_candidate(CandidateFactorSpec(
            "my_trend_strategy", "trend_momentum", "我的趋势策略",
            ("BTCUSDT",), 1, "my_trend_impl",
        ))

    Call before ``kronos agent start`` or ``kronos research ...``.
    """
    _registry.append(spec)


def list_candidate_factors() -> list[CandidateFactorSpec]:
    """Return all registered candidate strategies in priority order."""
    return sorted(_registry, key=lambda s: s.migration_rank)


def clear_candidates() -> None:
    """Remove all registered candidates (useful for testing)."""
    _registry.clear()


def register_builtin_strategies() -> list[CandidateFactorSpec]:
    """Register the built-in example strategies. Idempotent — no duplicates.

    Currently includes: R-breaker intraday breakout.
    Call once at startup (agent start or quickstart).
    """
    existing = {c.candidate_id for c in _registry}

    builtins: list[CandidateFactorSpec] = []
    if "r_breaker" not in existing:
        spec = CandidateFactorSpec(
            candidate_id="r_breaker",
            family="mean_reversion",
            title="R-breaker 日内突破",
            source_strategies=("BTCUSDT", "ETHUSDT"),
            migration_rank=1,
            implementation_name="r_breaker",
            origin="builtin",
            lifecycle_state=CandidateLifecycleState.OBSERVE,
        )
        _registry.append(spec)
        builtins.append(spec)

    return builtins
