# ruff: noqa: RUF001 -- human-facing budget messages are Chinese with full-width punctuation.
"""Budget executor for the v0.5.0 strategy-verdict loop (P13).

Implements the reserve -> spend -> receipt semantics required by the
task-runtime spec ("预算必须预留制且不可绕过") for four budget dimensions:

- LLM call counts      (per research round, default 3),
- tokens               (per round 16k, rolling 24h 100k, rolling 7d 500k),
- backtest counts      (per research round, default 40),
- wall clock seconds   (per research round, default 1800 s).

Initial values come from D-20260928-002 and planning section 4.7; they are
dataclass defaults on :class:`BudgetLimits` and fully overridable.

Storage decision: the ledger owns a dedicated small SQLite file
(``budget.sqlite3`` next to the task store's ``runtime.sqlite3``) instead of
adding tables to the task DB. A separate file keeps budget writes off the
task-queue database and makes the ledger self-contained; both files live in
the same state directory and are created by the caller.

Budgets never reset. Per-round budgets are keyed by ``round_id``; the daily
and weekly token budgets are trailing rolling windows computed from the
spend table by timestamp, so a new session, a process restart, or a fresh
round/subtask can never bypass them.

Schema (four tables):

- ``rounds``: one row per round_id with its frozen per-round budgets and the
  wall-clock anchor. Inserted on first use; never updated with new limits.
- ``reservations``: open reservations, idempotent by ``reservation_id``.
- ``spend``: append-only usage receipts (round_id, kind, amount, ts, meta).
- ``budget_events``: over-limit receipts and other budget events.

Semantics summary:

===============  ==========================  ============================
Dimension        Scope                       Enforcement point
===============  ==========================  ============================
llm_call         per round                   reserve + over_limit event
token            per round + rolling 24h/7d  reserve (all three); spend
                                             records per-round over_limit,
                                             rolling bites at next reserve
backtest         per round                   reserve + over_limit event
wall_clock_s     per round                   reserve (remaining must be
                                             positive) + over_limit event
===============  ==========================  ============================

Real usage may exceed a reservation (spend is never truncated); the excess
shows up as an ``over_limit`` event and as reduced headroom at the next
reserve. Token usage reported without provider numbers must be recorded with
``meta={"estimated": True}``; a non-positive amount then falls back to the
conservative ``unreported_usage_default_tokens`` (never zero).
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, cast

from kronos.common.errors import KronosError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from kronos.runtime.tasks import TaskStore

__all__ = [
    "BUDGET_DIMENSIONS",
    "RESERVATION_ID_PAYLOAD_KEY",
    "ROUND_ID_PAYLOAD_KEY",
    "SPEND_KINDS",
    "BudgetEvent",
    "BudgetExhausted",
    "BudgetGuardVerdict",
    "BudgetLedger",
    "BudgetLimits",
    "BudgetPlan",
    "DimensionUsage",
    "Reservation",
    "RoundInfo",
    "RoundUsage",
    "SpendKind",
    "SpendReceipt",
    "budget_guard",
    "render_budget_report",
]

type SpendKind = Literal["llm_call", "token", "backtest", "wall_clock_s"]
SPEND_KINDS: Final[tuple[SpendKind, ...]] = ("llm_call", "token", "backtest", "wall_clock_s")

type BudgetDimension = Literal[
    "llm_calls",
    "tokens_round",
    "tokens_day",
    "tokens_week",
    "backtests",
    "wall_clock",
]
BUDGET_DIMENSIONS: Final[tuple[BudgetDimension, ...]] = (
    "llm_calls",
    "tokens_round",
    "tokens_day",
    "tokens_week",
    "backtests",
    "wall_clock",
)

#: Payload keys a submitter uses to bind a task to its budget reservation
#: (checked by :func:`budget_guard` before a worker commits a result). The
#: ``budget_*`` forms are canonical; the shorter forms are accepted fallbacks.
RESERVATION_ID_PAYLOAD_KEY: Final[str] = "budget_reservation_id"
ROUND_ID_PAYLOAD_KEY: Final[str] = "budget_round_id"

_DAY_MS: Final[int] = 86_400_000
_WEEK_MS: Final[int] = 7 * _DAY_MS
#: Tolerance so integer-ish float sums compare exactly at the cap.
_EPS: Final[float] = 1e-9

_DIMENSION_LABELS: Final[dict[str, str]] = {
    "llm_calls": "本轮 LLM 调用次数",
    "tokens_round": "本轮 token 预算",
    "tokens_day": "当日 token 预算（近24小时滚动）",
    "tokens_week": "每周 token 预算（近7天滚动）",
    "backtests": "本轮回测次数",
    "wall_clock": "本轮墙钟时间",
}

_SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS rounds (
    round_id           TEXT PRIMARY KEY,
    created_at_ms      INTEGER NOT NULL,
    llm_calls_limit    INTEGER NOT NULL,
    tokens_limit       INTEGER NOT NULL,
    backtests_limit    INTEGER NOT NULL,
    wall_clock_limit_s REAL NOT NULL,
    clock_start_ms     INTEGER
);
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    round_id       TEXT NOT NULL,
    llm_calls      INTEGER NOT NULL,
    tokens         INTEGER NOT NULL,
    backtests      INTEGER NOT NULL,
    created_at_ms  INTEGER NOT NULL,
    meta_json      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reservations_created
    ON reservations(created_at_ms);
CREATE TABLE IF NOT EXISTS spend (
    round_id       TEXT NOT NULL,
    kind           TEXT NOT NULL,
    amount         REAL NOT NULL,
    ts_ms          INTEGER NOT NULL,
    reservation_id TEXT,
    meta_json      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spend_round_kind ON spend(round_id, kind);
CREATE INDEX IF NOT EXISTS idx_spend_kind_ts ON spend(kind, ts_ms);
CREATE TABLE IF NOT EXISTS budget_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id TEXT NOT NULL,
    kind     TEXT NOT NULL,
    detail   TEXT,
    ts_ms    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_budget_events_round ON budget_events(round_id);
"""


