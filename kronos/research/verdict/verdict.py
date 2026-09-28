"""Deterministic verdict evaluation (package P11).

``evaluate_verdict`` is a PURE function from ``(EvidenceBundle, VerdictPolicy,
identifiers)`` to ``StrategyVerdict``. It reads nothing but its arguments,
performs no I/O, calls no model, and always yields the same verdict for the
same inputs (replay-safe; ``generated_at_ms`` is an explicit argument so
replays are byte-identical).

Decision table (design.md section 3, decision 6; spec: verdict-card):

====================  ==========================  ==============================
evidence_status       trigger                     disposition
====================  ==========================  ==============================
invalid               snapshot data invalid       None (refuse to judge)
insufficient          zero trades OR all core     None (refuse to judge)
                      metrics null
limited               below ``min_closed_trades`` redesign if cost flip or
                      OR pseudo-robust flag       neighborhood inconsistent,
                      (warning-only, never        else observe; never
                      auto-invalid)               retire on limited evidence
valid                 none of the above           redesign if cost flip or
                                                  neighborhood inconsistent;
                                                  retire_current_revision iff
                                                  sample sufficient AND net
                                                  underperforms BOTH baselines
                                                  AND core metrics non-null;
                                                  else observe
====================  ==========================  ==============================

``execution_authority`` is always ``"none"`` (enforced again by the contract).

Two inputs arrive as explicit parameters because the frozen P05
``EvidenceBundle`` contract cannot carry them:

- ``snapshot_valid``: the bundle has only ``snapshot_id`` (no status field), so
  snapshot validity is passed explicitly instead of being guessed from naming
  conventions.
- ``cost_up_net_return``: ``StressRun`` descriptors carry no stressed metrics,
  so the net return under the ``cost_up`` scenario is passed explicitly; it is
  accepted only when the bundle actually contains a ``cost_up`` stress entry.
"""

from __future__ import annotations

from typing import Final

from kronos.research.verdict.contracts import (
    Comparison,
    Disposition,
    EvidenceBundle,
    EvidenceStatus,
    MetricsBlock,
    MetricValue,
    NeighborhoodBlock,
    NextAction,
    NextActionKind,
    StrategyVerdict,
)
from kronos.research.verdict.policy import (
    BOUNDARY_LIMITATIONS,
    REASON_CODE_ORDER,
    VerdictPolicy,
)

#: Closed-trade metrics that must be non-null for a retire disposition and
#: whose being all-null marks evidence as insufficient.
_CORE_METRIC_NAMES: Final[tuple[str, ...]] = (
    "net_return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
)

#: Baselines that must BOTH be underperformed before retiring a revision.
REQUIRED_BASELINES: Final[tuple[str, str]] = ("hold_same_symbol", "cash")

_MAX_NEXT_ACTIONS: Final[int] = 3

#: Ordered reason-code -> follow-up mapping (first 3 distinct kinds win).
_NEXT_ACTION_RULES: Final[tuple[tuple[str, NextActionKind, str], ...]] = (
    (
        "insufficient_zero_trades",
        "collect_more_data",
        "No closed trades in this window: extend the window or relax entry "
        "thresholds so the rule can trade, then re-evaluate.",
    ),
    (
        "insufficient_null_core_metrics",
        "collect_more_data",
        "Core closed-trade metrics are undefined: rebuild evidence on a window "
        "that produces closed trades before judging.",
    ),
    (
        "below_min_trades",
        "collect_more_data",
        "Closed-trade count is below the pre-declared engineering warning line: "
        "collect more data before judging performance.",
    ),
    (
        "cost_flip_under_stress",
        "add_filter",
        "Add an entry filter that raises expected per-trade edge so results "
        "survive the cost_up stress scenario.",
    ),
    (
        "neighborhood_inconsistent",
        "adjust_param",
        "Re-center the parameters: trade structure changes across most activated "
        "neighborhood points.",
    ),
    (
        "param_not_activated",
        "adjust_param",
        "Widen the pre-registered grid so the inactive parameter actually enters "
        "the decision path.",
    ),
    (
        "max_drawdown_exceeds_policy_flag",
        "add_filter",
        "Add a risk cap: observed max drawdown exceeds the policy flag.",
    ),
)

_DEFAULT_NEXT_ACTION: Final[NextAction] = NextAction(
    kind="collect_more_data",
    detail=(
        "No disqualifying trigger fired: extend the sample window or re-evaluate "
        "on new data before further tuning."
    ),
)

