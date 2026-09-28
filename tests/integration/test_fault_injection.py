"""Fault injection and recovery scenarios through the real service layer (P20).

Every scenario runs against the REAL persistence surfaces (ConversationService
on real SQLite files in tmp, TaskStore, BudgetLedger, real parquet store for
readiness) with only engines and the network faked:

- data faults: readiness repair with fake sync functions (retry / 429 / partial
  per-symbol completion) — planning doc section 7.3 data-test row;
- worker faults: worker death mid-run (lease expiry -> recovery -> attempt+1),
  stale worker late commit (StaleCommitError fencing), artifact written but DB
  ref never published (never served until published) — task-runtime spec
  scenarios 旧 worker 迟到提交 / 孤儿产物;
- cancel at every stage: queued / running / after success — task-runtime spec
  两步取消 scenario;
- model faults: GLM client under timeout / HTTP 500 / malformed payload /
  missing usage, plus the documented degradation (the deterministic
  conversation path performs zero model calls);
- restart recovery: sessions, messages, revisions, budgets and published
  verdicts survive a full close/reopen of every SQLite handle.

Determinism: no real network, no arbitrary sleeps — lease expiry is injected
via ``TaskStore.recover_expired_leases(now=...)``; the only waits are bounded
condition polls on cross-thread worker loops.
"""

from __future__ import annotations

import json
import threading
import time
from typing import TYPE_CHECKING, Any

import httpx
import pyarrow as pa
import pytest
from fastapi.testclient import TestClient

from kronos.conversation.llm_client import (
    GLMChatMessage,
    GLMClient,
    GLMNotConfiguredError,
    GLMRequestError,
)
from kronos.conversation.service import ConversationService
from kronos.data.schemas.candle import CANDLE_DEDUP_KEY
from kronos.data.schemas.funding import FUNDING_DEDUP_KEY
from kronos.data.storage.parquet_store import write_records_partitioned
from kronos.research.verdict.readiness import (
    apply_repair_actions,
    build_readiness_plan,
    render_readiness_report,
)
from kronos.runtime.budget import BudgetLedger
from kronos.runtime.tasks import (
    StaleCommitError,
    TaskNotFoundError,
    TaskStateError,
    TaskStore,
    now_ms,
)
from kronos.runtime.worker import Worker
from kronos.web import create_app

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

DAY_MS = 86_400_000
MINUTE_MS = 60_000
FUNDING_MS = 28_800_000
# 2026-06-01 00:00:00 UTC — a midnight-aligned window start (fully in the past).
W0 = 1_780_272_000_000
W1 = W0 + 2 * DAY_MS
BARS_PER_DAY = 1440
SETTLEMENTS_PER_WINDOW = 6  # 2 days of 8h funding settlements


# --------------------------------------------------------------------- helpers


def _wait_until(condition: Callable[[], bool], timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    pytest.fail("condition not met before timeout")


def _service(tmp_path: Path) -> ConversationService:
    return ConversationService(tmp_path / "state")


def _kline_table(symbol: str, times: list[int]) -> pa.Table:
    n = len(times)
    ingested = now_ms()
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array([t + MINUTE_MS for t in times], type=pa.int64()),
            "ingested_at": pa.array([ingested] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "open": pa.array([67000.0] * n, type=pa.float64()),
            "high": pa.array([67500.0] * n, type=pa.float64()),
            "low": pa.array([66800.0] * n, type=pa.float64()),
            "close": pa.array([67200.0] * n, type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
            "quote_volume": pa.array([6720000.0] * n, type=pa.float64()),
            "trade_count": pa.array([100] * n, type=pa.int64()),
            "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
            "venue": ["binance"] * n,
        }
    )


def _funding_table(symbol: str, times: list[int]) -> pa.Table:
    n = len(times)
    ingested = now_ms()
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array(times, type=pa.int64()),
            "ingested_at": pa.array([ingested] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
            "mark_price": pa.array([67000.0] * n, type=pa.float64()),
        }
    )


def _write_klines(base_path: Path, symbol: str, times: list[int]) -> int:
    return len(
        write_records_partitioned(
            _kline_table(symbol, times), base_path, symbol, "klines_1m", CANDLE_DEDUP_KEY
        )
    )