def now_ms() -> int:
    """Current wall-clock time in epoch milliseconds (injectable in tests)."""
    return int(time.time() * 1000)


def _g(value: float) -> str:
    """Format a budget quantity compactly (1500.0 -> '1500', 0.5 -> '0.5')."""
    return f"{value:g}"


@dataclass(frozen=True)
class BudgetLimits:
    """Initial budget fuses (D-20260928-002 + planning section 4.7)."""

    llm_calls_per_round: int = 3
    tokens_per_round: int = 16_000
    tokens_per_day: int = 100_000
    tokens_per_week: int = 500_000
    backtests_per_round: int = 40
    wall_clock_per_round_s: float = 1800.0


@dataclass(frozen=True)
class BudgetPlan:
    """Resources a caller wants reserved before doing work."""

    llm_calls: int = 0
    tokens: int = 0
    backtests: int = 0


@dataclass(frozen=True)
class Reservation:
    """A recorded reservation; idempotent by ``reservation_id``."""

    reservation_id: str
    round_id: str
    llm_calls: int
    tokens: int
    backtests: int
    created_at_ms: int


@dataclass(frozen=True)
class SpendReceipt:
    """Receipt for one recorded usage amount."""

    round_id: str
    kind: SpendKind
    amount: float
    ts_ms: int
    reservation_id: str | None
    over_limit: bool


@dataclass(frozen=True)
class BudgetEvent:
    """One budget event (currently only ``over_limit`` receipts)."""

    round_id: str
    kind: str
    detail: str | None
    ts_ms: int


@dataclass(frozen=True)
class RoundInfo:
    """Frozen per-round budgets plus the wall-clock anchor."""

    round_id: str
    created_at_ms: int
    limits: BudgetLimits
    clock_start_ms: int | None


@dataclass(frozen=True)
class DimensionUsage:
    """Limit / used / reserved projection for one budget dimension."""

    dimension: BudgetDimension
    limit: float
    used: float
    reserved: float

    @property
    def projected(self) -> float:
        """Used plus still-open reservations."""
        return self.used + self.reserved

    @property
    def remaining(self) -> float:
        """Headroom left after open reservations."""
        return max(0.0, self.limit - self.projected)


