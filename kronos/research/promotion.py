"""Candidate factor promotion workflow.

This module consumes real validation and walk-forward outputs, records the
evidence under a shared experiment run, and applies the registry state change
only when both gates pass.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pandas as pd

from kronos.common.errors import (
    BacktestError,
    DataError,
    FactorInputError,
    FactorRegistryError,
    FactorVersionError,
)
from kronos.common.types import FactorStatus
from kronos.data import load_universe
from kronos.factor.candidates import list_candidate_factors
from kronos.factor.validation.pipeline import validate_factor
from kronos.factor.validation.thresholds import ValidationConfig, ValidationOutcome
from kronos.research.experiments.artifacts import (
    experiment_root,
    write_validation_artifacts,
    write_walkforward_artifacts,
)
from kronos.research.experiments.ledger import append_run_record, rebuild_ledger_index
from kronos.research.experiments.schema import build_run_record
from kronos.research.knowledge_base import add_experiment_entry, add_failure_entry
from kronos.research.walkforward import audit_lookahead_inputs, run_walkforward_validation

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from kronos.factor.candidates import CandidateFactorSpec
    from kronos.factor.registry import FactorRegistry
    from kronos.factor.validation.pipeline import ValidationResult
    from kronos.research.walkforward.core import WalkforwardResult


@dataclass(frozen=True)
class PromotionCriteria:
    """Configurable gates for candidate -> validated promotion."""

    min_walkforward_test_mean: float = 0.0
    min_positive_test_window_ratio: float = 0.5
    max_decay_mean: float | None = None
    require_leak_audit_passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromotionDecision:
    """Structured promotion decision and evidence summary."""

    factor_name: str
    factor_version: str
    promoted: bool
    validation_passed: bool
    walkforward_passed: bool
    target_status: FactorStatus
    reasons: list[str]
    metrics: dict[str, Any]
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "factor_version": self.factor_version,
            "run_id": self.run_id,
            "promoted": self.promoted,
            "validation_passed": self.validation_passed,
            "walkforward_passed": self.walkforward_passed,
            "target_status": str(self.target_status),
            "reasons": self.reasons,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class CandidatePromotionBatchResult:
    """Summary of a catalog-level promotion batch."""

    batch_id: str
    decisions: list[PromotionDecision]
    skipped: list[dict[str, str]]
    artifact_path: str | None = None
    artifact_paths: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        promoted = sum(decision.promoted for decision in self.decisions)
        return {
            "evaluated": len(self.decisions),
            "promoted": promoted,
            "not_promoted": len(self.decisions) - promoted,
            "skipped": len(self.skipped),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "summary": self.summary(),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "skipped": self.skipped,
            "artifact_path": self.artifact_path,
            "artifact_paths": self.artifact_paths,
        }


def evaluate_factor_promotion(
    *,
    factor_name: str,
    factor_version: str,
    validation_result: ValidationResult,
    walkforward_result: WalkforwardResult,
    criteria: PromotionCriteria | None = None,
    run_id: str | None = None,
) -> PromotionDecision:
    """Evaluate whether a candidate factor has enough evidence to become validated."""
    resolved_criteria = criteria or PromotionCriteria()
    reasons: list[str] = []

    validation_passed = validation_result.outcome == ValidationOutcome.PASS
    if not validation_passed:
        reasons.append(f"validation outcome is {validation_result.outcome}")

    walkforward_passed, walkforward_reasons, walkforward_metrics = _evaluate_walkforward_gate(
        walkforward_result,
        resolved_criteria,
    )
    reasons.extend(walkforward_reasons)

    promoted = validation_passed and walkforward_passed
    target_status = _target_status(validation_result.outcome, promoted)
    if promoted:
        reasons.append("validation and walk-forward gates passed")

    metrics: dict[str, Any] = {
        "validation_outcome": str(validation_result.outcome),
        "mean_rank_ic": float(validation_result.mean_rank_ic),
        "rank_ic_positive_ratio": float(validation_result.rank_ic_positive_ratio),
        "top_minus_bottom": float(validation_result.top_minus_bottom),
        "median_turnover": float(validation_result.median_turnover),
        **walkforward_metrics,
    }

    return PromotionDecision(
        factor_name=factor_name,
        factor_version=factor_version,
        promoted=promoted,
        validation_passed=validation_passed,
        walkforward_passed=walkforward_passed,
        target_status=target_status,
        reasons=reasons,
        metrics=metrics,
        run_id=run_id,
    )


def run_candidate_promotion_batch(
    *,
    registry: FactorRegistry,
    validation_results: Mapping[str, ValidationResult],
    walkforward_results: Mapping[str, WalkforwardResult],
    base_path: str | Path,
    batch_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    universe: list[str],
    split_dates: dict[str, Any],
    candidate_specs: Sequence[CandidateFactorSpec] | None = None,
    factor_versions: Mapping[str, str] | None = None,
    timeframe: str | None = None,
    criteria: PromotionCriteria | None = None,
) -> CandidatePromotionBatchResult:
    """Run promotion decisions for a candidate catalog batch.

    The caller supplies real validation and walk-forward outputs keyed by
    implementation factor name. Missing implementation or missing evidence is
    recorded as skipped instead of silently failing the batch.
    """
    specs = list(candidate_specs) if candidate_specs is not None else list_candidate_factors()
    versions = factor_versions or {}
    decisions: list[PromotionDecision] = []
    skipped: list[dict[str, str]] = []

    for spec in specs:
        factor_name = spec.implementation_name
        if factor_name is None:
            skipped.append(_skip(spec.candidate_id, "", "missing_implementation"))
            continue
        if factor_name not in validation_results:
            skipped.append(_skip(spec.candidate_id, factor_name, "missing_validation_result"))
            continue
        if factor_name not in walkforward_results:
            skipped.append(_skip(spec.candidate_id, factor_name, "missing_walkforward_result"))
            continue

        try:
            factor = _resolve_factor_for_promotion(registry, factor_name, versions)
        except FactorVersionError:
            skipped.append(_skip(spec.candidate_id, factor_name, "unregistered_factor"))
            continue

        run_id = f"{batch_id}-{_safe_run_id_segment(spec.candidate_id)}"
        try:
            decision = run_factor_promotion_workflow(
                registry=registry,
                factor_name=factor.name,
                factor_version=factor.version,
                validation_result=validation_results[factor.name],
                walkforward_result=walkforward_results[factor.name],
                base_path=base_path,
                run_id=run_id,
                git_commit=git_commit,
                data_snapshot_id=data_snapshot_id,
                config_snapshot={
                    **config_snapshot,
                    "batch_id": batch_id,
                    "candidate_id": spec.candidate_id,
                    "candidate_title": spec.title,
                },
                universe=universe,
                split_dates=split_dates,
                timeframe=timeframe,
                criteria=criteria,
            )
        except FactorRegistryError as exc:
            skipped.append(_skip(spec.candidate_id, factor_name, f"promotion_error:{exc}"))
            continue
        decisions.append(decision)

    batch_root = experiment_root(base_path, batch_id)
    summary_path = batch_root / "promotion_batch_summary.json"
    report_path = batch_root / "promotion_batch_report.md"
    decisions_csv_path = batch_root / "promotion_batch_decisions.csv"
    result = CandidatePromotionBatchResult(
        batch_id=batch_id,
        decisions=decisions,
        skipped=skipped,
        artifact_path=str(summary_path),
        artifact_paths={
            "summary": str(summary_path),
            "report": str(report_path),
            "decisions_csv": str(decisions_csv_path),
        },
    )
    summary_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _write_batch_report(result, report_path)
    _write_batch_decisions_csv(result, decisions_csv_path)
    _record_batch_memory(result, base_path=base_path)
    return result


def run_market_data_promotion_batch(
    *,
    registry: FactorRegistry,
    symbols: list[str],
    data_base_path: str | Path,
    output_base_path: str | Path,
    batch_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    candidate_specs: Sequence[CandidateFactorSpec] | None = None,
    factor_versions: Mapping[str, str] | None = None,
    timeframe: str = "1h",
    since: str | int | None = None,
    until: str | int | None = None,
    validation_symbol: str | None = None,
    validation_config: ValidationConfig | None = None,
    criteria: PromotionCriteria | None = None,
    train_size: int = 24,
    validation_size: int = 8,
    test_size: int = 8,
    step_size: int | None = None,
    market_data: pd.DataFrame | None = None,
) -> CandidatePromotionBatchResult:
    """Run a market-data-backed promotion batch for candidate factors.

    This is the first operational layer above the generic promotion workflow:
    it loads or receives PIT-safe market data, computes candidate factor values,
    derives validation and walk-forward evidence, then delegates final state
    decisions to `run_candidate_promotion_batch`.
    """
    if not symbols:
        raise DataError("market-data promotion batch requires at least one symbol")

    data = (
        market_data.copy()
        if market_data is not None
        else load_universe(
            symbols,
            base_path=Path(data_base_path),
            timeframe=timeframe,
            since=since,
            until=until,
        )
    )
    if data.empty:
        raise DataError("market-data promotion batch found no market data")

    specs = list(candidate_specs) if candidate_specs is not None else list_candidate_factors()
    versions = factor_versions or {}
    selected_symbol = validation_symbol or symbols[0]
    validation_results: dict[str, ValidationResult] = {}
    walkforward_results: dict[str, WalkforwardResult] = {}

    for spec in specs:
        factor_name = spec.implementation_name
        if factor_name is None:
            continue
        try:
            factor = _resolve_factor_for_promotion(registry, factor_name, versions)
        except FactorVersionError:
            continue
        missing_columns = [column for column in factor.required_columns if column not in data.columns]
        if missing_columns:
            continue

        try:
            factor_scores = registry.compute_all(
                data,
                factor_names=[factor.name],
                version_map={factor.name: factor.version},
            )
        except FactorInputError:
            continue

        aligned = _align_factor_scores_for_symbol(
            factor_scores,
            data,
            selected_symbol,
        )
        if len(aligned) < train_size + validation_size + test_size:
            continue

        validation_results[factor.name] = validate_factor(
            aligned["factor_value"].reset_index(drop=True),
            aligned["close"].reset_index(drop=True),
            aligned["available_at"].reset_index(drop=True),
            config=validation_config,
        )
        try:
            walkforward_results[factor.name] = _run_factor_market_walkforward(
                aligned,
                train_size=train_size,
                validation_size=validation_size,
                test_size=test_size,
                step_size=step_size,
            )
        except BacktestError:
            validation_results.pop(factor.name, None)
            continue

    min_time = int(data["event_time"].min()) if "event_time" in data.columns else None
    max_time = int(data["event_time"].max()) if "event_time" in data.columns else None
    return run_candidate_promotion_batch(
        registry=registry,
        validation_results=validation_results,
        walkforward_results=walkforward_results,
        base_path=output_base_path,
        batch_id=batch_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot={
            **config_snapshot,
            "timeframe": timeframe,
            "since": since,
            "until": until,
            "validation_symbol": selected_symbol,
            "train_size": train_size,
            "validation_size": validation_size,
            "test_size": test_size,
            "step_size": step_size,
        },
        universe=symbols,
        split_dates={"market_data": f"{min_time}/{max_time}"},
        candidate_specs=specs,
        factor_versions=versions,
        timeframe=timeframe,
        criteria=criteria,
    )


def run_factor_promotion_workflow(
    *,
    registry: FactorRegistry,
    factor_name: str,
    factor_version: str,
    validation_result: ValidationResult,
    walkforward_result: WalkforwardResult,
    base_path: str | Path,
    run_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    universe: list[str],
    split_dates: dict[str, Any],
    timeframe: str | None = None,
    criteria: PromotionCriteria | None = None,
) -> PromotionDecision:
    """Record promotion evidence and update the registry if both gates pass."""
    resolved_criteria = criteria or PromotionCriteria()
    promotion_config = _drop_none({
        **config_snapshot,
        "promotion_criteria": resolved_criteria.to_dict(),
    })

    validation_paths = write_validation_artifacts(
        result=validation_result,
        factor_name=factor_name,
        factor_version=factor_version,
        base_path=base_path,
        run_id=run_id,
        timeframe=timeframe,
        universe=universe,
    )
    walkforward_paths = write_walkforward_artifacts(
        result=walkforward_result,
        signal_name=factor_name,
        base_path=base_path,
        run_id=run_id,
        config_snapshot=promotion_config,
    )
    validation_metrics_path = str(Path(validation_paths["report_dir"]) / "metrics.json")
    walkforward_summary_path = walkforward_paths["summary"]

    decision = evaluate_factor_promotion(
        factor_name=factor_name,
        factor_version=factor_version,
        validation_result=validation_result,
        walkforward_result=walkforward_result,
        criteria=resolved_criteria,
        run_id=run_id,
    )
    _apply_registry_decision(registry, decision)

    run_root = experiment_root(base_path, run_id)
    decision_path = run_root / "promotion_decision.json"
    decision_path.write_text(
        json.dumps(_json_safe(decision.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )

    validation_record = build_run_record(
        module="factor_validation",
        run_id=run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot=promotion_config,
        factors=[factor_name],
        universe=universe,
        split_dates=split_dates,
        results={
            "outcome": str(validation_result.outcome),
            "mean_rank_ic": validation_result.mean_rank_ic,
            "top_minus_bottom": validation_result.top_minus_bottom,
            "median_turnover": validation_result.median_turnover,
        },
        artifact_paths={
            "metrics": validation_metrics_path,
            "config_snapshot": validation_paths["config_snapshot"],
            "report_dir": validation_paths["report_dir"],
        },
    )
    walkforward_record = build_run_record(
        module="walkforward",
        run_id=run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot=promotion_config,
        factors=[factor_name],
        universe=universe,
        split_dates=split_dates,
        results={
            "validation_mean": walkforward_result.cross_window_decay.get("validation_mean"),
            "test_mean": walkforward_result.cross_window_decay.get("test_mean"),
            "decay_mean": walkforward_result.cross_window_decay.get("decay_mean"),
            "leak_audit_passed": walkforward_result.leak_audit.get("status") == "passed",
        },
        artifact_paths={
            "metrics": walkforward_summary_path,
            "config_snapshot": walkforward_paths["config_snapshot"],
            "summary": walkforward_summary_path,
            "windows": walkforward_paths["windows"],
            "best_trials": walkforward_paths["best_trials"],
            "stability": walkforward_paths["stability"],
        },
    )
    promotion_record = build_run_record(
        module="factor_promotion",
        run_id=run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot=promotion_config,
        factors=[factor_name],
        universe=universe,
        split_dates=split_dates,
        results={
            "promoted": decision.promoted,
            "validation_passed": decision.validation_passed,
            "walkforward_passed": decision.walkforward_passed,
            **decision.metrics,
        },
        artifact_paths={
            "validation_metrics": validation_metrics_path,
            "validation_report_dir": validation_paths["report_dir"],
            "walkforward_metrics": walkforward_summary_path,
            "walkforward_summary": walkforward_summary_path,
            "promotion_decision": str(decision_path),
        },
    )
    append_run_record(validation_record, base_path=base_path)
    append_run_record(walkforward_record, base_path=base_path)
    append_run_record(promotion_record, base_path=base_path)
    rebuild_ledger_index(base_path=base_path)
    _record_promotion_memory(decision, promotion_record, base_path=base_path)
    return decision


def _evaluate_walkforward_gate(
    result: WalkforwardResult,
    criteria: PromotionCriteria,
) -> tuple[bool, list[str], dict[str, Any]]:
    reasons: list[str] = []
    test_scores = [float(trial.test_score) for trial in result.best_trials]
    positive_ratio = _positive_window_ratio(test_scores, criteria.min_walkforward_test_mean)
    metrics: dict[str, Any] = {
        "walkforward_validation_mean": float(result.cross_window_decay.get("validation_mean", 0.0)),
        "walkforward_test_mean": float(result.cross_window_decay.get("test_mean", 0.0)),
        "walkforward_decay_mean": float(result.cross_window_decay.get("decay_mean", 0.0)),
        "walkforward_positive_test_window_ratio": positive_ratio,
        "walkforward_window_count": len(test_scores),
        "leak_audit_passed": result.leak_audit.get("status") == "passed",
    }

    if not test_scores:
        reasons.append("walk-forward produced no test windows")
    if criteria.require_leak_audit_passed and not metrics["leak_audit_passed"]:
        reasons.append("walk-forward leak audit did not pass")
    if metrics["walkforward_test_mean"] < criteria.min_walkforward_test_mean:
        reasons.append("walk-forward test mean is below threshold")
    if positive_ratio < criteria.min_positive_test_window_ratio:
        reasons.append("too few walk-forward windows meet the test threshold")
    if (
        criteria.max_decay_mean is not None
        and metrics["walkforward_decay_mean"] > criteria.max_decay_mean
    ):
        reasons.append("walk-forward decay mean is above threshold")

    return not reasons, reasons, metrics


def _positive_window_ratio(test_scores: list[float], threshold: float) -> float:
    if not test_scores:
        return 0.0
    passing = sum(score >= threshold for score in test_scores)
    return passing / len(test_scores)


def _target_status(outcome: ValidationOutcome, promoted: bool) -> FactorStatus:
    if promoted:
        return FactorStatus.VALIDATED
    if outcome == ValidationOutcome.PASS:
        return FactorStatus.CANDIDATE
    if outcome == ValidationOutcome.FAIL:
        return FactorStatus.REJECTED
    return FactorStatus.DRAFT


def _apply_registry_decision(registry: FactorRegistry, decision: PromotionDecision) -> None:
    if decision.validation_passed:
        registry.update_status(
            decision.factor_name,
            decision.factor_version,
            FactorStatus.CANDIDATE,
        )
    elif decision.target_status == FactorStatus.REJECTED:
        registry.update_status(
            decision.factor_name,
            decision.factor_version,
            FactorStatus.REJECTED,
        )

    if decision.promoted:
        registry.promote_validated(
            decision.factor_name,
            decision.factor_version,
            validation_passed=decision.validation_passed,
            walkforward_passed=decision.walkforward_passed,
        )


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _skip(candidate_id: str, factor_name: str, reason: str) -> dict[str, str]:
    return {
        "candidate_id": candidate_id,
        "factor_name": factor_name,
        "reason": reason,
    }


def _write_batch_report(result: CandidatePromotionBatchResult, path: Path) -> None:
    summary = result.summary()
    lines = [
        f"# Promotion Batch Report: {result.batch_id}",
        "",
        "## Summary",
        "",
        f"- Evaluated: {summary['evaluated']}",
        f"- Promoted: {summary['promoted']}",
        f"- Not promoted: {summary['not_promoted']}",
        f"- Skipped: {summary['skipped']}",
        "",
        "## Decisions",
        "",
    ]
    if result.decisions:
        lines.extend([
            "| Factor | Version | Promoted | Target status | Reasons |",
            "|---|---:|---:|---|---|",
        ])
        for decision in result.decisions:
            reasons = "; ".join(decision.reasons) if decision.reasons else "-"
            lines.append(
                "| "
                f"{decision.factor_name} | "
                f"{decision.factor_version} | "
                f"{decision.promoted} | "
                f"{decision.target_status} | "
                f"{reasons} |"
            )
    else:
        lines.append("- No candidates were evaluated.")

    lines.extend(["", "## Skipped", ""])
    if result.skipped:
        lines.extend([
            "| Candidate | Factor | Reason |",
            "|---|---|---|",
        ])
        for item in result.skipped:
            lines.append(
                "| "
                f"{item['candidate_id']} | "
                f"{item['factor_name'] or '-'} | "
                f"{item['reason']} |"
            )
    else:
        lines.append("- No candidates were skipped.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_batch_decisions_csv(result: CandidatePromotionBatchResult, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_type",
                "candidate_id",
                "factor_name",
                "factor_version",
                "promoted",
                "target_status",
                "reason",
                "run_id",
            ],
        )
        writer.writeheader()
        for decision in result.decisions:
            writer.writerow({
                "row_type": "decision",
                "candidate_id": "",
                "factor_name": decision.factor_name,
                "factor_version": decision.factor_version,
                "promoted": str(decision.promoted),
                "target_status": str(decision.target_status),
                "reason": "; ".join(decision.reasons),
                "run_id": decision.run_id or "",
            })
        for item in result.skipped:
            writer.writerow({
                "row_type": "skipped",
                "candidate_id": item["candidate_id"],
                "factor_name": item["factor_name"],
                "factor_version": "",
                "promoted": "",
                "target_status": "",
                "reason": item["reason"],
                "run_id": "",
            })


def _record_promotion_memory(
    decision: PromotionDecision,
    record: Any,
    *,
    base_path: str | Path,
) -> None:
    add_experiment_entry(record, base_path=base_path)
    if decision.promoted:
        return

    add_failure_entry(
        title=f"Promotion rejected: {decision.factor_name}",
        summary="; ".join(decision.reasons) or "promotion gates did not pass",
        factor_name=decision.factor_name,
        tags=["factor_promotion", "not_promoted", decision.factor_name],
        metadata={
            "run_id": decision.run_id,
            "factor_version": decision.factor_version,
            "validation_passed": decision.validation_passed,
            "walkforward_passed": decision.walkforward_passed,
            "target_status": str(decision.target_status),
            "metrics": decision.metrics,
            "reasons": decision.reasons,
        },
        base_path=base_path,
    )


def _record_batch_memory(result: CandidatePromotionBatchResult, *, base_path: str | Path) -> None:
    for item in result.skipped:
        add_failure_entry(
            title=f"Promotion skipped: {item['candidate_id']}",
            summary=item["reason"],
            factor_name=item["factor_name"] or None,
            tags=["factor_promotion", "skipped", item["candidate_id"]],
            metadata={
                "batch_id": result.batch_id,
                "candidate_id": item["candidate_id"],
                "factor_name": item["factor_name"],
                "reason": item["reason"],
            },
            base_path=base_path,
        )


def _safe_run_id_segment(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return safe[:48] or "candidate"


def _resolve_factor_for_promotion(
    registry: FactorRegistry,
    factor_name: str,
    versions: Mapping[str, str],
) -> Any:
    explicit_version = versions.get(factor_name)
    if explicit_version is not None:
        return registry.get(factor_name, explicit_version)

    summaries = [item for item in registry.list_factors() if item["name"] == factor_name]
    if len(summaries) == 1:
        return registry.get(factor_name, str(summaries[0]["version"]))

    defaults = [item for item in summaries if item["is_default"]]
    if len(defaults) == 1:
        return registry.get(factor_name, str(defaults[0]["version"]))

    return registry.get(factor_name)


def _align_factor_scores_for_symbol(
    factor_scores: pd.DataFrame,
    market_data: pd.DataFrame,
    symbol: str,
) -> pd.DataFrame:
    score_rows = factor_scores[factor_scores["symbol"] == symbol].copy()
    price_rows = market_data[market_data["symbol"] == symbol].copy()
    if score_rows.empty or price_rows.empty:
        return pd.DataFrame()

    score_rows["factor_value"] = score_rows["score"].where(
        score_rows["score"].notna(),
        score_rows["value"],
    )
    merged = score_rows[
        ["event_time", "available_at", "symbol", "factor_value"]
    ].merge(
        price_rows[["event_time", "available_at", "symbol", "close"]],
        on=["event_time", "available_at", "symbol"],
        how="inner",
    )
    return merged.sort_values("event_time").reset_index(drop=True)


def _run_factor_market_walkforward(
    aligned: pd.DataFrame,
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None,
) -> WalkforwardResult:
    signals = aligned[["symbol", "available_at"]].rename(columns={"available_at": "timestamp"})
    leak_audit = audit_lookahead_inputs(
        signals=signals,
        data=aligned[["symbol", "available_at", "event_time"]],
        execution_delay_bars=1,
    )

    def evaluator(window: Any, params: dict[str, Any]) -> dict[str, float]:
        direction = float(params["direction"])
        return {
            "train_score": _window_directional_score(
                aligned,
                start=window.train_start,
                end=window.train_end,
                direction=direction,
            ),
            "validation_score": _window_directional_score(
                aligned,
                start=window.validation_start,
                end=window.validation_end,
                direction=direction,
            ),
            "test_score": _window_directional_score(
                aligned,
                start=window.test_start,
                end=window.test_end,
                direction=direction,
            ),
        }

    return run_walkforward_validation(
        timestamps=aligned["event_time"].astype(int).tolist(),
        parameter_grid=[{"direction": 1.0}, {"direction": -1.0}],
        evaluator=evaluator,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=step_size,
        leak_audit=leak_audit,
    )


def _window_directional_score(
    frame: pd.DataFrame,
    *,
    start: int,
    end: int,
    direction: float,
) -> float:
    subset = frame[(frame["event_time"] >= start) & (frame["event_time"] <= end)].copy()
    if len(subset) < 3:
        return 0.0
    forward_returns = subset["close"].pct_change().shift(-1)
    exposure = subset["factor_value"].map(_sign).astype(float) * direction
    strategy_returns = (exposure * forward_returns).dropna()
    if strategy_returns.empty:
        return 0.0
    return float(strategy_returns.mean())


def _sign(value: object) -> float:
    numeric = float(cast("float", value))
    if numeric > 0:
        return 1.0
    if numeric < 0:
        return -1.0
    return 0.0