def _write_funding(base_path: Path, symbol: str, times: list[int]) -> int:
    return len(
        write_records_partitioned(
            _funding_table(symbol, times), base_path, symbol, "funding", FUNDING_DEDUP_KEY
        )
    )


def _full_kline_times() -> list[int]:
    return [W0 + i * MINUTE_MS for i in range(2 * BARS_PER_DAY)]


def _full_funding_times() -> list[int]:
    return [W0 + i * FUNDING_MS for i in range(SETTLEMENTS_PER_WINDOW)]


def _build_plan(symbols: list[str], base_path: Path) -> Any:
    return build_readiness_plan(
        symbols,
        base_path=base_path,
        window_start_ms=W0,
        window_end_ms=W1,
        warmup_bars=0,
        signal_timeframe="15m",
    )


def _fake_sync(
    log: list[str],
    *,
    fail_symbols: set[str] | None = None,
    flaky_first_fetch: bool = False,
) -> Callable[..., int]:
    """Deterministic fake for sync_klines/sync_funding modeling the real retry
    contract: the retry loop lives INSIDE the sync function (it receives
    ``max_retries`` from the orchestrator), and the orchestrator only ever sees
    the final result — one invoke per action, either rows or a raised error.

    Every fetch attempt is recorded in ``log`` as one line:
    ``<symbol> attempt=<n> <outcome>``. Succeeding invocations write REAL rows
    into the parquet store so repairs are verifiable by rebuilding the plan.
    ``fail_symbols`` simulate a persistent HTTP 429 (all retries consumed);
    ``flaky_first_fetch`` simulates one transient connection reset absorbed by
    the first internal retry.
    """
    fail_symbols = fail_symbols or set()
    state = {"fetch_attempts": 0}

    def fake(
        symbol: str,
        *,
        base_path: Path,
        since: int | None = None,
        max_retries: int = 5,
        request_interval_ms: int = 200,
    ) -> int:
        log.append(f"{symbol} invoke since={since} max_retries={max_retries}")
        if symbol in fail_symbols:
            for attempt in range(max_retries + 1):  # initial call + all retries
                state["fetch_attempts"] += 1
                log.append(f"{symbol} attempt={attempt} HTTP_429")
            raise RuntimeError(f"HTTP 429 rate limited after {max_retries + 1} attempts")
        if flaky_first_fetch and state["fetch_attempts"] == 0:
            state["fetch_attempts"] += 1
            log.append(f"{symbol} attempt=0 ConnectionError")
            log.append(f"{symbol} attempt=1 ok (retried once inside sync)")
        # A successful sync writes the full window through the real store.
        _write_klines(base_path, symbol, _full_kline_times())
        _write_funding(base_path, symbol, _full_funding_times())
        return 2 * BARS_PER_DAY + SETTLEMENTS_PER_WINDOW

    return fake


def _verdict_writer(state_dir: Path, received: list[dict[str, Any]] | None = None):
    """Fake evaluate_strategy engine: writes a verdict artifact, returns the
    publishable result (the worker then commits the DB ref = publication)."""

    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        run_dir = state_dir / "runs" / str(payload["spec_hash"][:16])
        run_dir.mkdir(parents=True, exist_ok=True)
        verdict_path = run_dir / "verdict.json"
        verdict = {
            "evidence_status": "valid",
            "disposition": "observe",
            "reason_codes": [f"spec_hash={str(payload['spec_hash'])[:12]}"],
        }
        verdict_path.write_text(json.dumps(verdict, sort_keys=True), encoding="utf-8")
        if received is not None:
            received.append(dict(payload))
        return {
            "verdict": verdict,
            "artifact_refs": {"verdict_json": str(verdict_path)},
        }

    return handler


# ----------------------------------------------------------------- data faults
# Planning doc 7.3: data tests must cover 429 / timeout / resume / partial
# per-symbol completion - every outcome recorded truthfully, never silent
# success.


