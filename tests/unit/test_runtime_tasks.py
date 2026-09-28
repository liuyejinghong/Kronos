"""Unit tests for the SQLite task store state machine (P12).

A module-level autouse fixture replaces the store's wall clock with a
deterministic strictly-increasing millisecond counter, so lease expiry, FIFO
ordering, and heartbeat timestamps are exact (no sleeps).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from kronos.research.verdict.contracts import BudgetBlock, TaskKind, TaskRecord, TaskState
from kronos.runtime.tasks import (
    COMMIT_OUTCOME_STATES,
    StaleCommitError,
    TaskNotFoundError,
    TaskStateError,
    TaskStore,
    canonical_payload_sha256,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _deterministic_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strictly increasing fake millisecond clock inside kronos.runtime.tasks."""
    tick = 1_000_000

    def fake_now_ms() -> int:
        nonlocal tick
        tick += 1
        return tick

    monkeypatch.setattr("kronos.runtime.tasks.now_ms", fake_now_ms)
    yield


def _budget() -> BudgetBlock:
    return BudgetBlock(
        llm_calls_reserved=3,
        llm_calls_used=0,
        tokens_reserved=16000,
        tokens_used=0,
        backtests_reserved=40,
        backtests_used=0,
        wall_clock_limit_s=1800.0,
    )


def _submit(
    store: TaskStore,
    payload: dict[str, Any] | None = None,
    kind: TaskKind = "evaluate_strategy",
) -> TaskRecord:
    body = payload if payload is not None else {"strategy_revision_id": "rev-1"}
    return store.submit(kind, body, _budget(), canonical_payload_sha256(body))


def _claim(store: TaskStore, worker_id: str = "w1", lease_ms: int = 60_000) -> TaskRecord:
    task = store.claim(worker_id, lease_ms)
    assert task is not None, "expected a queued task to claim"
    return task


def _arrange(store: TaskStore, state: TaskState) -> TaskRecord:
    """Drive a freshly submitted task into the requested non-terminal state."""
    task = _submit(store)
    if state == "queued":
        return task
    claimed = _claim(store)
    if state == "running":
        return claimed
    if state == "cancel_requested":
        return store.request_cancel(task.task_id)
    raise ValueError(f"arrange() only supports queued/running/cancel_requested, got {state}")


def _terminal(store: TaskStore, state: TaskState) -> TaskRecord:
    """Drive a task into the requested terminal state."""
    if state == "cancelled":
        task = _submit(store)
        return store.request_cancel(task.task_id)
    _submit(store)
    task = _claim(store)
    return store.commit_result(task.task_id, "w1", task.fencing_token or 0, state)


def _commit(store: TaskStore, task: TaskRecord, state: TaskState) -> TaskRecord:
    return store.commit_result(task.task_id, task.worker_id or "w1", task.fencing_token or 0, state)


# ------------------------------------------------------------------- submit


