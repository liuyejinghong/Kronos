"""Frozen field-level contracts for the v0.5.0 strategy-verdict loop.

Schema-only module (package P05): these pydantic models freeze the six
field-level contracts dispatched to the parallel v0.5.0 dev lanes. Authoritative
sources: ``openspec/changes/p5-strategy-verdict-loop/design.md`` (contract map,
section 2) and ``specs/*/spec.md``. Other packages import these names verbatim;
field names here are load-bearing and must not change outside the P05 revision
process.

No business logic lives here. In particular, the equity conservation check for
``ExecutionLedger`` (equity change == closed pnl + fees + funding +/- unrealized
movement) is enforced by package P09, not by this schema.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION: Final[int] = 1

type ExecutionEventType = Literal[
    "order",
    "fill",
    "fee",
    "funding",
    "position_open",
    "position_close",
    "equity_mark",
]
EXECUTION_EVENT_TYPES: Final[tuple[ExecutionEventType, ...]] = (
    "order",
    "fill",
    "fee",
    "funding",
    "position_open",
    "position_close",
    "equity_mark",
)

type TradeSide = Literal["buy", "sell"]
type TradeDirection = Literal["long", "short"]
type ExitReason = Literal["signal_exit", "day_end_flat", "end_of_data_open"]

type DatasetName = Literal["klines_1m", "funding"]
type ComparisonBaseline = Literal["hold_same_symbol", "cash"]
type ManifestStatus = Literal["valid", "invalid"]
type EvidenceStatus = Literal["valid", "limited", "insufficient", "invalid"]
type Disposition = Literal["observe", "redesign", "retire_current_revision"] | None
type ExecutionAuthority = Literal["none"]
type StressKind = Literal["cost_up", "delay"]
type NextActionKind = Literal[
    "adjust_param",
    "add_filter",
    "switch_symbol",
    "switch_timeframe",
    "collect_more_data",
    "drop_revision",
]

type TaskKind = Literal["ensure_data", "evaluate_strategy"]
type TaskState = Literal[
    "queued",
    "running",
    "cancel_requested",
    "succeeded",
    "blocked",
    "failed",
    "cancelled",
    "budget_exhausted",
]
TASK_STATES: Final[tuple[TaskState, ...]] = (
    "queued",
    "running",
    "cancel_requested",
    "succeeded",
    "blocked",
    "failed",
    "cancelled",
    "budget_exhausted",
)

REQUIRED_QUALITY_CHECKS: Final[tuple[str, ...]] = (
    "closed_bars_only",
    "no_interior_gaps",
    "no_duplicates",
    "no_synthetic_mix",
    "resample_buckets_complete",
)


class MetricValue(BaseModel):
    """A metric that is either a concrete float or an explicit null plus reason.

    Encodes the spec rule that zero-denominator / no-trade metrics are
    ``null + reason`` and must never be reported as ``0`` or ``Infinity``:
    exactly one of ``value`` / ``reason`` must be present.
    """

    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    reason: str | None = Field(
        None,
        description="Populated only when value is null; states why the metric is undefined.",
    )

    @model_validator(mode="after")
    def _exactly_one_of_value_or_reason(self) -> MetricValue:
        if self.value is not None:
            if self.reason is not None:
                raise ValueError("MetricValue with a concrete value must not carry a reason")
        elif self.reason is None or not self.reason.strip():
            raise ValueError(
                "null MetricValue must carry a non-empty reason "
                "(zero denominator / no-trade metrics are null + reason, never 0)"
            )
        return self


class MetricsBlock(BaseModel):
    """Closed-trade metrics shared by EvidenceBundle and StrategyVerdict.

    All ratio metrics come from closed round-trip trades only (spec:
    backtest-evidence). Zero denominators or zero trades yield
    ``MetricValue(value=None, reason=...)``.
    """

    model_config = ConfigDict(extra="forbid")

    net_return: MetricValue
    benchmark_return: MetricValue
    excess_return: MetricValue
    max_drawdown: MetricValue
    win_rate: MetricValue
    profit_factor: MetricValue
    trade_count: int = Field(ge=0)
    avg_hold_bars: MetricValue
    avg_win: MetricValue
    avg_loss: MetricValue
    sample_warning: str | None = None


class ExecutionRecord(BaseModel):
    """One ledger event: order, fill, fee, funding, position or equity mark."""

    model_config = ConfigDict(extra="forbid")

    ts_ms: int
    event: ExecutionEventType
    symbol: str
    side: TradeSide | None = None
    qty: float | None = None
    price: float | None = None
    fee: float | None = None
    fee_asset: str | None = None
    funding_rate: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    equity: float | None = None
    note: str | None = None


class ClosedTrade(BaseModel):
    """One closed round trip; the basis for every metric in MetricsBlock."""

    model_config = ConfigDict(extra="forbid")

    trade_id: str
    symbol: str
    direction: TradeDirection
    entry_ts_ms: int
    exit_ts_ms: int
    entry_price: float
    exit_price: float
    qty: float
    gross_pnl: float
    total_fees: float = Field(description="Fees plus funding attributed to this trade.")
    net_pnl: float
    holding_bars: int = Field(ge=0)
    exit_reason: ExitReason


class ExecutionLedger(BaseModel):
    """Per-run unified trade ledger produced by StrategyBacktestAdapter.

    Schema only: the equity conservation check (equity change must equal closed
    pnl + fees + funding +/- unrealized movement) lives in package P09, which
    consumes this ledger; it is intentionally NOT enforced here.
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str
    strategy_revision_id: str
    records: list[ExecutionRecord]
    final_equity: float
    closed_trades: list[ClosedTrade]


