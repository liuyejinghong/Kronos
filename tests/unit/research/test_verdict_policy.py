"""Unit tests for VerdictPolicy and evaluate_verdict (package P11).

Covers: policy determinism and fingerprint stability, all four evidence_status
paths, refuse-to-judge on insufficient evidence, redesign on cost flip, the
full retire conjunction, exact reason-code sets, fixed boundary limitations,
and JSON round-trip via the frozen contracts.
"""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from kronos.research.verdict.contracts import (
    Comparison,
    EvidenceBundle,
    GridPoint,
    MetricsBlock,
    MetricValue,
    NeighborhoodBlock,
    StressRun,
)
from kronos.research.verdict.policy import (
    BOUNDARY_LIMITATIONS,
    POLICY_VERSION,
    VerdictPolicy,
)
from kronos.research.verdict.verdict import evaluate_verdict

GENERATED_AT = 1_800_000_000_000
SPEC_HASH = "c" * 64
ENGINE_VERSION = "kronos-backtest-0.1.0"
ARTIFACT_REFS = {
    "ledger": "artifacts/run-001/ledger.jsonl",
    "evidence": "artifacts/run-001/evidence.json",
    "snapshot": "artifacts/run-001/snapshot.json",
    "manifest": "artifacts/run-001/manifest.json",
}


def make_metrics(
    *,
    trade_count: int = 40,
    net_return: float | None = 0.05,
    benchmark_return: float | None = 0.012,
    max_drawdown: float | None = -0.12,
    win_rate: float | None = 0.55,
    profit_factor: float | None = 1.7,
) -> MetricsBlock:
    """MetricsBlock builder; None turns a metric into null + explicit reason."""

    def mv(name: str, value: float | None) -> MetricValue:
        if value is not None:
            return MetricValue(value=value)
        return MetricValue(value=None, reason=f"{name} undefined: no closed trades")

    return MetricsBlock(
        net_return=mv("net_return", net_return),
        benchmark_return=mv("benchmark_return", benchmark_return),
        excess_return=mv("excess_return", net_return),
        max_drawdown=mv("max_drawdown", max_drawdown),
        win_rate=mv("win_rate", win_rate),
        profit_factor=mv("profit_factor", profit_factor),
        trade_count=trade_count,
        avg_hold_bars=mv("avg_hold_bars", 30.0),
        avg_win=mv("avg_win", 20.0),
        avg_loss=mv("avg_loss", -12.0),
        sample_warning=None,
    )


def make_comparison(
    baseline: Literal["hold_same_symbol", "cash"],
    net_return: float,
) -> Comparison:
    note = (
        "hold includes funding fee settlements"
        if baseline == "hold_same_symbol"
        else "cash earns nothing"
    )
    return Comparison(
        baseline=baseline,
        note=note,
        metrics=make_metrics(net_return=net_return, trade_count=1),
    )


def make_grid_point(
    *,
    param_activated: bool = True,
    trades_changed: bool = False,
    multiplier: float = 1.5,
) -> GridPoint:
    return GridPoint(
        atr_period=14,
        volatility_multiplier=multiplier,
        trades_changed=trades_changed,
        param_activated=param_activated,
        net_pnl=100.0,
    )


def make_neighborhood(
    matches: int = 5,
    mismatched: int = 0,
    inactive: int = 0,
    *,
    pseudo_note: str | None = None,
) -> NeighborhoodBlock:
    grid = [make_grid_point(trades_changed=False, multiplier=1.0 + 0.1 * i) for i in range(matches)]
    grid += [
        make_grid_point(trades_changed=True, multiplier=2.0 + 0.1 * i) for i in range(mismatched)
    ]
    grid += [make_grid_point(param_activated=False, multiplier=9.0) for _ in range(inactive)]
    return NeighborhoodBlock(grid=grid, pseudo_robust_note=pseudo_note)