@dataclass(frozen=True)
class RoundUsage:
    """Full budget projection for one round, including rolling windows."""

    round_id: str
    llm_calls: DimensionUsage
    tokens_round: DimensionUsage
    tokens_day: DimensionUsage
    tokens_week: DimensionUsage
    backtests: DimensionUsage
    wall_clock: DimensionUsage
    wall_clock_remaining_ms: int


@dataclass(frozen=True)
class BudgetGuardVerdict:
    """Result of :func:`budget_guard` for one task before result commit."""

    task_id: str
    round_id: str | None
    reservation_id: str | None
    allowed: bool
    reason: str | None
    wall_clock_remaining_ms: int | None


class BudgetExhausted(KronosError):  # noqa: N818 - name fixed by the P13 package contract.
    """A budget dimension has no headroom for the requested reservation.

    ``kind`` names the exhausted dimension, ``remaining`` is the headroom
    left after open reservations (zero or the unusable residue), and the
    exception text is a Chinese human-facing message safe to surface in the
    UI verbatim.
    """

    def __init__(self, kind: BudgetDimension, message: str, *, remaining: float = 0.0) -> None:
        super().__init__(message)
        self.kind = kind
        self.remaining = remaining
        self.human_message = message


def _exhausted_message(
    dimension: BudgetDimension, limit: float, used: float, reserved: float
) -> str:
    label = _DIMENSION_LABELS[dimension]
    return (
        f"预算不足：{label}已用尽（上限 {_g(limit)}，已用 {_g(used)}，预留 {_g(reserved)}，"
        "剩余 0）。本轮不得继续消耗该资源，也不得通过重开同义任务绕过；"
        "请开启新一轮研究或在设置中显式调整预算。"
    )


def _wall_clock_exhausted_message(limit_s: float, elapsed_s: float) -> str:
    return (
        f"预算不足：本轮墙钟时间已用尽（上限 {_g(limit_s)}s，已用 {_g(elapsed_s)}s，剩余 0s）。"
        "本轮必须停止并输出预算终止报告与已完成产物，不得通过重开同义任务绕过。"
    )