def test_readiness_repair_raises_once_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(a) first fetch fails once, internal retry succeeds: the action outcome
    is recorded as ok, the real store is repaired, and the orchestrator passes
    its retry budget (max_retries) through to the sync layer."""
    store = tmp_path / "parquet"
    _write_klines(store, "BTCUSDT", [W0 + i * MINUTE_MS for i in range(BARS_PER_DAY)])

    plan = _build_plan(["BTCUSDT"], store)
    assert plan.overall_status == "needs_repair"
    assert [a.dataset for a in plan.actions] == ["klines_1m", "funding"]

    log: list[str] = []
    fake = _fake_sync(log, flaky_first_fetch=True)
    monkeypatch.setattr("kronos.research.verdict.readiness.sync_klines", fake)
    monkeypatch.setattr("kronos.research.verdict.readiness.sync_funding", fake)

    outcomes = apply_repair_actions(plan, base_path=store, max_retries=3)

    assert [o.status for o in outcomes] == ["ok", "ok"]
    assert outcomes[0].rows_fetched == 2 * BARS_PER_DAY + SETTLEMENTS_PER_WINDOW
    assert outcomes[0].error is None
    # The transient failure and its recovery are recorded at the sync layer:
    # the first fetch attempt failed, the retry succeeded.
    assert "BTCUSDT attempt=0 ConnectionError" in log
    assert "BTCUSDT attempt=1 ok (retried once inside sync)" in log
    # The orchestrator handed its retry budget to every sync invocation.
    invokes = [line for line in log if "invoke" in line]
    assert len(invokes) == 2  # one per repair action
    assert all("max_retries=3" in line for line in invokes)
    # The repair really repaired: a rebuilt plan is fully ready.
    rebuilt = _build_plan(["BTCUSDT"], store)
    assert rebuilt.overall_status == "ready"
    assert all(entry.status == "ready" for entry in rebuilt.entries)


def test_readiness_repair_rate_limited_every_time_batch_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) 429 on every attempt: each action records an error outcome, the
    batch is not aborted, and the plan/report keep telling the truth."""
    store = tmp_path / "parquet"
    symbols = ["BTCUSDT", "ETHUSDT"]
    plan = _build_plan(symbols, store)
    assert len(plan.actions) == 4  # 2 symbols x (klines_1m, funding)

    log: list[str] = []
    fake = _fake_sync(log, fail_symbols=set(symbols))
    monkeypatch.setattr("kronos.research.verdict.readiness.sync_klines", fake)
    monkeypatch.setattr("kronos.research.verdict.readiness.sync_funding", fake)

    outcomes = apply_repair_actions(plan, base_path=store, max_retries=2)

    assert [o.status for o in outcomes] == ["error"] * 4
    assert all("429" in (o.error or "") for o in outcomes)
    assert all(o.rows_fetched == 0 for o in outcomes)
    # The batch continued: every action was invoked exactly once, and each one
    # consumed its full retry budget (initial + 2 retries) before failing.
    assert len([line for line in log if "invoke" in line]) == 4
    assert len([line for line in log if "HTTP_429" in line]) == 4 * 3
    attempted = {line.split()[0] for line in log if "invoke" in line}
    assert attempted == set(symbols)
    # No silent success: the rebuilt plan still needs repair and says so.
    rebuilt = _build_plan(symbols, store)
    assert rebuilt.overall_status == "needs_repair"
    report = render_readiness_report(rebuilt)
    assert "需修复" in report
    assert "无本地数据" in report


