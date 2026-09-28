"""SQLite-backed persistent task queue with a frozen state machine (P12).

Implements the task-runtime spec
(``openspec/changes/p5-strategy-verdict-loop/specs/task-runtime/spec.md``):

- durable queue in a single SQLite file (stdlib ``sqlite3`` only, WAL mode),
- the frozen eight-state machine from ``TaskRecord.state``
  (queued/running/cancel_requested/succeeded/blocked/failed/cancelled/
  budget_exhausted) with an explicit legal-transition table,
- idempotent submit keyed by content hash (double submit returns the
  existing task, no duplicate row),
- claim with lease + fencing token so a stale worker's late commit is
  rejected (spec scenario: old worker late commit),
- two-step cancel: ``request_cancel`` then worker-side ``confirm_cancel``
  only after work has truly stopped (spec scenario: two-step cancel),
- restart recovery: expired-lease tasks are re-queued with attempt
  counting and bounded max attempts, then failed,
- append-only per-task event log with monotonic ``seq`` and incremental
  reads via ``after_seq`` (used by the web UI for progress polling).

The DB path is parameterizable; the default layout is
``<state_dir>/runtime.sqlite3`` and the state dir comes from the caller.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

from pydantic import ValidationError

from kronos.common.errors import KronosError
from kronos.research.verdict.contracts import (
    BudgetBlock,
    TaskEvent,
    TaskKind,
    TaskRecord,
    TaskState,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

DEFAULT_DB_FILENAME: Final[str] = "runtime.sqlite3"

#: Frozen legal transitions (spec: task-runtime). Every state absent as a key
#: (or mapped to an empty set) is terminal.
LEGAL_TRANSITIONS: Final[dict[TaskState, frozenset[TaskState]]] = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset(
        {"cancel_requested", "succeeded", "failed", "budget_exhausted", "blocked"}
    ),
    "cancel_requested": frozenset({"cancelled"}),
    "succeeded": frozenset(),
    "blocked": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "budget_exhausted": frozenset(),
}

#: Terminal outcome states a worker may pass to ``commit_result``.
COMMIT_OUTCOME_STATES: Final[frozenset[TaskState]] = frozenset(
    {"succeeded", "failed", "budget_exhausted", "blocked"}
)

#: A task that has been claimed this many times and loses its lease again is
#: failed instead of re-queued (spec: bounded retries, deterministic after
#: restart).
DEFAULT_MAX_ATTEMPTS: Final[int] = 3

_ERROR_REF_MAX_CHARS: Final[int] = 512

_SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    payload_sha256  TEXT NOT NULL UNIQUE,
    payload_json    TEXT NOT NULL,
    state           TEXT NOT NULL,
    stage           TEXT NOT NULL DEFAULT '',
    attempt         INTEGER NOT NULL DEFAULT 0,
    worker_id       TEXT,
    lease_ms        INTEGER,
    lease_expiry_ms INTEGER,
    fencing_token   INTEGER,
    heartbeat_ms    INTEGER,
    budget_json     TEXT NOT NULL,
    error_ref       TEXT,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_state_created
    ON tasks(state, created_at, task_id);
CREATE TABLE IF NOT EXISTS task_events (
    task_id TEXT NOT NULL,
    seq     INTEGER NOT NULL,
    ts_ms   INTEGER NOT NULL,
    kind    TEXT NOT NULL,
    detail  TEXT,
    PRIMARY KEY (task_id, seq)
);
CREATE TABLE IF NOT EXISTS task_results (
    task_id      TEXT PRIMARY KEY,
    result_json  TEXT NOT NULL,
    committed_at INTEGER NOT NULL
);
"""


def now_ms() -> int:
    """Current wall-clock time in epoch milliseconds."""
    return int(time.time() * 1000)