def make_evidence(
    *,
    metrics: MetricsBlock | None = None,
    hold_net: float = 0.012,
    cash_net: float = 0.004,
    include_cash: bool = True,
    neighborhood: NeighborhoodBlock | None = None,
    with_cost_up_stress: bool = False,
) -> EvidenceBundle:
    comparisons = [make_comparison("hold_same_symbol", hold_net)]
    if include_cash:
        comparisons.append(make_comparison("cash", cash_net))
    stress = [StressRun(kind="delay", description="fills delayed to next 1m event")]
    if with_cost_up_stress:
        stress.append(StressRun(kind="cost_up", description="fees raised one tier"))
    return EvidenceBundle(
        run_id="run-001",
        strategy_revision_id="rev-001",
        snapshot_id="snap-001",
        metrics=metrics if metrics is not None else make_metrics(),
        comparisons=comparisons,
        time_slices=[],
        symbol_slices=[
            {
                "rule_id": "per_symbol",
                "label": "BTCUSDT",
                "sample_bars": 129_600,
                "trade_count": metrics.trade_count if metrics is not None else 40,
            }
        ],
        neighborhood=neighborhood if neighborhood is not None else make_neighborhood(),
        holdout={
            "dev_window": "first 60 complete UTC days",
            "holdout_window": "last 30 complete UTC days",
            "exposed_count": 0,
            "exposed": False,
        },
        stress=stress,
    )


def evaluate(
    evidence: EvidenceBundle,
    policy: VerdictPolicy | None = None,
    **overrides: object,
):
    kwargs: dict[str, object] = {
        "run_id": "run-001",
        "strategy_revision_id": "rev-001",
        "spec_hash": SPEC_HASH,
        "snapshot_id": "snap-001",
        "engine_version": ENGINE_VERSION,
        "artifact_refs": ARTIFACT_REFS,
        "snapshot_valid": True,
        "generated_at_ms": GENERATED_AT,
    }
    kwargs.update(overrides)
    return evaluate_verdict(evidence, policy if policy is not None else VerdictPolicy(), **kwargs)


class TestVerdictPolicy:
    def test_defaults_match_frozen_p0_policy(self) -> None:
        policy = VerdictPolicy()
        assert policy.policy_version == POLICY_VERSION == "v0.5.0-p0"
        assert policy.min_closed_trades == 30
        assert policy.neighborhood_consistency_min == 0.6
        assert policy.max_drawdown_flag == 0.5
        assert policy.cost_sensitivity_flag is True

    def test_policy_is_frozen(self) -> None:
        policy = VerdictPolicy()
        with pytest.raises(ValidationError):
            policy.min_closed_trades = 10  # type: ignore[misc]

    def test_invalid_thresholds_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VerdictPolicy(min_closed_trades=0)
        with pytest.raises(ValidationError):
            VerdictPolicy(neighborhood_consistency_min=1.5)
        with pytest.raises(ValidationError):
            VerdictPolicy(max_drawdown_flag=-0.1)

    def test_fingerprint_is_stable_for_identical_policies(self) -> None:
        assert VerdictPolicy().policy_fingerprint() == VerdictPolicy().policy_fingerprint()

    def test_fingerprint_changes_with_threshold_or_version(self) -> None:
        base = VerdictPolicy().policy_fingerprint()
        assert VerdictPolicy(min_closed_trades=25).policy_fingerprint() != base
        assert VerdictPolicy(policy_version="v0.5.0-p1").policy_fingerprint() != base

    def test_fingerprint_survives_json_round_trip(self) -> None:
        policy = VerdictPolicy()
        restored = VerdictPolicy.model_validate_json(policy.model_dump_json())
        assert restored.policy_fingerprint() == policy.policy_fingerprint()