def test_readiness_repair_partial_completion_reflects_per_symbol_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) BTCUSDT repairs, ETHUSDT fails: plan/report show per-symbol truth,
    overall status stays needs_repair (never a silent overall success)."""
    store = tmp_path / "parquet"
    symbols = ["BTCUSDT", "ETHUSDT"]
    plan = _build_plan(symbols, store)

    log: list[str] = []
    fake = _fake_sync(log, fail_symbols={"ETHUSDT"})
    monkeypatch.setattr("kronos.research.verdict.readiness.sync_klines", fake)
    monkeypatch.setattr("kronos.research.verdict.readiness.sync_funding", fake)

    outcomes = apply_repair_actions(plan, base_path=store)

    ok_symbols = {o.symbol for o in outcomes if o.status == "ok"}
    failed_symbols = {o.symbol for o in outcomes if o.status == "error"}
    assert ok_symbols == {"BTCUSDT"}
    assert failed_symbols == {"ETHUSDT"}

    rebuilt = _build_plan(symbols, store)
    by_symbol: dict[str, list[str]] = {}
    for entry in rebuilt.entries:
        by_symbol.setdefault(entry.symbol, []).append(entry.status)
    assert set(by_symbol["BTCUSDT"]) == {"ready"}
    assert set(by_symbol["ETHUSDT"]) == {"needs_repair"}
    assert rebuilt.overall_status == "needs_repair"  # partial != success

    report = render_readiness_report(rebuilt)
    assert "—— ETHUSDT ——" in report
    assert "需修复" in report
    assert "就绪" in report


# --------------------------------------------------------------- worker faults


def test_worker_dies_midrun_recovery_requeues_and_attempts_increment(
    tmp_path: Path,
) -> None:
    """(a) claim without commit + expired lease -> recovery requeues, attempt+1,
    bounded retries end in a deterministic failed terminal state."""
    service = _service(tmp_path)
    session = service.create_session()
    result = service.send_message(session.session_id, "把倍数改成 2.0")
    task_id = result.task_id
    assert task_id is not None
    store = service.task_store

    # Simulate a worker that claimed the task and died before committing.
    ghost = store.claim("ghost-worker", lease_ms=1)
    assert ghost is not None and ghost.attempt == 1
    # Deterministic lease-expiry injection (no sleep): recovery with a future now.
    recovered = store.recover_expired_leases(now=now_ms() + DAY_MS)
    assert [r.task_id for r in recovered] == [task_id]
    assert recovered[0].state == "queued"
    assert recovered[0].attempt == 1

    # A fresh worker after "restart" claims and completes it (attempt becomes 2).
    worker = Worker(
        store, {"evaluate_strategy": _verdict_writer(tmp_path / "state")}, heartbeat_s=0
    )
    done = worker.run_once()
    assert done is not None and done.task_id == task_id
    assert done.state == "succeeded"
    assert done.attempt == 2
    kinds = [e.kind for e in store.events(task_id)]
    assert kinds == ["submitted", "claimed", "lease_expired_recovered", "claimed", "succeeded"]

    # Bounded retries: a second task claimed-and-lost 3 times fails terminally.
    second = service.send_message(session.session_id, "ATR 改成 30")
    second_id = second.task_id
    assert second_id is not None
    for expected_attempt in (1, 2):
        claimed = store.claim("ghost-worker", lease_ms=1)
        assert claimed is not None and claimed.attempt == expected_attempt
        store.recover_expired_leases(now=now_ms() + DAY_MS)
    third = store.claim("ghost-worker", lease_ms=1)
    assert third is not None and third.attempt == 3
    failed = store.recover_expired_leases(now=now_ms() + DAY_MS)
    assert [r.task_id for r in failed] == [second_id]
    assert failed[0].state == "failed"
    assert failed[0].error_ref == "lease_expired_max_attempts"
    assert worker.run_once() is None  # terminal: nothing more claimable
    service.close()


def test_stale_worker_late_commit_rejected_after_takeover(tmp_path: Path) -> None:
    """(b) a stale worker's late commit is fenced out and cannot pollute the
    published verdict; the takeover worker's result is the only one served."""
    service = _service(tmp_path)
    session = service.create_session()
    result = service.send_message(session.session_id, "把倍数改成 2.0")
    task_id = result.task_id
    assert task_id is not None
    store = service.task_store

    stale = store.claim("worker-a", lease_ms=1)
    assert stale is not None and stale.fencing_token == 1
    store.recover_expired_leases(now=now_ms() + DAY_MS)  # lease gone, task requeued
    takeover = store.claim("worker-b", lease_ms=600_000)
    assert takeover is not None and takeover.fencing_token == 2
    assert takeover.attempt == 2

    # The stale worker finally finishes and tries to publish: rejected.
    with pytest.raises(StaleCommitError, match="owned by worker"):
        store.commit_result(
            task_id,
            "worker-a",
            int(stale.fencing_token or 0),
            "succeeded",
            result={"verdict": {"reason_codes": ["from_stale_worker_a"]}},
        )
    # The new owner committing with a stale token is equally rejected.
    with pytest.raises(StaleCommitError, match="stale fencing token"):
        store.commit_result(
            task_id,
            "worker-b",
            int(stale.fencing_token or 0),
            "succeeded",
            result={"verdict": {"reason_codes": ["stale_token"]}},
        )
    # Even a heartbeat from the dead owner is fenced out.
    with pytest.raises(StaleCommitError, match="owned by worker"):
        store.heartbeat(task_id, "worker-a")

    record = store.get(task_id)
    assert record.state == "running"
    assert record.worker_id == "worker-b"
    assert record.fencing_token == 2
    assert store.get_result(task_id) is None  # nothing polluted

    store.commit_result(
        task_id,
        "worker-b",
        int(takeover.fencing_token or 0),
        "succeeded",
        result={
            "verdict": {
                "evidence_status": "valid",
                "disposition": "observe",
                "reason_codes": ["from_worker_b"],
            },
            "artifact_refs": {},
        },
    )
    assert store.get_result(task_id) == {
        "verdict": {
            "evidence_status": "valid",
            "disposition": "observe",
            "reason_codes": ["from_worker_b"],
        },
        "artifact_refs": {},
    }
    # The service layer serves exactly the takeover worker's verdict.
    answered = service.send_message(session.session_id, "为什么不如持有")
    assert answered.status == "answered"
    assert "reason_code=from_worker_b" in answered.verdict_refs
    assert not any("from_stale_worker_a" in ref for ref in answered.verdict_refs)
    service.close()


