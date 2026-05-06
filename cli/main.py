"""Kronos CLI — data and research workflow commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from kronos.common.config import load_config
from kronos.common.i18n import init_i18n, t
from kronos.common.log import setup_logging

if TYPE_CHECKING:
    from kronos.factor.candidates import CandidateFactorSpec

_LANG_OPTION = typer.Option(
    None,
    "--lang",
    help="Display language: zh (简体中文) or en (English).",
)

app = typer.Typer(
    name="kronos",
    help="Kronos — crypto-native quantitative research system",
    context_settings={"help_option_names": ["-h", "--help"]},
)
data_app = typer.Typer(name="data", help="Data management commands")
research_app = typer.Typer(name="research", help="Research workflow commands")
run_app = typer.Typer(name="run", help="System-level Kronos run commands")
agent_app = typer.Typer(name="agent", help="Kronos Agent MVP commands")
report_app = typer.Typer(name="report", help="Report reading commands")
strategy_app = typer.Typer(name="strategy", help="User strategy configuration commands")
app.add_typer(data_app)
app.add_typer(research_app)
app.add_typer(run_app)
app.add_typer(agent_app)
app.add_typer(report_app)
app.add_typer(strategy_app)


@app.callback(invoke_without_command=True)
def _global(
    ctx: typer.Context,
    lang: str | None = _LANG_OPTION,
) -> None:
    """Resolve language and config before any subcommand runs."""
    init_i18n(cli_lang=lang)
    if ctx.invoked_subcommand is None:
        raise typer.Exit()


def _parse_since(since: str | None) -> int | None:
    """Convert a date string to epoch-ms."""
    if since is None:
        return None
    dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_periods(value: str) -> list[int]:
    periods = [int(item) for item in _split_csv(value)]
    if not periods:
        raise typer.BadParameter("periods must contain at least one integer")
    return periods


def _in_docker() -> bool:
    return Path("/.dockerenv").exists()


def _docker_run_prefix() -> str:
    return "docker compose run --rm kronos uv run"


def _strategy_path_hint(path: str) -> str | None:
    expanded = Path(path).expanduser()
    if expanded.exists():
        return None
    raw = str(expanded)
    if _in_docker() and raw.startswith(("/Users/", "/home/", "/private/")):
        return (
            "Docker path hint: this looks like a host path. "
            "Use the container path printed by `kronos strategy init-r-breaker`, "
            "usually /root/.kronos/strategies/r_breaker.toml."
        )
    return None


def _resolve_candidate_specs(candidates: str | None) -> tuple[list[CandidateFactorSpec], set[str]]:
    from kronos.factor.candidates import list_candidate_factors

    candidate_filter = set(_split_csv(candidates))
    candidate_specs = list_candidate_factors()
    if candidate_filter:
        candidate_specs = [
            spec for spec in candidate_specs
            if spec.candidate_id in candidate_filter or spec.implementation_name in candidate_filter
        ]
    return candidate_specs, candidate_filter


@data_app.command("sync")
def data_sync(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Comma-separated symbol list",
    ),
    since: str | None = typer.Option(
        None,
        help="Start date (YYYY-MM-DD). If omitted, auto-detects for incremental sync.",
    ),
    config: str = typer.Option(
        "configs/dev.toml",
        help="Path to config file",
    ),
) -> None:
    """Sync market data from Binance USDM."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.data.loaders.exchange_info import (
        fetch_exchange_info,
        save_exchange_info,
        validate_symbol,
    )
    from kronos.data.sync import sync_all

    base_path = Path(cfg.data.base_path)
    symbol_list = [s.strip() for s in symbols.split(",")]
    since_ms = _parse_since(since)

    _echo_data_sync_guidance(base_path=base_path, symbols=symbol_list, since=since)

    # Fetch exchange info first
    typer.echo("Fetching exchange info...")
    try:
        exchange_symbols = fetch_exchange_info()
        save_exchange_info(exchange_symbols, base_path)
        typer.echo(f"  {len(exchange_symbols)} perpetual contracts found")
    except Exception as e:
        typer.echo(f"Cannot connect to Binance API. Check network connection. ({e})", err=True)
        raise typer.Exit(code=1) from e

    # Validate symbols
    valid_symbols: list[str] = []
    for sym in symbol_list:
        if validate_symbol(sym, base_path):
            valid_symbols.append(sym)
        else:
            typer.echo(f"Symbol {sym} not found on Binance USDM", err=True)

    if not valid_symbols:
        typer.echo("No valid symbols to sync.", err=True)
        raise typer.Exit(code=1)

    # Sync data
    typer.echo(f"\nSyncing {len(valid_symbols)} symbols: {', '.join(valid_symbols)}")
    results = sync_all(
        valid_symbols,
        base_path=base_path,
        since=since_ms,
        max_retries=cfg.data.max_retries,
        request_interval_ms=cfg.data.request_interval_ms,
    )

    # Summary
    typer.echo("\n--- Sync Summary ---")
    for sym, counts in results.items():
        typer.echo(f"  {sym}: klines={counts['klines']}, funding={counts['funding']}, oi={counts['oi']}")
    typer.echo("Done.")


@report_app.command("latest")
def report_latest(
    reports_path: str = typer.Option(
        "reports/research",
        help="Base path for research reports.",
    ),
    max_lines: int = typer.Option(
        18,
        min=1,
        max=80,
        help="Maximum summary lines to print.",
    ),
) -> None:
    """Print the latest product-facing Kronos report summary."""
    from kronos.reporting import find_latest_report, summarize_report

    latest = find_latest_report(reports_path)
    if latest is None:
        typer.echo(f"No reports found under {Path(reports_path) / 'experiments'}.", err=True)
        typer.echo("Run `kronos quickstart` or `kronos run today` first.", err=True)
        raise typer.Exit(code=1)

    typer.echo("--- Latest Kronos Report ---")
    typer.echo(f"report: {latest.path}")
    typer.echo(f"run_dir: {latest.run_dir}")
    typer.echo()
    for line in summarize_report(latest.path, max_lines=max_lines):
        typer.echo(line)