class TestEvidenceStatusPaths:
    def test_healthy_evidence_is_valid_and_observed(self) -> None:
        verdict = evaluate(make_evidence())
        assert verdict.evidence_status == "valid"
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == []

    def test_invalid_snapshot_refuses_to_judge_even_with_healthy_metrics(self) -> None:
        verdict = evaluate(make_evidence(), snapshot_valid=False)
        assert verdict.evidence_status == "invalid"
        assert verdict.disposition is None
        assert verdict.reason_codes == ["snapshot_invalid"]

    def test_zero_trades_is_insufficient(self) -> None:
        metrics = make_metrics(
            trade_count=0,
            net_return=None,
            max_drawdown=None,
            win_rate=None,
            profit_factor=None,
        )
        verdict = evaluate(make_evidence(metrics=metrics))
        assert verdict.evidence_status == "insufficient"
        assert verdict.disposition is None
        # Zero trades also means all core metrics are null and the sample sits
        # below the engineering warning line; all three triggers are recorded.
        assert verdict.reason_codes == [
            "insufficient_zero_trades",
            "insufficient_null_core_metrics",
            "below_min_trades",
        ]

    def test_all_null_core_metrics_is_insufficient_even_with_trades(self) -> None:
        metrics = make_metrics(
            trade_count=40,
            net_return=None,
            max_drawdown=None,
            win_rate=None,
            profit_factor=None,
        )
        verdict = evaluate(make_evidence(metrics=metrics))
        assert verdict.evidence_status == "insufficient"
        assert verdict.disposition is None
        assert verdict.reason_codes == ["insufficient_null_core_metrics"]

    def test_below_min_trades_is_limited_never_invalid(self) -> None:
        verdict = evaluate(make_evidence(metrics=make_metrics(trade_count=12)))
        assert verdict.evidence_status == "limited"
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == ["below_min_trades"]

    def test_pseudo_robust_neighborhood_is_limited(self) -> None:
        note = "volatility_multiplier never entered the decision path in this window"
        neighborhood = make_neighborhood(
            inactive=1,
            pseudo_note=note,
        )
        verdict = evaluate(make_evidence(neighborhood=neighborhood))
        assert verdict.evidence_status == "limited"
        assert verdict.reason_codes == ["param_not_activated"]
        assert any(note in limitation for limitation in verdict.limitations)

    def test_invalid_wins_over_insufficient_in_status(self) -> None:
        metrics = make_metrics(
            trade_count=0,
            net_return=None,
            max_drawdown=None,
            win_rate=None,
            profit_factor=None,
        )
        verdict = evaluate(make_evidence(metrics=metrics), snapshot_valid=False)
        assert verdict.evidence_status == "invalid"
        assert verdict.disposition is None
        assert verdict.reason_codes == [
            "snapshot_invalid",
            "insufficient_zero_trades",
            "insufficient_null_core_metrics",
            "below_min_trades",
        ]