class DatasetManifest(BaseModel):
    """One frozen dataset inside a DataSnapshotManifest."""

    model_config = ConfigDict(extra="forbid")

    name: DatasetName
    venue: str = Field(description="e.g. binance-usdm; 'synthetic' taints the whole snapshot.")
    source: str
    row_count: int = Field(ge=0)
    content_sha256: str
    coverage_ok: bool


class DataSnapshotManifest(BaseModel):
    """Immutable data snapshot binding for one evaluation.

    ``window_start_ms`` / ``window_end_ms`` are epoch ms and must be aligned to
    complete UTC days. ``mock_available_at=True`` marks snapshots whose
    knowable-time semantics are historically simulated rather than live
    ingested (spec: data-snapshot, time knowability must be explicit).
    """

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    symbols: list[str] = Field(min_length=1)
    interval: Literal["1m"] = "1m"
    window_start_ms: int
    window_end_ms: int
    warmup_start_ms: int
    datasets: list[DatasetManifest]
    funding_coverage: bool
    quality_checks: dict[str, bool]
    frozen_at: int = Field(description="Epoch ms at which the snapshot was frozen.")
    mock_available_at: bool = Field(
        description="True when knowable-time semantics are historically simulated (mocked).",
    )
    overall_status: ManifestStatus

    @field_validator("quality_checks")
    @classmethod
    def _require_core_quality_keys(cls, value: dict[str, bool]) -> dict[str, bool]:
        missing = [key for key in REQUIRED_QUALITY_CHECKS if key not in value]
        if missing:
            raise ValueError(f"quality_checks missing required keys: {missing}")
        return value

    @model_validator(mode="after")
    def _force_invalid_on_taint(self) -> DataSnapshotManifest:
        """One-vote-veto rule: synthetic data or any failed check forces invalid.

        A snapshot containing any venue='synthetic' dataset, or any False entry
        in quality_checks, must never be reported as valid (spec: data-snapshot;
        security-boundary one-vote-veto list). The status is forced to
        'invalid' so a producer cannot ship a tainted snapshot as valid.
        """
        synthetic_present = any(dataset.venue == "synthetic" for dataset in self.datasets)
        check_failed = any(not ok for ok in self.quality_checks.values())
        if (synthetic_present or check_failed) and self.overall_status == "valid":
            self.overall_status = "invalid"
        return self


class Comparison(BaseModel):
    """Metrics of one comparison run against a fixed baseline."""

    model_config = ConfigDict(extra="forbid")

    baseline: ComparisonBaseline
    note: str = Field(
        description="For baseline='hold_same_symbol' this must state whether funding is counted.",
    )
    metrics: MetricsBlock


