"""Persistent local task runtime for the v0.5.0 strategy-verdict loop (P12).

SQLite-backed task queue with a frozen state machine, lease/heartbeat/fencing
for a single compute worker, two-step cancellation, restart recovery, and an
append-only event log pollable via ``after_seq``. Package P13 (budget
executor) and P14 (conversation service) build on these primitives.
"""

from __future__ import annotations

from kronos.research.verdict.contracts import BudgetBlock, TaskEvent, TaskRecord
from kronos.runtime.tasks import (
    StaleCommitError,
    TaskNotFoundError,
    TaskStateError,
    TaskStore,
    canonical_payload_sha256,
)
from kronos.runtime.worker import Worker

__all__ = [
    "BudgetBlock",
    "StaleCommitError",
    "TaskEvent",
    "TaskNotFoundError",
    "TaskRecord",
    "TaskStateError",
    "TaskStore",
    "Worker",
    "canonical_payload_sha256",
]