class BudgetLedger:
    """Persistent budget ledger over one dedicated SQLite file.

    All mutating operations run inside ``BEGIN IMMEDIATE`` transactions under
    an in-process lock (same pattern as the task store), and every method
    that depends on time accepts ``now`` (epoch ms) for deterministic tests.
    Reopening the same path continues from the persisted state: budgets are
    never reset by restarts, new sessions, or new subtasks.
    """

    def __init__(
        self,
        state_path: str | Path,
        *,
        limits: BudgetLimits | None = None,
        unreported_usage_default_tokens: int = 2_000,
    ) -> None:
        self._path = Path(state_path)
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        self.limits = limits if limits is not None else BudgetLimits()
        #: Conservative token estimate when the provider reports no usage.
        self.unreported_usage_default_tokens = int(unreported_usage_default_tokens)

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> BudgetLedger:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    @property
    def db_path(self) -> Path:
        """Path of the backing SQLite file."""
        return self._path

    # ------------------------------------------------------------------ internals

    @contextmanager
    def _write_tx(self) -> Iterator[sqlite3.Cursor]:
        """Serialized write transaction: BEGIN IMMEDIATE .. COMMIT/ROLLBACK."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn.cursor()
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    @staticmethod
    def _row_to_round(row: sqlite3.Row) -> RoundInfo:
        limits = BudgetLimits(
            llm_calls_per_round=int(row["llm_calls_limit"]),
            tokens_per_round=int(row["tokens_limit"]),
            backtests_per_round=int(row["backtests_limit"]),
            wall_clock_per_round_s=float(row["wall_clock_limit_s"]),
        )
        clock_start = row["clock_start_ms"]
        return RoundInfo(
            round_id=row["round_id"],
            created_at_ms=int(row["created_at_ms"]),
            limits=limits,
            clock_start_ms=None if clock_start is None else int(clock_start),
        )

    @staticmethod
    def _row_to_reservation(row: sqlite3.Row) -> Reservation:
        return Reservation(
            reservation_id=row["reservation_id"],
            round_id=row["round_id"],
            llm_calls=int(row["llm_calls"]),
            tokens=int(row["tokens"]),
            backtests=int(row["backtests"]),
            created_at_ms=int(row["created_at_ms"]),
        )

    def _ensure_round(
        self, cur: sqlite3.Cursor, round_id: str, ts: int, limits: BudgetLimits
    ) -> sqlite3.Row:
        """Return the round row, auto-registering it with ``limits`` if unknown.

        Existing rounds are returned untouched: budgets are frozen at round
        creation and are never reset or widened.
        """
        row = cur.execute("SELECT * FROM rounds WHERE round_id = ?", (round_id,)).fetchone()
        if row is None:
            cur.execute(
                """
                INSERT INTO rounds (
                    round_id, created_at_ms, llm_calls_limit, tokens_limit,
                    backtests_limit, wall_clock_limit_s
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    round_id,
                    ts,
                    limits.llm_calls_per_round,
                    limits.tokens_per_round,
                    limits.backtests_per_round,
                    limits.wall_clock_per_round_s,
                ),
            )
            row = cur.execute("SELECT * FROM rounds WHERE round_id = ?", (round_id,)).fetchone()
        assert row is not None
        return cast("sqlite3.Row", row)

    @staticmethod
    def _spent_by_reservation(cur: sqlite3.Cursor) -> dict[tuple[str, str], float]:
        """Total spend per (reservation_id, kind) for open-reservation math."""
        rows = cur.execute(
            """
            SELECT reservation_id, kind, COALESCE(SUM(amount), 0) AS total
            FROM spend WHERE reservation_id IS NOT NULL
            GROUP BY reservation_id, kind
            """
        ).fetchall()
        return {(row["reservation_id"], row["kind"]): float(row["total"]) for row in rows}

    @staticmethod
    def _open_reserved(
        res_rows: Sequence[sqlite3.Row],
        spent: Mapping[tuple[str, str], float],
        spend_kind: SpendKind,
        attr: str,
    ) -> float:
        """Reservation amounts not yet covered by spend (per dimension)."""
        total = 0.0
        for row in res_rows:
            planned = float(row[attr])
            used = spent.get((row["reservation_id"], spend_kind), 0.0)
            total += max(0.0, planned - used)
        return total

    def _totals(
        self, cur: sqlite3.Cursor, round_row: sqlite3.Row, ts: int
    ) -> dict[str, tuple[float, float]]:
        """(used, open_reserved) per dimension for one round at time ``ts``.

        Token spend counts toward the per-round budget AND both rolling
        windows; llm_call/backtest are per-round only.
        """
        round_id: str = round_row["round_id"]
        round_used = {
            row["kind"]: float(row["total"])
            for row in cur.execute(
                "SELECT kind, COALESCE(SUM(amount), 0) AS total FROM spend "
                "WHERE round_id = ? GROUP BY kind",
                (round_id,),
            ).fetchall()
        }
        spent = self._spent_by_reservation(cur)
        round_res = cur.execute(
            "SELECT * FROM reservations WHERE round_id = ?", (round_id,)
        ).fetchall()
        day_start = ts - _DAY_MS
        week_start = ts - _WEEK_MS
        day_res = cur.execute(
            "SELECT * FROM reservations WHERE created_at_ms >= ?", (day_start,)
        ).fetchall()
        week_res = cur.execute(
            "SELECT * FROM reservations WHERE created_at_ms >= ?", (week_start,)
        ).fetchall()

        def window_used(start_ms: int) -> float:
            row = cur.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM spend "
                "WHERE kind = 'token' AND ts_ms >= ?",
                (start_ms,),
            ).fetchone()
            assert row is not None
            return float(row["total"])

        return {
            "llm_calls": (
                round_used.get("llm_call", 0.0),
                self._open_reserved(round_res, spent, "llm_call", "llm_calls"),
            ),
            "tokens_round": (
                round_used.get("token", 0.0),
                self._open_reserved(round_res, spent, "token", "tokens"),
            ),
            "tokens_day": (
                window_used(day_start),
                self._open_reserved(day_res, spent, "token", "tokens"),
            ),
            "tokens_week": (
                window_used(week_start),
                self._open_reserved(week_res, spent, "token", "tokens"),
            ),
            "backtests": (
                round_used.get("backtest", 0.0),
                self._open_reserved(round_res, spent, "backtest", "backtests"),
            ),
        }

    @staticmethod
    def _round_limit(round_row: sqlite3.Row, kind: SpendKind) -> float:
        if kind == "llm_call":
            return float(round_row["llm_calls_limit"])
        if kind == "token":
            return float(round_row["tokens_limit"])
        if kind == "backtest":
            return float(round_row["backtests_limit"])
        return float(round_row["wall_clock_limit_s"])

    # ------------------------------------------------------------------ rounds

    def start_round(
        self,
        round_id: str,
        *,
        limits: BudgetLimits | None = None,
        now: int | None = None,
    ) -> RoundInfo:
        """Register a round, or return the existing one unchanged.

        Idempotent: an existing round keeps its frozen budgets and clock
        anchor; the ``limits`` argument only applies to newly created rounds.
        Nothing here can reset a budget.
        """
        ts = now if now is not None else now_ms()
        effective = limits if limits is not None else self.limits
        with self._write_tx() as cur:
            row = self._ensure_round(cur, round_id, ts, effective)
            return self._row_to_round(row)

    def start_round_clock(self, round_id: str, *, now: int | None = None) -> int:
        """Anchor the round's wall clock; returns the anchor epoch ms.

        The first anchor wins: a second call (or a restart) can never move
        the anchor and therefore never extends the round's wall-clock budget.
        """
        ts = now if now is not None else now_ms()
        with self._write_tx() as cur:
            row = self._ensure_round(cur, round_id, ts, self.limits)
            anchor = row["clock_start_ms"]
            if anchor is not None:
                return int(anchor)
            cur.execute("UPDATE rounds SET clock_start_ms = ? WHERE round_id = ?", (ts, round_id))
            return ts

    def remaining_ms(self, round_id: str, *, now: int | None = None) -> int:
        """Wall-clock headroom for the round in ms (>= 0; 0 means exhausted).

        Rounds without a started clock have their full budget remaining.
        """
        ts = now if now is not None else now_ms()
        with self._lock:
            row = self._conn.execute(
                "SELECT wall_clock_limit_s, clock_start_ms FROM rounds WHERE round_id = ?",
                (round_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown round: {round_id}")
        limit_ms = float(row["wall_clock_limit_s"]) * 1000.0
        anchor = row["clock_start_ms"]
        if anchor is None:
            return int(limit_ms)
        return max(0, int(limit_ms - (ts - int(anchor))))

    def round_info(self, round_id: str) -> RoundInfo:
        """Return the frozen round record."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rounds WHERE round_id = ?", (round_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown round: {round_id}")
        return self._row_to_round(row)

    # ------------------------------------------------------------------ reserve

    def reserve(
        self,
        round_id: str,
        plan: BudgetPlan,
        *,
        reservation_id: str | None = None,
        meta: Mapping[str, object] | None = None,
        now: int | None = None,
    ) -> Reservation:
        """Atomically check headroom on every dimension, then reserve.

        Checks per-round budgets (llm_calls, tokens, backtests), both rolling
        token windows (24h / 7d, reservations included), and the round's wall
        clock. Raises :class:`BudgetExhausted` with a Chinese human message
        naming the first exhausted dimension. Idempotent by
        ``reservation_id``: reserving again with the same id returns the
        original reservation without re-checking or double-charging.
        """
        ts = now if now is not None else now_ms()
        if plan.llm_calls < 0 or plan.tokens < 0 or plan.backtests < 0:
            raise ValueError("BudgetPlan amounts must be non-negative")
        with self._write_tx() as cur:
            if reservation_id is not None:
                existing = cur.execute(
                    "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,)
                ).fetchone()
                if existing is not None:
                    return self._row_to_reservation(existing)
            round_row = self._ensure_round(cur, round_id, ts, self.limits)

            anchor = round_row["clock_start_ms"]
            if anchor is not None:
                limit_s = float(round_row["wall_clock_limit_s"])
                elapsed_s = (ts - int(anchor)) / 1000.0
                if elapsed_s >= limit_s:
                    raise BudgetExhausted(
                        "wall_clock",
                        _wall_clock_exhausted_message(limit_s, elapsed_s),
                    )

            totals = self._totals(cur, round_row, ts)
            day_limit = float(self.limits.tokens_per_day)
            week_limit = float(self.limits.tokens_per_week)
            checks: tuple[tuple[BudgetDimension, float, float, float, int], ...] = (
                (
                    "llm_calls",
                    float(round_row["llm_calls_limit"]),
                    *totals["llm_calls"],
                    plan.llm_calls,
                ),
                (
                    "tokens_round",
                    float(round_row["tokens_limit"]),
                    *totals["tokens_round"],
                    plan.tokens,
                ),
                ("tokens_day", day_limit, *totals["tokens_day"], plan.tokens),
                ("tokens_week", week_limit, *totals["tokens_week"], plan.tokens),
                (
                    "backtests",
                    float(round_row["backtests_limit"]),
                    *totals["backtests"],
                    plan.backtests,
                ),
            )
            for dimension, limit, used, reserved, want in checks:
                if used + reserved + want > limit + _EPS:
                    raise BudgetExhausted(
                        dimension,
                        _exhausted_message(dimension, limit, used, reserved),
                        remaining=max(0.0, limit - used - reserved),
                    )
            rid = reservation_id if reservation_id is not None else uuid.uuid4().hex
            meta_json = json.dumps(dict(meta) if meta else {}, sort_keys=True, default=str)
            cur.execute(
                """
                INSERT INTO reservations (
                    reservation_id, round_id, llm_calls, tokens, backtests,
                    created_at_ms, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    round_row["round_id"],
                    plan.llm_calls,
                    plan.tokens,
                    plan.backtests,
                    ts,
                    meta_json,
                ),
            )
            return Reservation(
                reservation_id=rid,
                round_id=round_row["round_id"],
                llm_calls=plan.llm_calls,
                tokens=plan.tokens,
                backtests=plan.backtests,
                created_at_ms=ts,
            )

    def reservation(self, reservation_id: str) -> Reservation | None:
        """Return a stored reservation, or ``None`` if unknown."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,)
            ).fetchone()
        return None if row is None else self._row_to_reservation(row)

    # ------------------------------------------------------------------ spend

    def spend(
        self,
        round_id: str,
        kind: SpendKind,
        amount: float,
        *,
        reservation_id: str | None = None,
        meta: Mapping[str, object] | None = None,
        now: int | None = None,
    ) -> SpendReceipt:
        """Record real usage; never truncates or rejects over-reservation.

        Per-round overspend is recorded as an ``over_limit`` budget event.
        Rolling-window overspend is not rejected here either: it simply bites
        as reduced headroom at the next :meth:`reserve`. Token usage without
        provider numbers must pass ``meta={"estimated": True}``; a
        non-positive amount then falls back to
        ``unreported_usage_default_tokens`` (usage is never recorded as 0).
        """
        if kind not in SPEND_KINDS:
            raise ValueError(f"unknown spend kind: {kind!r} (expected one of {SPEND_KINDS})")
        value = float(amount)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"spend amount must be a finite non-negative number, got {amount!r}")
        meta_dict: dict[str, object] = dict(meta) if meta else {}
        if kind == "token" and value <= 0:
            if meta_dict.get("estimated") is True:
                value = float(self.unreported_usage_default_tokens)
            else:
                raise ValueError(
                    "token usage must be > 0; for usage without provider numbers pass "
                    "meta={'estimated': True} so the conservative default "
                    f"({self.unreported_usage_default_tokens} tokens) is recorded instead of zero"
                )
        ts = now if now is not None else now_ms()
        with self._write_tx() as cur:
            round_row = self._ensure_round(cur, round_id, ts, self.limits)
            if reservation_id is not None:
                res_row = cur.execute(
                    "SELECT round_id FROM reservations WHERE reservation_id = ?",
                    (reservation_id,),
                ).fetchone()
                if res_row is None:
                    raise ValueError(f"unknown reservation_id: {reservation_id}")
                if res_row["round_id"] != round_row["round_id"]:
                    raise ValueError(
                        f"reservation {reservation_id} belongs to round "
                        f"{res_row['round_id']!r}, not {round_id!r}"
                    )
            cur.execute(
                """
                INSERT INTO spend (round_id, kind, amount, ts_ms, reservation_id, meta_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    round_row["round_id"],
                    kind,
                    value,
                    ts,
                    reservation_id,
                    json.dumps(meta_dict, sort_keys=True, default=str),
                ),
            )
            used_row = cur.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM spend "
                "WHERE round_id = ? AND kind = ?",
                (round_row["round_id"], kind),
            ).fetchone()
            assert used_row is not None
            used = float(used_row["total"])
            limit = self._round_limit(round_row, kind)
            over_limit = used > limit + _EPS
            if over_limit:
                cur.execute(
                    "INSERT INTO budget_events (round_id, kind, detail, ts_ms) "
                    "VALUES (?, 'over_limit', ?, ?)",
                    (
                        round_row["round_id"],
                        f"{kind} 已用 {_g(used)} 超出本轮上限 {_g(limit)}",
                        ts,
                    ),
                )
            return SpendReceipt(
                round_id=round_row["round_id"],
                kind=kind,
                amount=value,
                ts_ms=ts,
                reservation_id=reservation_id,
                over_limit=over_limit,
            )

    # ------------------------------------------------------------------ usage / events

    def round_usage(self, round_id: str, *, now: int | None = None) -> RoundUsage:
        """Project every budget dimension for the round, rolling windows included."""
        ts = now if now is not None else now_ms()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rounds WHERE round_id = ?", (round_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown round: {round_id}")
            cur = self._conn.cursor()
            totals = self._totals(cur, row, ts)
        anchor = row["clock_start_ms"]
        limit_ms = float(row["wall_clock_limit_s"]) * 1000.0
        elapsed_s = 0.0 if anchor is None else max(0.0, (ts - int(anchor)) / 1000.0)
        remaining_ms = (
            int(limit_ms) if anchor is None else max(0, int(limit_ms - (ts - int(anchor))))
        )

        def usage(dimension: BudgetDimension, limit: float) -> DimensionUsage:
            used, reserved = totals[dimension]
            return DimensionUsage(dimension=dimension, limit=limit, used=used, reserved=reserved)

        return RoundUsage(
            round_id=round_id,
            llm_calls=usage("llm_calls", float(row["llm_calls_limit"])),
            tokens_round=usage("tokens_round", float(row["tokens_limit"])),
            tokens_day=usage("tokens_day", float(self.limits.tokens_per_day)),
            tokens_week=usage("tokens_week", float(self.limits.tokens_per_week)),
            backtests=usage("backtests", float(row["backtests_limit"])),
            wall_clock=DimensionUsage(
                dimension="wall_clock",
                limit=float(row["wall_clock_limit_s"]),
                used=elapsed_s,
                reserved=0.0,
            ),
            wall_clock_remaining_ms=remaining_ms,
        )

    def events(self, round_id: str) -> list[BudgetEvent]:
        """All budget events for the round, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT round_id, kind, detail, ts_ms FROM budget_events "
                "WHERE round_id = ? ORDER BY event_id",
                (round_id,),
            ).fetchall()
        return [
            BudgetEvent(
                round_id=row["round_id"], kind=row["kind"], detail=row["detail"], ts_ms=row["ts_ms"]
            )
            for row in rows
        ]


# ---------------------------------------------------------------------- guard


def _payload_ref(payload: Mapping[str, object], keys: tuple[str, ...]) -> str | None:
    """First non-empty string value among ``keys`` in the task payload."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def budget_guard(
    task_store: TaskStore,
    ledger: BudgetLedger,
    task_id: str,
    *,
    now: int | None = None,
) -> BudgetGuardVerdict:
    """Pre-commit budget check for a task (wired into the worker by P14).

    Reads the task payload for the canonical binding keys
    (``budget_reservation_id`` / ``budget_round_id``, with the short forms
    accepted) and validates, before the worker commits a result:

    - a referenced reservation must exist in the ledger, and must belong to
      the referenced round when both are given;
    - the owning round's wall clock must still have headroom.

    Tasks whose payload carries no budget references pass untouched (the
    caller decides whether that is acceptable). A failing check means the
    worker should commit ``budget_exhausted`` instead of the result; this
    function never mutates the task store.
    """
    payload = task_store.get_payload(task_id)
    reservation_id = _payload_ref(payload, (RESERVATION_ID_PAYLOAD_KEY, "reservation_id"))
    round_id = _payload_ref(payload, (ROUND_ID_PAYLOAD_KEY, "round_id"))
    if reservation_id is None and round_id is None:
        return BudgetGuardVerdict(
            task_id=task_id,
            round_id=None,
            reservation_id=None,
            allowed=True,
            reason=None,
            wall_clock_remaining_ms=None,
        )
    reservation = ledger.reservation(reservation_id) if reservation_id is not None else None
    if reservation_id is not None and reservation is None:
        return BudgetGuardVerdict(
            task_id=task_id,
            round_id=round_id,
            reservation_id=reservation_id,
            allowed=False,
            reason=(
                f"预算预留无效：找不到预留记录 {reservation_id}。"
                "该任务不得提交结果，应按 budget_exhausted 终态处理。"
            ),
            wall_clock_remaining_ms=None,
        )
    if reservation is not None:
        if round_id is not None and round_id != reservation.round_id:
            return BudgetGuardVerdict(
                task_id=task_id,
                round_id=round_id,
                reservation_id=reservation_id,
                allowed=False,
                reason=(
                    f"预算预留无效：预留 {reservation_id} 属于轮次 {reservation.round_id!r}，"
                    f"与任务声明的轮次 {round_id!r} 不一致。"
                ),
                wall_clock_remaining_ms=None,
            )
        round_id = reservation.round_id
    assert round_id is not None
    remaining = ledger.remaining_ms(round_id, now=now)
    if remaining <= 0:
        return BudgetGuardVerdict(
            task_id=task_id,
            round_id=round_id,
            reservation_id=reservation_id,
            allowed=False,
            reason=(
                f"本轮墙钟预算已耗尽（轮次 {round_id} 剩余 0 ms）。"
                "必须停止工作并输出预算终止报告与已完成产物，不得提交新结果。"
            ),
            wall_clock_remaining_ms=0,
        )
    return BudgetGuardVerdict(
        task_id=task_id,
        round_id=round_id,
        reservation_id=reservation_id,
        allowed=True,
        reason=None,
        wall_clock_remaining_ms=remaining,
    )