def canonical_payload_sha256(payload: Mapping[str, Any]) -> str:
    """Content hash of a payload; the idempotency key for ``submit``.

    The canonical form is sorted-key compact JSON so the same logical payload
    always hashes identically regardless of dict insertion order.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TaskStateError(KronosError):
    """An illegal state-machine transition or state-dependent request."""


class StaleCommitError(TaskStateError):
    """A commit/heartbeat from a worker whose lease is gone (fenced out).

    Raised when the worker id does not own the task, the fencing token is
    stale, or the lease already expired. The late commit must never override
    the work of the current owner (spec: old worker late commit).
    """


class TaskNotFoundError(KronosError):
    """No task row exists for the given task id."""


class TaskStore:
    """Persistent task queue, event log, and state machine over one SQLite file.

    All mutating operations run inside ``BEGIN IMMEDIATE`` transactions under
    an in-process lock, so the store is safe to share between the worker's
    heartbeat thread and the caller thread, and between processes (WAL mode).
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> TaskStore:
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
    def _row_to_task(row: sqlite3.Row) -> TaskRecord:
        try:
            budget = BudgetBlock.model_validate_json(row["budget_json"])
        except ValidationError as exc:  # pragma: no cover - corrupt row guard
            raise KronosError(f"corrupt budget_json for task {row['task_id']}: {exc}") from exc
        return TaskRecord(
            task_id=row["task_id"],
            kind=row["kind"],
            payload_sha256=row["payload_sha256"],
            state=row["state"],
            stage=row["stage"],
            attempt=row["attempt"],
            worker_id=row["worker_id"],
            lease_expiry_ms=row["lease_expiry_ms"],
            fencing_token=row["fencing_token"],
            heartbeat_ms=row["heartbeat_ms"],
            budget_reserved=budget,
            error_ref=row["error_ref"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _get_row(self, cur: sqlite3.Cursor, task_id: str) -> sqlite3.Row:
        row = cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFoundError(f"unknown task_id: {task_id}")
        return cast("sqlite3.Row", row)

    def _append_event(
        self, cur: sqlite3.Cursor, task_id: str, kind: str, detail: str | None = None
    ) -> TaskEvent:
        row = cur.execute(
            "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM task_events WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        seq = int(row["max_seq"]) + 1
        ts = now_ms()
        cur.execute(
            "INSERT INTO task_events (task_id, seq, ts_ms, kind, detail) VALUES (?, ?, ?, ?, ?)",
            (task_id, seq, ts, kind, detail),
        )
        return TaskEvent(seq=seq, task_id=task_id, ts_ms=ts, kind=kind, detail=detail)

    def _check_owner(self, row: sqlite3.Row, worker_id: str, fencing_token: int | None) -> None:
        """Reject commits from wrong workers or stale fencing tokens."""
        owner = row["worker_id"]
        if owner is None or owner != worker_id:
            raise StaleCommitError(
                f"task {row['task_id']} is owned by worker {owner!r}, not {worker_id!r}"
            )
        token = row["fencing_token"]
        if fencing_token is None or token is None or fencing_token != token:
            raise StaleCommitError(
                f"stale fencing token {fencing_token!r} for task {row['task_id']} "
                f"(current token: {token!r}); late commit rejected"
            )

    # ------------------------------------------------------------------ submit / read

    def submit(
        self,
        kind: TaskKind,
        payload: Mapping[str, Any],
        budget_reserved: BudgetBlock,
        idempotency_sha256: str,
    ) -> TaskRecord:
        """Enqueue a task; an existing task with the same content hash is returned.

        Idempotent by construction: the caller hashes the payload with
        :func:`canonical_payload_sha256` and passes it as ``idempotency_sha256``.
        A second submit with the same hash returns the already-existing task
        unchanged (no duplicate row, no state change). A hash that does not
        match the payload is rejected: an unsound hash would let two different
        requests collide silently.
        """
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        if idempotency_sha256 != canonical_payload_sha256(payload):
            raise ValueError(
                "idempotency_sha256 does not match canonical sha256 of payload "
                f"(expected {canonical_payload_sha256(payload)!r}, got {idempotency_sha256!r})"
            )
        with self._write_tx() as cur:
            row = cur.execute(
                "SELECT * FROM tasks WHERE payload_sha256 = ?", (idempotency_sha256,)
            ).fetchone()
            if row is not None:
                if row["kind"] != kind:
                    raise ValueError(
                        f"payload hash {idempotency_sha256!r} already submitted as kind "
                        f"{row['kind']!r}; refusing to reuse it for kind {kind!r}"
                    )
                return self._row_to_task(row)
            ts = now_ms()
            task_id = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO tasks (
                    task_id, kind, payload_sha256, payload_json, state, stage,
                    attempt, budget_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', '', 0, ?, ?, ?)
                """,
                (
                    task_id,
                    kind,
                    idempotency_sha256,
                    payload_json,
                    budget_reserved.model_dump_json(),
                    ts,
                    ts,
                ),
            )
            self._append_event(cur, task_id, "submitted", detail=f"kind={kind}")
            row = self._get_row(cur, task_id)
            return self._row_to_task(row)

    def get(self, task_id: str) -> TaskRecord:
        """Return the current task record."""
        with self._lock:
            return self._row_to_task(self._get_row(self._conn.cursor(), task_id))

    def get_payload(self, task_id: str) -> dict[str, Any]:
        """Return the stored request payload for a task (worker input)."""
        with self._lock:
            row = self._get_row(self._conn.cursor(), task_id)
            payload: dict[str, Any] = json.loads(row["payload_json"])
            return payload

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        """Return the result dict committed by a succeeded worker, if any."""
        with self._lock:
            row = (
                self._conn.cursor()
                .execute("SELECT result_json FROM task_results WHERE task_id = ?", (task_id,))
                .fetchone()
            )
        return None if row is None else json.loads(row["result_json"])

    def list_tasks(self, state: TaskState | None = None) -> list[TaskRecord]:
        """List tasks, optionally filtered by state, oldest first."""
        with self._lock:
            cur = self._conn.cursor()
            if state is None:
                rows = cur.execute("SELECT * FROM tasks ORDER BY created_at, task_id").fetchall()
            else:
                rows = cur.execute(
                    "SELECT * FROM tasks WHERE state = ? ORDER BY created_at, task_id",
                    (state,),
                ).fetchall()
        return [self._row_to_task(row) for row in rows]

    # ------------------------------------------------------------------ claim / lease

    def claim(self, worker_id: str, lease_ms: int) -> TaskRecord | None:
        """Atomically claim the oldest queued task, or return ``None``.

        Moves queued -> running, stamps ``worker_id``, ``lease_expiry_ms`` and
        ``heartbeat_ms``, increments ``attempt``, and bumps the per-task
        ``fencing_token`` monotonically so any previous owner's commits become
        stale. A second claim while a lease is held returns ``None`` because
        the task is no longer queued.
        """
        if lease_ms <= 0:
            raise ValueError("lease_ms must be positive")
        with self._write_tx() as cur:
            row = cur.execute(
                """
                SELECT * FROM tasks WHERE state = 'queued'
                ORDER BY created_at, task_id LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            task_id = row["task_id"]
            ts = now_ms()
            cur.execute(
                """
                UPDATE tasks SET
                    state = 'running',
                    worker_id = ?,
                    lease_ms = ?,
                    lease_expiry_ms = ?,
                    heartbeat_ms = ?,
                    fencing_token = COALESCE(fencing_token, 0) + 1,
                    attempt = attempt + 1,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (worker_id, lease_ms, ts + lease_ms, ts, ts, task_id),
            )
            self._append_event(
                cur, task_id, "claimed", detail=f"worker={worker_id} lease_ms={lease_ms}"
            )
            return self._row_to_task(self._get_row(cur, task_id))

    def heartbeat(self, task_id: str, worker_id: str) -> TaskRecord:
        """Renew the calling worker's lease and stamp the heartbeat time.

        Raises :class:`StaleCommitError` when the worker does not own the task
        or its lease already expired: a worker that lost its lease must stop
        working immediately.
        """
        with self._write_tx() as cur:
            row = self._get_row(cur, task_id)
            self._check_owner(row, worker_id, row["fencing_token"])
            if row["state"] != "running":
                raise StaleCommitError(
                    f"task {task_id} is no longer running (state={row['state']!r})"
                )
            expiry = row["lease_expiry_ms"]
            if expiry is not None and expiry <= now_ms():
                raise StaleCommitError(
                    f"lease on task {task_id} expired at {expiry}; worker {worker_id!r} is fenced out"
                )
            lease_ms = row["lease_ms"]
            if lease_ms is None:  # pragma: no cover - claim always sets lease_ms
                raise StaleCommitError(f"task {task_id} has no lease duration")
            ts = now_ms()
            cur.execute(
                "UPDATE tasks SET heartbeat_ms = ?, lease_expiry_ms = ?, updated_at = ? "
                "WHERE task_id = ?",
                (ts, ts + lease_ms, ts, task_id),
            )
            return self._row_to_task(self._get_row(cur, task_id))

    # ------------------------------------------------------------------ state machine

    def commit_result(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        state: TaskState,
        error_ref: str | None = None,
        *,
        stage: str | None = None,
        result: Mapping[str, Any] | None = None,
    ) -> TaskRecord:
        """Commit a terminal outcome for a claimed task (fencing-checked).

        ``state`` must be one of succeeded/failed/budget_exhausted/blocked and
        the task must currently be ``running`` with ``worker_id`` and
        ``fencing_token`` matching the current owner exactly; anything else
        raises :class:`StaleCommitError` or :class:`TaskStateError`. In
        particular a late commit from a worker whose lease was taken over is
        rejected and cannot pollute the published outcome.
        """
        if state not in COMMIT_OUTCOME_STATES:
            raise TaskStateError(
                f"commit_result requires a terminal outcome state "
                f"{sorted(COMMIT_OUTCOME_STATES)}, got {state!r}"
            )
        with self._write_tx() as cur:
            row = self._get_row(cur, task_id)
            self._check_owner(row, worker_id, fencing_token)
            self._require_transition(row, state)
            ts = now_ms()
            cur.execute(
                """
                UPDATE tasks SET
                    state = ?, error_ref = ?, stage = COALESCE(?, stage),
                    lease_expiry_ms = NULL, updated_at = ?
                WHERE task_id = ?
                """,
                (state, error_ref, stage, ts, task_id),
            )
            if result is not None:
                cur.execute(
                    "INSERT OR REPLACE INTO task_results (task_id, result_json, committed_at) "
                    "VALUES (?, ?, ?)",
                    (task_id, json.dumps(result, sort_keys=True, default=str), ts),
                )
            self._append_event(cur, task_id, state, detail=error_ref)
            return self._row_to_task(self._get_row(cur, task_id))

    def request_cancel(self, task_id: str) -> TaskRecord:
        """First step of cancellation.

        From ``running`` the task moves to ``cancel_requested``; the worker is
        expected to notice, stop, and call :meth:`confirm_cancel`. From
        ``queued`` there is no work to stop, so the task goes straight to
        ``cancelled`` (legal transition queued -> cancelled). Anything else is
        a :class:`TaskStateError`.
        """
        with self._write_tx() as cur:
            row = self._get_row(cur, task_id)
            current: TaskState = row["state"]
            if current == "queued":
                target: TaskState = "cancelled"
                detail = "cancelled while queued (no work started)"
            elif current == "running":
                target = "cancel_requested"
                detail = "cancel requested; waiting for worker confirmation"
            else:
                raise TaskStateError(
                    f"request_cancel is illegal from state {current!r} for task {task_id}"
                )
            self._require_transition(row, target)
            # Keep the worker's lease as the confirmation deadline: if the
            # worker dies before confirming, lease recovery can still move the
            # task to cancelled instead of stranding it in cancel_requested.
            cur.execute(
                "UPDATE tasks SET state = ?, updated_at = ? WHERE task_id = ?",
                (target, now_ms(), task_id),
            )
            self._append_event(cur, task_id, target, detail=detail)
            return self._row_to_task(self._get_row(cur, task_id))

    def confirm_cancel(self, task_id: str, worker_id: str, fencing_token: int) -> TaskRecord:
        """Second step of cancellation: the worker confirms work truly stopped.

        Only legal from ``cancel_requested`` and only for the current owner
        (matching ``worker_id`` + ``fencing_token``). A UI flag flip alone is
        never treated as cancellation completed (spec: two-step cancel).
        """
        with self._write_tx() as cur:
            row = self._get_row(cur, task_id)
            current: TaskState = row["state"]
            if current != "cancel_requested":
                raise TaskStateError(
                    f"confirm_cancel is illegal from state {current!r} for task {task_id}"
                )
            self._check_owner(row, worker_id, fencing_token)
            ts = now_ms()
            cur.execute(
                "UPDATE tasks SET state = 'cancelled', lease_expiry_ms = NULL, updated_at = ? "
                "WHERE task_id = ?",
                (ts, task_id),
            )
            self._append_event(cur, task_id, "cancelled", detail=f"confirmed by {worker_id}")
            return self._row_to_task(self._get_row(cur, task_id))

    @staticmethod
    def _require_transition(row: sqlite3.Row, target: TaskState) -> None:
        current: TaskState = row["state"]
        if target not in LEGAL_TRANSITIONS[current]:
            raise TaskStateError(
                f"illegal transition {current!r} -> {target!r} for task {row['task_id']}"
            )

    # ------------------------------------------------------------------ recovery

    def recover_expired_leases(
        self, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS, now: int | None = None
    ) -> list[TaskRecord]:
        """Make orphaned tasks decidable after a crash/restart (spec: recovery).

        - ``running`` tasks whose lease expired are re-queued with an event
          ``lease_expired_recovered``; if they have already been attempted
          ``max_attempts`` times they are failed instead (bounded retries).
        - ``cancel_requested`` tasks whose lease expired have no worker left
          to confirm the stop; they are moved to ``cancelled`` so the state
          machine cannot strand non-terminal tasks.

        Returns the affected records. ``now`` is injectable for tests.
        """
        current = now if now is not None else now_ms()
        recovered: list[TaskRecord] = []
        with self._write_tx() as cur:
            rows = cur.execute(
                "SELECT * FROM tasks WHERE state IN ('running', 'cancel_requested')"
            ).fetchall()
            for row in rows:
                expiry = row["lease_expiry_ms"]
                if expiry is None or expiry > current:
                    continue
                task_id = row["task_id"]
                if row["state"] == "cancel_requested":
                    cur.execute(
                        "UPDATE tasks SET state = 'cancelled', lease_expiry_ms = NULL, "
                        "updated_at = ? WHERE task_id = ?",
                        (now_ms(), task_id),
                    )
                    self._append_event(
                        cur,
                        task_id,
                        "cancelled",
                        detail="lease expired after cancel_requested; worker presumed dead",
                    )
                elif int(row["attempt"]) >= max_attempts:
                    cur.execute(
                        "UPDATE tasks SET state = 'failed', lease_expiry_ms = NULL, "
                        "error_ref = ?, updated_at = ? WHERE task_id = ?",
                        ("lease_expired_max_attempts", now_ms(), task_id),
                    )
                    self._append_event(
                        cur,
                        task_id,
                        "lease_expired_recovered",
                        detail=f"attempt {row['attempt']} >= max_attempts {max_attempts}",
                    )
                    self._append_event(cur, task_id, "failed", detail="lease_expired_max_attempts")
                else:
                    cur.execute(
                        "UPDATE tasks SET state = 'queued', worker_id = NULL, "
                        "lease_expiry_ms = NULL, heartbeat_ms = NULL, updated_at = ? "
                        "WHERE task_id = ?",
                        (now_ms(), task_id),
                    )
                    self._append_event(
                        cur,
                        task_id,
                        "lease_expired_recovered",
                        detail=f"re-queued (attempt {row['attempt']} of {max_attempts})",
                    )
                recovered.append(self._row_to_task(self._get_row(cur, task_id)))
        return recovered

    # ------------------------------------------------------------------ events

    def append_event(self, task_id: str, kind: str, detail: str | None = None) -> TaskEvent:
        """Append one lifecycle event with the next monotonic per-task ``seq``."""
        with self._write_tx() as cur:
            self._get_row(cur, task_id)  # existence check
            return self._append_event(cur, task_id, kind, detail=detail)

    def events(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        """Return the task's events with ``seq > after_seq`` in order.

        Incremental polling contract for the web UI: remember the last seen
        ``seq`` and pass it as ``after_seq`` to receive only newer events.
        """
        with self._lock:
            rows = (
                self._conn.cursor()
                .execute(
                    "SELECT seq, task_id, ts_ms, kind, detail FROM task_events "
                    "WHERE task_id = ? AND seq > ? ORDER BY seq",
                    (task_id, after_seq),
                )
                .fetchall()
            )
        return [
            TaskEvent(
                seq=row["seq"],
                task_id=row["task_id"],
                ts_ms=row["ts_ms"],
                kind=row["kind"],
                detail=row["detail"],
            )
            for row in rows
        ]