class TestDispositionRules:
    def test_insufficient_and_invalid_have_null_disposition(self) -> None:
        assert evaluate(make_evidence(), snapshot_valid=False).disposition is None
        zero = make_metrics(
            trade_count=0,
            net_return=None,
            max_drawdown=None,
            win_rate=None,
            profit_factor=None,
        )
        assert evaluate(make_evidence(metrics=zero)).disposition is None

    def test_cost_flip_under_stress_yields_redesign(self) -> None:
        evidence = make_evidence(with_cost_up_stress=True)
        verdict = evaluate(evidence, cost_up_net_return=-0.01)
        assert verdict.evidence_status == "valid"
        assert verdict.disposition == "redesign"
        assert verdict.reason_codes == ["cost_flip_under_stress"]
        assert any("cost_up" in limitation for limitation in verdict.limitations)

    def test_disarmed_cost_sensitivity_flag_ignores_flip(self) -> None:
        policy = VerdictPolicy(cost_sensitivity_flag=False)
        evidence = make_evidence(with_cost_up_stress=True)
        verdict = evaluate(evidence, policy, cost_up_net_return=-0.01)
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == []

    def test_neighborhood_inconsistency_yields_redesign(self) -> None:
        neighborhood = make_neighborhood(matches=1, mismatched=4)  # 0.2 < 0.6
        verdict = evaluate(make_evidence(neighborhood=neighborhood))
        assert verdict.disposition == "redesign"
        assert verdict.reason_codes == ["neighborhood_inconsistent"]

    def test_consistency_exactly_at_threshold_is_not_inconsistent(self) -> None:
        neighborhood = make_neighborhood(matches=3, mismatched=2)  # 0.6 == min
        verdict = evaluate(make_evidence(neighborhood=neighborhood))
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == []

    def test_retire_requires_underperforming_both_baselines(self) -> None:
        metrics = make_metrics(net_return=-0.03)
        verdict = evaluate(make_evidence(metrics=metrics, hold_net=0.012, cash_net=0.004))
        assert verdict.evidence_status == "valid"
        assert verdict.disposition == "retire_current_revision"
        assert verdict.reason_codes == ["underperform_both_baselines"]

    def test_beating_one_baseline_observes_instead_of_retiring(self) -> None:
        metrics = make_metrics(net_return=0.05)
        # base 0.05 beats cash (0.004) but trails hold (0.06): conjunction broken.
        verdict = evaluate(make_evidence(metrics=metrics, hold_net=0.06))
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == []

    def test_missing_baseline_blocks_retire(self) -> None:
        metrics = make_metrics(net_return=-0.03)
        verdict = evaluate(make_evidence(metrics=metrics, include_cash=False))
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == []

    def test_never_auto_retire_on_limited_evidence(self) -> None:
        metrics = make_metrics(trade_count=12, net_return=-0.03)
        verdict = evaluate(make_evidence(metrics=metrics))
        assert verdict.evidence_status == "limited"
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == ["below_min_trades", "underperform_both_baselines"]

    def test_redesign_takes_precedence_over_retire(self) -> None:
        # Positive net that loses to BOTH baselines (0.002 < 0.004 < 0.012) plus
        # a cost flip (0.002 -> -0.01) plus an inconsistent neighborhood.
        metrics = make_metrics(net_return=0.002)
        evidence = make_evidence(
            metrics=metrics,
            neighborhood=make_neighborhood(matches=1, mismatched=4),
            with_cost_up_stress=True,
        )
        verdict = evaluate(evidence, cost_up_net_return=-0.01)
        assert verdict.disposition == "redesign"
        assert verdict.reason_codes == [
            "cost_flip_under_stress",
            "neighborhood_inconsistent",
            "underperform_both_baselines",
        ]

    def test_drawdown_flag_adds_limitation_without_changing_disposition(self) -> None:
        metrics = make_metrics(max_drawdown=-0.65)
        verdict = evaluate(make_evidence(metrics=metrics))
        assert verdict.disposition == "observe"
        assert verdict.reason_codes == ["max_drawdown_exceeds_policy_flag"]
        assert any("0.6500" in limitation for limitation in verdict.limitations)


class TestLimitations:
    def test_healthy_verdict_carries_exactly_the_boundary_strings(self) -> None:
        verdict = evaluate(make_evidence())
        assert tuple(verdict.limitations) == BOUNDARY_LIMITATIONS

    def test_flag_limitations_come_before_boundary_strings(self) -> None:
        verdict = evaluate(make_evidence(metrics=make_metrics(trade_count=12)))
        assert len(verdict.limitations) == 4
        assert tuple(verdict.limitations[-3:]) == BOUNDARY_LIMITATIONS
        assert "12" in verdict.limitations[0]
        assert "30" in verdict.limitations[0]

    def test_boundary_strings_are_always_appended(self) -> None:
        verdict = evaluate(make_evidence(), snapshot_valid=False)
        assert tuple(verdict.limitations[-3:]) == BOUNDARY_LIMITATIONS


