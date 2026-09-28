"""Real evaluation pipeline integration tests (package P14b).

The full deterministic chain runs against a CONSTRUCTED parquet store with
only two things mocked, both at declared seams:

- the network sync (``kronos.research.verdict.readiness.sync_klines`` /
  ``sync_funding`` monkeypatched to write the same shaped data locally);
- the wall clock / window (the handler map takes ``eval_window_days`` /
  ``warmup_days`` / ``now_ms`` overrides, so a 14d-warmup + 4d-eval
  micro window runs instead of the production 90d+14d window).

No freqtrade venv and no GLM anywhere: engine scenarios use the reference
ledger engine and the adapter-missing fallback path.

Covered here:

1. full chain: conversation task queued -> running -> succeeded, verdict
   artifact with ``execution_authority="none"``, evidence time slices present
   (the 14-day warmup ruling makes the terciles compute), engine_version
   recorded, budget spend receipts, and an idempotent re-run (attempt >= 2
   after recovery) that reuses the artifacts instead of recomputing;
2. invalid snapshot path (synthetic row injected) -> task failed with the
   snapshot report and NO verdict artifact;
3. engine fallback task event when ``KRONOS_EVAL_ENGINE=adapter`` and the
   venv is missing;
4. ensure_data with the mocked sync repairing an empty store to ready, then
   evaluating on the repaired store;
5. multi-symbol spec fails closed with a visible reason;
6. ``create_app`` attaches the daemon worker thread (and the kill switch).
"""

from __future__ import annotations

import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from kronos.conversation.handlers import (
    ENGINE_FALLBACK_EVENT,
    ENGINE_VERSION_REFERENCE,
    EVAL_WARMUP_DAYS,
    EVAL_WINDOW_DAYS,
    make_handler_map,
)
from kronos.conversation.pipeline_wiring import WORKER_ENV_SWITCH, attach_worker, stop_worker
from kronos.conversation.service import ConversationService
from kronos.data.schemas.candle import CANDLE_DEDUP_KEY
from kronos.data.schemas.funding import FUNDING_DEDUP_KEY
from kronos.data.storage.parquet_store import write_records_partitioned
from kronos.research.verdict import readiness as readiness_module
from kronos.research.verdict.contracts import EvidenceBundle, StrategyVerdict
from kronos.runtime.budget import BudgetLedger
from kronos.runtime.tasks import TaskStore
from kronos.runtime.worker import Worker
from kronos.web.app import create_app

DAY_MS = 86_400_000
MINUTE_MS = 60_000
FUNDING_MS = 28_800_000

# 2026-06-01 00:00:00 UTC (same midnight-aligned anchor as the P07 unit tests).
W0 = 1_780_272_000_000
TOTAL_DAYS = 18  # 14d warmup + 4d eval
EVAL_DAYS = 4
NOW_MS = W0 + TOTAL_DAYS * DAY_MS
SYMBOLS = ("BTCUSDT", "ETHUSDT")


# --------------------------------------------------------------- store builder


def _bars(symbol: str, seed: int) -> list[tuple[int, float, float, float, float]]:
    """Deterministic pseudo-random 1m walk with realistic OHLC shape."""
    rng = random.Random(seed + hash(symbol) % 1000)
    price = 67_000.0
    out: list[tuple[int, float, float, float, float]] = []
    ts = W0
    while ts < NOW_MS:
        open_ = price
        close = open_ * (1.0 + rng.gauss(0.0, 0.0006))
        high = max(open_, close) * (1.0 + abs(rng.gauss(0.0, 0.0002)))
        low = min(open_, close) * (1.0 - abs(rng.gauss(0.0, 0.0002)))
        out.append((ts, open_, high, low, close))
        price = close
        ts += MINUTE_MS
    return out


