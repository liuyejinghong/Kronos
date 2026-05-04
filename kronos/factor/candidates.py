"""Structured candidate-factor registry for mined legacy hypotheses."""

from __future__ import annotations

from dataclasses import dataclass

from kronos.agent.types import CandidateLifecycleState


@dataclass(frozen=True)
class CandidateFactorSpec:
    """Structured description of a candidate factor hypothesis."""

    candidate_id: str
    family: str
    title: str
    source_strategies: tuple[str, ...]
    migration_rank: int
    implementation_name: str | None = None
    origin: str = "legacy_mine"
    initial_status: str = "candidate"
    lifecycle_state: CandidateLifecycleState | None = None


LEGACY_CANDIDATES: tuple[CandidateFactorSpec, ...] = (
    # Top 6 — 已跑完 90 天验证，按 Agent 交付批次结论分配状态
    CandidateFactorSpec(
        "indicator_spread_regime", "trend_momentum", "指标 spread regime", ("all",), 1,
        "asi_spread", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "signal_persistence_density", "trend_momentum", "信号持续性密度", ("all",), 2,
        "signal_persistence_density", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "trend_pullback_tolerance", "trend_momentum", "趋势回撤容忍度", ("L", "LP", "BR"), 3,
        "trend_pullback_tolerance", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "bar_close_pressure", "volatility_path", "bar 内收盘位置压力", ("L15", "L34", "LP15"), 4,
        "bar_close_pressure", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "body_energy", "volatility_path", "body-energy 累积",
        ("L3", "LP4", "LP16", "LP34"), 5, "body_energy",
        lifecycle_state=CandidateLifecycleState.OBSERVE,
    ),
    CandidateFactorSpec(
        "trend_pullback_entry", "mean_reversion", "趋势内回踩入场", ("CU", "M", "RB"), 6,
        "trend_pullback_entry", lifecycle_state=CandidateLifecycleState.REDESIGN,
    ),
    # Bottom 6 — 暂缓观察或退休
    CandidateFactorSpec(
        "midpoint_power", "volatility_path", "midpoint-power 不对称", ("L36", "LP36"), 7,
        "midpoint_power", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "range_chop_filter", "volatility_path", "range-chop 过滤器", ("BR",), 8,
        "range_chop_filter", lifecycle_state=CandidateLifecycleState.OBSERVE,
    ),
    CandidateFactorSpec(
        "band_position_conditioning", "trend_momentum", "band 位置条件化", ("GMEXR",), 9,
        "band_position_conditioning", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "volume_drought", "volume_liquidity", "volume drought 过滤器", ("LP",), 10,
        "volume_drought", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "move_density", "volume_liquidity", "move-density 因子", ("BIDEL",), 11,
        "move_density", lifecycle_state=CandidateLifecycleState.RETIRED,
    ),
    CandidateFactorSpec(
        "multi_timeframe_confirmation", "trend_momentum", "多时间框架确认",
        ("TPBRAB", "KIBCM", "V1"), 12, "multi_timeframe_confirmation",
        lifecycle_state=CandidateLifecycleState.OBSERVE,
    ),
)


def list_candidate_factors() -> list[CandidateFactorSpec]:
    """Return the structured candidate-factor list in migration priority order."""
    return list(LEGACY_CANDIDATES)
