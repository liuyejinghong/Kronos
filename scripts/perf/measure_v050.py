"""Performance measurement harness for v0.5.0 M3 (package P21).

Measures the §7.6 performance-gate numbers on the owner's Mac (the formal
machine) and writes them as one JSON document to stdout (``--out`` saves a
copy). Read-only with respect to product code: the only repo writes are the
market-data files the product itself writes under ``./data`` (runtime state,
reused later by M4 acceptance) — snapshots freeze into a temp dir and every
other artifact stays in memory.

Subcommands
-----------
env          machine / interpreter / proxy / dependency facts
web-start    time `uv run kronos web` -> first /api/health 200 (fresh process)
data-sync    real-network 90d sync via the product path (proxy via env), then
             an incremental re-sync; counts HTTP requests and 429s by wrapping
             httpx.get in THIS process (no production edits)
readiness    P06 readiness plan + P07 snapshot build/freeze on the 90d window
ledger       P04 reference ledger, one full-window run (15m native; 1h probe)
evidence     P10 full evidence bundle via the REFERENCE engine (default 9-point
             neighborhood grid on the dev window)
adapter      P08 freqtrade adapter, ONE full-window run (per-run subprocess
             overhead; budget extrapolation happens in the report, honestly)
model-probe  GLM probe(): configured status from env/secret store, never sends
             the key; one tiny completion only when a key is actually present
targets      Web accept-latency (sendMessage via TestClient) + heartbeat /
             round-budget default assertions read from the code

Usage (from the repo root, via uv so the project env is used):
    uv run python scripts/perf/measure_v050.py <subcommand> [options]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_BASE = REPO_ROOT / "data"

DAY_MS = 86_400_000
WINDOW_DAYS = 90
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
ATR_PERIOD = 14
MULTIPLIER = 1.0
FEE_BPS = 4.0
SLIPPAGE_BPS = 5.0
START_EQUITY = 10_000.0
#: design.md: 60/30 dev/holdout split of the 90d window.
DEV_DAYS = 54
HOLDOUT_DAYS = 27


def window_bounds() -> tuple[int, int, tuple[int, int], tuple[int, int]]:
    """Return (window_start_ms, window_end_ms, dev_ms, holdout_ms).

    window_end = today 00:00 UTC (the "90 complete UTC days" policy);
    window_start = window_end - 90d; dev = first 54d of the window;
    holdout = the following 27d (last 9d stay unexposed).
    """
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end_ms = int(today.timestamp() * 1000)
    start_ms = end_ms - WINDOW_DAYS * DAY_MS
    dev = (start_ms, start_ms + DEV_DAYS * DAY_MS)
    holdout = (dev[1], dev[1] + HOLDOUT_DAYS * DAY_MS)
    return start_ms, end_ms, dev, holdout


def peak_rss_mb() -> float:
    """Peak RSS of THIS process in MB (macOS reports ru_maxrss in bytes)."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    bytes_ = raw if sys.platform == "darwin" else raw * 1024
    return round(bytes_ / (1024 * 1024), 1)