# ---------------------------------------------------------------------- report


def render_budget_report(ledger: BudgetLedger, round_id: str, *, now: int | None = None) -> str:
    """Chinese human-readable budget report for one round.

    Per dimension: limit, reserved (open reservations), used, remaining;
    plus the rolling 24h/7d token windows and any over-limit events.
    """
    usage = ledger.round_usage(round_id, now=now)
    events = ledger.events(round_id)

    def line(label: str, dim: DimensionUsage) -> str:
        return (
            f"- {label}：上限 {_g(dim.limit)} ｜ 预留 {_g(dim.reserved)} ｜ "
            f"已用 {_g(dim.used)} ｜ 剩余 {_g(dim.remaining)}"
        )

    lines: list[str] = [f"预算报告（轮次 {round_id}）"]
    lines.append(line("LLM 调用", usage.llm_calls))
    lines.append(line("Token（本轮）", usage.tokens_round))
    lines.append(line("回测次数", usage.backtests))
    clock = usage.wall_clock
    remaining_s = usage.wall_clock_remaining_ms / 1000.0
    lines.append(
        f"- 墙钟（本轮）：上限 {_g(clock.limit)}s ｜ 预留 0 ｜ "
        f"已用 {_g(clock.used)}s ｜ 剩余 {_g(remaining_s)}s"
    )
    lines.append(
        f"- Token 滚动窗口：近24小时 已用 {_g(usage.tokens_day.used)}/"
        f"{_g(usage.tokens_day.limit)}（剩余 {_g(usage.tokens_day.remaining)}）｜ "
        f"近7天 已用 {_g(usage.tokens_week.used)}/{_g(usage.tokens_week.limit)}"
        f"（剩余 {_g(usage.tokens_week.remaining)}）"
    )
    over = [event for event in events if event.kind == "over_limit"]
    if over:
        lines.append(f"- 超限事件：{len(over)} 条（最近：{over[-1].detail}）")
    else:
        lines.append("- 超限事件：无")
    return "\n".join(lines)