def test_submit_creates_queued_task(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        assert task.state == "queued"
        assert task.kind == "evaluate_strategy"
        assert task.attempt == 0
        assert task.worker_id is None
        assert task.fencing_token is None
        assert task.lease_expiry_ms is None
        assert task.budget_reserved == _budget()
        assert store.get_payload(task.task_id) == {"strategy_revision_id": "rev-1"}


def test_submit_is_idempotent_on_content_hash(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        first = _submit(store)
        second = _submit(store)
        assert first.task_id == second.task_id
        assert len(store.list_tasks()) == 1

        # A different payload is a different request, even for the same kind.
        other = _submit(store, payload={"strategy_revision_id": "rev-2"})
        assert other.task_id != first.task_id
        assert len(store.list_tasks()) == 2


def test_submit_rejects_hash_mismatch(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        body = {"strategy_revision_id": "rev-1"}
        with pytest.raises(ValueError, match="idempotency_sha256"):
            store.submit("evaluate_strategy", body, _budget(), "0" * 64)


def test_submit_rejects_hash_reuse_across_kinds(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        body = {"strategy_revision_id": "rev-1"}
        digest = canonical_payload_sha256(body)
        store.submit("evaluate_strategy", body, _budget(), digest)
        with pytest.raises(ValueError, match="already submitted as kind"):
            store.submit("ensure_data", body, _budget(), digest)


def test_wal_mode_is_enabled(tmp_path: Any) -> None:
    store = TaskStore(tmp_path / "runtime.sqlite3")
    try:
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode) == "wal"
    finally:
        store.close()


def test_get_unknown_task_raises(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store, pytest.raises(TaskNotFoundError):
        store.get("missing")


# -------------------------------------------------- legal transition matrix


@pytest.mark.parametrize(
    ("from_state", "action", "expected_state"),
    [
        ("queued", "claim", "running"),
        ("queued", "request_cancel", "cancelled"),
        ("running", "request_cancel", "cancel_requested"),
        ("running", "commit:succeeded", "succeeded"),
        ("running", "commit:failed", "failed"),
        ("running", "commit:blocked", "blocked"),
        ("running", "commit:budget_exhausted", "budget_exhausted"),
        ("cancel_requested", "confirm_cancel", "cancelled"),
    ],
)
def test_legal_transitions(
    tmp_path: Any, from_state: TaskState, action: str, expected_state: TaskState
) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _arrange(store, from_state)
        if action == "claim":
            result = _claim(store)
            assert result.task_id == task.task_id
        elif action == "request_cancel":
            result = store.request_cancel(task.task_id)
        elif action == "confirm_cancel":
            result = store.confirm_cancel(
                task.task_id, task.worker_id or "w1", task.fencing_token or 0
            )
        else:
            target = action.split(":", 1)[1]
            assert target in COMMIT_OUTCOME_STATES
            result = _commit(store, task, target)
        assert result.state == expected_state


# --------------------------------------------- illegal transitions rejected


def _apply(store: TaskStore, task: TaskRecord, action: str) -> Any:
    if action == "request_cancel":
        return store.request_cancel(task.task_id)
    if action == "confirm_cancel":
        return store.confirm_cancel(task.task_id, task.worker_id or "w1", task.fencing_token or 0)
    if action == "commit:succeeded":
        return _commit(store, task, "succeeded")
    raise ValueError(action)


@pytest.mark.parametrize("terminal", sorted(COMMIT_OUTCOME_STATES | {"cancelled"}))
@pytest.mark.parametrize("action", ["request_cancel", "confirm_cancel", "commit:succeeded"])
def test_terminal_states_are_frozen(tmp_path: Any, terminal: TaskState, action: str) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _terminal(store, terminal)
        with pytest.raises(TaskStateError):
            _apply(store, task, action)


def test_illegal_transitions_rejected(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store, payload={"k": "queued"})
        running = _claim(store)  # claims `queued` (oldest, FIFO)
        second = _submit(store, payload={"k": "second"})  # stays queued

        requested = _submit(store, payload={"k": "requested"})
        claimed = _claim(store, worker_id="w9")  # FIFO -> claims `second`
        assert claimed.task_id == second.task_id
        cancel_requested = store.request_cancel(second.task_id)

        # commit from a task that was never claimed -> fenced out.
        with pytest.raises(StaleCommitError):
            _commit(store, second, "succeeded")
        # confirm_cancel is only legal from cancel_requested.
        with pytest.raises(TaskStateError):
            store.confirm_cancel(second.task_id, "w1", 1)
        with pytest.raises(TaskStateError):
            store.confirm_cancel(running.task_id, "w1", running.fencing_token or 0)
        # committing success over a cancel request is illegal: the worker must
        # confirm the cancellation instead of publishing the result.
        with pytest.raises(TaskStateError, match="cancel_requested"):
            _commit(store, cancel_requested, "succeeded")
        # a second cancel request is not a transition.
        with pytest.raises(TaskStateError):
            store.request_cancel(cancel_requested.task_id)
        # after cancelling the only queued task, nothing is claimable.
        store.request_cancel(requested.task_id)
        assert store.claim("w2", 60_000) is None


def test_commit_result_rejects_non_outcome_state(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store)
        with pytest.raises(TaskStateError, match="terminal outcome state"):
            store.commit_result(task.task_id, "w1", task.fencing_token or 0, "running")


# ------------------------------------------------------------ claim / lease


def test_claim_fifo_and_held_lease_blocks_second_claim(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        first = _submit(store, payload={"n": 1})
        second = _submit(store, payload={"n": 2})

        taken1 = _claim(store, worker_id="w1", lease_ms=60_000)
        assert taken1.task_id == first.task_id
        assert taken1.attempt == 1
        assert taken1.fencing_token == 1
        assert taken1.lease_expiry_ms is not None

        # The lease on task 1 is held; the second worker gets the next task.
        taken2 = _claim(store, worker_id="w2", lease_ms=60_000)
        assert taken2 is not None and taken2.task_id == second.task_id

        # Both leases held -> nothing left to claim.
        assert store.claim("w3", 60_000) is None


def test_fencing_token_increments_monotonically_per_task(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        first = _claim(store, worker_id="w1", lease_ms=1)
        assert first.fencing_token == 1
        expiry = first.lease_expiry_ms
        assert expiry is not None

        store.recover_expired_leases(now=expiry + 1)
        second = _claim(store, worker_id="w2", lease_ms=60_000)
        assert second.task_id == task.task_id
        assert second.fencing_token == 2
        assert second.attempt == 2


def test_stale_fencing_token_rejected_after_takeover(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        stale = _claim(store, worker_id="w1", lease_ms=1)
        expiry = stale.lease_expiry_ms
        assert expiry is not None
        store.recover_expired_leases(now=expiry + 1)

        current = _claim(store, worker_id="w2", lease_ms=60_000)
        assert current.fencing_token == 2

        # Wrong worker (even with the current token): rejected.
        with pytest.raises(StaleCommitError, match="owned by worker"):
            store.commit_result(task.task_id, "w1", 2, "succeeded")
        # Old worker's late commit with the stale token: rejected.
        with pytest.raises(StaleCommitError, match="stale fencing token"):
            store.commit_result(task.task_id, "w2", 1, "succeeded")
        # Current owner with the current token: accepted.
        done = store.commit_result(task.task_id, "w2", 2, "succeeded")
        assert done.state == "succeeded"


# ---------------------------------------------------------------- heartbeat


def test_heartbeat_renews_lease(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store, worker_id="w1", lease_ms=60_000)
        claimed_expiry = task.lease_expiry_ms
        claimed_heartbeat = task.heartbeat_ms
        assert claimed_expiry is not None and claimed_heartbeat is not None

        renewed = store.heartbeat(task.task_id, "w1")
        assert renewed.heartbeat_ms is not None
        assert renewed.heartbeat_ms > claimed_heartbeat
        assert renewed.lease_expiry_ms is not None
        assert renewed.lease_expiry_ms > claimed_expiry


def test_heartbeat_rejects_wrong_worker(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store, worker_id="w1", lease_ms=60_000)
        with pytest.raises(StaleCommitError, match="owned by worker"):
            store.heartbeat(task.task_id, "w2")


def test_heartbeat_rejects_expired_lease(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store, worker_id="w1", lease_ms=1)
        expiry = task.lease_expiry_ms
        assert expiry is not None
        # The fake clock has already advanced past expiry by the next call:
        # the heartbeat must be fenced out instead of silently renewing.
        with pytest.raises(StaleCommitError, match="expired"):
            store.heartbeat(task.task_id, "w1")


# ------------------------------------------------------------------- cancel


def test_two_step_cancel_of_running_task(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store, worker_id="w1")

        requested = store.request_cancel(task.task_id)
        assert requested.state == "cancel_requested"

        # UI flag alone must not complete cancellation: confirm requires the
        # owner's fencing credentials.
        confirmed = store.confirm_cancel(task.task_id, "w1", requested.fencing_token or 0)
        assert confirmed.state == "cancelled"
        assert store.claim("w2", 60_000) is None


def test_confirm_cancel_rejects_wrong_worker(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store, worker_id="w1")
        requested = store.request_cancel(task.task_id)
        with pytest.raises(StaleCommitError, match="owned by worker"):
            store.confirm_cancel(task.task_id, "w2", requested.fencing_token or 0)
        assert store.get(task.task_id).state == "cancel_requested"


def test_request_cancel_queued_task_cancels_directly(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        cancelled = store.request_cancel(task.task_id)
        assert cancelled.state == "cancelled"


# ------------------------------------------------------------------- events


def test_events_append_only_with_incremental_reads(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        other = _submit(store, payload={"n": 0})
        claimed = _claim(store)  # FIFO: claims `task`
        assert claimed.task_id == task.task_id
        store.request_cancel(task.task_id)
        store.confirm_cancel(task.task_id, "w1", claimed.fencing_token or 0)

        all_events = store.events(task.task_id)
        assert [e.kind for e in all_events] == [
            "submitted",
            "claimed",
            "cancel_requested",
            "cancelled",
        ]
        seqs = [e.seq for e in all_events]
        assert seqs == [1, 2, 3, 4]

        # after_seq pagination: strictly newer events only.
        tail = store.events(task.task_id, after_seq=2)
        assert [e.seq for e in tail] == [3, 4]
        assert store.events(task.task_id, after_seq=4) == []

        # Per-task sequences are independent monotonic counters.
        assert [e.seq for e in store.events(other.task_id)] == [1]

        with pytest.raises(TaskNotFoundError):
            store.append_event("missing", "kind")


# ----------------------------------------------------------------- recovery


def test_recovery_requeues_expired_lease_with_attempt_counting(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        claimed = _claim(store, worker_id="ghost", lease_ms=60_000)
        expiry = claimed.lease_expiry_ms
        assert expiry is not None

        # A live lease is left alone.
        assert store.recover_expired_leases(now=expiry - 1) == []
        assert store.get(task.task_id).state == "running"

        recovered = store.recover_expired_leases(now=expiry + 1)
        assert [t.task_id for t in recovered] == [task.task_id]
        back = store.get(task.task_id)
        assert back.state == "queued"
        assert back.attempt == 1  # re-queued; the next claim becomes attempt 2
        assert back.worker_id is None
        assert back.fencing_token == 1  # fencing token never resets

        kinds = [e.kind for e in store.events(task.task_id)]
        assert kinds == ["submitted", "claimed", "lease_expired_recovered"]


def test_recovery_fails_task_after_max_attempts(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        task = _submit(store)
        for attempt in range(1, 4):  # attempts 1..3 all lose their leases
            claimed = _claim(store, worker_id=f"ghost-{attempt}", lease_ms=1)
            assert claimed.attempt == attempt
            expiry = claimed.lease_expiry_ms
            assert expiry is not None
            recovered = store.recover_expired_leases(max_attempts=3, now=expiry + 1)
            assert len(recovered) == 1
            assert recovered[0].state == ("queued" if attempt < 3 else "failed")
        final = store.get(task.task_id)
        assert final.state == "failed"
        assert final.error_ref == "lease_expired_max_attempts"
        event_kinds = [e.kind for e in store.events(task.task_id)]
        assert event_kinds.count("lease_expired_recovered") == 3
        assert event_kinds[-1] == "failed"
        assert store.claim("w1", 60_000) is None


def test_recovery_cancels_expired_cancel_requested_task(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store, worker_id="ghost", lease_ms=1)
        expiry = task.lease_expiry_ms
        assert expiry is not None
        # The cancel request keeps the lease as the confirmation deadline, so
        # lease recovery can still cancel the task if the worker dies first.
        requested = store.request_cancel(task.task_id)
        assert requested.state == "cancel_requested"
        assert requested.lease_expiry_ms == expiry

        recovered = store.recover_expired_leases(now=expiry + 1)
        assert recovered[0].state == "cancelled"
        assert store.get(task.task_id).state == "cancelled"


# ------------------------------------------------------------------ results


def test_result_roundtrip(tmp_path: Any) -> None:
    with TaskStore(tmp_path / "runtime.sqlite3") as store:
        _submit(store)
        task = _claim(store)
        assert store.get_result(task.task_id) is None
        done = store.commit_result(
            task.task_id,
            "w1",
            task.fencing_token or 0,
            "succeeded",
            result={"artifact": "verdict.json"},
        )
        assert done.state == "succeeded"
        assert store.get_result(task.task_id) == {"artifact": "verdict.json"}
