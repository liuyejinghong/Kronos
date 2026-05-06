"""Candidate factor registry — users define their own research candidates.

Built-in strategies (R-breaker) are automatically registered and persisted
to ``~/.kronos/candidates.json`` so they survive across process restarts
(quickstart → agent start).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from kronos.agent.types import CandidateLifecycleState

_DEFAULT_PERSIST_PATH = Path.home() / ".kronos" / "candidates.json"
_PERSIST_ENV_VAR = "KRONOS_CANDIDATES_PATH"


@dataclass(frozen=True)
class CandidateFactorSpec:
    """Structured description of a candidate factor hypothesis."""

    candidate_id: str
    family: str
    title: str
    source_strategies: tuple[str, ...]
    migration_rank: int
    implementation_name: str | None = None
    origin: str = "user"
    initial_status: str = "candidate"
    lifecycle_state: CandidateLifecycleState | None = None


# Module-level registry — lazy-loaded from disk on first access.
_registry: list[CandidateFactorSpec] | None = None
_loaded_path: Path | None = None


def candidate_store_path() -> Path:
    """Return the candidate registry path for this process."""
    override = os.environ.get(_PERSIST_ENV_VAR)
    if override and override.strip():
        return Path(override).expanduser()
    return _DEFAULT_PERSIST_PATH


def _load_from_disk() -> list[CandidateFactorSpec]:
    persist_path = candidate_store_path()
    if not persist_path.exists():
        return []
    try:
        raw = json.loads(persist_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    specs: list[CandidateFactorSpec] = []
    for entry in raw:
        try:
            lifecycle = None
            if entry.get("lifecycle_state"):
                lifecycle = CandidateLifecycleState(entry["lifecycle_state"])
            specs.append(CandidateFactorSpec(
                candidate_id=entry["candidate_id"],
                family=entry["family"],
                title=entry["title"],
                source_strategies=tuple(entry.get("source_strategies", [])),
                migration_rank=entry.get("migration_rank", 99),
                implementation_name=entry.get("implementation_name"),
                origin=entry.get("origin", "user"),
                initial_status=entry.get("initial_status", "candidate"),
                lifecycle_state=lifecycle,
            ))
        except (KeyError, ValueError):
            continue
    return specs


def _save_to_disk(specs: list[CandidateFactorSpec]) -> None:
    persist_path = candidate_store_path()
    persist_path.parent.mkdir(parents=True, exist_ok=True)
    payload: list[dict[str, object]] = []
    for s in specs:
        entry: dict[str, object] = {
            "candidate_id": s.candidate_id,
            "family": s.family,
            "title": s.title,
            "source_strategies": list(s.source_strategies),
            "migration_rank": s.migration_rank,
            "implementation_name": s.implementation_name,
            "origin": s.origin,
            "initial_status": s.initial_status,
        }
        if s.lifecycle_state is not None:
            entry["lifecycle_state"] = s.lifecycle_state.value
        payload.append(entry)
    persist_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_loaded() -> list[CandidateFactorSpec]:
    global _loaded_path, _registry
    current_path = candidate_store_path()
    if _registry is None or _loaded_path != current_path:
        _registry = _load_from_disk()
        _loaded_path = current_path
    return _registry


def register_candidate(spec: CandidateFactorSpec) -> None:
    """Register one candidate strategy. Persisted to ~/.kronos/candidates.json."""
    reg = _ensure_loaded()
    reg.append(spec)
    _save_to_disk(reg)


def list_candidate_factors() -> list[CandidateFactorSpec]:
    """Return all registered candidates (from disk cache), sorted by rank."""
    return sorted(_ensure_loaded(), key=lambda s: s.migration_rank)


def clear_candidates() -> None:
    """Remove all registered candidates (useful for testing)."""
    global _loaded_path, _registry
    _registry = []
    _loaded_path = candidate_store_path()
    _save_to_disk([])


def register_builtin_strategies() -> list[CandidateFactorSpec]:
    """Register the built-in example strategies. Idempotent — no duplicates.

    Currently includes: R-breaker intraday breakout.
    Persisted to ~/.kronos/candidates.json so strategies survive across
    quickstart → agent start process restarts.
    """
    reg = _ensure_loaded()
    existing = {c.candidate_id for c in reg}

    builtins: list[CandidateFactorSpec] = []
    if "r_breaker" not in existing:
        spec = CandidateFactorSpec(
            candidate_id="r_breaker",
            family="trend_momentum",
            title="R-breaker 日内突破",
            source_strategies=("BTCUSDT", "ETHUSDT"),
            migration_rank=1,
            implementation_name="r_breaker",
            origin="builtin",
            lifecycle_state=CandidateLifecycleState.OBSERVE,
        )
        reg.append(spec)
        builtins.append(spec)
        _save_to_disk(reg)

    return builtins
