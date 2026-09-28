"""Integration tests: Worker loop against a real TaskStore on disk (P12).

Covers the spec scenarios end to end: submit -> run_once -> succeeded with
heartbeats, handler exception -> failed, two-step cancel during execution,
crashed-worker recovery by a fresh worker (restart), a second worker finding
nothing claimable while a lease is held, and the service run loop.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from kronos.research.verdict.contracts import BudgetBlock, TaskRecord
from kronos.runtime.tasks import TaskStore
from kronos.runtime.worker import Worker

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _wait_until(condition: Callable[[], bool], timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    pytest.fail("condition not met before timeout")


def _store(tmp_path: Path) -> TaskStore:
    return TaskStore(tmp_path / "state" / "runtime.sqlite3")


def _submit(store: TaskStore, payload: dict[str, Any]) -> TaskRecord:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    budget = BudgetBlock(
        llm_calls_reserved=1,
        llm_calls_used=0,
        tokens_reserved=1000,
        tokens_used=0,
        backtests_reserved=1,
        backtests_used=0,
        wall_clock_limit_s=60.0,
    )
    return store.submit("evaluate_strategy", payload, budget, digest)


def test_submit_run_once_succeeds_with_heartbeat(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        task = _submit(store, {"strategy_revision_id": "rev-1"})

        def handler(payload: dict[str, Any]) -> dict[str, Any]:
            time.sleep(0.15)  # long enough for the heartbeat cadence to fire
            return {"echo": payload["strategy_revision_id"]}

        worker = Worker(store, {"evaluate_strategy": handler}, lease_ms=10_000, heartbeat_s=0.05)
        done = worker.run_once()
        assert done is not None
        assert done.task_id == task.task_id
        assert done.state == "succeeded"
        assert store.get_result(task.task_id) == {"echo": "rev-1"}

        # Heartbeat recorded during execution (claimed stamp < later heartbeat).
        claimed_ts = next(e.ts_ms for e in store.events(task.task_id) if e.kind == "claimed")
        assert done.heartbeat_ms is not None
        assert done.heartbeat_ms > claimed_ts

        kinds = [e.kind for e in store.events(task.task_id)]
        assert kinds == ["submitted", "claimed", "succeeded"]

        # Queue drained: a further pass has nothing to do.
        assert worker.run_once() is None


def test_handler_exception_marks_task_failed(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        task = _submit(store, {"strategy_revision_id": "rev-bad"})

        def handler(payload: dict[str, Any]) -> dict[str, Any]:
            raise ValueError("boom")

        worker = Worker(store, {"evaluate_strategy": handler}, heartbeat_s=0)
        done = worker.run_once()
        assert done is not None
        assert done.task_id == task.task_id
        assert done.state == "failed"
        assert done.error_ref is not None
        assert "ValueError" in done.error_ref
        assert "boom" in done.error_ref
        assert store.get_result(task.task_id) is None

        # Terminal failure: nothing further to claim.
        assert worker.run_once() is None
        kinds = [e.kind for e in store.events(task.task_id)]
        assert kinds == ["submitted", "claimed", "failed"]


def test_unknown_kind_fails_task(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        task = _submit(store, {"strategy_revision_id": "rev-x"})
        worker = Worker(store, {}, heartbeat_s=0)  # no handlers registered at all
        done = worker.run_once()
        assert done is not None
        assert done.task_id == task.task_id
        assert done.state == "failed"
        assert done.error_ref == "no_handler_registered_for_kind:evaluate_strategy"


def test_two_step_cancel_during_execution(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        task = _submit(store, {"strategy_revision_id": "rev-cancel"})
        release = threading.Event()

        def handler(payload: dict[str, Any]) -> dict[str, Any]:
            release.wait(timeout=5.0)
            return {"finished_normally": True}

        worker = Worker(store, {"evaluate_strategy": handler}, heartbeat_s=0)
        stop = threading.Event()
        runner = threading.Thread(target=worker.run, kwargs={"poll_s": 0.01, "stop": stop})
        runner.start()

        try:
            _wait_until(lambda: store.get(task.task_id).state == "running")
            # Owner requests cancel while the handler is still working.
            requested = store.request_cancel(task.task_id)
            assert requested.state == "cancel_requested"
            # Only now may the handler finish: the worker must notice the
            # cancel request and confirm it instead of publishing its result.
            release.set()
            _wait_until(lambda: store.get(task.task_id).state == "cancelled")
        finally:
            stop.set()
            release.set()
            runner.join(timeout=5.0)

        assert not runner.is_alive()
        final = store.get(task.task_id)
        assert final.state == "cancelled"
        # The completed result was discarded, not published.
        assert store.get_result(task.task_id) is None
        kinds = [e.kind for e in store.events(task.task_id)]
        assert kinds == ["submitted", "claimed", "cancel_requested", "cancelled"]


def test_crashed_worker_recovered_by_fresh_worker(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        task = _submit(store, {"strategy_revision_id": "rev-recover"})
        # Simulate a worker that claimed the task and then crashed: the lease
        # it held is 1 ms, so it is already expired.
        ghost = store.claim("ghost-worker", lease_ms=1)
        assert ghost is not None and ghost.attempt == 1
        time.sleep(0.01)

        def handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"recovered": True}

        # Fresh worker after restart: recovery must re-queue the orphan, then
        # claim and complete it.
        restarted = Worker(store, {"evaluate_strategy": handler}, heartbeat_s=0)
        done = restarted.run_once()
        assert done is not None
        assert done.task_id == task.task_id
        assert done.state == "succeeded"
        assert done.attempt == 2

        kinds = [e.kind for e in store.events(task.task_id)]
        assert "lease_expired_recovered" in kinds
        assert store.get_result(task.task_id) == {"recovered": True}


def test_second_worker_claims_nothing_while_lease_held(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        submitted = _submit(store, {"strategy_revision_id": "rev-held"})
        holder = store.claim("holder", lease_ms=60_000)
        assert holder is not None

        # While the holder's lease is live, another worker's claim and pass
        # both come up empty (the expired-lease path is covered by recovery).
        other = Worker(store, {"evaluate_strategy": lambda p: {}}, heartbeat_s=0)
        assert other.run_once() is None
        assert store.get(submitted.task_id).state == "running"


def test_run_loop_drains_queue_and_stops(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        for n in range(3):
            _submit(store, {"n": n})
        worker = Worker(store, {"evaluate_strategy": lambda p: {"saw": p["n"]}}, heartbeat_s=0)
        stop = threading.Event()
        processed: list[int] = []

        def serve() -> None:
            processed.append(worker.run(poll_s=0.01, stop=stop))

        runner = threading.Thread(target=serve)
        runner.start()
        _wait_until(lambda: len(store.list_tasks("succeeded")) == 3)
        stop.set()
        runner.join(timeout=5.0)

        assert not runner.is_alive()
        assert processed == [3]
        assert {t.state for t in store.list_tasks()} == {"succeeded"}


def test_worker_validates_constructor_args(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        with pytest.raises(ValueError, match="lease_ms"):
            Worker(store, {}, lease_ms=0)
        with pytest.raises(ValueError, match="heartbeat_s"):
            Worker(store, {}, heartbeat_s=-1.0)