def emit(result: dict[str, Any], out: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if out is not None:
        out.write_text(text + "\n", encoding="utf-8")
    print(text)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------- env


def cmd_env(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {
        "machine": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "proxy_env": {
            name: bool(os.environ.get(name))
            for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY")
        },
        "data_base": str(DATA_BASE),
        "window": {
            "days": WINDOW_DAYS,
            "start": iso(window_bounds()[0]),
            "end": iso(window_bounds()[1]),
            "dev": [iso(window_bounds()[2][0]), iso(window_bounds()[2][1])],
            "holdout": [iso(window_bounds()[3][0]), iso(window_bounds()[3][1])],
        },
        "freqtrade_venv": str(REPO_ROOT / ".tools" / "freqtrade-venv"),
    }
    try:
        uv = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, timeout=30, check=False
        )
        result["machine"]["uv"] = uv.stdout.strip() or uv.stderr.strip()
    except OSError as exc:
        result["machine"]["uv"] = f"unavailable: {exc}"
    try:
        ft = subprocess.run(
            [str(REPO_ROOT / ".tools" / "freqtrade-venv" / "bin" / "freqtrade"), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result["freqtrade_version"] = (ft.stdout or ft.stderr).strip()[:200]
    except OSError as exc:
        result["freqtrade_version"] = f"unavailable: {exc}"
    emit(result, args.out)
    return result


# ---------------------------------------------------------------- web start


def cmd_web_start(args: argparse.Namespace) -> dict[str, Any]:
    import httpx

    runs: list[dict[str, Any]] = []
    for index in range(args.repeats):
        port = args.port + index
        started = time.monotonic()
        proc = subprocess.Popen(
            ["uv", "run", "kronos", "web", "--port", str(port)],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        first_200: float | None = None
        deadline = started + args.timeout_s
        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                try:
                    resp = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1.0)
                    if resp.status_code == 200:
                        first_200 = time.monotonic() - started
                        break
                except httpx.HTTPError:
                    time.sleep(0.1)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        runs.append(
            {
                "run": index + 1,
                "port": port,
                "health_200_s": round(first_200, 3) if first_200 is not None else None,
                "label": "cold" if index == 0 else "warm",
            }
        )
        time.sleep(0.5)
    times = [r["health_200_s"] for r in runs if r["health_200_s"] is not None]
    result = {
        "runs": runs,
        "median_s": round(statistics.median(times), 3) if times else None,
        "note": "cold = first fresh process (page-cache as-is), warm = subsequent fresh "
        "processes; every run is a brand-new `uv run kronos web` process",
    }
    emit(result, args.out)
    return result


# ---------------------------------------------------------------- data sync


class RequestCounter:
    """Counts httpx.get calls and 429s inside THIS process (no product edits)."""

    def __init__(self) -> None:
        self.total = 0
        self.status_429 = 0
        self.errors = 0
        self._original: Any = None

    def install(self) -> None:
        import httpx

        counter = self
        original = httpx.get

        def wrapped(url: Any, *a: Any, **kw: Any) -> Any:
            counter.total += 1
            try:
                resp = original(url, *a, **kw)
            except httpx.HTTPError:
                counter.errors += 1
                raise
            if getattr(resp, "status_code", None) == 429:
                counter.status_429 += 1
            return resp

        self._original = original
        httpx.get = wrapped  # type: ignore[assignment]

    def restore(self) -> None:
        import httpx

        if self._original is not None:
            httpx.get = self._original  # type: ignore[assignment]


def _run_sync(since_ms: int | None, counter: RequestCounter) -> dict[str, Any]:
    from kronos.data.loaders.exchange_info import (
        fetch_exchange_info,
        save_exchange_info,
        validate_symbol,
    )
    from kronos.data.sync import sync_all

    started = time.monotonic()
    exchange_symbols = fetch_exchange_info()
    save_exchange_info(exchange_symbols, DATA_BASE)
    t_exchange = time.monotonic() - started
    valid = [s for s in SYMBOLS if validate_symbol(s, DATA_BASE)]
    requests_before = counter.total
    started = time.monotonic()
    counts = sync_all(
        valid,
        base_path=DATA_BASE,
        since=since_ms,
        max_retries=5,
        request_interval_ms=200,
    )
    wall = time.monotonic() - started
    return {
        "symbols": valid,
        "exchange_info_s": round(t_exchange, 3),
        "wall_s": round(wall, 2),
        "rows": counts,
        "http_requests": counter.total - requests_before,
        "http_429s": counter.status_429,
        "http_errors": counter.errors,
    }


def cmd_data_sync(args: argparse.Namespace) -> dict[str, Any]:
    counter = RequestCounter()
    counter.install()
    result: dict[str, Any] = {}
    try:
        if args.mode in ("full", "both"):
            since_ms = None
            if args.since:
                since_dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=UTC)
                since_ms = int(since_dt.timestamp() * 1000)
            counter.status_429 = 0
            counter.errors = 0
            result["full"] = _run_sync(since_ms, counter)
            result["full"]["since"] = args.since
        if args.mode in ("incremental", "both"):
            counter.status_429 = 0
            counter.errors = 0
            # since=None -> the product auto-detects from the store (incremental)
            result["incremental"] = _run_sync(None, counter)
    finally:
        counter.restore()
    result["peak_rss_mb"] = peak_rss_mb()
    emit(result, args.out)
    return result


# ------------------------------------------------------------ load helpers


def _bars_from_df(df: Any) -> list[tuple[int, float, float, float, float]]:
    return [
        (int(r.event_time), float(r.open), float(r.high), float(r.low), float(r.close))
        for r in df.itertuples()
    ]


def _load_window(symbol: str, timeframe: str, start_ms: int, end_ms: int) -> Any:
    from kronos.data.storage.query import load

    return load(symbol, base_path=DATA_BASE, timeframe=timeframe, since=start_ms, until=end_ms)


def _prepare_bars(
    symbol: str, timeframe: str, *, snap_funding_hour: bool = False
) -> dict[str, Any]:
    """Load 1m + signal bars + funding for the snapshot span, timing each leg.

    Span = (window_start - 2d headroom, window_end): carries the warmup the
    ledger/evaluator need before the evaluation window starts.
    """
    start_ms, end_ms, _dev, _hold = window_bounds()
    span_start = start_ms - 2 * DAY_MS
    timings: dict[str, float] = {}
    frames: dict[str, Any] = {}
    for name, timeframe_ in (("bars_1m", "1m"), ("bars_sig", timeframe)):
        t0 = time.monotonic()
        frames[name] = _load_window(symbol, timeframe_, span_start, end_ms)
        timings[timeframe_] = round(time.monotonic() - t0, 3)
    t0 = time.monotonic()
    from kronos.data.storage.query import load as _load

    fdf = _load(
        symbol,
        base_path=DATA_BASE,
        timeframe="1m",
        dataset="funding",
        since=span_start,
        until=end_ms,
    )
    timings["funding"] = round(time.monotonic() - t0, 3)
    funding = (
        [(int(r.event_time), float(r.funding_rate)) for r in fdf.itertuples()]
        if not fdf.empty
        else []
    )
    funding_note: str | None = None
    if snap_funding_hour:
        # Real Binance funding event_time carries 0-26ms jitter past the hour;
        # the P08 kernel adapter fails closed on non-hour-aligned events
        # (FundingDataError). Floor to the hour HERE (measurement-side input
        # shaping, not a production fix) so the overhead can be measured.
        floored = [(ts - ts % 3_600_000, rate) for ts, rate in funding]
        changed = sum(1 for (a, _), (b, _) in zip(funding, floored, strict=True) if a != b)
        funding = floored
        funding_note = (
            f"{changed}/{len(floored)} funding timestamps floored to the hour "
            "(real Binance jitter; adapter fails closed otherwise) — measurement-side "
            "shaping, production fix is an engine-lane finding"
        )
    return {
        "bars_1m": _bars_from_df(frames["bars_1m"]),
        "bars_sig": _bars_from_df(frames["bars_sig"]),
        "funding": funding,
        "funding_note": funding_note,
        "load_s": timings,
        "n_1m": len(frames["bars_1m"]),
        "n_sig": len(frames["bars_sig"]),
        "n_funding": len(funding),
    }


# ------------------------------------------------- readiness + snapshot (P06/P07)


def cmd_readiness(args: argparse.Namespace) -> dict[str, Any]:
    from kronos.research.verdict.readiness import (
        apply_repair_actions,
        build_readiness_plan,
    )
    from kronos.research.verdict.snapshot import build_snapshot, freeze_snapshot
    from kronos.strategy.variant_rules import required_warmup_bars

    start_ms, end_ms, _dev, _hold = window_bounds()
    # one UTC day of signal bars + atr_period (variant rule); the extra day
    # keeps the ledger's previous-UTC-day pivot requirement satisfied.
    warmup_bars = required_warmup_bars(ATR_PERIOD, "15m") + 96

    def _plan() -> Any:
        return build_readiness_plan(
            list(SYMBOLS),
            base_path=DATA_BASE,
            window_start_ms=start_ms,
            window_end_ms=end_ms,
            warmup_bars=warmup_bars,
            signal_timeframe="15m",
        )

    started = time.monotonic()
    plan = _plan()
    t_plan = time.monotonic() - started

    # Product flow P06 -> repair -> re-plan: close only the gaps the plan found.
    repair: dict[str, Any] = {"ran": False}
    if plan.overall_status == "needs_repair":
        repair["ran"] = True
        repair["actions"] = [
            {
                "symbol": a.symbol,
                "dataset": a.dataset,
                "since": iso(a.since_ms),
                "until": iso(a.until_ms),
            }
            for a in plan.actions
        ]
        started = time.monotonic()
        outcomes = apply_repair_actions(
            plan, base_path=DATA_BASE, max_retries=5, request_interval_ms=200
        )
        repair["wall_s"] = round(time.monotonic() - started, 2)
        repair["rows_fetched"] = {f"{o.symbol}/{o.dataset}": o.rows_fetched for o in outcomes}
        repair["statuses"] = sorted({o.status for o in outcomes})
        started = time.monotonic()
        plan = _plan()
        repair["replan_s"] = round(time.monotonic() - started, 3)
        repair["plan_status_after"] = plan.overall_status

    started = time.monotonic()
    manifest = build_snapshot(plan, base_path=DATA_BASE)
    t_snapshot = time.monotonic() - started

    with tempfile.TemporaryDirectory(prefix="kronos-perf-snap-") as tmp:
        started = time.monotonic()
        path = freeze_snapshot(manifest, snapshots_dir=Path(tmp))
        t_freeze = time.monotonic() - started
        freeze_bytes = path.stat().st_size

    result = {
        "warmup_bars": warmup_bars,
        "window": {"start": iso(start_ms), "end": iso(end_ms)},
        "plan_status": plan.overall_status,
        "plan_build_s": round(t_plan, 3),
        "repair": repair,
        "snapshot_status": manifest.overall_status,
        "snapshot_id": manifest.snapshot_id,
        "snapshot_build_s": round(t_snapshot, 3),
        "snapshot_freeze_s": round(t_freeze, 3),
        "snapshot_manifest_bytes": freeze_bytes,
        "datasets": {
            f"{entry.symbol}/{entry.dataset}": {
                "status": entry.status,
                "bar_count": entry.bar_count,
            }
            for entry in plan.entries
        },
        "peak_rss_mb": peak_rss_mb(),
    }
    emit(result, args.out)
    return result


# -------------------------------------------------------------------- ledger


def cmd_ledger(args: argparse.Namespace) -> dict[str, Any]:
    from kronos.research.verdict.reference_ledger import CostPolicy, run_reference_backtest
    from kronos.strategy.spec import VariantParams

    symbol = args.symbol
    atr_period = args.atr_period
    prepared = _prepare_bars(symbol, args.timeframe)
    params = VariantParams(atr_period=atr_period, volatility_multiplier=MULTIPLIER)
    started = time.monotonic()
    ledger = run_reference_backtest(
        prepared["bars_sig"],
        prepared["bars_1m"],
        params=params,
        cost=CostPolicy(fee_bps=FEE_BPS, slippage_bps=SLIPPAGE_BPS),
        start_equity=START_EQUITY,
        funding_events=prepared["funding"],
        symbol=symbol,
    )
    engine_s = time.monotonic() - started
    result: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": args.timeframe,
        "atr_period": atr_period,
        "load_s": prepared["load_s"],
        "n_bars_signal": prepared["n_sig"],
        "n_bars_1m": prepared["n_1m"],
        "n_funding_events": prepared["n_funding"],
        "engine_run_s": round(engine_s, 3),
        "trades": len(ledger.closed_trades),
        "final_equity": round(ledger.final_equity, 2),
        "peak_rss_mb": peak_rss_mb(),
        "note": (
            "the frozen P04 ledger is 15m-native (TF_MS/BARS_PER_DAY constants); a '1h' "
            "run is the same code path walked over the 1h resampled series — recorded as "
            "a timing probe, not a semantics acceptance"
            if args.timeframe == "1h"
            else "native 15m path"
        ),
    }
    emit(result, args.out)
    return result


# ------------------------------------------------------------------ evidence


def cmd_evidence(args: argparse.Namespace) -> dict[str, Any]:
    from kronos.research.verdict.evidence import (
        build_evidence_bundle,
        make_reference_engine,
        tag_engine,
    )
    from kronos.research.verdict.reference_ledger import CostPolicy
    from kronos.strategy.spec import VariantParams

    symbol = args.symbol
    prepared = _prepare_bars(symbol, "15m")
    start_ms, end_ms, dev, holdout = window_bounds()
    params = VariantParams(atr_period=ATR_PERIOD, volatility_multiplier=MULTIPLIER)

    calls = {"n": 0}
    base_engine = make_reference_engine()

    def counting_engine(run_input: Any) -> Any:
        calls["n"] += 1
        return base_engine(run_input)

    tag_engine(counting_engine, "reference")

    started = time.monotonic()
    bundle = build_evidence_bundle(
        engine=counting_engine,
        bars_15m=prepared["bars_sig"],
        bars_1m=prepared["bars_1m"],
        params=params,
        cost=CostPolicy(fee_bps=FEE_BPS, slippage_bps=SLIPPAGE_BPS),
        start_equity=START_EQUITY,
        funding_events=prepared["funding"],
        snapshot_id="perf-snapshot-0000",
        run_id="perf-evidence-0001",
        strategy_revision_id="kronos_threshold_v1",
        spec_hash="perf-spec-hash-not-a-real-revision",
        dev_window_ms=dev,
        holdout_window_ms=holdout,
        holdout_exposed_count=0,
        neighborhood_grid=None,  # default pre-registered 3x3 grid
        symbol=symbol,
    )
    wall = time.monotonic() - started
    grid_points = bundle.neighborhood.grid
    result = {
        "symbol": symbol,
        "engine": "reference (P04)",
        "window": {"start": iso(start_ms), "end": iso(end_ms)},
        "dev_window": [iso(dev[0]), iso(dev[1])],
        "holdout_window": [iso(holdout[0]), iso(holdout[1])],
        "engine_invocations": calls["n"],
        "grid_points": len(grid_points),
        "grid_coords": [[p.atr_period, p.volatility_multiplier] for p in grid_points],
        "metrics_block_keys": sorted(bundle.metrics.model_dump().keys())[:6],
        "time_slices": len(bundle.time_slices),
        "holdout_block": {
            "window": bundle.holdout.holdout_window,
            "exposed": bundle.holdout.exposed,
        },
        "bundle_bytes": len(bundle.model_dump_json()),
        "build_s": round(wall, 3),
        "n_bars_signal": prepared["n_sig"],
        "n_bars_1m": prepared["n_1m"],
        "load_s": prepared["load_s"],
        "peak_rss_mb": peak_rss_mb(),
    }
    emit(result, args.out)
    return result


# ------------------------------------------------------------------- adapter


def cmd_adapter(args: argparse.Namespace) -> dict[str, Any]:
    from kronos.research.verdict.backtest_adapter import BacktestCaseInput, StrategyBacktestAdapter

    symbol = args.symbol
    prepared = _prepare_bars(symbol, "15m", snap_funding_hour=True)
    case = BacktestCaseInput(
        bars_15m=prepared["bars_sig"],
        bars_1m=prepared["bars_1m"],
        funding_events=prepared["funding"],
        atr_period=ATR_PERIOD,
        volatility_multiplier=MULTIPLIER,
        fee_bps=FEE_BPS,
        slippage_bps=0.0,
        start_equity=START_EQUITY,
        equity_fraction=1.0,
        symbol=symbol,
        strategy_revision_id="kronos_threshold_v1",
        funding_declared_absent=not prepared["funding"],
    )
    adapter = StrategyBacktestAdapter()
    started = time.monotonic()
    out_ledger = adapter.run_backtest(case)
    wall = time.monotonic() - started
    result = {
        "symbol": symbol,
        "engine": "freqtrade adapter (P08) subprocess",
        "n_bars_signal": prepared["n_sig"],
        "n_bars_1m": prepared["n_1m"],
        "n_funding_events": prepared["n_funding"],
        "load_s": prepared["load_s"],
        "wall_s": round(wall, 3),
        "trades": len(out_ledger.closed_trades),
        "final_equity": round(out_ledger.final_equity, 2),
        "funding_note": prepared["funding_note"],
        "peak_rss_mb": peak_rss_mb(),
        "note": (
            "single full-window run; the 14-run bundle / 40-run round budget "
            "extrapolations are computed in the report and labeled as extrapolations"
        ),
    }
    emit(result, args.out)
    return result


# --------------------------------------------------------------- model probe


def cmd_model_probe(args: argparse.Namespace) -> dict[str, Any]:
    from kronos.agent.secrets import resolve_secret_store_path
    from kronos.conversation.llm_client import GLMChatMessage, GLMClient

    env_present = bool(os.environ.get("KRONOS_GLM_API_KEY"))
    store_path = resolve_secret_store_path()
    client = GLMClient()
    status = client.probe()
    result: dict[str, Any] = {
        "env_key_present": env_present,
        "secret_store_path": str(store_path),
        "secret_store_exists": store_path.exists(),
        "probe": status.model_dump(),
    }
    if status.configured:
        started = time.monotonic()
        try:
            chat = client.complete([GLMChatMessage(role="user", content="reply ok")], max_tokens=16)
            result["completion_smoke"] = {
                "ok": True,
                "wall_s": round(time.monotonic() - started, 3),
                "model": chat.model,
                "latency_ms_reported": chat.latency_ms,
                "total_tokens": chat.usage.total_tokens,
            }
        except Exception as exc:  # record any provider failure honestly
            result["completion_smoke"] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }
    else:
        result["completion_smoke"] = None
        result["note"] = "pending owner key (GLM): probe() reports not configured; leg skipped"
    emit(result, args.out)
    return result