class TestDeterminismAndRoundTrip:
    def test_replay_twice_produces_identical_verdicts(self) -> None:
        evidence = make_evidence(with_cost_up_stress=True)
        policy = VerdictPolicy()
        first = evaluate(evidence, policy, cost_up_net_return=-0.01)
        second = evaluate(evidence, policy, cost_up_net_return=-0.01)
        assert first == second
        assert first.model_dump_json() == second.model_dump_json()

    def test_verdict_json_round_trips_through_contract(self) -> None:
        verdict = evaluate(make_evidence(), cost_up_net_return=None)
        restored = type(verdict).model_validate_json(verdict.model_dump_json())
        assert restored == verdict
        assert restored.schema_version == 1
        assert restored.metrics == verdict.metrics

    def test_verdict_records_policy_version_and_policy_fields_are_traceable(self) -> None:
        policy = VerdictPolicy()
        evidence = make_evidence()
        verdict = evaluate(evidence, policy)
        assert verdict.policy_version == policy.policy_version
        assert verdict.metrics == evidence.metrics
        assert verdict.comparisons == evidence.comparisons

    @pytest.mark.parametrize(
        ("evidence_kwargs", "overrides", "expected_status"),
        [
            pytest.param({}, {}, "valid", id="valid"),
            pytest.param({}, {"snapshot_valid": False}, "invalid", id="invalid"),
            pytest.param(
                {
                    "metrics": make_metrics(
                        trade_count=0,
                        net_return=None,
                        max_drawdown=None,
                        win_rate=None,
                        profit_factor=None,
                    )
                },
                {},
                "insufficient",
                id="insufficient",
            ),
            pytest.param(
                {"metrics": make_metrics(trade_count=12)},
                {},
                "limited",
                id="limited",
            ),
        ],
    )
    def test_execution_authority_is_always_none(
        self,
        evidence_kwargs: dict[str, object],
        overrides: dict[str, object],
        expected_status: str,
    ) -> None:
        evidence = make_evidence(**evidence_kwargs)  # type: ignore[arg-type]
        verdict = evaluate(evidence, **overrides)  # type: ignore[arg-type]
        assert verdict.evidence_status == expected_status
        assert verdict.execution_authority == "none"


class TestNextActions:
    def test_zero_trades_propose_collect_more_data_then_switch_symbol(self) -> None:
        # The default fixture mirrors evidence trade_count into the symbol slice,
        # so zero trades overall implies every slice traded zero times.
        metrics = make_metrics(
            trade_count=0,
            net_return=None,
            max_drawdown=None,
            win_rate=None,
            profit_factor=None,
        )
        verdict = evaluate(make_evidence(metrics=metrics))
        kinds = [action.kind for action in verdict.next_actions]
        assert kinds == ["collect_more_data", "switch_symbol"]

    def test_retire_proposes_drop_revision(self) -> None:
        metrics = make_metrics(net_return=-0.03)
        verdict = evaluate(make_evidence(metrics=metrics))
        assert [action.kind for action in verdict.next_actions] == ["drop_revision"]

    def test_pseudo_robust_proposes_adjust_param(self) -> None:
        neighborhood = make_neighborhood(inactive=1, pseudo_note="param never activated")
        verdict = evaluate(make_evidence(neighborhood=neighborhood))
        assert [action.kind for action in verdict.next_actions] == ["adjust_param"]

    def test_healthy_observe_still_has_one_follow_up(self) -> None:
        verdict = evaluate(make_evidence())
        assert len(verdict.next_actions) == 1
        assert verdict.next_actions[0].kind == "collect_more_data"

    def test_actions_are_capped_at_three_and_unique_by_kind(self) -> None:
        metrics = make_metrics(trade_count=12, net_return=-0.03, max_drawdown=-0.9)
        evidence = make_evidence(
            metrics=metrics,
            neighborhood=make_neighborhood(
                matches=1,
                mismatched=4,
                inactive=1,
                pseudo_note="volatility_multiplier never activated",
            ),
            with_cost_up_stress=True,
        )
        # base -0.03 flips sign against a positive stressed net return.
        verdict = evaluate(evidence, cost_up_net_return=0.01)
        kinds = [action.kind for action in verdict.next_actions]
        assert len(kinds) <= 3
        assert len(kinds) == len(set(kinds))


class TestInputValidation:
    def test_run_id_mismatch_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="run_id mismatch"):
            evaluate(make_evidence(), run_id="run-002")

    def test_snapshot_id_mismatch_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="snapshot_id mismatch"):
            evaluate(make_evidence(), snapshot_id="snap-002")

    def test_strategy_revision_id_mismatch_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="strategy_revision_id mismatch"):
            evaluate(make_evidence(), strategy_revision_id="rev-002")

    def test_cost_up_return_without_cost_up_stress_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cost_up"):
            evaluate(make_evidence(with_cost_up_stress=False), cost_up_net_return=-0.01)