@data_app.command("status")
def data_status(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Comma-separated symbol list",
    ),
    config: str = typer.Option(
        "configs/dev.toml",
        help="Path to config file",
    ),
) -> None:
    """Show data coverage and status."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.data.storage.query import coverage

    base_path = Path(cfg.data.base_path)
    symbol_list = [s.strip() for s in symbols.split(",")]

    typer.echo("Data Coverage:")
    typer.echo(f"{'Symbol':<12} {'Dataset':<12} {'From':<22} {'To':<22} {'Bars':>10}")
    typer.echo("-" * 80)

    for sym in symbol_list:
        infos = coverage(sym, base_path=base_path)
        if not infos:
            typer.echo(f"{sym:<12} {'—':<12} {'no data':<22} {'—':<22} {'—':>10}")
            continue
        for info in infos:
            from_dt = datetime.fromtimestamp(info.min_event_time / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
            to_dt = datetime.fromtimestamp(info.max_event_time / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
            typer.echo(f"{info.symbol:<12} {info.dataset:<12} {from_dt:<22} {to_dt:<22} {info.bar_count:>10}")
            if info.gaps:
                for gap_start, gap_end in info.gaps:
                    g_start = datetime.fromtimestamp(gap_start / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
                    g_end = datetime.fromtimestamp(gap_end / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
                    typer.echo(f"{'':>12} {'GAP':<12} {g_start:<22} {g_end:<22}")


@research_app.command("promote-candidates")
def research_promote_candidates(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Comma-separated symbol list to load from curated data.",
    ),
    candidates: str | None = typer.Option(
        None,
        help="Optional comma-separated candidate IDs or implementation factor names.",
    ),
    timeframe: str = typer.Option("1h", help="Market data timeframe to load."),
    since: str | None = typer.Option(None, help="Start time accepted by data loader."),
    until: str | None = typer.Option(None, help="End time accepted by data loader."),
    batch_id: str | None = typer.Option(None, help="Promotion batch id."),
    output_path: str = typer.Option("reports/research", help="Base path for experiment outputs."),
    git_commit: str = typer.Option("working-tree", help="Git commit or working tree label."),
    data_snapshot_id: str = typer.Option("local-curated-data", help="Data snapshot id."),
    periods: str = typer.Option("1,5,20", help="Comma-separated forward periods."),
    train_size: int = typer.Option(120, help="Walk-forward train window size in bars."),
    validation_size: int = typer.Option(40, help="Walk-forward validation window size in bars."),
    test_size: int = typer.Option(40, help="Walk-forward test window size in bars."),
    step_size: int | None = typer.Option(None, help="Walk-forward step size in bars."),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
    preflight_only: bool = typer.Option(
        False,
        "--preflight-only",
        help="Check candidate selection and local data readiness without running promotion.",
    ),
) -> None:
    """Run a local-data candidate factor promotion batch."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.common.errors import DataError
    from kronos.factor.bootstrap import registry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research import PromotionCriteria, run_market_data_promotion_batch

    symbol_list = _split_csv(symbols)
    candidate_specs, candidate_filter = _resolve_candidate_specs(candidates)
    if not candidate_specs:
        typer.echo("No matching candidate factors.", err=True)
        raise typer.Exit(code=1)

    base_path = Path(cfg.data.base_path)
    if preflight_only:
        ready = _echo_promotion_preflight(
            base_path=base_path,
            symbols=symbol_list,
            candidate_count=len(candidate_specs),
            timeframe=timeframe,
        )
        if not ready:
            raise typer.Exit(code=1)
        return

    resolved_batch_id = batch_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-candidate-promotion")
    try:
        batch = run_market_data_promotion_batch(
            registry=registry,
            symbols=symbol_list,
            data_base_path=base_path,
            output_base_path=Path(output_path),
            batch_id=resolved_batch_id,
            git_commit=git_commit,
            data_snapshot_id=data_snapshot_id,
            config_snapshot={
                "command": "research promote-candidates",
                "timeframe": timeframe,
                "symbols": symbol_list,
                "candidates": sorted(candidate_filter),
            },
            candidate_specs=candidate_specs,
            timeframe=timeframe,
            since=since,
            until=until,
            validation_config=ValidationConfig(periods=_parse_periods(periods)),
            criteria=PromotionCriteria(),
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step_size=step_size,
        )
    except DataError as exc:
        typer.echo(f"Cannot run promotion batch: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = batch.summary()
    typer.echo("--- Promotion Batch Summary ---")
    typer.echo(f"batch_id: {batch.batch_id}")
    typer.echo(f"evaluated: {summary['evaluated']}")
    typer.echo(f"promoted: {summary['promoted']}")
    typer.echo(f"not_promoted: {summary['not_promoted']}")
    typer.echo(f"skipped: {summary['skipped']}")
    if batch.artifact_path:
        typer.echo(f"artifact: {batch.artifact_path}")
    report_path = batch.artifact_paths.get("report")
    if report_path:
        typer.echo(f"report: {report_path}")


@research_app.command("workbench")
def research_workbench(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Comma-separated symbol list to load from curated data.",
    ),
    candidates: str | None = typer.Option(
        None,
        help="Optional comma-separated candidate IDs or implementation factor names.",
    ),
    timeframe: str = typer.Option("1m", help="Market data timeframe to load."),
    since: str | None = typer.Option(None, help="Start time accepted by data loader."),
    until: str | None = typer.Option(None, help="End time accepted by data loader."),
    batch_id: str | None = typer.Option(None, help="Research workbench batch id."),
    output_path: str = typer.Option("reports/research", help="Base path for workbench outputs."),
    git_commit: str = typer.Option("working-tree", help="Git commit or working tree label."),
    data_snapshot_id: str = typer.Option("local-curated-data", help="Data snapshot id."),
    periods: str = typer.Option("1,5,20", help="Comma-separated forward periods."),
    train_size: int = typer.Option(720, help="Walk-forward train window size in bars."),
    validation_size: int = typer.Option(360, help="Walk-forward validation window size in bars."),
    test_size: int = typer.Option(360, help="Walk-forward test window size in bars."),
    step_size: int = typer.Option(360, help="Walk-forward step size in bars."),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
    preflight_only: bool = typer.Option(
        False,
        "--preflight-only",
        help="Check candidate selection and local data readiness without running workbench.",
    ),
) -> None:
    """Run the fixed product-facing research workbench flow."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.common.errors import DataError
    from kronos.factor.bootstrap import registry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research import PromotionCriteria, run_research_workbench

    symbol_list = _split_csv(symbols)
    candidate_specs, candidate_filter = _resolve_candidate_specs(candidates)
    if not candidate_specs:
        typer.echo("No matching candidate factors.", err=True)
        raise typer.Exit(code=1)

    base_path = Path(cfg.data.base_path)
    if preflight_only:
        ready = _echo_promotion_preflight(
            base_path=base_path,
            symbols=symbol_list,
            candidate_count=len(candidate_specs),
            timeframe=timeframe,
        )
        if not ready:
            raise typer.Exit(code=1)
        return

    resolved_batch_id = batch_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-workbench")
    try:
        result = run_research_workbench(
            registry=registry,
            symbols=symbol_list,
            data_base_path=base_path,
            output_base_path=Path(output_path),
            batch_id=resolved_batch_id,
            git_commit=git_commit,
            data_snapshot_id=data_snapshot_id,
            config_snapshot={
                "command": "research workbench",
                "timeframe": timeframe,
                "symbols": symbol_list,
                "candidates": sorted(candidate_filter),
            },
            candidate_specs=candidate_specs,
            timeframe=timeframe,
            since=since,
            until=until,
            validation_config=ValidationConfig(periods=_parse_periods(periods)),
            criteria=PromotionCriteria(),
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step_size=step_size,
        )
    except DataError as exc:
        typer.echo(f"Cannot run research workbench: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    typer.echo("--- Research Workbench Summary ---")
    typer.echo(f"batch_id: {result.batch.batch_id}")
    typer.echo(f"readiness: {summary['readiness']}")
    typer.echo(f"evaluated: {summary['evaluated']}")
    typer.echo(f"promoted: {summary['promoted']}")
    typer.echo(f"not_promoted: {summary['not_promoted']}")
    typer.echo(f"skipped: {summary['skipped']}")
    typer.echo(f"pm_report: {result.artifact_paths['pm_report']}")
    typer.echo(f"failure_groups: {result.artifact_paths['failure_groups']}")
    typer.echo(f"candidate_dispositions: {result.artifact_paths['candidate_dispositions']}")
    typer.echo(f"watchlist_reviews: {result.artifact_paths['watchlist_reviews']}")


@research_app.command("auto-run")
def research_auto_run(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Comma-separated symbol list to load from curated data.",
    ),
    candidates: str | None = typer.Option(
        None,
        help="Optional comma-separated candidate IDs or implementation factor names.",
    ),
    watchlist_candidates: str | None = typer.Option(
        "range_chop_filter,body_energy",
        help="Optional comma-separated watchlist candidates for focused evidence.",
    ),
    timeframe: str = typer.Option("1m", help="Market data timeframe to load."),
    since: str | None = typer.Option(None, help="Start time accepted by data loader."),
    until: str | None = typer.Option(None, help="End time accepted by data loader."),
    run_id: str | None = typer.Option(None, help="Auto-run id."),
    output_path: str = typer.Option("reports/research", help="Base path for auto-run outputs."),
    git_commit: str = typer.Option("working-tree", help="Git commit or working tree label."),
    data_snapshot_id: str = typer.Option("local-curated-data", help="Data snapshot id."),
    periods: str = typer.Option("1,5,20", help="Comma-separated forward periods."),
    train_size: int = typer.Option(720, help="Walk-forward train window size in bars."),
    validation_size: int = typer.Option(360, help="Walk-forward validation window size in bars."),
    test_size: int = typer.Option(360, help="Walk-forward test window size in bars."),
    step_size: int = typer.Option(360, help="Walk-forward step size in bars."),
    min_history_days: int = typer.Option(
        90,
        help="Minimum history span required before a watchlist candidate can be upgraded.",
    ),
    sync_data: bool = typer.Option(
        False,
        "--sync-data/--skip-sync-data",
        help="Refresh market data before running research. Defaults to local-only.",
    ),
    sync_since: str | None = typer.Option(
        None,
        help="Start date (YYYY-MM-DD) for optional data sync.",
    ),
    run_watchlist_evidence: bool = typer.Option(
        True,
        "--watchlist-evidence/--skip-watchlist-evidence",
        help="Run focused evidence for configured watchlist candidates.",
    ),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Run one automatic research cycle and write a PM-readable daily report."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.common.errors import DataError
    from kronos.factor.bootstrap import registry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research import PromotionCriteria, run_auto_research_cycle

    symbol_list = _split_csv(symbols)
    candidate_specs, candidate_filter = _resolve_candidate_specs(candidates)
    if not candidate_specs:
        typer.echo("No matching candidate factors.", err=True)
        raise typer.Exit(code=1)

    watchlist_specs: list[CandidateFactorSpec] = []
    if run_watchlist_evidence:
        watchlist_specs, watchlist_filter = _resolve_candidate_specs(watchlist_candidates)
        if not watchlist_specs:
            typer.echo("No matching watchlist candidate factors.", err=True)
            raise typer.Exit(code=1)
    else:
        watchlist_filter = set[str]()

    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-auto-run")
    try:
        result = run_auto_research_cycle(
            registry=registry,
            symbols=symbol_list,
            data_base_path=Path(cfg.data.base_path),
            output_base_path=Path(output_path),
            run_id=resolved_run_id,
                git_commit=git_commit,
                data_snapshot_id=data_snapshot_id,
                config_snapshot={
                    "command": "research auto-run",
                    "timeframe": timeframe,
                    "symbols": symbol_list,
                    "candidates": sorted(candidate_filter),
                    "watchlist_candidates": sorted(watchlist_filter),
                    "data_snapshot_id": data_snapshot_id,
                    "data_kind": "synced" if sync_data else "local",
                },
            candidate_specs=candidate_specs,
            watchlist_candidate_specs=watchlist_specs,
            timeframe=timeframe,
            since=since,
            until=until,
            validation_config=ValidationConfig(periods=_parse_periods(periods)),
            criteria=PromotionCriteria(),
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step_size=step_size,
            sync_data=sync_data,
            sync_since=_parse_since(sync_since),
            max_retries=cfg.data.max_retries,
            request_interval_ms=cfg.data.request_interval_ms,
            min_history_days=min_history_days,
        )
    except DataError as exc:
        typer.echo(f"Cannot run auto research cycle: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    typer.echo("--- Auto Runner Summary ---")
    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"sync_data: {'yes' if result.sync_requested else 'no'}")
    typer.echo(f"readiness: {summary['readiness']}")
    typer.echo(f"evaluated: {summary['evaluated']}")
    typer.echo(f"promoted: {summary['promoted']}")
    typer.echo(f"not_promoted: {summary['not_promoted']}")
    typer.echo(f"skipped: {summary['skipped']}")
    typer.echo(f"watchlist_evidence: {summary['evidence_reviews']}")
    typer.echo(f"evidence_blockers: {summary['evidence_blockers']}")
    typer.echo(f"daily_report: {result.artifact_paths['auto_run_report']}")
    typer.echo(f"auto_run_summary: {result.artifact_paths['auto_run_summary']}")


@run_app.command("today")
def run_today(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Default comma-separated symbol list for today's Kronos run.",
    ),
    candidates: str | None = typer.Option(
        None,
        help="Optional comma-separated candidate IDs or implementation factor names.",
    ),
    watchlist_candidates: str | None = typer.Option(
        "range_chop_filter,body_energy",
        help="Optional comma-separated watchlist candidates for focused evidence.",
    ),
    timeframe: str = typer.Option("1m", help="Market data timeframe to load."),
    since: str | None = typer.Option(None, help="Start time accepted by data loader."),
    until: str | None = typer.Option(None, help="End time accepted by data loader."),
    run_id: str | None = typer.Option(None, help="Top-level Kronos run id."),
    output_path: str = typer.Option("reports/research", help="Base path for run outputs."),
    git_commit: str = typer.Option("working-tree", help="Git commit or working tree label."),
    data_snapshot_id: str = typer.Option("local-curated-data", help="Data snapshot id."),
    periods: str = typer.Option("1,5,20", help="Comma-separated forward periods."),
    train_size: int = typer.Option(720, help="Walk-forward train window size in bars."),
    validation_size: int = typer.Option(360, help="Walk-forward validation window size in bars."),
    test_size: int = typer.Option(360, help="Walk-forward test window size in bars."),
    step_size: int = typer.Option(360, help="Walk-forward step size in bars."),
    min_history_days: int = typer.Option(
        90,
        help="Minimum local history span required before the default run proceeds.",
    ),
    max_data_age_hours: int = typer.Option(
        72,
        help="Warn when local data is older than this many hours. Use 0 to disable.",
    ),
    require_fresh_data: bool = typer.Option(
        False,
        "--require-fresh-data/--allow-stale-data",
        help="Fail the run when local data is stale instead of only warning.",
    ),
    sync_data: bool = typer.Option(
        False,
        "--sync-data/--skip-sync-data",
        help="Refresh market data before running research. Defaults to local-only.",
    ),
    sync_since: str | None = typer.Option(
        None,
        help="Start date (YYYY-MM-DD) for optional data sync.",
    ),
    run_watchlist_evidence: bool = typer.Option(
        True,
        "--watchlist-evidence/--skip-watchlist-evidence",
        help="Run focused evidence for configured watchlist candidates.",
    ),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Run today's default Kronos MVP flow and write a system status report."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.factor.bootstrap import registry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research import PromotionCriteria
    from kronos.run_mvp import run_kronos_today

    symbol_list = _split_csv(symbols)
    candidate_specs, candidate_filter = _resolve_candidate_specs(candidates)
    if not candidate_specs:
        typer.echo("No matching candidate factors.", err=True)
        raise typer.Exit(code=1)

    watchlist_specs: list[CandidateFactorSpec] = []
    if run_watchlist_evidence:
        watchlist_specs, watchlist_filter = _resolve_candidate_specs(watchlist_candidates)
        if not watchlist_specs:
            typer.echo("No matching watchlist candidate factors.", err=True)
            raise typer.Exit(code=1)
    else:
        watchlist_filter = set[str]()

    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-kronos-run")
    result = run_kronos_today(
        registry=registry,
        symbols=symbol_list,
        data_base_path=Path(cfg.data.base_path),
        output_base_path=Path(output_path),
        run_id=resolved_run_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot={
            "command": "kronos run today",
            "timeframe": timeframe,
            "symbols": symbol_list,
            "candidates": sorted(candidate_filter),
            "watchlist_candidates": sorted(watchlist_filter),
        },
        candidate_specs=candidate_specs,
        watchlist_candidate_specs=watchlist_specs,
        timeframe=timeframe,
        since=since,
        until=until,
        validation_config=ValidationConfig(periods=_parse_periods(periods)),
        criteria=PromotionCriteria(),
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=step_size,
        sync_data=sync_data,
        sync_since=_parse_since(sync_since),
        max_retries=cfg.data.max_retries,
        request_interval_ms=cfg.data.request_interval_ms,
        min_history_days=min_history_days,
        max_data_age_hours=max_data_age_hours,
        require_fresh_data=require_fresh_data,
    )

    summary = result.summary()
    typer.echo("--- Kronos Run Summary ---")
    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"status: {summary['status']}")
    typer.echo(f"blockers: {summary['blockers']}")
    typer.echo(f"warnings: {summary['warnings']}")
    typer.echo(f"evaluated: {summary['evaluated']}")
    typer.echo(f"promoted: {summary['promoted']}")
    typer.echo(f"skipped: {summary['skipped']}")
    if result.failure_reason is not None:
        typer.echo(f"failure_reason: {result.failure_reason}")
    typer.echo(f"status_report: {result.artifact_paths['run_status_report']}")
    typer.echo(f"status_json: {result.artifact_paths['run_status_json']}")
    if "auto_run_report" in result.artifact_paths:
        typer.echo(f"auto_run_report: {result.artifact_paths['auto_run_report']}")
    if result.status != "success":
        raise typer.Exit(code=1)


@agent_app.command("propose")
def agent_propose(
    summary_json: str = typer.Option(
        ...,
        "--summary-json",
        help="Path to the latest deterministic research summary JSON.",
    ),
    goal: str = typer.Option(
        "把旧 A 股 / 期货策略资产重新适配到 crypto 市场并找出下一轮最值得验证的方向",
        help="Research goal for the Agent MVP planning cycle.",
    ),
    run_id: str | None = typer.Option(None, help="Agent planning run id."),
    output_path: str = typer.Option("reports/research", help="Base path for agent outputs."),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Generate the next RD-Agent-style hypotheses and experiments."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.research import run_research_agent_planner

    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-agent-plan")
    try:
        result = run_research_agent_planner(
            summary_json_path=summary_json,
            output_base_path=Path(output_path),
            run_id=resolved_run_id,
            goal_zh=goal,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(f"Cannot generate agent research plan: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    typer.echo("--- Kronos Agent Plan ---")
    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"source_run_id: {summary['source_run_id'] or '-'}")
    typer.echo(f"selected_candidates: {summary['selected_candidates']}")
    typer.echo(f"retirement_review_candidates: {summary['retirement_review_candidates']}")
    typer.echo(f"hypotheses: {summary['hypotheses']}")
    typer.echo(f"next_action: {summary['next_action_zh']}")
    typer.echo(f"agent_plan_report: {result.artifact_paths['agent_plan_report']}")
    typer.echo(f"agent_plan_json: {result.artifact_paths['agent_plan_json']}")


@agent_app.command("status")
def agent_status(
    runtime_path: str = typer.Option(
        "reports/agent_runtime",
        help="Path to the local Agent runtime status directory.",
    ),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Show the current local Agent runtime status."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.agent.supervisor import AgentSupervisor

    status = AgentSupervisor(Path(runtime_path)).get_status()

    typer.echo("--- Kronos Agent Status ---")
    typer.echo(f"active: {'yes' if status.active else 'no'}")
    typer.echo(f"pending_count: {status.pending_count}")
    if status.current_run is None:
        typer.echo("message: 当前没有正在运行的 Agent 任务。")
        return

    typer.echo(f"current_run: {status.current_run.run_id}")
    typer.echo(f"run_status: {status.current_run.status.value}")
    if status.current_task is not None:
        typer.echo(f"current_task: {status.current_task.task_id}")
        typer.echo(f"task_status: {status.current_task.status.value}")
        typer.echo(f"task_title: {status.current_task.title_zh}")
    else:
        typer.echo("current_task: -")
        typer.echo("task_status: -")
    if status.last_event is not None:
        typer.echo(f"last_event: {status.last_event.message_zh}")
        typer.echo(f"last_event_type: {status.last_event.event_type.value}")
    else:
        typer.echo("last_event: -")
        typer.echo("last_event_type: -")


@agent_app.command("run-once")
def agent_run_once(
    summary_json: str = typer.Option(
        ...,
        "--summary-json",
        help="Path to the latest deterministic research summary JSON.",
    ),
    evidence_json: str = typer.Option(
        ...,
        "--evidence-json",
        help="Comma-separated deterministic evidence review JSON paths.",
    ),
    goal: str = typer.Option(
        "把旧 A 股 / 期货策略资产重新适配到 crypto 市场并找出下一轮最值得验证的方向",
        help="Research goal for this bounded Agent cycle.",
    ),
    run_id: str | None = typer.Option(None, help="Agent cycle run id."),
    output_path: str = typer.Option("reports/research", help="Base path for agent outputs."),
    runtime_path: str = typer.Option(
        "reports/agent_runtime",
        help="Path to publish the latest Web-readable Agent status snapshot.",
    ),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Run one bounded Agent cycle: plan, execute approved tools, and conclude."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.agent.planner import run_agent_once
    from kronos.agent.types import AgentRunStatus

    resolved_evidence_json = _split_csv(evidence_json)
    if not resolved_evidence_json:
        typer.echo("At least one --evidence-json path is required.", err=True)
        raise typer.Exit(code=1)

    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-agent-cycle")
    try:
        result = run_agent_once(
            summary_json_path=Path(summary_json),
            evidence_json_paths=[Path(path) for path in resolved_evidence_json],
            output_base_path=Path(output_path),
            run_id=resolved_run_id,
            goal_zh=goal,
            runtime_path=Path(runtime_path),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(f"Cannot run agent cycle: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    typer.echo("--- Kronos Agent Run Once ---")
    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"status: {summary['status']}")
    typer.echo(f"tools: {summary['tools']}")
    typer.echo(f"failed_tools: {summary['failed_tools']}")
    typer.echo(f"next_action: {summary['next_action_zh']}")
    typer.echo(f"agent_run_report: {result.artifact_paths['agent_run_report']}")
    typer.echo(f"agent_run_summary: {result.artifact_paths['agent_run_summary']}")
    typer.echo(f"agent_events: {result.artifact_paths['agent_events']}")
    if "agent_errors" in result.artifact_paths:
        typer.echo(f"agent_errors: {result.artifact_paths['agent_errors']}")
    if result.status != AgentRunStatus.COMPLETED:
        raise typer.Exit(code=1)


@agent_app.command("conclude")
def agent_conclude(
    evidence_json: str = typer.Option(
        "",
        "--evidence-json",
        help="Comma-separated deterministic evidence review JSON paths.",
    ),
    run_id: str | None = typer.Option(None, help="Agent decision run id."),
    output_path: str = typer.Option("reports/research", help="Base path for agent outputs."),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Read deterministic evidence and produce Agent next-step decisions."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.research import run_research_agent_decision

    resolved_evidence_json = _split_csv(evidence_json)
    if not resolved_evidence_json:
        typer.echo("At least one --evidence-json path is required.", err=True)
        raise typer.Exit(code=1)

    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-agent-decision")
    try:
        result = run_research_agent_decision(
            evidence_json_paths=[Path(path) for path in resolved_evidence_json],
            output_base_path=Path(output_path),
            run_id=resolved_run_id,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(f"Cannot generate agent research decision: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    typer.echo("--- Kronos Agent Decision ---")
    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"evidence_reviews: {summary['evidence_reviews']}")
    typer.echo(f"decisions: {summary['decisions']}")
    typer.echo(f"next_action: {summary['next_action_zh']}")
    typer.echo(f"agent_decision_report: {result.artifact_paths['agent_decision_report']}")
    typer.echo(f"agent_decision_json: {result.artifact_paths['agent_decision_json']}")


@research_app.command("watchlist-evidence")
def research_watchlist_evidence(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT",
        help="Comma-separated symbol list to load from curated data.",
    ),
    candidate: str = typer.Option(
        "range_chop_filter",
        help="Candidate ID or implementation factor name to review.",
    ),
    timeframe: str = typer.Option("1m", help="Market data timeframe to load."),
    since: str | None = typer.Option(None, help="Start time accepted by data loader."),
    until: str | None = typer.Option(None, help="End time accepted by data loader."),
    batch_id: str | None = typer.Option(None, help="Watchlist evidence batch id."),
    output_path: str = typer.Option("reports/research", help="Base path for evidence outputs."),
    data_snapshot_id: str = typer.Option("local-curated-data", help="Data snapshot id."),
    periods: str = typer.Option("1,5,20", help="Comma-separated forward periods."),
    min_history_days: int = typer.Option(
        90,
        help="Minimum history span required before a watchlist candidate can be upgraded.",
    ),
    config: str = typer.Option("configs/dev.toml", help="Path to config file."),
) -> None:
    """Run a focused evidence review for one watchlist candidate."""
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.common.errors import DataError
    from kronos.factor.bootstrap import registry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research import run_watchlist_evidence_review

    symbol_list = _split_csv(symbols)
    candidate_specs, _ = _resolve_candidate_specs(candidate)
    if not candidate_specs:
        typer.echo("No matching candidate factor.", err=True)
        raise typer.Exit(code=1)
    if len(candidate_specs) > 1:
        typer.echo("Watchlist evidence requires exactly one candidate.", err=True)
        raise typer.Exit(code=1)

    resolved_batch_id = batch_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-watchlist-evidence")
    try:
        result = run_watchlist_evidence_review(
            registry=registry,
            symbols=symbol_list,
            data_base_path=Path(cfg.data.base_path),
            output_base_path=Path(output_path),
            batch_id=resolved_batch_id,
            candidate_spec=candidate_specs[0],
            data_snapshot_id=data_snapshot_id,
            config_snapshot={
                "command": "research watchlist-evidence",
                "symbols": symbol_list,
                "candidate": candidate,
            },
            timeframe=timeframe,
            since=since,
            until=until,
            validation_config=ValidationConfig(periods=_parse_periods(periods)),
            min_history_days=min_history_days,
        )
    except DataError as exc:
        typer.echo(f"Cannot run watchlist evidence review: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    typer.echo("--- Watchlist Evidence Summary ---")
    typer.echo(f"batch_id: {result.batch_id}")
    typer.echo(f"candidate: {result.candidate_id}")
    typer.echo(f"factor: {result.factor_name}")
    typer.echo(f"history_status: {summary['history_status']}")
    typer.echo(f"supportive_slices: {summary['supportive_slices']}")
    typer.echo(f"weak_positive_slices: {summary['weak_positive_slices']}")
    typer.echo(f"evidence_report: {result.artifact_paths['evidence_report']}")
    typer.echo(f"evidence_json: {result.artifact_paths['evidence_json']}")


def _print_benchmark(symbol: str, base_path: Path, _result: object | None = None) -> None:
    """Print benchmark comparison: strategy vs buy-and-hold."""
    from kronos.data.storage.query import load

    try:
        df = load(symbol, base_path=base_path, timeframe="1m")
        if df.empty:
            typer.echo(f"  📊 {t('quickstart.benchmark')}: {t('quickstart.no_benchmark_data')}")
            return

        # Skip benchmark for synthetic data — random walks are meaningless
        venue = str(df.iloc[0].get("venue", "")) if "venue" in df.columns else ""
        if venue == "synthetic":
            typer.echo(f"  📊 {t('quickstart.benchmark')}: {t('quickstart.benchmark_synthetic')}")
            return

        prices = df.sort_values("event_time")["close"]
        buyhold_ret = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
        n_days = (df["event_time"].max() - df["event_time"].min()) / (1000 * 86400)

        typer.echo(f"  📊 {t('quickstart.benchmark')}:")
        typer.echo(f"     {t('quickstart.benchmark_period')}: {n_days:.0f} {t('quickstart.days')}")
        typer.echo(f"     {t('quickstart.benchmark_buyhold')}: {buyhold_ret:+.1f}%")
        typer.echo(f"     {t('quickstart.benchmark_note')}")
    except Exception:
        typer.echo(f"  📊 {t('quickstart.benchmark')}: {t('quickstart.no_benchmark_data')}")


def _echo_promotion_preflight(
    *,
    base_path: Path,
    symbols: list[str],
    candidate_count: int,
    timeframe: str,
) -> bool:
    from kronos.data.storage.query import coverage

    typer.echo("--- Promotion Preflight ---")
    typer.echo(f"data_path: {base_path}")
    typer.echo(f"timeframe: {timeframe}")
    typer.echo(f"candidates: {candidate_count}")

    ready = candidate_count > 0 and bool(symbols)
    if not symbols:
        typer.echo("symbols: none", err=True)
        ready = False

    for symbol in symbols:
        infos = coverage(symbol, base_path=base_path, datasets=["klines_1m"])
        if not infos:
            typer.echo(f"{symbol}: no klines_1m data")
            ready = False
            continue

        info = infos[0]
        from_dt = datetime.fromtimestamp(info.min_event_time / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
        to_dt = datetime.fromtimestamp(info.max_event_time / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
        gap_text = f", gaps={len(info.gaps)}" if info.gaps else ""
        typer.echo(f"{symbol}: {info.bar_count} bars, {from_dt} -> {to_dt}{gap_text}")

    typer.echo(f"ready: {'yes' if ready else 'no'}")
    return ready


def _echo_data_sync_guidance(
    *,
    base_path: Path,
    symbols: list[str],
    since: str | None,
) -> None:
    typer.echo("--- Data Sync Guide ---")
    typer.echo("source: Binance USDM public market data")
    typer.echo("datasets: 1m klines, funding rates, open interest")
    typer.echo("api_key_required: no")
    typer.echo(f"symbols: {', '.join(symbols) if symbols else '-'}")
    typer.echo(f"data_path: {base_path}")
    if since is None:
        typer.echo(
            "time_range: incremental if local data exists; otherwise Binance earliest available "
            "history for the selected symbols"
        )
        typer.echo("tip: for a bounded first sync, add `--since 2026-01-01` or another start date")
    else:
        typer.echo(f"time_range: from {since} UTC to latest closed records")
    typer.echo("trading_enabled: no; this command only downloads research data")
    typer.echo()


@strategy_app.command("init-r-breaker")
def strategy_init_r_breaker(
    strategy_id: str = typer.Option(
        "r_breaker",
        "--id",
        help="Stable strategy id. Used as the TOML filename and candidate id.",
    ),
    name: str = typer.Option(
        "R-breaker 日内突破",
        help="Human-facing strategy name.",
    ),
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT",
        help="Comma-separated symbol list.",
    ),
    timeframe: str = typer.Option(
        "15m",
        help="Research timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d.",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Directory for strategy TOML. Defaults to ~/.kronos/strategies.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite an existing TOML file.",
    ),
) -> None:
    """Create a validated R-breaker strategy TOML file."""
    from pydantic import ValidationError

    from kronos.common.errors import ConfigError
    from kronos.strategy.config import default_r_breaker_config, write_strategy_config

    try:
        strategy_config = default_r_breaker_config(
            strategy_id=strategy_id,
            name=name,
            symbols=_split_csv(symbols),
            timeframe=timeframe,
        )
        path = write_strategy_config(
            strategy_config,
            directory=output_dir,
            overwrite=overwrite,
        )
    except (ConfigError, ValidationError) as exc:
        typer.echo(f"Cannot create strategy config: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("--- Strategy Config Created ---")
    typer.echo(f"path: {path}")
    typer.echo(f"strategy: {strategy_config.strategy.name} ({strategy_config.strategy.id})")
    typer.echo(f"symbols: {', '.join(strategy_config.universe.symbols)}")
    typer.echo(f"timeframe: {strategy_config.universe.timeframe}")
    typer.echo(
        "note: quickstart uses 1m sample data for installation smoke testing; "
        f"this TOML is your editable {strategy_config.universe.timeframe} strategy config."
    )
    if _in_docker():
        typer.echo(f"next: {_docker_run_prefix()} kronos strategy smoke-test {path}")
        typer.echo(f"then: {_docker_run_prefix()} kronos strategy register {path}")
    else:
        typer.echo("next: kronos strategy smoke-test " + str(path))
        typer.echo("then: kronos strategy register " + str(path))


@strategy_app.command("validate")
def strategy_validate(
    path: str = typer.Argument(..., help="Path to a strategy TOML file."),
) -> None:
    """Validate a strategy TOML file without registering it."""
    from pydantic import ValidationError

    from kronos.common.errors import ConfigError
    from kronos.strategy.config import load_strategy_config

    try:
        strategy_config = load_strategy_config(path)
    except (ConfigError, ValidationError) as exc:
        typer.echo(f"Strategy config invalid: {exc}", err=True)
        hint = _strategy_path_hint(path)
        if hint:
            typer.echo(hint, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("--- Strategy Config Valid ---")
    typer.echo(f"strategy: {strategy_config.strategy.name} ({strategy_config.strategy.id})")
    typer.echo(f"kind: {strategy_config.strategy.kind}")
    typer.echo(f"symbols: {', '.join(strategy_config.universe.symbols)}")
    typer.echo(f"timeframe: {strategy_config.universe.timeframe}")
    typer.echo("trading_enabled: no")


@strategy_app.command("smoke-test")
def strategy_smoke_test(
    path: str = typer.Argument(..., help="Path to a strategy TOML file."),
    config: str = typer.Option("configs/dev.toml", help="Path to Kronos config file."),
) -> None:
    """Run a local data smoke test for a strategy TOML file."""
    from pydantic import ValidationError

    from kronos.common.errors import ConfigError
    from kronos.strategy.config import load_strategy_config
    from kronos.strategy.smoke import run_strategy_smoke_test

    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    try:
        strategy_config = load_strategy_config(path)
    except (ConfigError, ValidationError) as exc:
        typer.echo(f"Strategy config invalid: {exc}", err=True)
        hint = _strategy_path_hint(path)
        if hint:
            typer.echo(hint, err=True)
        raise typer.Exit(code=1) from exc

    result = run_strategy_smoke_test(strategy_config, data_base_path=cfg.data.base_path)
    typer.echo("--- Strategy Smoke Test ---")
    for line in result.summary_lines():
        typer.echo(line)
    if not result.passed:
        raise typer.Exit(code=1)


@strategy_app.command("register")
def strategy_register(
    path: str = typer.Argument(..., help="Path to a strategy TOML file."),
    config: str = typer.Option("configs/dev.toml", help="Path to Kronos config file."),
    skip_smoke: bool = typer.Option(
        False,
        "--skip-smoke",
        help="Register without local data smoke test. Use only when data is unavailable.",
    ),
    migration_rank: int = typer.Option(
        50,
        min=1,
        max=999,
        help="Candidate ordering rank in Agent/Web surfaces.",
    ),
) -> None:
    """Register a validated strategy TOML into the shared candidate pool."""
    from pydantic import ValidationError

    from kronos.common.errors import ConfigError
    from kronos.strategy.config import load_strategy_config, register_strategy_config
    from kronos.strategy.smoke import run_strategy_smoke_test

    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    try:
        strategy_config = load_strategy_config(path)
    except (ConfigError, ValidationError) as exc:
        typer.echo(f"Strategy config invalid: {exc}", err=True)
        hint = _strategy_path_hint(path)
        if hint:
            typer.echo(hint, err=True)
        raise typer.Exit(code=1) from exc

    if not skip_smoke:
        smoke = run_strategy_smoke_test(strategy_config, data_base_path=cfg.data.base_path)
        if not smoke.passed:
            typer.echo("--- Strategy Smoke Test ---")
            for line in smoke.summary_lines():
                typer.echo(line)
            typer.echo("registration: blocked", err=True)
            raise typer.Exit(code=1)

    spec = register_strategy_config(strategy_config, migration_rank=migration_rank)
    typer.echo("--- Strategy Registered ---")
    typer.echo(f"candidate_id: {spec.candidate_id}")
    typer.echo(f"title: {spec.title}")
    typer.echo(f"symbols: {', '.join(spec.source_strategies)}")
    typer.echo(f"origin: {spec.origin}")
    typer.echo("visible_to_agent: yes")
    typer.echo(f"next: kronos agent start will see {spec.title}")


@agent_app.command("start")
def agent_start(
    lang: str | None = _LANG_OPTION,
    config: str = typer.Option(
        "configs/dev.toml",
        help="Path to config file.",
    ),
) -> None:
    """Launch the interactive Agent console."""
    init_i18n(cli_lang=lang)
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    from kronos.agent.console import start_agent_console

    start_agent_console(config_path=config)


@app.command("quickstart")
def quickstart(
    lang: str | None = _LANG_OPTION,
    config: str = typer.Option(
        "configs/dev.toml",
        help="Path to config file.",
    ),
    skip_data_gen: bool = typer.Option(
        False,
        "--skip-data-gen",
        help="Skip sample data generation.",
    ),
    symbols: str = typer.Option(
        "BTCUSDT",
        help="Symbol for sample data generation.",
    ),
    days: int = typer.Option(
        7,
        help="Days of sample data to generate.",
        min=1,
        max=30,
    ),
) -> None:
    """One-command bootstrap: generate sample data and run a minimal research cycle."""
    init_i18n(cli_lang=lang)
    cfg = load_config(config)
    setup_logging(level=cfg.runtime.log_level, json_output=cfg.runtime.log_json)

    base_path = Path(cfg.data.base_path)

    typer.echo(f"⚡ {t('quickstart.title')}")
    typer.echo()

    # Step 1: ensure data exists
    typer.echo(f"… {t('quickstart.checking_data')}")
    from kronos.data.seed import generate_sample_klines, has_any_data

    if not skip_data_gen and not has_any_data(base_path):
        typer.echo(f"  {t('quickstart.generating_sample')}")
        symbol = symbols.split(",")[0].strip()
        bars = generate_sample_klines(symbol, base_path=base_path, days=days)
        typer.echo(f"  {t('quickstart.sample_ready', path=str(base_path / 'curated' / symbol))}")
        typer.echo(f"  [{bars} bars, {days}d, venue=synthetic]")
    else:
        typer.echo(f"  {t('quickstart.data_found')}")
    typer.echo()

    # Step 2: register builtin strategies
    typer.echo()
    typer.echo(f"… {t('quickstart.registering_strategies')}")
    from kronos.factor.candidates import register_builtin_strategies

    builtins = register_builtin_strategies()
    for spec in builtins:
        typer.echo(f"  ✅ {spec.title} ({spec.candidate_id}) — {spec.family}")
    typer.echo()

    # Step 3: verify data is readable
    from kronos.data.storage.query import coverage

    symbol = symbols.split(",")[0].strip()
    infos = coverage(symbol, base_path=base_path, datasets=["klines_1m"])
    bar_count = infos[0].bar_count if infos else 0
    from_ms = infos[0].min_event_time if infos else 0
    to_ms = infos[0].max_event_time if infos else 0
    from_dt = datetime.fromtimestamp(from_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M") if from_ms else "—"
    to_dt = datetime.fromtimestamp(to_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M") if to_ms else "—"
    typer.echo(f"  {symbol}: {bar_count} bars, {from_dt} → {to_dt}")
    typer.echo()

    # Step 4: run minimal research
    typer.echo(f"… {t('quickstart.running_research')}")
    from kronos.factor.bootstrap import registry
    from kronos.factor.candidates import list_candidate_factors
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research import PromotionCriteria, run_auto_research_cycle

    candidates = list_candidate_factors()
    if candidates:
        try:
            run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-quickstart")
            result = run_auto_research_cycle(
                registry=registry,
                symbols=[symbol],
                data_base_path=base_path,
                output_base_path=Path("reports/research"),
                run_id=run_id,
                git_commit="quickstart",
                data_snapshot_id="quickstart-sample",
                config_snapshot={
                    "command": "quickstart",
                    "symbols": [symbol],
                    "data_snapshot_id": "quickstart-sample",
                    "data_kind": "synthetic",
                },
                candidate_specs=candidates,
                watchlist_candidate_specs=candidates,
                timeframe="1m",
                since=None, until=None,
                validation_config=ValidationConfig(periods=[1, 5]),
                criteria=PromotionCriteria(),
                train_size=60, validation_size=20, test_size=20, step_size=20,
                sync_data=False, min_history_days=1,
            )
            summary = result.summary()
            evaluated = summary.get("evaluated", 0)
            promoted = summary.get("promoted", 0)

            typer.echo()
            typer.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            typer.echo(f"  {t('quickstart.trust_title')}")
            typer.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            typer.echo()

            # Benchmark: buy-and-hold
            _print_benchmark(symbol, base_path, result)
            typer.echo()

            # Strategy evaluation
            if evaluated > 0:
                typer.echo(f"  {evaluated} {t('quickstart.strategies_evaluated')}")
                typer.echo(f"  {promoted} {t('quickstart.strategies_promoted_label')}")
                typer.echo()
                if promoted == 0:
                    typer.echo(f"  💡 {t('quickstart.verdict_none_promoted')}")
                    typer.echo(f"     {t('quickstart.verdict_none_reason')}")
                else:
                    typer.echo(f"  🎯 {t('quickstart.verdict_promoted')}")
            else:
                typer.echo(f"  {t('quickstart.no_evaluation')}")
            typer.echo()

            if result.artifact_paths.get("auto_run_report"):
                typer.echo(f"  📄 {t('quickstart.report_at')}: {result.artifact_paths['auto_run_report']}")
                typer.echo(f"  🔎 {t('quickstart.report_latest_hint')}: kronos report latest")
        except Exception as exc:
            typer.echo(f"  ⚠️ {t('quickstart.research_skipped')}: {exc}")

    typer.echo()
    typer.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    typer.echo(f"  {t('quickstart.what_next_title')}")
    typer.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    typer.echo()
    import os as _os
    typer.echo(t("quickstart.next_steps_docker") if _os.path.exists("/.dockerenv") else t("quickstart.next_steps"))
