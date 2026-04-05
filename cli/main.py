"""Kronos CLI — data sync and status commands."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from kronos.common.config import load_config
from kronos.common.log import setup_logging

app = typer.Typer(name="kronos", help="Kronos — crypto-native quantitative research system")
data_app = typer.Typer(name="data", help="Data management commands")
app.add_typer(data_app)


def _parse_since(since: str | None) -> int | None:
    """Convert a date string to epoch-ms."""
    if since is None:
        return None
    dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


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
