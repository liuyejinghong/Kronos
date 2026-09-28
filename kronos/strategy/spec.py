"""Frozen strategy protocol for the Kronos threshold variant (``kronos_threshold_v1``).

Single source of truth for the *identity* of a judged strategy revision
(v0.5.0 "strategy verdict loop", package P01).

What is frozen here
--------------------
- ``StrategySpec`` encodes the complete identity of one judgeable revision of
  the **Kronos threshold variant of the R-breaker score** (variant id
  ``kronos_threshold_v1``, label "Kronos 变体").  It is deliberately *not*
  classic R-breaker: decisions use the normalized score
  ``q = (close - pivot) / (ATR * volatility_multiplier)`` with hard thresholds
  (q >= +1 open long, q <= -1 open short, zero-cross exits, UTC day-flat).
  The pure decision rules live in :mod:`kronos.strategy.variant_rules`.
- Unknown fields are rejected everywhere (``extra="forbid"``); nothing is
  silently ignored.
- ``signal_timeframe`` is ``Literal["15m", "1h"]``.  ``atr_period`` counts
  *signal bars*, not wall-clock time: switching 15m -> 1h with the same number
  re-interprets the ATR window as that many 1h bars (4x longer window).
- Fills happen at the NEXT available 1m bar open (``fill_ref="next_1m_open"``),
  so ``execution_timeframe`` must be ``"1m"``.  Costs (fee/slippage) are NOT
  part of the spec; they come from a separate cost policy referenced by id.

Identity scheme
----------------
- ``spec_hash`` = sha256 over the canonical JSON (``json.dumps`` with sorted
  keys, compact separators, UTF-8) of the spec *content*: every field except
  ``strategy_revision_id``, ``parent_revision_id``, ``created_at`` and
  ``spec_hash`` itself.
- ``strategy_revision_id`` derives deterministically:
  - root revision (``parent_revision_id is None``): first 12 hex chars of the
    ``spec_hash``;
  - child revision: ``"<parent_revision_id>-<first 8 hex chars of spec_hash>"``.
  Chained children accumulate ``-<hash8>`` suffixes; ids stay traceable and
  collision-resistant for the depth a conversation produces.
- Content that differs only in identity fields (timestamps, lineage) shares a
  ``spec_hash``; changing any content field (e.g. ``volatility_multiplier``)
  changes both ``spec_hash`` and the derived revision id.
- A supplied ``spec_hash`` / ``strategy_revision_id`` that does not match the
  content is rejected, so identity can never be forged.

Construction is ergonomically partial: identity fields may be omitted and are
auto-derived on validation.  :func:`make_revision` builds child revisions for
the conversation service (package P14).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from collections.abc import Mapping

TEMPLATE_VERSION = "kronos_threshold_v1"
VARIANT_LABEL_ZH = "Kronos 变体"
EXECUTION_TIMEFRAME = "1m"
DEFAULT_COST_POLICY_ID = "default_taker"
FILL_REF_NEXT_1M_OPEN = "next_1m_open"
SUPPORTED_SIGNAL_TIMEFRAMES = ("15m", "1h")
MAX_SYMBOLS = 3

_IDENTITY_FIELDS = frozenset(
    {"strategy_revision_id", "parent_revision_id", "created_at", "spec_hash"}
)
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,20}$")
_SYMBOL_MESSAGE = "each symbol must match ^[A-Z0-9]{3,20}$ after strip/upper"
_SPEC_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_REVISION_ID_RE = re.compile(r"^[0-9a-f]{12}(-[0-9a-f]{8})*$")


class VariantParams(BaseModel):
    """Threshold-variant decision parameters.

    ``atr_period`` is measured in *signal bars* (15m or 1h), never in fixed
    wall-clock time: the same number on 1h means a 4x longer ATR window.
    ``volatility_multiplier`` is the ``m`` in ``q = (close - pivot) / (ATR*m)``.
    """

    model_config = ConfigDict(extra="forbid")

    atr_period: int = Field(default=14, ge=2, le=1000)
    volatility_multiplier: float = Field(default=1.0, gt=0.0, le=20.0)


class PositionPolicy(BaseModel):
    """Single-position policy: fraction of equity fixed at entry, never resized.

    Quantity is computed once at entry (``equity_fraction`` of equity at that
    moment) and held constant until the position closes.
    """

    model_config = ConfigDict(extra="forbid")

    equity_fraction: float = Field(default=1.0, gt=0.0, le=1.0)


class FillPolicy(BaseModel):
    """Fill semantics: signal evaluated at completed-bar close, filled at the
    NEXT available 1m bar open."""

    model_config = ConfigDict(extra="forbid")

    fill_ref: Literal["next_1m_open"] = "next_1m_open"


class StrategySpec(BaseModel):
    """Frozen protocol for one judgeable strategy revision (Kronos 变体).

    Identity fields (``strategy_revision_id``, ``parent_revision_id``,
    ``spec_hash``, ``created_at``) may be omitted at construction; they are
    derived on validation (see module docstring).  Supplied values that do not
    match the derivation rule are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    strategy_revision_id: str = ""
    parent_revision_id: str | None = None
    template_version: str = TEMPLATE_VERSION
    variant_label_zh: str = VARIANT_LABEL_ZH
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT"])
    signal_timeframe: Literal["15m", "1h"] = "15m"
    execution_timeframe: str = EXECUTION_TIMEFRAME
    params: VariantParams = Field(default_factory=lambda: VariantParams())
    position_policy: PositionPolicy = Field(default_factory=lambda: PositionPolicy())
    fill_policy: FillPolicy = Field(default_factory=lambda: FillPolicy())
    cost_policy_id: str = DEFAULT_COST_POLICY_ID
    spec_hash: str = ""
    created_at: str = ""

    @field_validator("strategy_revision_id")
    @classmethod
    def _validate_strategy_revision_id(cls, value: str) -> str:
        if value and not _REVISION_ID_RE.match(value):
            raise ValueError(
                "strategy_revision_id must match ^[0-9a-f]{12}(-[0-9a-f]{8})*$ "
                f"or be empty (auto-derived), got {value!r}"
            )
        return value

    @field_validator("parent_revision_id")
    @classmethod
    def _normalize_parent_revision_id(cls, value: str | None) -> str | None:
        if value is None or not value:
            return None
        if not _REVISION_ID_RE.match(value):
            raise ValueError(
                f"parent_revision_id must match ^[0-9a-f]{{12}}(-[0-9a-f]{{8}})*$, got {value!r}"
            )
        return value

    @field_validator("template_version")
    @classmethod
    def _pin_template_version(cls, value: str) -> str:
        if value != TEMPLATE_VERSION:
            raise ValueError(f"template_version is frozen to {TEMPLATE_VERSION!r}, got {value!r}")
        return value

    @field_validator("variant_label_zh")
    @classmethod
    def _validate_variant_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("variant_label_zh must be a non-empty label")
        return value

    @field_validator("symbols")
    @classmethod
    def _validate_symbols(cls, value: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in value]
        if not normalized:
            raise ValueError("symbols must contain at least one symbol")
        invalid = [symbol for symbol in normalized if not _SYMBOL_RE.match(symbol)]
        if invalid:
            raise ValueError(f"{_SYMBOL_MESSAGE}, invalid: {invalid}")
        deduped = list(dict.fromkeys(normalized))
        if len(deduped) > MAX_SYMBOLS:
            raise ValueError(
                f"symbols supports at most {MAX_SYMBOLS} distinct symbols, "
                f"got {len(deduped)}: {deduped}"
            )
        return deduped

    @field_validator("cost_policy_id")
    @classmethod
    def _pin_cost_policy_id(cls, value: str) -> str:
        if value != DEFAULT_COST_POLICY_ID:
            raise ValueError(
                f"cost_policy_id is frozen to {DEFAULT_COST_POLICY_ID!r}, got {value!r}"
            )
        return value

    @field_validator("spec_hash")
    @classmethod
    def _validate_spec_hash(cls, value: str) -> str:
        if value and not _SPEC_HASH_RE.match(value):
            raise ValueError(
                f"spec_hash must be 64 lowercase hex chars or empty (auto-derived), got {value!r}"
            )
        return value

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: str) -> str:
        if not value:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"created_at must be an ISO-8601 datetime, got {value!r}") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError(f"created_at must be UTC (...Z or +00:00), got {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_timeframe_combination(self) -> StrategySpec:
        if (
            self.fill_policy.fill_ref == FILL_REF_NEXT_1M_OPEN
            and self.execution_timeframe != EXECUTION_TIMEFRAME
        ):
            raise ValueError(
                f"execution_timeframe must be {EXECUTION_TIMEFRAME!r} when fill_ref is "
                f"{FILL_REF_NEXT_1M_OPEN!r} (signals fill at the next 1m bar open), "
                f"got {self.execution_timeframe!r}"
            )
        return self

    @model_validator(mode="after")
    def _finalize_identity(self) -> StrategySpec:
        content_hash = compute_spec_hash(spec_identity_content(self))
        if self.spec_hash and self.spec_hash != content_hash:
            raise ValueError(
                f"spec_hash does not match spec content: expected {content_hash}, "
                f"got {self.spec_hash}"
            )
        derived_id = derive_revision_id(content_hash, self.parent_revision_id)
        if self.strategy_revision_id and self.strategy_revision_id != derived_id:
            raise ValueError(
                "strategy_revision_id does not match the derivation rule: "
                f"expected {derived_id}, got {self.strategy_revision_id}"
            )
        updates: dict[str, str] = {}
        if not self.spec_hash:
            updates["spec_hash"] = content_hash
        if not self.strategy_revision_id:
            updates["strategy_revision_id"] = derived_id
        if not self.created_at:
            updates["created_at"] = utc_now_iso()
        if updates:
            return self.model_copy(update=updates)
        return self


def utc_now_iso() -> str:
    """Return the current UTC time as a second-precision ISO-8601 string."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def spec_identity_content(spec: StrategySpec) -> dict[str, Any]:
    """Return the spec content fields covered by the hash (identity excluded)."""
    payload = spec.model_dump(mode="json")
    return {key: value for key, value in payload.items() if key not in _IDENTITY_FIELDS}


def compute_spec_hash(content: Mapping[str, Any]) -> str:
    """Return the sha256 of the canonical JSON of ``content``.

    Canonical form: ``json.dumps`` with sorted keys, compact separators and
    ``ensure_ascii=False``, encoded as UTF-8.  Deterministic across processes.
    """
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_revision_id(spec_hash: str, parent_revision_id: str | None) -> str:
    """Derive ``strategy_revision_id`` from content hash and lineage.

    - root (``parent_revision_id is None``): ``spec_hash[:12]``;
    - child: ``"<parent_revision_id>-<spec_hash[:8]>"`` (rule frozen in v0.5.0).
    """
    if parent_revision_id is None:
        return spec_hash[:12]
    return f"{parent_revision_id}-{spec_hash[:8]}"


def make_revision(spec: StrategySpec, param_overrides: Mapping[str, Any]) -> StrategySpec:
    """Create a child revision of ``spec`` with ``param_overrides`` applied.

    Only ``VariantParams`` fields may be overridden; unknown names raise
    ``ValueError`` and out-of-range values fail pydantic validation.  All other
    content is inherited unchanged.  The child's ``spec_hash`` covers the merged
    content, so overriding with the current parameter values yields a no-op
    revision whose id still differs from its parent's (lineage is in the id, not
    the hash).  The parent is never mutated.
    """
    current_params = spec.params.model_dump()
    unknown = sorted(set(param_overrides) - set(current_params))
    if unknown:
        raise ValueError(f"unknown param names for make_revision: {unknown}")
    child_params = VariantParams.model_validate({**current_params, **param_overrides})
    child_content = spec_identity_content(spec)
    child_content["params"] = child_params.model_dump(mode="json")
    child_hash = compute_spec_hash(child_content)
    return StrategySpec.model_validate(
        {
            **child_content,
            "parent_revision_id": spec.strategy_revision_id,
            "spec_hash": child_hash,
            "strategy_revision_id": derive_revision_id(child_hash, spec.strategy_revision_id),
            "created_at": utc_now_iso(),
        }
    )