# ------------------------------------------------------------------- targets


def cmd_targets(args: argparse.Namespace) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from kronos.conversation.service import DEFAULT_ROUND_WALL_CLOCK_S
    from kronos.runtime.worker import _DEFAULT_HEARTBEAT_S, _DEFAULT_LEASE_MS
    from kronos.web.app import create_app

    with tempfile.TemporaryDirectory(prefix="kronos-perf-targets-") as tmp:
        app = create_app(project_root=Path(tmp))
        client = TestClient(app)
        session = client.post("/api/conversations").json()
        session_id = session["session_id"]
        latencies: list[float] = []
        statuses: list[int] = []
        task_states: list[str | None] = []
        for _ in range(args.repeats):
            started = time.monotonic()
            resp = client.post(
                f"/api/conversations/{session_id}/messages",
                # revision change: the path that actually enqueues an
                # evaluate_strategy task (the real "受理" the 1s target is about)
                json={"text": "把倍数改成 2.0"},
            )
            latencies.append(time.monotonic() - started)
            statuses.append(resp.status_code)
            task_states.append(resp.json().get("task_state"))
        latencies.sort()
    result = {
        "sendMessage_accept": {
            "repeats": args.repeats,
            "status_codes": sorted(set(statuses)),
            "task_states": sorted({s for s in task_states if s is not None}),
            "p50_s": round(statistics.median(latencies), 4),
            "max_s": round(latencies[-1], 4),
            "target_accept_s": 1.0,
            "pass": max(latencies) < 1.0 and set(statuses) == {202} and bool(task_states[0]),
        },
        "heartbeat": {
            "worker_default_heartbeat_s": _DEFAULT_HEARTBEAT_S,
            "worker_default_lease_ms": _DEFAULT_LEASE_MS,
            "target_every_s": 5.0,
            "pass": _DEFAULT_HEARTBEAT_S <= 5.0,
            "note": "runtime worker heartbeats from a background thread every "
            "heartbeat_s while a task runs (kronos/runtime/worker.py)",
        },
        "round_budget": {
            "wall_clock_per_round_s": DEFAULT_ROUND_WALL_CLOCK_S,
            "backtests_per_round": 40,
            "note": "BudgetLimits defaults (kronos/runtime/budget.py) + service constant",
        },
    }
    emit(result, args.out)
    return result


