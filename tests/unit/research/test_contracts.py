"""Unit tests for the frozen v0.5.0 verdict contracts (package P05)."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from kronos.research.verdict.contracts import (
    EXECUTION_EVENT_TYPES,
    REQUIRED_QUALITY_CHECKS,
    TASK_STATES,
    BudgetBlock,
    ClosedTrade,
    Comparison,
    DatasetManifest,
    DataSnapshotManifest,
    EvidenceBundle,
    ExecutionLedger,
    ExecutionRecord,
    GridPoint,
    HoldoutBlock,
    MetricsBlock,
    MetricValue,
    NeighborhoodBlock,
    NextAction,
    Slice,
    StrategyVerdict,
    StressRun,
    TaskEvent,
    TaskRecord,
    TaskState,
)

DAY_MS = 86_400_000
DAY_START = 1_790_035_200_000  # 2026-09-01T00:00:00Z, UTC-day aligned


def metric(value: float | None = None, *, reason: str | None = None) -> MetricValue:
    """Build a MetricValue with exactly one of value/reason set."""
    return MetricValue(value=value, reason=reason)


def concrete_metric(value: float) -> MetricValue:
    return metric(value)


def make_metrics() -> MetricsBlock:
    return MetricsBlock(
        net_return=concrete_metric(0.042),
        benchmark_return=concrete_metric(0.011),
        excess_return=concrete_metric(0.031),
        max_drawdown=concrete_metric(-0.08),
        win_rate=concrete_metric(0.55),
        profit_factor=concrete_metric(1.4),
        trade_count=12,
        avg_hold_bars=concrete_metric(37.5),
        avg_win=concrete_metric(21.0),
        avg_loss=concrete_metric(-13.0),
        sample_warning=None,
    )


def make_record(ts_ms: int = DAY_START + 60_000, **overrides: object) -> ExecutionRecord:
    payload: dict[str, object] = {
        "ts_ms": ts_ms,
        "event": "fill",
        "symbol": "BTCUSDT",
        "side": "buy",
        "qty": 0.001,
        "price": 65_000.0,
    }
    payload.update(overrides)
    return ExecutionRecord.model_validate(payload)


def make_closed_trade(trade_id: str = "t1") -> ClosedTrade:
    return ClosedTrade(
        trade_id=trade_id,
        symbol="BTCUSDT",
        direction="long",
        entry_ts_ms=DAY_START + 60_000,
        exit_ts_ms=DAY_START + 3_600_000,
        entry_price=65_000.0,
        exit_price=65_500.0,
        qty=0.001,
        gross_pnl=0.5,
        total_fees=0.08,
        net_pnl=0.42,
        holding_bars=59,
        exit_reason="signal_exit",
    )


def make_ledger() -> ExecutionLedger:
    return ExecutionLedger(
        symbol="BTCUSDT",
        strategy_revision_id="rev-001",
        records=[make_record()],
        final_equity=10_000.42,
        closed_trades=[make_closed_trade()],
    )


def make_dataset(**overrides: object) -> DatasetManifest:
    payload: dict[str, object] = {
        "name": "klines_1m",
        "venue": "binance-usdm",
        "source": "rest_backfill",
        "row_count": 129_600,
        "content_sha256": "a" * 64,
        "coverage_ok": True,
    }
    payload.update(overrides)
    return DatasetManifest.model_validate(payload)


def passing_quality_checks() -> dict[str, bool]:
    return dict.fromkeys(REQUIRED_QUALITY_CHECKS, True)


def make_manifest(**overrides: object) -> DataSnapshotManifest:
    payload: dict[str, object] = {
        "snapshot_id": "snap-001",
        "symbols": ["BTCUSDT"],
        "interval": "1m",
        "window_start_ms": DAY_START,
        "window_end_ms": DAY_START + 90 * DAY_MS,
        "warmup_start_ms": DAY_START - 14 * DAY_MS,
        "datasets": [make_dataset()],
        "funding_coverage": True,
        "quality_checks": passing_quality_checks(),
        "frozen_at": DAY_START + 90 * DAY_MS + 1_000,
        "mock_available_at": False,
        "overall_status": "valid",
    }
    payload.update(overrides)
    return DataSnapshotManifest.model_validate(payload)


def make_comparison(
    baseline: Literal["hold_same_symbol", "cash"] = "hold_same_symbol",
) -> Comparison:
    note = (
        "hold includes funding fee settlements"
        if baseline == "hold_same_symbol"
        else "cash earns nothing"
    )
    return Comparison(baseline=baseline, note=note, metrics=make_metrics())


def make_grid_point(**overrides: object) -> GridPoint:
    payload: dict[str, object] = {
        "atr_period": 14,
        "volatility_multiplier": 1.5,
        "trades_changed": True,
        "param_activated": True,
        "net_pnl": 512.0,
    }
    payload.update(overrides)
    return GridPoint.model_validate(payload)


def make_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        run_id="run-001",
        strategy_revision_id="rev-001",
        snapshot_id="snap-001",
        metrics=make_metrics(),
        comparisons=[make_comparison()],
        time_slices=[
            Slice(rule_id="thirds", label="first_third", sample_bars=43_200, trade_count=4),
        ],
        symbol_slices=[
            Slice(rule_id="per_symbol", label="BTCUSDT", sample_bars=129_600, trade_count=12),
        ],
        neighborhood=NeighborhoodBlock(grid=[make_grid_point()], pseudo_robust_note=None),
        holdout=HoldoutBlock(
            dev_window="first 60 complete UTC days",
            holdout_window="last 30 complete UTC days",
            exposed_count=0,
            exposed=False,
        ),
        stress=[StressRun(kind="delay", description="fills delayed to next tradable 1m event")],
    )


def make_budget() -> BudgetBlock:
    return BudgetBlock(
        llm_calls_reserved=3,
        llm_calls_used=0,
        tokens_reserved=16_000,
        tokens_used=0,
        backtests_reserved=40,
        backtests_used=0,
        wall_clock_limit_s=1_800.0,
    )


def make_task_record(state: TaskState) -> TaskRecord:
    return TaskRecord(
        task_id="task-001",
        kind="evaluate_strategy",
        payload_sha256="b" * 64,
        state=state,
        stage="backtesting",
        attempt=1,
        worker_id="worker-1",
        lease_expiry_ms=DAY_START + 300_000,
        fencing_token=7,
        heartbeat_ms=DAY_START + 120_000,
        budget_reserved=make_budget(),
        error_ref=None,
        created_at=DAY_START,
        updated_at=DAY_START + 60_000,
    )


def make_verdict() -> StrategyVerdict:
    return StrategyVerdict(
        run_id="run-001",
        parent_run_id=None,
        strategy_revision_id="rev-001",
        spec_hash="c" * 64,
        snapshot_id="snap-001",
        engine_version="kronos-backtest-0.1.0",
        policy_version="verdict-policy-1",
        evidence_status="valid",
        disposition="observe",
        reason_codes=["positive_excess_return"],
        metrics=make_metrics(),
        comparisons=[make_comparison()],
        limitations=["single symbol", "90-day window"],
        next_actions=[
            NextAction(kind="adjust_param", detail="try volatility_multiplier 1.2 and 1.8"),
        ],
        artifact_refs={
            "ledger": "artifacts/run-001/ledger.jsonl",
            "evidence": "artifacts/run-001/evidence.json",
            "snapshot": "artifacts/run-001/snapshot.json",
            "manifest": "artifacts/run-001/manifest.json",
        },
        generated_at=DAY_START + 90 * DAY_MS + 2_000,
        execution_authority="none",
    )


class TestMetricValueNullSemantics:
    def test_concrete_value_without_reason_is_accepted(self) -> None:
        mv = MetricValue(value=0.25)
        assert mv.value == 0.25
        assert mv.reason is None

    def test_zero_value_is_concrete_not_null(self) -> None:
        mv = MetricValue(value=0.0)
        assert mv.value == 0.0
        assert mv.reason is None

    def test_null_value_with_reason_is_accepted(self) -> None:
        mv = MetricValue(value=None, reason="no closed trades")
        assert mv.value is None
        assert mv.reason == "no closed trades"

    def test_value_and_reason_both_set_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MetricValue(value=0.5, reason="why")

    def test_value_and_reason_both_missing_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MetricValue()

    def test_null_value_with_empty_reason_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MetricValue(value=None, reason="   ")


class TestMetricsBlock:
    def test_null_metric_inside_block_is_preserved(self) -> None:
        base = make_metrics().model_dump()
        base["profit_factor"] = {"value": None, "reason": "zero gross loss denominator"}
        block = MetricsBlock.model_validate(base)
        assert block.profit_factor.value is None
        assert block.profit_factor.reason == "zero gross loss denominator"


class TestDataSnapshotManifest:
    def test_clean_manifest_stays_valid(self) -> None:
        manifest = make_manifest()
        assert manifest.overall_status == "valid"

    def test_synthetic_dataset_forces_invalid(self) -> None:
        manifest = make_manifest(datasets=[make_dataset(venue="synthetic")])
        assert manifest.overall_status == "invalid"

    def test_failed_quality_check_forces_invalid(self) -> None:
        checks = passing_quality_checks()
        checks["no_interior_gaps"] = False
        manifest = make_manifest(quality_checks=checks)
        assert manifest.overall_status == "invalid"

    def test_explicitly_invalid_manifest_with_taint_is_allowed(self) -> None:
        manifest = make_manifest(
            datasets=[make_dataset(venue="synthetic")],
            overall_status="invalid",
        )
        assert manifest.overall_status == "invalid"

    def test_missing_required_quality_key_is_rejected(self) -> None:
        checks = passing_quality_checks()
        del checks["no_synthetic_mix"]
        with pytest.raises(ValidationError, match="no_synthetic_mix"):
            make_manifest(quality_checks=checks)

    def test_extra_quality_keys_are_allowed(self) -> None:
        checks = passing_quality_checks() | {"extra_check": True}
        manifest = make_manifest(quality_checks=checks)
        assert manifest.quality_checks["extra_check"] is True

    def test_interval_is_frozen_to_1m(self) -> None:
        with pytest.raises(ValidationError):
            make_manifest(interval="5m")


class TestExecutionLedger:
    def test_ledger_parses_with_all_event_types(self) -> None:
        records = [make_record(event=event) for event in EXECUTION_EVENT_TYPES]
        ledger = ExecutionLedger(
            symbol="BTCUSDT",
            strategy_revision_id="rev-001",
            records=records,
            final_equity=10_000.42,
            closed_trades=[make_closed_trade()],
        )
        assert len(ledger.records) == len(EXECUTION_EVENT_TYPES)
        assert ledger.closed_trades[0].exit_reason == "signal_exit"

    def test_unknown_event_type_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_record(event="liquidation")

    def test_unknown_exit_reason_is_rejected(self) -> None:
        trade = make_closed_trade().model_dump()
        trade["exit_reason"] = "manual_close"
        with pytest.raises(ValidationError):
            ClosedTrade.model_validate(trade)

    def test_construction_succeeds_without_conservation_check(self) -> None:
        # Equity conservation is enforced by package P09 downstream; the schema
        # must accept an internally inconsistent ledger so P09 owns the veto.
        ledger = make_ledger()
        assert ledger.final_equity == 10_000.42


class TestEvidenceBundle:
    def test_evidence_round_trips(self) -> None:
        evidence = make_evidence()
        restored = EvidenceBundle.model_validate_json(evidence.model_dump_json())
        assert restored == evidence

    def test_inactive_grid_point_requires_pseudo_robust_note(self) -> None:
        with pytest.raises(ValidationError, match="pseudo_robust_note"):
            make_evidence().model_copy(
                update={
                    "neighborhood": NeighborhoodBlock(
                        grid=[make_grid_point(param_activated=False, trades_changed=False)],
                        pseudo_robust_note=None,
                    )
                }
            )

    def test_inactive_grid_point_with_note_is_accepted(self) -> None:
        bundle = make_evidence()
        bundle.neighborhood = NeighborhoodBlock(
            grid=[make_grid_point(param_activated=False, trades_changed=False)],
            pseudo_robust_note="multiplier never entered the decision path in this window",
        )
        assert bundle.neighborhood.pseudo_robust_note is not None


class TestExecutionAuthorityAlwaysNone:
    def test_default_and_explicit_none_are_accepted(self) -> None:
        verdict = make_verdict()
        assert verdict.execution_authority == "none"
        assert StrategyVerdict.model_validate(verdict.model_dump()).execution_authority == "none"

    def test_any_other_authority_is_rejected(self) -> None:
        payload = make_verdict().model_dump()
        payload["execution_authority"] = "paper"
        with pytest.raises(ValidationError):
            StrategyVerdict.model_validate(payload)

    def test_refusal_disposition_is_representable(self) -> None:
        payload = make_verdict().model_dump()
        payload["disposition"] = None
        payload["evidence_status"] = "insufficient"
        verdict = StrategyVerdict.model_validate(payload)
        assert verdict.disposition is None
        assert verdict.evidence_status == "insufficient"


class TestTaskStates:
    def test_task_state_enum_is_complete(self) -> None:
        assert set(TASK_STATES) == {
            "queued",
            "running",
            "cancel_requested",
            "succeeded",
            "blocked",
            "failed",
            "cancelled",
            "budget_exhausted",
        }
        assert len(TASK_STATES) == 8

    @pytest.mark.parametrize("state", TASK_STATES)
    def test_every_state_produces_a_valid_task_record(self, state: str) -> None:
        record = make_task_record(state)
        assert record.state == state

    def test_unknown_state_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_task_record("paused")

    def test_task_event_parses(self) -> None:
        event = TaskEvent(
            seq=3,
            task_id="task-001",
            ts_ms=DAY_START + 60_000,
            kind="state_changed",
            detail="running -> cancel_requested",
        )
        assert event.seq == 3
        assert event.detail is not None


class TestStrategyVerdictRoundTrip:
    def test_json_round_trip_preserves_model(self) -> None:
        verdict = make_verdict()
        restored = StrategyVerdict.model_validate_json(verdict.model_dump_json())
        assert restored == verdict
        assert restored.schema_version == 1

    def test_unknown_fields_are_rejected(self) -> None:
        payload = make_verdict().model_dump()
        payload["surprise_field"] = 1
        with pytest.raises(ValidationError, match="surprise_field"):
            StrategyVerdict.model_validate(payload)

    def test_extra_forbid_on_nested_models(self) -> None:
        with pytest.raises(ValidationError):
            make_record(unexpected="field")
