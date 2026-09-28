"""Single-worker runner for the persistent task queue (P12).

Loop per iteration: recover expired leases -> claim one queued task (lease +
fencing token) -> heartbeat in a background thread while the handler runs ->
execute ``handler(payload)`` -> commit succeeded/failed with the fencing
token. Exceptions from a handler mark the task failed with the error string;
a cancel requested during execution wins over a finished result (the worker
confirms cancellation instead of committing success, per the two-step cancel
spec). ``run_once`` is the testable unit; ``run(poll_s)`` is the service loop.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Final

from kronos.runtime.tasks import StaleCommitError, TaskStateError, TaskStore

if TYPE_CHECKING:
    from kronos.research.verdict.contracts import TaskRecord

#: A task handler receives the submitted payload and returns a result dict.
#: Exceptions propagate to the worker, which marks the task failed.
TaskHandler = Callable[[dict[str, Any]], dict[str, Any]]

_DEFAULT_LEASE_MS: Final[int] = 300_000
_DEFAULT_HEARTBEAT_S: Final[float] = 5.0
_DEFAULT_POLL_S: Final[float] = 1.0
_HEARTBEAT_JOIN_TIMEOUT_S: Final[float] = 2.0


class Worker:
    """Executes claimed tasks via a kind -> handler map against one TaskStore."""

    def __init__(
        self,
        store: TaskStore,
        handler_map: Mapping[str, TaskHandler],
        *,
        lease_ms: int = _DEFAULT_LEASE_MS,
        heartbeat_s: float = _DEFAULT_HEARTBEAT_S,
        poll_s: float = _DEFAULT_POLL_S,
        max_attempts: int = 3,
        worker_id: str | None = None,
    ) -> None:
        if lease_ms <= 0:
            raise ValueError("lease_ms must be positive")
        if heartbeat_s < 0:
            raise ValueError("heartbeat_s must be >= 0 (0 disables heartbeats)")
        self._store = store
        self._handlers: dict[str, TaskHandler] = dict(handler_map)
        self.lease_ms = lease_ms
        self.heartbeat_s = heartbeat_s
        self.poll_s = poll_s
        self.max_attempts = max_attempts
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------ public API

    def recover(self) -> list[TaskRecord]:
        """Re-queue or fail tasks orphaned by crashed workers (startup recovery)."""
        return self._store.recover_expired_leases(max_attempts=self.max_attempts)

    def run_once(self) -> TaskRecord | None:
        """Claim and execute at most one task; return its final record or ``None``.

        Recovery of expired leases runs first, so a fresh worker instance
        makes restart-orphaned tasks decidable before claiming new work.
        """
        self.recover()
        task = self._store.claim(self.worker_id, self.lease_ms)
        if task is None:
            return None
        return self._execute(task)

    def run(self, poll_s: float | None = None, *, stop: threading.Event | None = None) -> int:
        """Service loop: process tasks until ``stop`` is set; return processed count."""
        interval = self.poll_s if poll_s is None else poll_s
        processed = 0
        while stop is None or not stop.is_set():
            if self.run_once() is not None:
                processed += 1
            elif stop is not None and stop.wait(interval):
                break
            elif stop is None:
                # No stop signal provided: sleep inline to keep polling bounded.
                threading.Event().wait(interval)
        return processed

    # ------------------------------------------------------------------ internals

    def _execute(self, task: TaskRecord) -> TaskRecord:
        """Run the handler for a claimed task and commit its outcome."""
        heartbeat_stop = threading.Event()
        heart = threading.Thread(
            target=self._heartbeat_loop,
            args=(task.task_id, heartbeat_stop),
            name=f"heartbeat-{task.task_id[:8]}",
            daemon=True,
        )
        error_ref: str | None = None
        result: dict[str, Any] | None = None
        try:
            heart.start()
            error_ref, result = self._invoke(task)
        finally:
            heartbeat_stop.set()
            if heart.is_alive():
                heart.join(timeout=_HEARTBEAT_JOIN_TIMEOUT_S)

        current = self._store.get(task.task_id)
        if current.state == "cancel_requested":
            # Cancel arrived while we worked: stop means stop - the completed
            # result is discarded and the worker confirms the cancellation.
            return self._store.confirm_cancel(task.task_id, self.worker_id, task.fencing_token or 0)
        try:
            if error_ref is not None:
                return self._store.commit_result(
                    task.task_id,
                    self.worker_id,
                    task.fencing_token or 0,
                    "failed",
                    error_ref=error_ref,
                )
            assert result is not None
            return self._store.commit_result(
                task.task_id,
                self.worker_id,
                task.fencing_token or 0,
                "succeeded",
                result=result,
            )
        except TaskStateError:
            # request_cancel landed between our re-read and the commit.
            if self._store.get(task.task_id).state == "cancel_requested":
                return self._store.confirm_cancel(
                    task.task_id, self.worker_id, task.fencing_token or 0
                )
            raise

    def _invoke(self, task: TaskRecord) -> tuple[str | None, dict[str, Any] | None]:
        """Execute the handler; return ``(error_ref, result)`` exactly one of which is set."""
        handler = self._handlers.get(task.kind)
        if handler is None:
            return f"no_handler_registered_for_kind:{task.kind}", None
        try:
            payload = self._store.get_payload(task.task_id)
            outcome = handler(payload)
        except Exception as exc:  # handler failures become task failures
            return f"{type(exc).__name__}: {exc}"[:512], None
        if not isinstance(outcome, dict):
            return f"handler returned non-dict result: {type(outcome).__name__}", None
        return None, outcome

    def _heartbeat_loop(self, task_id: str, stop: threading.Event) -> None:
        """Renew the lease every ``heartbeat_s`` until the work (or lease) ends."""
        if self.heartbeat_s <= 0:
            return
        while not stop.wait(self.heartbeat_s):
            try:
                self._store.heartbeat(task_id, self.worker_id)
            except StaleCommitError:
                # Lease lost (expired or taken over); stop signalling. The
                # execution thread's own commit will be fenced if it is late.
                return
            except TaskStateError:
                return