# ----------------------------------------------------------------------- all


def cmd_all(args: argparse.Namespace) -> dict[str, Any]:
    from kronos.data.storage.query import coverage

    start_ms, _end, _dev, _hold = window_bounds()
    existing = coverage("BTCUSDT", base_path=DATA_BASE, datasets=["klines_1m"])
    has_window = (
        bool(existing)
        and existing[0].min_event_time is not None
        and existing[0].min_event_time <= start_ms
    )

    steps: list[tuple[str, list[str]]] = [("env", [])]
    if not args.skip_sync:
        steps.append(
            ("data-sync", ["--mode", "both", "--since", args.since])
            if not has_window
            else ("data-sync", ["--mode", "incremental"])
        )
    steps += [
        ("readiness", []),
        ("ledger", ["--timeframe", "15m"]),
        ("ledger", ["--timeframe", "1h"]),
        ("evidence", []),
        ("adapter", []),
        ("model-probe", []),
        ("targets", []),
    ]
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="kronos-perf-out-") as tmp:
        for name, extra in steps:
            out_path = Path(tmp) / f"{name}_{'_'.join(extra).replace('-', '')}.json"
            sub = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/perf/measure_v050.py",
                    name,
                    *extra,
                    "--out",
                    str(out_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=args.step_timeout_s,
                check=False,
            )
            payload: Any
            try:
                payload = json.loads(out_path.read_text())
            except (OSError, json.JSONDecodeError):
                payload = {
                    "error": "no json",
                    "stdout_tail": sub.stdout[-1500:],
                    "stderr_tail": sub.stderr[-1500:],
                }
            key = name + ("_" + "_".join(extra[1::2]) if extra else "")
            results[key] = payload
            print(f"[measure_v050] {key}: done (rc={sub.returncode})", file=sys.stderr)
    emit({"env": results.get("env"), "steps": results}, args.out)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=None, help="also write the JSON here")
    sub = parser.add_subparsers(dest="command", required=True)

    simple = {
        "env": cmd_env,
        "readiness": cmd_readiness,
        "model-probe": cmd_model_probe,
    }
    for name, func in simple.items():
        p = sub.add_parser(name)
        p.set_defaults(func=func)

    p = sub.add_parser("web-start")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--port", type=int, default=8123)
    p.add_argument("--timeout-s", type=float, default=180.0)
    p.set_defaults(func=cmd_web_start)

    p = sub.add_parser("data-sync")
    p.add_argument("--mode", choices=("full", "incremental", "both"), default="both")
    p.add_argument("--since", type=str, default=None, help="YYYY-MM-DD UTC start for full sync")
    p.set_defaults(func=cmd_data_sync)

    p = sub.add_parser("ledger")
    p.add_argument("--timeframe", choices=("15m", "1h"), default="15m")
    p.add_argument("--symbol", type=str, default="BTCUSDT")
    p.add_argument("--atr-period", type=int, default=ATR_PERIOD, help="use 1000 for max warmup")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("evidence")
    p.add_argument("--symbol", type=str, default="BTCUSDT")
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("adapter")
    p.add_argument("--symbol", type=str, default="BTCUSDT")
    p.set_defaults(func=cmd_adapter)

    p = sub.add_parser("targets")
    p.add_argument("--repeats", type=int, default=10)
    p.set_defaults(func=cmd_targets)

    p = sub.add_parser("all")
    p.add_argument("--skip-sync", action="store_true")
    p.add_argument(
        "--since",
        type=str,
        default=(datetime.now(UTC) - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d"),
    )
    p.add_argument("--step-timeout-s", type=float, default=1800.0)
    p.set_defaults(func=cmd_all)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