_DROP_REVISION_ACTION: Final[NextAction] = NextAction(
    kind="drop_revision",
    detail=(
        "Net return trails both the hold and cash baselines with a sufficient "
        "sample: drop this strategy revision."
    ),
)

_SWITCH_SYMBOL_ACTION: Final[NextAction] = NextAction(
    kind="switch_symbol",
    detail=(
        "No trades in any evaluated symbol slice: try a more active or more "
        "trending symbol before collecting more data."
    ),
)


def _core_metric_values(metrics: MetricsBlock) -> tuple[float | None, ...]:
    return (
        metrics.net_return.value,
        metrics.max_drawdown.value,
        metrics.win_rate.value,
        metrics.profit_factor.value,
    )


def _all_core_null(metrics: MetricsBlock) -> bool:
    return all(value is None for value in _core_metric_values(metrics))


def _all_core_present(metrics: MetricsBlock) -> bool:
    return all(value is not None for value in _core_metric_values(metrics))


def _neighborhood_consistency(neighborhood: NeighborhoodBlock) -> float:
    """Fraction of activated grid points whose trade structure matches center.

    A point "matches" the center when it does not change any trade
    (``trades_changed=False``). With no activated points the structure is
    trivially unchanged, so consistency is 1.0 (the pseudo-robustness rule
    handles that case instead).
    """
    activated = [point for point in neighborhood.grid if point.param_activated]
    if not activated:
        return 1.0
    matching = sum(1 for point in activated if not point.trades_changed)
    return matching / len(activated)


def _net_return_flips_sign(base: MetricValue, stressed: float | None) -> bool:
    """True when a concrete base net return flips sign under the stress value."""
    if base.value is None or stressed is None:
        return False
    return (base.value > 0.0 and stressed < 0.0) or (base.value < 0.0 and stressed > 0.0)


def _underperforms_both_baselines(evidence: EvidenceBundle) -> bool:
    """True only when both required baselines are present AND beaten by net.

    Conservative: a missing baseline, a null baseline net return, or a tie all
    count as NOT underperforming both.
    """
    base_net = evidence.metrics.net_return.value
    if base_net is None:
        return False
    by_baseline: dict[str, Comparison] = {
        comparison.baseline: comparison for comparison in evidence.comparisons
    }
    for baseline in REQUIRED_BASELINES:
        comparison = by_baseline.get(baseline)
        if comparison is None:
            return False
        baseline_net = comparison.metrics.net_return.value
        if baseline_net is None or not base_net < baseline_net:
            return False
    return True


def _build_reason_codes(fired: set[str]) -> list[str]:
    return [code for code in REASON_CODE_ORDER if code in fired]


def _build_next_actions(
    fired: set[str],
    evidence: EvidenceBundle,
    disposition: Disposition,
) -> list[NextAction]:
    actions: list[NextAction] = []
    seen_kinds: set[NextActionKind] = set()

    def add(action: NextAction) -> None:
        if action.kind not in seen_kinds:
            actions.append(action)
            seen_kinds.add(action.kind)

    for reason_code, kind, detail in _NEXT_ACTION_RULES:
        if reason_code in fired:
            add(NextAction(kind=kind, detail=detail))
        if len(actions) == _MAX_NEXT_ACTIONS:
            return actions
    if disposition == "retire_current_revision":
        add(_DROP_REVISION_ACTION)
    if (
        "insufficient_zero_trades" in fired
        and evidence.symbol_slices
        and all(slice_.trade_count == 0 for slice_ in evidence.symbol_slices)
    ):
        add(_SWITCH_SYMBOL_ACTION)
    if not actions:
        add(_DEFAULT_NEXT_ACTION)
    return actions[:_MAX_NEXT_ACTIONS]


