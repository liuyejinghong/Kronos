"""Pre-frozen verdict policy for the v0.5.0 strategy-verdict loop (package P11).

This module owns every threshold the verdict layer applies, declared BEFORE any
evidence is seen (spec: verdict-card, "disposition rules must be frozen before
results are seen"). ``VerdictPolicy`` is a frozen, versioned pydantic model;
``policy_fingerprint`` produces a stable content hash for artifact recording so
a replay can prove the same policy was applied.

Pure declaration only: the evaluation itself lives in
:mod:`kronos.research.verdict.verdict`. No LLM and no I/O anywhere.

Policy defaults (v0.5.0-p0):

- ``min_closed_trades=30``: engineering warning line (warning-only). Below it
  the evidence is *limited*, never auto-invalid, and disposition is never
  ``retire_current_revision``.
- ``neighborhood_consistency_min=0.6``: minimum fraction of *activated* grid
  points whose trade structure matches the center (i.e. ``trades_changed`` is
  False). Strictly below this counts the neighborhood as inconsistent.
- ``max_drawdown_flag=0.5``: drawdown magnitude beyond this adds a limitation
  note only; it never drives a disposition by itself.
- ``cost_sensitivity_flag=True``: arms the cost-robustness rule. When armed and
  the net return flips sign under the ``cost_up`` stress scenario, the verdict
  gains a limitation plus the redesign-leaning reason code
  ``cost_flip_under_stress``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

POLICY_VERSION: Final[str] = "v0.5.0-p0"

#: Default minimum number of closed trades before performance is judged
#: (engineering warning line, warning-only per the v0.5.0 planning baseline).
DEFAULT_MIN_CLOSED_TRADES: Final[int] = 30

#: Default minimum fraction of activated neighborhood points whose trade
#: structure matches the center point.
DEFAULT_NEIGHBORHOOD_CONSISTENCY_MIN: Final[float] = 0.6

#: Default drawdown-magnitude flag that adds a limitation note (never a
#: disposition by itself).
DEFAULT_MAX_DRAWDOWN_FLAG: Final[float] = 0.5

#: Canonical reason-code vocabulary in the fixed order used by every verdict.
REASON_CODE_ORDER: Final[tuple[str, ...]] = (
    "snapshot_invalid",
    "insufficient_zero_trades",
    "insufficient_null_core_metrics",
    "below_min_trades",
    "param_not_activated",
    "cost_flip_under_stress",
    "neighborhood_inconsistent",
    "underperform_both_baselines",
    "max_drawdown_exceeds_policy_flag",
)

#: Fixed boundary limitations appended to every verdict, in this order:
#: testnet does not prove live, the sample-window declaration, and the Kronos
#: variant labeling.
LIMITATION_TESTNET_NOT_LIVE: Final[str] = (
    "Boundary: testnet and backtest results do not prove live-trading performance."
)
LIMITATION_SAMPLE_WINDOW: Final[str] = (
    "Boundary: this verdict holds only for the declared sample window of the frozen "
    "snapshot; it is not a claim about periods outside that window."
)
LIMITATION_KRONOS_VARIANT: Final[str] = (
    "Boundary: results apply only to the Kronos threshold-variant strategy semantics "
    "and do not transfer to other strategy families."
)
BOUNDARY_LIMITATIONS: Final[tuple[str, str, str]] = (
    LIMITATION_TESTNET_NOT_LIVE,
    LIMITATION_SAMPLE_WINDOW,
    LIMITATION_KRONOS_VARIANT,
)


class VerdictPolicy(BaseModel):
    """Frozen, versioned verdict policy constructed before evidence is seen.

    The instance is immutable (``frozen=True``) so a policy captured in an
    artifact cannot be mutated after the fact; thresholds must never be tuned
    after results are known (spec: verdict-card). Replay determinism is proven
    by :meth:`policy_fingerprint`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(
        default=POLICY_VERSION,
        description="Version tag of this pre-frozen policy.",
    )
    min_closed_trades: int = Field(
        default=DEFAULT_MIN_CLOSED_TRADES,
        ge=1,
        description=(
            "Engineering warning line for closed-trade sample size. Below it the "
            "evidence is 'limited' (warning-only, never auto-invalid) and the "
            "disposition is never 'retire_current_revision'."
        ),
    )
    neighborhood_consistency_min: float = Field(
        default=DEFAULT_NEIGHBORHOOD_CONSISTENCY_MIN,
        gt=0.0,
        le=1.0,
        description=(
            "Minimum fraction of activated grid points whose trade structure matches "
            "the center; strictly below this is 'neighborhood_inconsistent'."
        ),
    )
    max_drawdown_flag: float = Field(
        default=DEFAULT_MAX_DRAWDOWN_FLAG,
        gt=0.0,
        le=1.0,
        description=(
            "Drawdown-magnitude flag; exceeding it adds a limitation note only and "
            "never changes the disposition by itself."
        ),
    )
    cost_sensitivity_flag: bool = Field(
        default=True,
        description=(
            "Arms the cost-robustness rule: when the net return flips sign under the "
            "cost_up stress scenario, record a limitation and the "
            "'cost_flip_under_stress' reason code (redesign-leaning)."
        ),
    )

    def policy_fingerprint(self) -> str:
        """Stable sha256 content hash of the full policy for artifact recording.

        Deterministic across processes for the same field values: the canonical
        JSON dump (sorted keys, no whitespace) is hashed. Includes
        ``policy_version``, so any threshold or version change changes the
        fingerprint.
        """
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