class Slice(BaseModel):
    """A pre-registered slice of the evaluation window (time or symbol)."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    label: str
    sample_bars: int = Field(ge=0)
    trade_count: int = Field(ge=0)


class GridPoint(BaseModel):
    """One pre-registered neighborhood parameter combination."""

    model_config = ConfigDict(extra="forbid")

    atr_period: int
    volatility_multiplier: float
    trades_changed: bool = Field(
        description="True when this parameter change alters at least one trade.",
    )
    param_activated: bool = Field(
        description="True when the parameter actually entered the decision path.",
    )
    net_pnl: float | None = None


class NeighborhoodBlock(BaseModel):
    """Pre-registered parameter neighborhood with pseudo-robustness note.

    Spec rule: a parameter change that does not change any trade must be
    flagged as 'parameter not activated' and must not be reported as evidence
    that the strategy is robust to that parameter.
    """

    model_config = ConfigDict(extra="forbid")

    grid: list[GridPoint] = Field(min_length=1)
    pseudo_robust_note: str | None = Field(
        None,
        description="Required when any grid point has param_activated=False.",
    )

    @model_validator(mode="after")
    def _inactive_params_require_note(self) -> NeighborhoodBlock:
        if any(not point.param_activated for point in self.grid) and not (
            self.pseudo_robust_note and self.pseudo_robust_note.strip()
        ):
            raise ValueError(
                "pseudo_robust_note is required when any grid point has param_activated=False: "
                "inactive parameters must not be reported as robustness"
            )
        return self


class HoldoutBlock(BaseModel):
    """Dev/holdout split with holdout-exposure accounting (60/30 default)."""

    model_config = ConfigDict(extra="forbid")

    dev_window: str
    holdout_window: str
    exposed_count: int = Field(ge=0)
    exposed: bool = Field(
        description="True once holdout results have been viewed and tuning resumed.",
    )


class StressRun(BaseModel):
    """One cost or delay stress scenario."""

    model_config = ConfigDict(extra="forbid")

    kind: StressKind
    description: str


class EvidenceBundle(BaseModel):
    """Full evidence package for one evaluation run (contract owner: P10)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    strategy_revision_id: str
    snapshot_id: str
    metrics: MetricsBlock
    comparisons: list[Comparison]
    time_slices: list[Slice] = Field(description="Pre-registered time slices; lagging info only.")
    symbol_slices: list[Slice]
    neighborhood: NeighborhoodBlock
    holdout: HoldoutBlock
    stress: list[StressRun] = Field(
        description="At least one delay stress scenario must exist (design section 3).",
    )


class NextAction(BaseModel):
    """One concrete follow-up proposed by the verdict."""

    model_config = ConfigDict(extra="forbid")

    kind: NextActionKind
    detail: str


class StrategyVerdict(BaseModel):
    """Two-layer, refuse-to-judge capable verdict (contract owner: P11).

    ``evidence_status`` x ``disposition`` follow design section 3 decision 6:
    insufficient data, zero trades, or unconfirmed semantics must refuse to
    judge (disposition=None) and list blocking reasons.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    run_id: str
    parent_run_id: str | None = None
    strategy_revision_id: str
    spec_hash: str
    snapshot_id: str
    engine_version: str
    policy_version: str = Field(
        description="Version of the VerdictPolicy frozen before results were seen.",
    )
    evidence_status: EvidenceStatus
    disposition: Disposition = None
    reason_codes: list[str] = Field(default_factory=list)
    metrics: MetricsBlock
    comparisons: list[Comparison]
    limitations: list[str] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(
        description="Artifact id -> path; expected keys include ledger, evidence, snapshot, "
        "manifest.",
    )
    generated_at: int = Field(description="Epoch ms at which the verdict was generated.")
    execution_authority: ExecutionAuthority = "none"

    @field_validator("execution_authority")
    @classmethod
    def _authority_is_always_none(cls, value: ExecutionAuthority) -> ExecutionAuthority:
        # Invariant per spec (verdict-card): no disposition ever grants order,
        # paper, or live permission. The Literal already restricts the type;
        # this validator documents the rule at the contract level.
        if value != "none":
            raise ValueError(
                "execution_authority must always be 'none': verdicts never grant trading "
                "permission (observe is not an order, paper, or live license)"
            )
        return value


class BudgetBlock(BaseModel):
    """Reserved vs used budget counters for one task (reserve-then-deduct)."""

    model_config = ConfigDict(extra="forbid")

    llm_calls_reserved: int = Field(ge=0)
    llm_calls_used: int = Field(ge=0)
    tokens_reserved: int = Field(ge=0)
    tokens_used: int = Field(ge=0)
    backtests_reserved: int = Field(ge=0)
    backtests_used: int = Field(ge=0)
    wall_clock_limit_s: float = Field(gt=0.0)


class TaskRecord(BaseModel):
    """Persistent queue task row (contract owner: P12; consumers P13/P14/P16)."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    kind: TaskKind
    payload_sha256: str = Field(description="Content hash for idempotent request reuse.")
    state: TaskState
    stage: str
    attempt: int = Field(ge=0)
    worker_id: str | None = None
    lease_expiry_ms: int | None = None
    fencing_token: int | None = Field(
        None,
        description="Monotonic token rejecting late commits from workers with expired leases.",
    )
    heartbeat_ms: int | None = None
    budget_reserved: BudgetBlock
    error_ref: str | None = None
    created_at: int
    updated_at: int


class TaskEvent(BaseModel):
    """One appended task lifecycle event (incremental polling via ?after_seq=)."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0)
    task_id: str
    ts_ms: int
    kind: str
    detail: str | None = None