def evaluate_verdict(
    evidence: EvidenceBundle,
    policy: VerdictPolicy,
    *,
    run_id: str,
    strategy_revision_id: str,
    spec_hash: str,
    snapshot_id: str,
    engine_version: str,
    artifact_refs: dict[str, str],
    snapshot_valid: bool,
    generated_at_ms: int,
    parent_run_id: str | None = None,
    cost_up_net_return: float | None = None,
) -> StrategyVerdict:
    """Evaluate one evidence bundle under a pre-frozen policy. PURE.

    Raises ``ValueError`` on inconsistent inputs (identifier mismatches, or a
    ``cost_up_net_return`` without a matching ``cost_up`` stress entry in the
    bundle) so a mis-wired caller cannot silently produce a verdict.
    """
    if evidence.run_id != run_id:
        raise ValueError(f"run_id mismatch: evidence has {evidence.run_id!r}, got {run_id!r}")
    if evidence.strategy_revision_id != strategy_revision_id:
        raise ValueError(
            f"strategy_revision_id mismatch: evidence has "
            f"{evidence.strategy_revision_id!r}, got {strategy_revision_id!r}"
        )
    if evidence.snapshot_id != snapshot_id:
        raise ValueError(
            f"snapshot_id mismatch: evidence has {evidence.snapshot_id!r}, got {snapshot_id!r}"
        )
    if cost_up_net_return is not None and not any(
        stress.kind == "cost_up" for stress in evidence.stress
    ):
        raise ValueError(
            "cost_up_net_return was provided but evidence.stress contains no "
            "'cost_up' scenario to anchor it"
        )

    trade_count = evidence.metrics.trade_count
    zero_trades = trade_count == 0
    all_core_null = _all_core_null(evidence.metrics)
    below_min_trades = trade_count < policy.min_closed_trades
    pseudo_robust = any(not point.param_activated for point in evidence.neighborhood.grid)
    consistency = _neighborhood_consistency(evidence.neighborhood)
    neighborhood_inconsistent = consistency < policy.neighborhood_consistency_min
    cost_flip = policy.cost_sensitivity_flag and _net_return_flips_sign(
        evidence.metrics.net_return, cost_up_net_return
    )
    underperforms_both = _underperforms_both_baselines(evidence)
    max_drawdown = evidence.metrics.max_drawdown.value
    drawdown_flagged = max_drawdown is not None and abs(max_drawdown) > policy.max_drawdown_flag

    fired: set[str] = set()
    if not snapshot_valid:
        fired.add("snapshot_invalid")
    if zero_trades:
        fired.add("insufficient_zero_trades")
    if all_core_null:
        fired.add("insufficient_null_core_metrics")
    if below_min_trades:
        fired.add("below_min_trades")
    if pseudo_robust:
        fired.add("param_not_activated")
    if cost_flip:
        fired.add("cost_flip_under_stress")
    if neighborhood_inconsistent:
        fired.add("neighborhood_inconsistent")
    if underperforms_both:
        fired.add("underperform_both_baselines")
    if drawdown_flagged:
        fired.add("max_drawdown_exceeds_policy_flag")

    if not snapshot_valid:
        evidence_status: EvidenceStatus = "invalid"
    elif zero_trades or all_core_null:
        evidence_status = "insufficient"
    elif below_min_trades or pseudo_robust:
        evidence_status = "limited"
    else:
        evidence_status = "valid"

    disposition: Disposition = None
    if evidence_status in ("valid", "limited"):
        if cost_flip or neighborhood_inconsistent:
            disposition = "redesign"
        elif (
            evidence_status == "valid"
            and underperforms_both
            and _all_core_present(evidence.metrics)
        ):
            disposition = "retire_current_revision"
        else:
            disposition = "observe"

    limitations: list[str] = []
    if below_min_trades:
        limitations.append(
            f"Engineering warning line: {trade_count} closed trades is below the "
            f"pre-declared minimum of {policy.min_closed_trades}; conclusions are "
            "indicative only (warning-only, never auto-invalid)."
        )
    if pseudo_robust and evidence.neighborhood.pseudo_robust_note:
        limitations.append(
            "Pseudo-robustness guard: "
            + evidence.neighborhood.pseudo_robust_note
            + " An inactive parameter must not be read as robustness."
        )
    if cost_flip:
        limitations.append(
            "Cost sensitivity: net return flips sign under the cost_up stress "
            "scenario; profitability does not survive higher costs."
        )
    if drawdown_flagged and max_drawdown is not None:
        limitations.append(
            f"Max drawdown magnitude {abs(max_drawdown):.4f} exceeds the policy "
            f"flag {policy.max_drawdown_flag:.2f}; flagged for review only, not an "
            "auto-disposition."
        )
    limitations.extend(BOUNDARY_LIMITATIONS)

    return StrategyVerdict(
        run_id=run_id,
        parent_run_id=parent_run_id,
        strategy_revision_id=strategy_revision_id,
        spec_hash=spec_hash,
        snapshot_id=snapshot_id,
        engine_version=engine_version,
        policy_version=policy.policy_version,
        evidence_status=evidence_status,
        disposition=disposition,
        reason_codes=_build_reason_codes(fired),
        metrics=evidence.metrics,
        comparisons=list(evidence.comparisons),
        limitations=limitations,
        next_actions=_build_next_actions(fired, evidence, disposition),
        artifact_refs=dict(artifact_refs),
        generated_at=generated_at_ms,
        execution_authority="none",
    )
