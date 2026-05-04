"""Unit tests for candidate factor promotion workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pandas as pd

from kronos.common.types import FactorStatus
from kronos.factor.base import BaseFactor
from kronos.factor.candidates import CandidateFactorSpec
from kronos.factor.registry import FactorRegistry
from kronos.factor.validation.pipeline import ValidationResult
from kronos.factor.validation.thresholds import ValidationConfig, ValidationOutcome
from kronos.research.experiments import query_runs
from kronos.research.knowledge_base import search_entries
from kronos.research.promotion import (
    PromotionCriteria,
    evaluate_factor_promotion,
    run_candidate_promotion_batch,
    run_factor_promotion_workflow,
    run_market_data_promotion_batch,
)
from kronos.research.walkforward import run_walkforward_validation
from kronos.research.workbench import (
    CandidateDispositionStatus,
    FailureReasonCategory,
    WatchlistReviewAction,
    build_candidate_dispositions,
    build_watchlist_reviews,
    group_failure_reasons,
)

if TYPE_CHECKING:
    from kronos.research.walkforward.core import WalkforwardResult, WalkforwardWindow


class _PromotionFactor(BaseFactor):
    name = "promotion_factor"
    family = "trend_momentum"
    version = "1.0.0"
    lookback = 2
    warmup_bars = 2
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["close"]
    description = "Factor used by promotion workflow tests"

    def metadata(self) -> dict[str, Any]:
        return {"lookback": 2}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].diff()


def _validation_result(outcome: ValidationOutcome = ValidationOutcome.PASS) -> ValidationResult:
    return ValidationResult(
        outcome=outcome,
        ic_table=pd.DataFrame([{"period": 1, "ic": 0.1, "rank_ic": 0.2, "n_obs": 10}]),
        mean_rank_ic=0.2,
        rank_ic_positive_ratio=0.7,
        ic_ir=1.0,
        quantile_returns=pd.Series({1: -0.01, 2: 0.02}, dtype=float),
        top_minus_bottom=0.03,
        median_turnover=0.3,
        top_turnover=0.2,
        bottom_turnover=0.4,
        decay=pd.DataFrame([{"period": 1, "mean_rank_ic": 0.2, "rank_ic_positive_ratio": 0.7}]),
        forward_returns=pd.DataFrame({"fwd_1": [0.01, 0.02]}),
        n_obs=10,
        skipped_pct=0.0,
        config=ValidationConfig(periods=[1, 3], quantiles=2),
    )


def _walkforward_result(*, test_offset: float = -0.2, leak_status: str = "passed") -> WalkforwardResult:
    def evaluator(window: WalkforwardWindow, params: dict[str, Any]) -> dict[str, float]:
        speed = float(params["speed"])
        return {
            "train_score": speed + 1.0,
            "validation_score": speed,
            "test_score": speed + test_offset,
        }

    return run_walkforward_validation(
        timestamps=list(range(12)),
        parameter_grid=[{"speed": 1}, {"speed": 2}],
        evaluator=evaluator,
        train_size=4,
        validation_size=2,
        test_size=2,
        step_size=2,
        leak_audit={"status": leak_status, "reason": None},
    )


def _registry(*, set_default: bool = True) -> FactorRegistry:
    registry = FactorRegistry()
    registry.register(_PromotionFactor(), set_default=set_default)
    return registry


def _market_data(rows: int = 48) -> pd.DataFrame:
    base = 1_700_000_000_000
    return pd.DataFrame({
        "event_time": [base + index * 3_600_000 for index in range(rows)],
        "available_at": [base + (index + 1) * 3_600_000 for index in range(rows)],
        "symbol": ["BTCUSDT"] * rows,
        "close": [100.0 + index + 0.02 * index * index for index in range(rows)],
    })


class TestEvaluateFactorPromotion:
    def test_promotes_when_validation_and_walkforward_gates_pass(self) -> None:
        decision = evaluate_factor_promotion(
            factor_name="promotion_factor",
            factor_version="1.0.0",
            validation_result=_validation_result(),
            walkforward_result=_walkforward_result(),
        )

        assert decision.promoted is True
        assert decision.target_status == FactorStatus.VALIDATED
        assert decision.metrics["walkforward_test_mean"] > 0

    def test_keeps_candidate_when_walkforward_gate_fails(self) -> None:
        decision = evaluate_factor_promotion(
            factor_name="promotion_factor",
            factor_version="1.0.0",
            validation_result=_validation_result(),
            walkforward_result=_walkforward_result(test_offset=-3.0),
        )

        assert decision.promoted is False
        assert decision.validation_passed is True
        assert decision.walkforward_passed is False
        assert decision.target_status == FactorStatus.CANDIDATE
        assert "walk-forward test mean is below threshold" in decision.reasons

    def test_rejects_failed_leak_audit_when_required(self) -> None:
        decision = evaluate_factor_promotion(
            factor_name="promotion_factor",
            factor_version="1.0.0",
            validation_result=_validation_result(),
            walkforward_result=_walkforward_result(leak_status="failed"),
            criteria=PromotionCriteria(require_leak_audit_passed=True),
        )

        assert decision.promoted is False
        assert "walk-forward leak audit did not pass" in decision.reasons


class TestRunFactorPromotionWorkflow:
    def test_records_evidence_and_promotes_registry_status(self, tmp_path: Path) -> None:
        registry = _registry()

        decision = run_factor_promotion_workflow(
            registry=registry,
            factor_name="promotion_factor",
            factor_version="1.0.0",
            validation_result=_validation_result(),
            walkforward_result=_walkforward_result(),
            base_path=tmp_path,
            run_id="20260425T120000Z-promo1",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT", "ETHUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            timeframe="1h",
        )

        status = registry.status("promotion_factor", "1.0.0")
        assert decision.run_id is not None
        decision_path = tmp_path / "experiments" / decision.run_id / "promotion_decision.json"
        decision_payload = json.loads(decision_path.read_text(encoding="utf-8"))
        records = query_runs(base_path=tmp_path, git_commit="abc123")

        assert decision.promoted is True
        assert status["status"] == FactorStatus.VALIDATED
        assert decision_payload["target_status"] == "validated"
        assert set(records["module"].tolist()) == {
            "factor_validation",
            "walkforward",
            "factor_promotion",
        }

    def test_failed_walkforward_records_decision_without_validated_status(self, tmp_path: Path) -> None:
        registry = _registry()

        decision = run_factor_promotion_workflow(
            registry=registry,
            factor_name="promotion_factor",
            factor_version="1.0.0",
            validation_result=_validation_result(),
            walkforward_result=_walkforward_result(test_offset=-3.0),
            base_path=tmp_path,
            run_id="20260425T121500Z-promo2",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            timeframe="1h",
        )

        status = registry.status("promotion_factor", "1.0.0")

        assert decision.promoted is False
        assert status["status"] == FactorStatus.CANDIDATE


class TestRunCandidatePromotionBatch:
    def test_runs_catalog_batch_and_writes_summary(self, tmp_path: Path) -> None:
        registry = _registry(set_default=False)
        specs = (
            CandidateFactorSpec(
                candidate_id="promotion_candidate",
                family="trend_momentum",
                title="Promotion candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )

        batch = run_candidate_promotion_batch(
            registry=registry,
            validation_results={"promotion_factor": _validation_result()},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260425T130000Z-batch",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT", "ETHUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        assert batch.summary() == {"evaluated": 1, "promoted": 1, "not_promoted": 0, "skipped": 0}
        assert registry.status("promotion_factor", "1.0.0")["status"] == FactorStatus.VALIDATED
        assert batch.artifact_path is not None
        payload = json.loads(Path(batch.artifact_path).read_text(encoding="utf-8"))
        assert payload["summary"]["promoted"] == 1
        assert payload["decisions"][0]["run_id"] == "20260425T130000Z-batch-promotion_candidate"
        assert payload["artifact_paths"]["report"].endswith("promotion_batch_report.md")
        assert (tmp_path / "experiments" / batch.batch_id / "promotion_batch_report.md").exists()
        assert (tmp_path / "experiments" / batch.batch_id / "promotion_batch_decisions.csv").exists()
        assert search_entries("promotion_factor", base_path=tmp_path)

    def test_batch_summary_writes_strict_json_for_non_finite_metrics(self, tmp_path: Path) -> None:
        registry = _registry(set_default=False)
        specs = (
            CandidateFactorSpec(
                candidate_id="nan_candidate",
                family="trend_momentum",
                title="NaN candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        validation = _validation_result()
        validation.rank_ic_positive_ratio = float("nan")

        batch = run_candidate_promotion_batch(
            registry=registry,
            validation_results={"promotion_factor": validation},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260425T130500Z-batch",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        assert batch.artifact_path is not None
        summary_text = Path(batch.artifact_path).read_text(encoding="utf-8")
        payload = json.loads(summary_text)

        assert "NaN" not in summary_text
        assert payload["decisions"][0]["metrics"]["rank_ic_positive_ratio"] is None

    def test_skips_catalog_entries_without_evidence_or_implementation(self, tmp_path: Path) -> None:
        registry = _registry()
        specs = (
            CandidateFactorSpec(
                candidate_id="not_mapped",
                family="trend_momentum",
                title="No implementation",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name=None,
            ),
            CandidateFactorSpec(
                candidate_id="missing_evidence",
                family="trend_momentum",
                title="Missing evidence",
                source_strategies=("test",),
                migration_rank=2,
                implementation_name="promotion_factor",
            ),
        )

        batch = run_candidate_promotion_batch(
            registry=registry,
            validation_results={},
            walkforward_results={},
            base_path=tmp_path,
            batch_id="20260425T131500Z-batch",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        assert batch.summary() == {"evaluated": 0, "promoted": 0, "not_promoted": 0, "skipped": 2}
        assert [item["reason"] for item in batch.skipped] == [
            "missing_implementation",
            "missing_validation_result",
        ]
        skipped_hits = search_entries("missing_validation_result", base_path=tmp_path)
        assert skipped_hits[0].entry_type == "failure_reason"


class TestRunMarketDataPromotionBatch:
    def test_computes_evidence_from_market_data_and_runs_batch(self, tmp_path: Path) -> None:
        registry = _registry(set_default=False)
        specs = (
            CandidateFactorSpec(
                candidate_id="market_candidate",
                family="trend_momentum",
                title="Market data candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )

        batch = run_market_data_promotion_batch(
            registry=registry,
            symbols=["BTCUSDT"],
            data_base_path=tmp_path / "data",
            output_base_path=tmp_path,
            batch_id="20260425T140000Z-market",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            candidate_specs=specs,
            timeframe="1h",
            market_data=_market_data(),
            validation_config=ValidationConfig(
                periods=[1],
                quantiles=2,
                min_mean_rank_ic=-1.0,
                min_rank_ic_positive_ratio=0.0,
                min_top_minus_bottom_return=-1.0,
                max_median_turnover=1.0,
            ),
            criteria=PromotionCriteria(
                min_walkforward_test_mean=-1.0,
                min_positive_test_window_ratio=0.0,
            ),
            train_size=12,
            validation_size=6,
            test_size=6,
            step_size=6,
        )

        assert batch.summary()["evaluated"] == 1
        assert batch.summary()["skipped"] == 0
        assert batch.artifact_path is not None
        payload = json.loads(Path(batch.artifact_path).read_text(encoding="utf-8"))
        assert payload["summary"]["evaluated"] == 1
        assert payload["decisions"][0]["factor_name"] == "promotion_factor"


class TestWorkbenchFailureGrouping:
    def test_groups_failed_decisions_for_pm_review(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="migration_candidate",
                family="trend_momentum",
                title="Migration candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={"promotion_factor": _validation_result(ValidationOutcome.FAIL)},
            walkforward_results={"promotion_factor": _walkforward_result(test_offset=-3.0)},
            base_path=tmp_path,
            batch_id="20260426T100000Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        groups = group_failure_reasons(batch, specs)
        categories = {group.category for group in groups}

        assert FailureReasonCategory.MIGRATION_INVALIDATION in categories
        assert FailureReasonCategory.MARKET_MECHANISM_MISMATCH in categories
        assert any(group.items[0]["candidate_title"] == "Migration candidate" for group in groups)

    def test_groups_review_outcomes_as_unstable_watchlist(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="review_candidate",
                family="trend_momentum",
                title="Review candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={"promotion_factor": _validation_result(ValidationOutcome.REVIEW)},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260426T101000Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        groups = group_failure_reasons(batch, specs)
        categories = {group.category for group in groups}

        assert FailureReasonCategory.UNSTABLE_PARAMETERS in categories
        assert FailureReasonCategory.MIGRATION_INVALIDATION not in categories

    def test_groups_skipped_candidates_as_data_or_report_gaps(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="missing_evidence",
                family="trend_momentum",
                title="Missing evidence",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={},
            walkforward_results={},
            base_path=tmp_path,
            batch_id="20260426T101500Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        groups = group_failure_reasons(batch, specs)

        assert groups[0].category == FailureReasonCategory.DATA_INSUFFICIENCY
        assert groups[0].items[0]["candidate_id"] == "missing_evidence"


class TestWorkbenchCandidateDispositions:
    def test_marks_failed_candidates_as_retirement_recommended(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="failed_candidate",
                family="trend_momentum",
                title="Failed candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={"promotion_factor": _validation_result(ValidationOutcome.FAIL)},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260426T102000Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        dispositions = build_candidate_dispositions(batch, specs)

        assert dispositions[0].candidate_id == "failed_candidate"
        assert dispositions[0].status == CandidateDispositionStatus.RETIREMENT_RECOMMENDED

    def test_marks_review_candidates_as_watchlist(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="review_candidate",
                family="trend_momentum",
                title="Review candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={"promotion_factor": _validation_result(ValidationOutcome.REVIEW)},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260426T102500Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        dispositions = build_candidate_dispositions(batch, specs)

        assert dispositions[0].status == CandidateDispositionStatus.WATCHLIST
        assert "保留观察" in dispositions[0].recommendation_zh

    def test_marks_skipped_candidates_as_blocked(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="missing_evidence",
                family="trend_momentum",
                title="Missing evidence",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={},
            walkforward_results={},
            base_path=tmp_path,
            batch_id="20260426T103000Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        dispositions = build_candidate_dispositions(batch, specs)

        assert dispositions[0].status == CandidateDispositionStatus.BLOCKED


class TestWorkbenchWatchlistReviews:
    def test_prioritizes_stronger_watchlist_for_evidence_extension(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="strong_review_candidate",
                family="trend_momentum",
                title="Strong review candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        validation_result = _validation_result(ValidationOutcome.REVIEW)
        validation_result = ValidationResult(
            outcome=validation_result.outcome,
            ic_table=validation_result.ic_table,
            mean_rank_ic=0.03,
            rank_ic_positive_ratio=validation_result.rank_ic_positive_ratio,
            ic_ir=validation_result.ic_ir,
            quantile_returns=validation_result.quantile_returns,
            top_minus_bottom=0.04,
            median_turnover=validation_result.median_turnover,
            top_turnover=validation_result.top_turnover,
            bottom_turnover=validation_result.bottom_turnover,
            decay=validation_result.decay,
            forward_returns=validation_result.forward_returns,
            n_obs=validation_result.n_obs,
            skipped_pct=validation_result.skipped_pct,
            config=validation_result.config,
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={"promotion_factor": validation_result},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260426T103500Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        reviews = build_watchlist_reviews(build_candidate_dispositions(batch, specs))

        assert reviews[0].action == WatchlistReviewAction.EXTEND_EVIDENCE
        assert reviews[0].priority == 1
        assert "更长历史" in "".join(reviews[0].next_evidence_zh)

    def test_sends_weaker_watchlist_to_redesign_review(self, tmp_path: Path) -> None:
        specs = (
            CandidateFactorSpec(
                candidate_id="weak_review_candidate",
                family="trend_momentum",
                title="Weak review candidate",
                source_strategies=("test",),
                migration_rank=1,
                implementation_name="promotion_factor",
            ),
        )
        validation_result = _validation_result(ValidationOutcome.REVIEW)
        validation_result = ValidationResult(
            outcome=validation_result.outcome,
            ic_table=validation_result.ic_table,
            mean_rank_ic=0.006,
            rank_ic_positive_ratio=validation_result.rank_ic_positive_ratio,
            ic_ir=validation_result.ic_ir,
            quantile_returns=validation_result.quantile_returns,
            top_minus_bottom=0.004,
            median_turnover=validation_result.median_turnover,
            top_turnover=validation_result.top_turnover,
            bottom_turnover=validation_result.bottom_turnover,
            decay=validation_result.decay,
            forward_returns=validation_result.forward_returns,
            n_obs=validation_result.n_obs,
            skipped_pct=validation_result.skipped_pct,
            config=validation_result.config,
        )
        batch = run_candidate_promotion_batch(
            registry=_registry(),
            validation_results={"promotion_factor": validation_result},
            walkforward_results={"promotion_factor": _walkforward_result()},
            base_path=tmp_path,
            batch_id="20260426T104000Z-workbench-unit",
            git_commit="abc123",
            data_snapshot_id="snapshot-1",
            config_snapshot={"timeframe": "1h"},
            universe=["BTCUSDT"],
            split_dates={"walkforward": "2024-01-01/2024-04-01"},
            candidate_specs=specs,
            timeframe="1h",
        )

        reviews = build_watchlist_reviews(build_candidate_dispositions(batch, specs))

        assert reviews[0].action == WatchlistReviewAction.REDESIGN_CANDIDATE
        assert reviews[0].priority == 2