def test_artifact_written_but_not_published_is_never_served(tmp_path: Path) -> None:
    """(c) engine crash between artifact write and DB publication: the verdict
    read path 404s (serves nothing unpublished); a later publish makes the very
    same artifact visible."""
    service = _service(tmp_path)
    session = service.create_session()
    result = service.send_message(session.session_id, "把倍数改成 2.0")
    task_id = result.task_id
    assert task_id is not None
    store = service.task_store

    # Claim and "write the artifact", then die before publishing the DB ref.
    claimed = store.claim("engine", lease_ms=600_000)
    assert claimed is not None
    verdict_path = tmp_path / "state" / "runs" / task_id / "verdict.json"
    verdict_path.parent.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(
        json.dumps({"evidence_status": "valid", "disposition": "observe"}), encoding="utf-8"
    )

    # The service must not serve the unpublished artifact.
    evidence = service.send_message(session.session_id, "为什么不如持有")
    assert evidence.status == "answered"
    assert evidence.verdict_refs == []
    evidence_msg = service.list_messages(session.session_id)[-1]
    assert "还没有可引用的结论" in evidence_msg.content
    ask = service.send_message(session.session_id, "现在结论如何")
    assert ask.status == "answered" and ask.verdict_refs == []
    ask_msg = service.list_messages(session.session_id)[-1]
    assert "还没有已完成的结论" in ask_msg.content
    assert store.get(task_id).state == "running"
    with pytest.raises(TaskNotFoundError):
        service.invoke_tool("read_evidence", {"run_id": "no-such-run"})

    # Later publish (same artifact, DB ref committed): now visible.
    store.commit_result(
        task_id,
        "engine",
        int(claimed.fencing_token or 0),
        "succeeded",
        result={
            "verdict": {
                "evidence_status": "valid",
                "disposition": "observe",
                "reason_codes": ["baseline_ok"],
            },
            "artifact_refs": {"verdict_json": str(verdict_path)},
        },
    )
    after = service.send_message(session.session_id, "为什么不如持有")
    assert after.status == "answered"
    assert f"verdict_json={verdict_path}" in after.verdict_refs
    assert verdict_path.is_file()  # the served ref points at the real artifact
    service.close()


# ---------------------------------------------------------------------- cancel