def _kline_table(
    symbol: str,
    bars: list[tuple[int, float, float, float, float]],
    *,
    venues: list[str] | None = None,
) -> pa.Table:
    n = len(bars)
    now = int(time.time() * 1000)
    return pa.table(
        {
            "event_time": pa.array([bar[0] for bar in bars], type=pa.int64()),
            "available_at": pa.array([bar[0] + MINUTE_MS for bar in bars], type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "open": pa.array([bar[1] for bar in bars], type=pa.float64()),
            "high": pa.array([bar[2] for bar in bars], type=pa.float64()),
            "low": pa.array([bar[3] for bar in bars], type=pa.float64()),
            "close": pa.array([bar[4] for bar in bars], type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
            "quote_volume": pa.array([6_700_000.0] * n, type=pa.float64()),
            "trade_count": pa.array([100] * n, type=pa.int64()),
            "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
            "venue": venues if venues is not None else ["binance"] * n,
        }
    )


def _funding_table(symbol: str, times: list[int], rate: float = 0.0001) -> pa.Table:
    n = len(times)
    now = int(time.time() * 1000)
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array(times, type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "funding_rate": pa.array([rate] * n, type=pa.float64()),
            "mark_price": pa.array([67_000.0] * n, type=pa.float64()),
        }
    )


def _write_store(base_path: Path, symbols: tuple[str, ...] = SYMBOLS) -> None:
    for index, symbol in enumerate(symbols):
        write_records_partitioned(
            _kline_table(symbol, _bars(symbol, seed=index)),
            base_path,
            symbol,
            "klines_1m",
            CANDLE_DEDUP_KEY,
        )
        times = list(range(W0, NOW_MS, FUNDING_MS))
        write_records_partitioned(
            _funding_table(symbol, times),
            base_path,
            symbol,
            "funding",
            FUNDING_DEDUP_KEY,
        )


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------- rig


@dataclass
class Rig:
    """Task/budget/conversation stores over one tmp state dir + data store."""

    base_path: Path
    state_dir: Path
    snapshots_dir: Path
    task_store: TaskStore
    budget_ledger: BudgetLedger
    service: ConversationService

    def handlers(
        self, *, engine_env: str = "reference", venv_dir: Path | None = None
    ) -> dict[str, Any]:
        return make_handler_map(
            base_path=self.base_path,
            state_dir=self.state_dir,
            snapshots_dir=self.snapshots_dir,
            engine_env=engine_env,
            venv_dir=venv_dir,
            task_store=self.task_store,
            budget_ledger=self.budget_ledger,
            conversations_db=self.state_dir / "conversations.sqlite3",
            eval_window_days=EVAL_DAYS,
            warmup_days=EVAL_WARMUP_DAYS,
            now_ms=NOW_MS,
        )

    def worker(self, handlers: dict[str, Any]) -> Worker:
        return Worker(self.task_store, handlers, heartbeat_s=0)


@pytest.fixture()
def rig(tmp_path: Path) -> Any:
    base = tmp_path / "data"
    base.mkdir()
    _write_store(base)
    state = tmp_path / "state"
    task_store = TaskStore(state / "runtime.sqlite3")
    budget_ledger = BudgetLedger(state / "budget.sqlite3")
    service = ConversationService(state, task_store=task_store, budget_ledger=budget_ledger)
    yield Rig(
        base_path=base,
        state_dir=state,
        snapshots_dir=state / "snapshots",
        task_store=task_store,
        budget_ledger=budget_ledger,
        service=service,
    )
    service.close()
    task_store.close()
    budget_ledger.close()


def _submit_revision(rig: Rig, session_id: str) -> str:
    """Submit one real revision evaluation through the conversation service."""
    result = rig.service.send_message(session_id, "把倍数改成 2.0")
    assert result.status == "submitted"
    assert result.task_state == "queued"
    assert result.task_id is not None
    return result.task_id


def _requeue_for_retry(task_store: TaskStore, task_id: str) -> None:
    """Force a succeeded task back to queued (the attempt>=2 recovery path)."""
    conn = sqlite3.connect(str(task_store.db_path))
    try:
        conn.execute(
            "UPDATE tasks SET state = 'queued', worker_id = NULL, lease_expiry_ms = NULL, "
            "heartbeat_ms = NULL WHERE task_id = ?",
            (task_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------- 1. chain


def test_full_chain_real_handlers(rig: Any) -> None:
    session = rig.service.create_session()
    task_id = _submit_revision(rig, session.session_id)

    done = rig.worker(rig.handlers()).run_once()
    assert done is not None and done.task_id == task_id
    assert done.state == "succeeded"

    # queued -> running -> succeeded event trail.
    assert [event.kind for event in rig.task_store.events(task_id)] == [
        "submitted",
        "claimed",
        "succeeded",
    ]

    result = rig.task_store.get_result(task_id)
    assert result is not None
    verdict_path = Path(str(result["verdict_path"]))
    assert verdict_path.is_file()
    verdict = StrategyVerdict.model_validate_json(verdict_path.read_text(encoding="utf-8"))
    assert verdict.execution_authority == "none"
    assert verdict.engine_version == ENGINE_VERSION_REFERENCE
    assert result["evidence_status"] == verdict.evidence_status
    assert result["disposition"] == verdict.disposition
    assert result["reused"] is False
    assert result["engine"] == "reference"

    # Evidence artifact: the 14d warmup ruling makes the terciles compute.
    evidence_path = Path(str(result["artifact_refs"]["evidence"]))
    bundle = EvidenceBundle.model_validate_json(evidence_path.read_text(encoding="utf-8"))
    assert bundle.run_id == result["run_id"]
    assert len(bundle.time_slices) == 3  # empty slices would mean memberships=None
    assert all(slice_.rule_id == "trailing_10d_vol_tercile" for slice_ in bundle.time_slices)
    assert sum(slice_.sample_bars for slice_ in bundle.time_slices) > 0
    # Dev = first 2 days, holdout = last 2 days of the 4d evaluation window
    # (proportional to the ruled 60d/30d split of the 90d window).
    window_start = W0 + EVAL_WARMUP_DAYS * DAY_MS
    assert bundle.holdout.dev_window == f"{_iso(window_start)}..{_iso(window_start + 2 * DAY_MS)}"
    assert (
        bundle.holdout.holdout_window
        == f"{_iso(window_start + 2 * DAY_MS)}..{_iso(window_start + 4 * DAY_MS)}"
    )
    assert bundle.holdout.exposed_count == 0 and bundle.holdout.exposed is False

    assert Path(str(result["artifact_refs"]["ledger"])).is_file()
    assert Path(str(result["artifact_refs"]["snapshot"])).is_file()

    # Budget spend receipts recorded against the service round.
    usage = rig.budget_ledger.round_usage(f"conv-{session.session_id}")
    assert usage.backtests.used == float(result["backtests_used"])
    assert usage.backtests.used > 0
    assert usage.wall_clock.used > 0

    # The service evidence path serves the published verdict.
    evidence = rig.service.send_message(session.session_id, "为什么不如持有")
    assert evidence.status == "answered"
    assert any(ref.startswith(f"verdict={verdict_path}") for ref in evidence.verdict_refs)


def test_rerun_after_recovery_reuses_artifacts(rig: Any) -> None:
    session = rig.service.create_session()
    task_id = _submit_revision(rig, session.session_id)
    worker = rig.worker(rig.handlers())
    assert worker.run_once() is not None
    result = rig.task_store.get_result(task_id)
    assert result is not None
    verdict_path = Path(str(result["verdict_path"]))
    content_before = verdict_path.read_text(encoding="utf-8")
    mtime_before = verdict_path.stat().st_mtime_ns

    # attempt >= 2: the task is re-queued exactly like lease recovery does.
    _requeue_for_retry(rig.task_store, task_id)
    done = worker.run_once()
    assert done is not None and done.state == "succeeded"
    rerun = rig.task_store.get_result(task_id)
    assert rerun is not None
    assert rerun["reused"] is True
    assert verdict_path.read_text(encoding="utf-8") == content_before
    assert verdict_path.stat().st_mtime_ns == mtime_before


# -------------------------------------------------------- 2. invalid snapshot


def test_invalid_snapshot_fails_task(rig: Any) -> None:
    # Inject one synthetic venue row inside the window (off-grid timestamp so
    # it cannot dedup-collide): one-vote-veto taints the whole snapshot.
    bars = _bars("BTCUSDT", seed=0)
    ts, open_, high, low, close = bars[len(bars) // 2]
    write_records_partitioned(
        _kline_table("BTCUSDT", [(ts + 1_000, open_, high, low, close)], venues=["synthetic"]),
        rig.base_path,
        "BTCUSDT",
        "klines_1m",
        CANDLE_DEDUP_KEY,
    )

    session = rig.service.create_session()
    task_id = _submit_revision(rig, session.session_id)
    done = rig.worker(rig.handlers()).run_once()
    assert done is not None and done.task_id == task_id
    assert done.state == "failed"
    assert done.error_ref is not None
    assert "数据快照无效" in done.error_ref
    assert "snap-" in done.error_ref  # rendered snapshot report text present
    assert rig.task_store.get_result(task_id) is None
    # NEVER a verdict on invalid data: no run artifacts at all.
    runs_dir = rig.state_dir / "runs"
    assert not runs_dir.exists() or not any(runs_dir.rglob("verdict.json"))


# -------------------------------------------------------- 3. engine fallback


def test_engine_fallback_when_venv_missing(rig: Any) -> None:
    session = rig.service.create_session()
    task_id = _submit_revision(rig, session.session_id)
    missing_venv = rig.state_dir / "no-such-venv"
    done = rig.worker(rig.handlers(engine_env="adapter", venv_dir=missing_venv)).run_once()
    assert done is not None and done.state == "succeeded"

    fallback_events = [
        event for event in rig.task_store.events(task_id) if event.kind == ENGINE_FALLBACK_EVENT
    ]
    assert len(fallback_events) == 1
    assert "freqtrade" in (fallback_events[0].detail or "")

    result = rig.task_store.get_result(task_id)
    assert result is not None
    assert result["engine"] == "reference"
    assert result["engine_fallback"] is not None
    verdict = StrategyVerdict.model_validate_json(
        Path(str(result["verdict_path"])).read_text(encoding="utf-8")
    )
    assert verdict.engine_version == ENGINE_VERSION_REFERENCE


# --------------------------------------------- 4. ensure_data (mocked sync)


def test_ensure_data_repairs_empty_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "data"
    base.mkdir()  # EMPTY store: everything must come from the (mocked) sync
    state = tmp_path / "state"

    def fake_sync_klines(
        symbol: str,
        *,
        base_path: Path,
        since: int | None = None,
        max_retries: int = 5,
        request_interval_ms: int = 200,
    ) -> int:
        start = max(since if since is not None else W0, W0)
        bars = [bar for bar in _bars(symbol, seed=0) if bar[0] >= start]
        if bars:
            write_records_partitioned(
                _kline_table(symbol, bars), Path(base_path), symbol, "klines_1m", CANDLE_DEDUP_KEY
            )
        return len(bars)

    def fake_sync_funding(
        symbol: str,
        *,
        base_path: Path,
        since: int | None = None,
        max_retries: int = 5,
        request_interval_ms: int = 200,
    ) -> int:
        start = max(since if since is not None else W0, W0)
        times = [ts for ts in range(W0, NOW_MS, FUNDING_MS) if ts >= start]
        write_records_partitioned(
            _funding_table(symbol, times), Path(base_path), symbol, "funding", FUNDING_DEDUP_KEY
        )
        return len(times)

    # The ONLY mock seam: the network sync functions inside the readiness
    # module. Planning, repair application and re-planning stay real.
    monkeypatch.setattr(readiness_module, "sync_klines", fake_sync_klines)
    monkeypatch.setattr(readiness_module, "sync_funding", fake_sync_funding)

    task_store = TaskStore(state / "runtime.sqlite3")
    budget_ledger = BudgetLedger(state / "budget.sqlite3")
    service = ConversationService(state, task_store=task_store, budget_ledger=budget_ledger)
    try:
        session = service.create_session()
        tool_result = service.invoke_tool(
            "ensure_data", {"session_id": session.session_id, "symbol": "BTCUSDT"}
        )
        task_id = str(tool_result["task_id"])
        done = Worker(
            task_store,
            make_handler_map(
                base_path=base,
                state_dir=state,
                snapshots_dir=state / "snapshots",
                engine_env="reference",
                task_store=task_store,
                budget_ledger=budget_ledger,
                conversations_db=state / "conversations.sqlite3",
                eval_window_days=EVAL_DAYS,
                warmup_days=EVAL_WARMUP_DAYS,
                now_ms=NOW_MS,
            ),
        ).run_once()
        assert done is not None and done.state == "succeeded"
        result = task_store.get_result(task_id)
        assert result is not None
        assert result["plan_status"] == "ready"
        assert "就绪" in str(result["report"])
        assert int(result["repairs_applied"]) >= 1

        # The repaired store feeds a full real evaluation.
        submitted = service.send_message(session.session_id, "把倍数改成 2.0")
        assert submitted.status == "submitted"
        done = Worker(
            task_store,
            make_handler_map(
                base_path=base,
                state_dir=state,
                snapshots_dir=state / "snapshots",
                engine_env="reference",
                task_store=task_store,
                budget_ledger=budget_ledger,
                conversations_db=state / "conversations.sqlite3",
                eval_window_days=EVAL_DAYS,
                warmup_days=EVAL_WARMUP_DAYS,
                now_ms=NOW_MS,
            ),
        ).run_once()
        assert done is not None and done.state == "succeeded"
    finally:
        service.close()
        task_store.close()
        budget_ledger.close()


# --------------------------------------------------- 5. multi-symbol boundary


def test_multi_symbol_spec_fails_closed(rig: Any) -> None:
    session = rig.service.create_session()
    root = rig.service.current_revision(session.session_id)
    content = root.model_dump(
        mode="json",
        exclude={"strategy_revision_id", "parent_revision_id", "spec_hash", "created_at"},
    )
    content["symbols"] = ["BTCUSDT", "ETHUSDT"]
    tool_result = rig.service.invoke_tool(
        "evaluate_strategy", {"session_id": session.session_id, "spec": content}
    )
    task_id = str(tool_result["task_id"])
    done = rig.worker(rig.handlers()).run_once()
    assert done is not None and done.task_id == task_id
    assert done.state == "failed"
    assert done.error_ref is not None
    assert "单一交易对" in done.error_ref


# ------------------------------------------------------------- 6. web wiring


def test_create_app_attaches_daemon_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KRONOS_SECRET_STORE_PATH", str(tmp_path / "secrets"))
    monkeypatch.setenv(WORKER_ENV_SWITCH, "on")
    app = create_app(
        project_root=tmp_path,
        state_path=tmp_path / "state",
        data_path=tmp_path / "data",
        snapshots_path=tmp_path / "state" / "snapshots",
        freqtrade_venv_path=tmp_path / "venv",
    )
    worker = getattr(app.state, "pipeline_worker", None)
    assert isinstance(worker, Worker)
    thread = app.state.pipeline_worker_thread
    assert thread.daemon is True
    assert thread.is_alive()
    # Idempotent attach: a second call returns the running worker.
    assert (
        attach_worker(
            app.state,
            base_path=tmp_path / "data",
            state_dir=tmp_path / "state",
            snapshots_dir=tmp_path / "state" / "snapshots",
        )
        is worker
    )
    stop_worker(app.state)
    thread.join(timeout=5.0)
    assert not thread.is_alive()


def test_create_app_worker_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KRONOS_SECRET_STORE_PATH", str(tmp_path / "secrets"))
    monkeypatch.setenv(WORKER_ENV_SWITCH, "off")
    app = create_app(
        project_root=tmp_path,
        state_path=tmp_path / "state",
        data_path=tmp_path / "data",
        snapshots_path=tmp_path / "state" / "snapshots",
        freqtrade_venv_path=tmp_path / "venv",
    )
    assert getattr(app.state, "pipeline_worker", None) is None
    assert EVAL_WINDOW_DAYS == 90  # production default untouched by test overrides
