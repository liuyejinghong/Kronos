"""Loader for the P02 hand-computed golden cases (v0.5.0 strategy verdict loop).

Public API
----------
- :func:`load_case` -> :class:`GoldenCase` (bars, params, cost, funding, expected).
- :func:`load_expected` -> :class:`GoldenExpected` (raw JSON payload).
- :func:`expected_models` -> :class:`kronos.research.verdict.contracts.ExecutionLedger`
  built by validating the expected JSON against the frozen contracts models.

File layout
-----------
- ``cases/<CASE_ID>.json``: ``meta``, ``symbol``, ``signal_timeframe``, ``spec``
  (atr_period / volatility_multiplier / symbol), ``cost`` (fee_bps=4,
  slippage_bps=5), ``start_equity``, ``equity_fraction``, ``bars_15m``,
  ``bars_1m``, ``funding_events``.
- ``expected/<CASE_ID>.json``: ``case_id``, ``final_equity``, ``closed_trades``
  (contracts.ClosedTrade fields), ``ledger_events`` (contracts.ExecutionRecord
  fields). Every number was derived by hand; see ``HAND_MATH.md`` for the full
  step-by-step arithmetic (this is the independence guarantee).

Series semantics (documented here and in HAND_MATH.md)
------------------------------------------------------
- ``bars_15m`` is the SIGNAL series (one entry per completed 15m UTC bar;
  ``ts_ms`` is the bar OPEN time, close = open + 900_000). It always contains
  the full warmup: one complete prior UTC day (96 bars) plus ``atr_period``
  seed bars. Day 0 is 96 identical standard bars in every case.
- ``bars_1m`` is the EXECUTION series and is deliberately SPARSE: it contains
  flat 1m bars only around fill moments (and the first minutes of the next UTC
  day for day-end fills). The fill rule "next available 1m bar open" means the
  first 1m bar with ``ts_ms >=`` the signal bar's close ts; cases with zero
  trades carry an empty ``bars_1m``. It is NOT a contiguous 1m series and must
  not be resampled.
- Cost convention (canonical, per Lead ruling 2026-09-27): fill price = raw
  next-1m open adjusted adversely by slippage 5bps ONLY -> buy at
  ``open * 1.0005``, sell at ``open * 0.9995``; PLUS a fee of ``4bps`` on the
  notional at the adjusted fill price, charged as its own ``fee`` ledger event.
  The fee is NOT compounded into the fill price; all-in cost is ~9bps per side.
  Quantities are ``equity_at_entry / fill_price`` rounded to 6 decimals; the
  rounded quantity is used for all downstream math. Derived values
  (gross/fees/net/final equity) are computed from the published 6-decimal
  components so a reader summing the JSON numbers reproduces them.

Only the stdlib and ``kronos.research.verdict.contracts`` are imported.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kronos.research.verdict.contracts import ClosedTrade, ExecutionLedger, ExecutionRecord
from kronos.strategy.spec import VariantParams

GOLDEN_DIR: Path = Path(__file__).resolve().parent
CASES_DIR: Path = GOLDEN_DIR / "cases"
EXPECTED_DIR: Path = GOLDEN_DIR / "expected"

CASE_IDS: tuple[str, ...] = (
    "G01",
    "G02",
    "G03",
    "G04",
    "G05",
    "G06",
    "G07",
    "G08",
    "G09",
    "G10",
    "G11",
)


@dataclass(frozen=True)
class Bar:
    """One OHLC bar; ``ts_ms`` is the bar OPEN time (epoch ms, UTC).

    Field names mirror the JSON keys (``o``/``h``/``l``/``c``).
    """

    ts_ms: int
    o: float
    h: float
    l: float  # noqa: E741 - mirrors the OHLC "l" JSON key
    c: float


@dataclass(frozen=True)
class FundingEvent:
    """One perpetual-funding settlement instant (rate applies to open positions)."""

    ts_ms: int
    rate: float


@dataclass(frozen=True)
class CostPolicy:
    """Per-side cost parameters shared by every golden case."""

    fee_bps: float
    slippage_bps: float


@dataclass(frozen=True)
class SpecParams:
    """Threshold-variant decision parameters for one case."""

    atr_period: int
    volatility_multiplier: float
    symbol: str


@dataclass(frozen=True)
class GoldenExpected:
    """Raw expected payload (dicts shaped like the contracts models)."""

    case_id: str
    final_equity: float
    closed_trades: list[dict[str, Any]]
    ledger_events: list[dict[str, Any]]


@dataclass(frozen=True)
class GoldenCase:
    """One hand-computed golden case with its expected results."""

    case_id: str
    description: str
    signal_timeframe: str
    bars_15m: list[Bar]
    bars_1m: list[Bar]
    params: SpecParams
    funding_events: list[FundingEvent]
    cost: CostPolicy
    start_equity: float
    equity_fraction: float
    expected: GoldenExpected


def list_cases() -> tuple[str, ...]:
    """Return all golden case ids in canonical order."""
    return CASE_IDS


def _read_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}, got {type(payload).__name__}")
    return payload


def _require(payload: dict[str, Any], key: str, path: Path) -> Any:
    if key not in payload:
        raise ValueError(f"missing key {key!r} in {path}")
    return payload[key]


def _parse_bars(raw: Any, path: Path, key: str) -> list[Bar]:
    if not isinstance(raw, list):
        raise ValueError(f"{key!r} must be a list in {path}")
    bars: list[Bar] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"{key!r} entries must be objects in {path}")
        bars.append(
            Bar(
                ts_ms=int(item["ts_ms"]),
                o=float(item["o"]),
                h=float(item["h"]),
                l=float(item["l"]),
                c=float(item["c"]),
            )
        )
    return bars


def load_case(case_id: str) -> GoldenCase:
    """Load one golden case (bars, params, cost, funding, expected)."""
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise ValueError(f"unknown golden case {case_id!r} (no file {path})")
    payload = _read_json(path)
    meta = _require(payload, "meta", path)
    if not isinstance(meta, dict):
        raise ValueError(f"'meta' must be an object in {path}")
    spec = _require(payload, "spec", path)
    if not isinstance(spec, dict):
        raise ValueError(f"'spec' must be an object in {path}")
    cost = _require(payload, "cost", path)
    if not isinstance(cost, dict):
        raise ValueError(f"'cost' must be an object in {path}")
    funding_raw = _require(payload, "funding_events", path)
    if not isinstance(funding_raw, list):
        raise ValueError(f"'funding_events' must be a list in {path}")
    funding = [FundingEvent(ts_ms=int(e["ts_ms"]), rate=float(e["rate"])) for e in funding_raw]
    return GoldenCase(
        case_id=str(meta["case_id"]),
        description=str(meta["description"]),
        signal_timeframe=str(_require(payload, "signal_timeframe", path)),
        bars_15m=_parse_bars(_require(payload, "bars_15m", path), path, "bars_15m"),
        bars_1m=_parse_bars(_require(payload, "bars_1m", path), path, "bars_1m"),
        params=SpecParams(
            atr_period=int(spec["atr_period"]),
            volatility_multiplier=float(spec["volatility_multiplier"]),
            symbol=str(spec["symbol"]),
        ),
        funding_events=funding,
        cost=CostPolicy(fee_bps=float(cost["fee_bps"]), slippage_bps=float(cost["slippage_bps"])),
        start_equity=float(_require(payload, "start_equity", path)),
        equity_fraction=float(_require(payload, "equity_fraction", path)),
        expected=load_expected(case_id),
    )


def load_expected(case_id: str) -> GoldenExpected:
    """Load the hand-computed expected payload for one case."""
    path = EXPECTED_DIR / f"{case_id}.json"
    if not path.exists():
        raise ValueError(f"unknown golden case {case_id!r} (no file {path})")
    payload = _read_json(path)
    trades = _require(payload, "closed_trades", path)
    events = _require(payload, "ledger_events", path)
    if not isinstance(trades, list) or not isinstance(events, list):
        raise ValueError(f"'closed_trades' and 'ledger_events' must be lists in {path}")
    return GoldenExpected(
        case_id=str(_require(payload, "case_id", path)),
        final_equity=float(_require(payload, "final_equity", path)),
        closed_trades=trades,
        ledger_events=events,
    )


def expected_models(case_id: str) -> ExecutionLedger:
    """Validate the expected JSON against the frozen contracts models.

    Returns an :class:`ExecutionLedger` whose ``records``/``closed_trades`` are
    contract-typed, proving the hand-computed expectations serialize into the
    frozen v0.5.0 field-level contracts.
    """
    raw = load_expected(case_id)
    records = [ExecutionRecord.model_validate(event) for event in raw.ledger_events]
    trades = [ClosedTrade.model_validate(trade) for trade in raw.closed_trades]
    case = load_case(case_id)
    return ExecutionLedger(
        symbol=case.params.symbol,
        strategy_revision_id=f"golden-{case_id}",
        records=records,
        final_equity=raw.final_equity,
        closed_trades=trades,
    )


@dataclass(frozen=True)
class GoldenCaseBundle:
    """Engine-integration view of one golden case (P04 cross-check shape).

    ``bars_15m``/``bars_1m``/``funding_events`` are plain tuples because the
    reference ledger consumes positional OHLC rows; ``params`` is the frozen
    :class:`VariantParams` model; ``expected_ledger`` is the hand-computed
    expectation validated against the contracts (NOT produced by any engine).
    """

    name: str
    description: str
    bars_15m: list[tuple[int, float, float, float, float]]
    bars_1m: list[tuple[int, float, float, float, float]]
    params: VariantParams
    cost: CostPolicy
    start_equity: float
    funding_events: list[tuple[int, float]]
    expected_ledger: ExecutionLedger


def load_golden_cases() -> list[GoldenCaseBundle]:
    """Load every golden case in the tuple/params shape the P04 match test uses."""
    bundles: list[GoldenCaseBundle] = []
    for case_id in CASE_IDS:
        case = load_case(case_id)
        bundles.append(
            GoldenCaseBundle(
                name=case.case_id,
                description=case.description,
                bars_15m=[(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_15m],
                bars_1m=[(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_1m],
                params=VariantParams(
                    atr_period=case.params.atr_period,
                    volatility_multiplier=case.params.volatility_multiplier,
                ),
                cost=case.cost,
                start_equity=case.start_equity,
                funding_events=[(f.ts_ms, f.rate) for f in case.funding_events],
                expected_ledger=expected_models(case.case_id),
            )
        )
    return bundles
