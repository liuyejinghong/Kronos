"""Experiment ledger schema and run-id helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, model_validator


def compute_config_hash(config_snapshot: dict[str, Any]) -> str:
    """Compute a stable short hash for a config snapshot."""
    payload = json.dumps(config_snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def generate_run_id(seed: dict[str, Any], *, now: datetime | None = None) -> str:
    """Generate a `timestamp + short hash` run identifier."""
    instant = now or datetime.now(UTC)
    timestamp = instant.strftime("%Y%m%dT%H%M%SZ")
    payload = json.dumps(seed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    short_hash = hashlib.sha1(payload.encode()).hexdigest()[:7]
    return f"{timestamp}-{short_hash}"


class ExperimentRunRecord(BaseModel):
    """Structured experiment ledger entry."""

    run_id: str
    git_commit: str
    data_snapshot_id: str
    config_hash: str
    factors: list[str]
    universe: list[str]
    split_dates: dict[str, Any]
    results: dict[str, Any]
    artifact_paths: dict[str, str]
    module: str
    created_at: str
    factors_key: str
    universe_key: str
    split_dates_key: str
    numeric_results_json: str

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_minimum_fields(self) -> ExperimentRunRecord:
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        if not self.git_commit:
            raise ValueError("git_commit must not be empty")
        if not self.data_snapshot_id:
            raise ValueError("data_snapshot_id must not be empty")
        if not self.config_hash:
            raise ValueError("config_hash must not be empty")
        if not self.results:
            raise ValueError("results must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        return self


def build_run_record(
    *,
    module: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    factors: list[str],
    universe: list[str],
    split_dates: dict[str, Any],
    results: dict[str, Any],
    artifact_paths: dict[str, str],
    run_id: str | None = None,
    now: datetime | None = None,
) -> ExperimentRunRecord:
    """Build a validated experiment ledger record with derived fields."""
    config_hash = compute_config_hash(config_snapshot)
    payload_seed = {
        "module": module,
        "git_commit": git_commit,
        "data_snapshot_id": data_snapshot_id,
        "config_hash": config_hash,
        "factors": sorted(factors),
        "universe": sorted(universe),
        "split_dates": split_dates,
        "results": results,
    }
    instant = now or datetime.now(UTC)
    resolved_run_id = run_id or generate_run_id(payload_seed, now=instant)

    return ExperimentRunRecord(
        run_id=resolved_run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_hash=config_hash,
        factors=factors,
        universe=universe,
        split_dates=split_dates,
        results=results,
        artifact_paths=artifact_paths,
        module=module,
        created_at=instant.isoformat(),
        factors_key=_stable_json(sorted(factors)),
        universe_key=_stable_json(sorted(universe)),
        split_dates_key=_stable_json(split_dates),
        numeric_results_json=_stable_json(_numeric_results(results)),
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _numeric_results(results: dict[str, Any]) -> dict[str, float]:
    numeric: dict[str, float] = {}
    for key, value in results.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numeric[key] = float(value)
    return numeric
