"""In-process pipeline worker wiring for the Kronos web app (package P14b).

Boots a single :class:`~kronos.runtime.worker.Worker` over the REAL handler
map (:func:`kronos.conversation.handlers.make_handler_map`) so tasks submitted
through the conversation service / web tools actually execute against the
local data store.  The worker runs in-process (P18 verified the worker has no
separate process home): its poll loop lives on a **daemon** thread that is
started once per app and stops with the process — in-flight tasks abandoned at
process exit are made decidable again by the worker's startup lease recovery
(``recover_expired_leases``), so daemon semantics are safe by design, not an
oversight.

Store layout: the wiring reopens the SAME SQLite files the conversation
service uses (``<state_dir>/runtime.sqlite3`` and ``budget.sqlite3``) through
separate connections.  Both stores are WAL-mode with ``BEGIN IMMEDIATE``
write transactions and a 5s busy timeout, so concurrent access from the
service and the worker is safe.

Test switch: ``KRONOS_PIPELINE_WORKER=off`` (or 0/false/no) disables
attachment entirely.  The web integration tests set this in their conftest
because they claim and commit tasks manually and assert intermediate task
states; production (default) is always on.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Final

from kronos.common.log import get_logger
from kronos.conversation.handlers import make_handler_map
from kronos.runtime.tasks import TaskStore
from kronos.runtime.worker import Worker

log = get_logger("kronos.conversation.pipeline_wiring")

#: Env kill-switch ("off"/"0"/"false"/"no" disables attachment; tests only).
WORKER_ENV_SWITCH: Final[str] = "KRONOS_PIPELINE_WORKER"
_DEFAULT_POLL_S: Final[float] = 1.0

_OFF_VALUES: Final[frozenset[str]] = frozenset({"off", "0", "false", "no"})


def worker_switch_enabled() -> bool:
    """True unless ``KRONOS_PIPELINE_WORKER`` is explicitly switched off."""
    return os.environ.get(WORKER_ENV_SWITCH, "on").strip().lower() not in _OFF_VALUES


def attach_worker(
    app_state: Any,
    *,
    base_path: Path,
    state_dir: Path,
    snapshots_dir: Path,
    venv_dir: Path | None = None,
    engine_env: str | None = None,
    poll_s: float = _DEFAULT_POLL_S,
) -> Worker | None:
    """Build the handler map, start the poll loop as a daemon thread.

    Idempotent: a second call on the same app state returns the already
    running worker.  Returns ``None`` when the kill switch is off.

    The thread is a daemon: on process exit it dies with the interpreter and
    any in-flight task's lease expires; the next worker boot re-queues it
    (bounded attempts) via startup recovery, so no task is ever stranded
    non-terminal by a restart.
    """
    if not worker_switch_enabled():
        return None
    existing = getattr(app_state, "pipeline_worker", None)
    if existing is not None:
        return existing  # type: ignore[no-any-return]
    state_dir_path = Path(state_dir)
    state_dir_path.mkdir(parents=True, exist_ok=True)
    task_store = TaskStore(state_dir_path / "runtime.sqlite3")
    handlers = make_handler_map(
        base_path=Path(base_path),
        state_dir=state_dir_path,
        snapshots_dir=Path(snapshots_dir),
        engine_env=engine_env,
        venv_dir=Path(venv_dir) if venv_dir is not None else None,
        task_store=task_store,
    )
    stop = threading.Event()
    worker = Worker(task_store, handlers, poll_s=poll_s)
    thread = threading.Thread(
        target=worker.run,
        kwargs={"poll_s": poll_s, "stop": stop},
        name="kronos-pipeline-worker",
        daemon=True,
    )
    app_state.pipeline_worker = worker
    app_state.pipeline_worker_stop = stop
    app_state.pipeline_worker_thread = thread
    thread.start()
    log.info("pipeline.worker_attached", worker_id=worker.worker_id, poll_s=poll_s)
    return worker


def stop_worker(app_state: Any) -> None:
    """Signal the worker's poll loop to stop (safe when nothing was attached).

    The daemon thread exits after its current task; this helper only sets the
    stop event.  Production relies on process exit instead (daemon semantics,
    see module docstring); the handle exists for tests and graceful shutdown.
    """
    stop: threading.Event | None = getattr(app_state, "pipeline_worker_stop", None)
    if stop is not None:
        stop.set()