def test_cancel_queued_goes_straight_to_cancelled(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session()
    result = service.send_message(session.session_id, "把倍数改成 2.0")
    task_id = result.task_id
    assert task_id is not None

    record = service.task_store.request_cancel(task_id)
    assert record.state == "cancelled"  # queued -> cancelled, no work to stop
    kinds = [e.kind for e in service.task_store.events(task_id)]
    assert kinds == ["submitted", "cancelled"]
    assert service.task_store.get_result(task_id) is None
    # The queue is drained: a worker has nothing to claim.
    worker = Worker(
        service.task_store,
        {"evaluate_strategy": _verdict_writer(tmp_path / "state")},
        heartbeat_s=0,
    )
    assert worker.run_once() is None
    service.close()


def test_cancel_running_two_step_result_discarded(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session()
    result = service.send_message(session.session_id, "把倍数改成 2.0")
    task_id = result.task_id
    assert task_id is not None

    release = threading.Event()

    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        release.wait(timeout=5.0)
        return {"verdict": {"finished": True}}

    worker = Worker(service.task_store, {"evaluate_strategy": handler}, heartbeat_s=0)
    stop = threading.Event()
    runner = threading.Thread(target=worker.run, kwargs={"poll_s": 0.01, "stop": stop})
    runner.start()
    try:
        _wait_until(lambda: service.task_store.get(task_id).state == "running")
        requested = service.task_store.request_cancel(task_id)
        assert requested.state == "cancel_requested"  # step 1: flag only
        release.set()
        _wait_until(lambda: service.task_store.get(task_id).state == "cancelled")
    finally:
        stop.set()
        release.set()
        runner.join(timeout=5.0)

    final = service.task_store.get(task_id)
    assert final.state == "cancelled"
    # The completed result was discarded, never published.
    assert service.task_store.get_result(task_id) is None
    kinds = [e.kind for e in service.task_store.events(task_id)]
    assert kinds == ["submitted", "claimed", "cancel_requested", "cancelled"]
    service.close()


def test_cancel_after_success_is_rejected_and_task_stays_succeeded(tmp_path: Path) -> None:
    """After-success cancel: the store raises TaskStateError (the exact error
    the HTTP layer maps to 409); the task and its verdict are untouched."""
    service = _service(tmp_path)
    session = service.create_session()
    result = service.send_message(session.session_id, "把倍数改成 2.0")
    task_id = result.task_id
    assert task_id is not None

    worker = Worker(
        service.task_store,
        {"evaluate_strategy": _verdict_writer(tmp_path / "state")},
        heartbeat_s=0,
    )
    done = worker.run_once()
    assert done is not None and done.state == "succeeded"

    with pytest.raises(TaskStateError, match="request_cancel"):
        service.task_store.request_cancel(task_id)
    assert service.task_store.get(task_id).state == "succeeded"
    assert service.task_store.get_result(task_id) is not None
    service.close()


def test_cancel_http_semantics_via_real_web_layer(tmp_path: Path) -> None:
    """The HTTP boundary: cancel of a queued run succeeds, a second cancel and
    a cancel after success both map TaskStateError to 409. Write requests go
    through the real local-security flow (loopback Host + session token)."""
    app = create_app(project_root=tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")  # loopback Host
    token = client.get("/api/session-token").json()["token"]
    headers = {"X-Kronos-Local-Token": token}

    # queued -> cancel 200 (straight to cancelled), cancel again -> 409.
    session_a = client.post("/api/conversations", headers=headers).json()
    turn = client.post(
        f"/api/conversations/{session_a['session_id']}/messages",
        json={"text": "把倍数改成 2.0"},
        headers=headers,
    ).json()
    first = client.post(f"/api/runs/{turn['task_id']}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["state"] == "cancelled"
    second = client.post(f"/api/runs/{turn['task_id']}/cancel", headers=headers)
    assert second.status_code == 409

    # succeeded -> cancel -> 409, and the verdict stays readable over HTTP.
    session_b = client.post("/api/conversations", headers=headers).json()
    turn_b = client.post(
        f"/api/conversations/{session_b['session_id']}/messages",
        json={"text": "把倍数改成 2.0"},
        headers=headers,
    ).json()
    with TaskStore(tmp_path / "state" / "runtime.sqlite3") as store:
        worker = Worker(
            store, {"evaluate_strategy": _verdict_writer(tmp_path / "state")}, heartbeat_s=0
        )
        done = worker.run_once()
        assert done is not None and done.state == "succeeded"
    late_cancel = client.post(f"/api/runs/{turn_b['task_id']}/cancel", headers=headers)
    assert late_cancel.status_code == 409
    status = client.get(f"/api/runs/{turn_b['task_id']}")
    assert status.status_code == 200
    assert status.json()["state"] == "succeeded"
    assert status.json()["result_available"] is True


# ---------------------------------------------------------------- model faults
# The conversation LLM-assist hook is documented as deliberately unwired
# (kronos/conversation/service.py module docstring), so the client contract is
# exercised directly with fake HTTP transports, plus the documented
# degradation: the deterministic service path performs zero model calls.


class _FakeResponse:
    def __init__(self, payload: Any, *, status_code: int | None = None) -> None:
        self.payload = payload
        self._status_code = status_code

    def raise_for_status(self) -> None:
        if self._status_code is not None:
            request = httpx.Request("POST", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
            response = httpx.Response(status_code=self._status_code, request=request)
            raise httpx.HTTPStatusError("server error", request=request, response=response)

    def json(self) -> Any:
        return self.payload


class _FakeHttpClient:
    """Minimal httpx.Client stand-in with a programmable failure script."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> _FakeResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _messages() -> list[GLMChatMessage]:
    return [GLMChatMessage(role="user", content="把「改成 2」解析成参数。")]


def test_glm_timeout_bounded_retry_then_typed_error() -> None:
    http = _FakeHttpClient([httpx.ReadTimeout("timed out")] * 3)
    client = GLMClient(api_key="test-key", max_retries=2, http_client=http)

    with pytest.raises(GLMRequestError, match="ReadTimeout"):
        client.complete(_messages())
    assert http.calls == 3  # 1 initial + 2 retries, no unbounded loop


def test_glm_http_500_fails_fast_without_retry() -> None:
    http = _FakeHttpClient([_FakeResponse({}, status_code=500)])
    client = GLMClient(api_key="test-key", max_retries=2, http_client=http)

    with pytest.raises(GLMRequestError, match="HTTP 500"):
        client.complete(_messages())
    assert http.calls == 1  # deterministic HTTP failures never retry


def test_glm_malformed_payloads_raise_typed_error() -> None:
    for bad in (["not", "an", "object"], {}, {"choices": []}, {"choices": [{"message": {}}]}):
        http = _FakeHttpClient([_FakeResponse(bad)])
        client = GLMClient(api_key="test-key", http_client=http)
        with pytest.raises(GLMRequestError):
            client.complete(_messages())
        assert http.calls == 1


def test_glm_transport_level_json_garbage_surfaces_as_valueerror() -> None:
    """Honest behavior record: only schema-level malformation is typed. A
    transport payload that json() itself cannot decode surfaces as the raw
    decode error (not GLMRequestError) — documented edge, not silently eaten."""

    class _GarbageResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            msg = "Expecting value"
            raise json.JSONDecodeError(msg, "<html>502</html>", 0)

    client = GLMClient(api_key="test-key", http_client=_FakeHttpClient([_GarbageResponse()]))
    with pytest.raises(json.JSONDecodeError):
        client.complete(_messages())


def test_glm_missing_usage_is_marked_estimated_and_ledger_defaults_conservatively(
    tmp_path: Path,
) -> None:
    http = _FakeHttpClient([_FakeResponse({"choices": [{"message": {"content": "解析结果"}}]})])
    client = GLMClient(api_key="test-key", http_client=http)

    result = client.complete(_messages())
    assert result.usage.estimated is True
    assert result.usage.total_tokens is None

    # The budget ledger never records zero for unreported usage (task-runtime
    # spec: usage 缺失按保守估计).
    ledger = BudgetLedger(tmp_path / "budget.sqlite3")
    receipt = ledger.spend("round-usage-missing", "token", 0, meta={"estimated": True})
    assert receipt.amount == ledger.unreported_usage_default_tokens == 2_000.0
    usage = ledger.round_usage("round-usage-missing")
    assert usage.tokens_round.used == 2_000.0
    ledger.close()


def test_deterministic_conversation_path_makes_zero_llm_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Documented degradation: with the GLM client attached (and no key), the
    full deterministic turn chain runs untouched — adjust, engine, evidence Q&A,
    verdict Q&A, refusal — and the client is never given a single request."""

    class _ForbiddenHttpClient:
        def __init__(self) -> None:
            self.calls = 0

        def post(
            self, url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float
        ) -> Any:
            self.calls += 1
            raise AssertionError("deterministic conversation path must not call the LLM")

    monkeypatch.delenv("KRONOS_GLM_API_KEY", raising=False)
    forbidden = _ForbiddenHttpClient()
    assert GLMClient(http_client=forbidden)  # wired-in standby client
    service = _service(tmp_path)
    session = service.create_session()

    adjust = service.send_message(session.session_id, "把倍数改成 2.0")
    assert adjust.status == "submitted"
    worker = Worker(
        service.task_store,
        {"evaluate_strategy": _verdict_writer(tmp_path / "state")},
        heartbeat_s=0,
    )
    assert worker.run_once() is not None
    evidence = service.send_message(session.session_id, "为什么不如持有")
    assert evidence.status == "answered" and evidence.verdict_refs
    ask = service.send_message(session.session_id, "现在结论如何")
    assert ask.status == "answered"
    refused = service.send_message(session.session_id, "把实盘打开")
    assert refused.status == "refused"

    assert forbidden.calls == 0
    # And an unconfigured client fails typed, before any network traffic.
    with pytest.raises(GLMNotConfiguredError):
        GLMClient(http_client=_FakeHttpClient([])).complete(
            [GLMChatMessage(role="user", content="x")]
        )
    service.close()


# ------------------------------------------------------------------- restart


def test_restart_recovery_preserves_sessions_tasks_budgets_and_verdicts(
    tmp_path: Path,
) -> None:
    """Full close/reopen of every SQLite handle ("restart"): session, messages,
    revision lineage and published verdicts survive; queued work stays
    claimable; budgets are NOT reset and the wall-clock anchor never moves."""
    state = tmp_path / "state"
    service = _service(tmp_path)
    session = service.create_session()
    adjust = service.send_message(session.session_id, "把倍数改成 2.0")
    first_task = adjust.task_id
    assert first_task is not None
    worker = Worker(
        service.task_store, {"evaluate_strategy": _verdict_writer(state)}, heartbeat_s=0
    )
    done = worker.run_once()
    assert done is not None and done.state == "succeeded"
    pre = service.send_message(session.session_id, "为什么不如持有")
    assert pre.verdict_refs

    round_id = f"conv-{session.session_id}"
    usage_before = service.budget_ledger.round_usage(round_id)
    info_before = service.budget_ledger.round_info(round_id)
    messages_before = service.list_messages(session.session_id)
    service.close()  # closes conversations + runtime + budget SQLite handles

    reopened = ConversationService(state)
    try:
        detail = reopened.get_session(session.session_id)
        assert [m.content for m in detail.messages] == [m.content for m in messages_before]
        assert [m.status for m in detail.messages] == [m.status for m in messages_before]
        assert detail.current_revision["params"]["volatility_multiplier"] == 2.0
        assert detail.session.current_revision_id == adjust.revision_id

        # The verdict published before the restart is still readable.
        post = reopened.send_message(session.session_id, "为什么不如持有")
        assert post.status == "answered"
        assert post.verdict_refs == pre.verdict_refs

        # Budgets unchanged: same reservation, same frozen round record, and
        # the wall-clock anchor was not moved by the restart.
        usage_after = reopened.budget_ledger.round_usage(round_id)
        assert usage_after.backtests.reserved == usage_before.backtests.reserved == 1.0
        info_after = reopened.budget_ledger.round_info(round_id)
        assert (info_after.created_at_ms, info_after.clock_start_ms) == (
            info_before.created_at_ms,
            info_before.clock_start_ms,
        )

        # Queued work stays claimable: a post-restart adjustment runs to done.
        adjust2 = reopened.send_message(session.session_id, "ATR 改成 30")
        assert adjust2.task_state == "queued"
        assert adjust2.parent_revision_id == adjust.revision_id
        worker2 = Worker(
            reopened.task_store, {"evaluate_strategy": _verdict_writer(state)}, heartbeat_s=0
        )
        done2 = worker2.run_once()
        assert done2 is not None and done2.task_id == adjust2.task_id
        assert done2.state == "succeeded"
        # Reservations accumulate across the restart (never reset).
        usage_final = reopened.budget_ledger.round_usage(round_id)
        assert usage_final.backtests.reserved == 2.0
    finally:
        reopened.close()
