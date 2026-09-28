"""v0.5.0 strategy-verdict loop contracts and policies (package P05).

Schema-only home for the frozen field-level contracts consumed by the parallel
v0.5.0 dev lanes (see openspec/changes/p5-strategy-verdict-loop/design.md).
"""

from __future__ import annotations

from kronos.research.verdict.contracts import (
    REQUIRED_QUALITY_CHECKS,
    SCHEMA_VERSION,
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
)
from kronos.research.verdict.policy_schema import (
    LiveTradingGate,
    TestnetAutonomyPolicy,
    load_testnet_policy,
)

__all__ = [
    "REQUIRED_QUALITY_CHECKS",
    "SCHEMA_VERSION",
    "TASK_STATES",
    "BudgetBlock",
    "ClosedTrade",
    "Comparison",
    "DataSnapshotManifest",
    "DatasetManifest",
    "EvidenceBundle",
    "ExecutionLedger",
    "ExecutionRecord",
    "GridPoint",
    "HoldoutBlock",
    "LiveTradingGate",
    "MetricValue",
    "MetricsBlock",
    "NeighborhoodBlock",
    "NextAction",
    "Slice",
    "StrategyVerdict",
    "StressRun",
    "TaskEvent",
    "TaskRecord",
    "TestnetAutonomyPolicy",
    "load_testnet_policy",
]
