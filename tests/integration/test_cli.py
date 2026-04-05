"""Integration tests for CLI commands."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pyarrow as pa
from typer.testing import CliRunner

from cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def _make_kline_table(symbol: str = "BTCUSDT", n: int = 10) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 60_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 60_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
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
    })


def _make_funding_table(symbol: str = "BTCUSDT", n: int = 3) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 28_800_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + i * 28_800_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
        "mark_price": pa.array([67000.0] * n, type=pa.float64()),
    })


def _make_oi_table(symbol: str = "BTCUSDT", n: int = 3) -> pa.Table:
    base = 1709251200000
    now = int(time.time() * 1000)
    return pa.table({
        "event_time": pa.array([base + i * 300_000 for i in range(n)], type=pa.int64()),
        "available_at": pa.array([base + (i + 1) * 300_000 for i in range(n)], type=pa.int64()),
        "ingested_at": pa.array([now] * n, type=pa.int64()),
        "symbol": [symbol] * n,
        "sum_open_interest": pa.array([50000.0] * n, type=pa.float64()),
        "sum_open_interest_value": pa.array([3350000000.0] * n, type=pa.float64()),
    })


def _write_test_config(tmp_path: Path) -> Path:
    """Write a test config pointing to tmp_path for data."""
    config = tmp_path / "test.toml"
    data_path = str(tmp_path / "data")
    config.write_text(
        f'[runtime]\nmode = "dev"\nlog_level = "WARNING"\nlog_json = false\n\n'
        f'[data]\nbase_path = "{data_path}"\n'
    )
    return config


class TestDataStatusCLI:
    """Integration tests for 'kronos data status' command."""

    def test_status_no_data(self, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        result = runner.invoke(app, ["data", "status", "--symbols", "BTCUSDT", "--config", str(config)])
        assert result.exit_code == 0
        assert "no data" in result.stdout

    @patch("kronos.data.sync.fetch_klines")
    def test_status_with_data(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        config = _write_test_config(tmp_path)
        data_path = tmp_path / "data"

        mock_fetch.return_value = _make_kline_table(n=60)
        from kronos.data.sync import sync_klines
        sync_klines("BTCUSDT", base_path=data_path, since=1709251200000)

        result = runner.invoke(app, ["data", "status", "--symbols", "BTCUSDT", "--config", str(config)])
        assert result.exit_code == 0
        assert "klines_1m" in result.stdout
        assert "60" in result.stdout


class TestDataSyncCLI:
    """Integration tests for 'kronos data sync' command."""

    @patch("kronos.data.sync.fetch_open_interest")
    @patch("kronos.data.sync.fetch_funding_rates")
    @patch("kronos.data.sync.fetch_klines")
    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_success(
        self,
        mock_exchange: MagicMock,
        mock_klines: MagicMock,
        mock_funding: MagicMock,
        mock_oi: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)

        from kronos.data.loaders.exchange_info import SymbolInfo
        mock_exchange.return_value = [
            SymbolInfo(
                symbol="BTCUSDT", onboard_date=1569398400000,
                price_precision=2, quantity_precision=3,
                tick_size=0.01, step_size=0.001,
                status="TRADING", contract_type="PERPETUAL",
            ),
        ]
        mock_klines.return_value = _make_kline_table(n=10)
        mock_funding.return_value = _make_funding_table(n=3)
        mock_oi.return_value = _make_oi_table(n=3)

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "BTCUSDT",
            "--config", str(config),
        ])
        assert result.exit_code == 0
        assert "Sync Summary" in result.stdout
        assert "BTCUSDT" in result.stdout

    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_invalid_symbol(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)
        mock_exchange.return_value = []  # No symbols

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "FAKECOIN",
            "--config", str(config),
        ])
        assert result.exit_code == 1

    @patch("kronos.data.loaders.exchange_info.fetch_exchange_info")
    def test_sync_network_error(
        self,
        mock_exchange: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = _write_test_config(tmp_path)
        mock_exchange.side_effect = Exception("Connection refused")

        result = runner.invoke(app, [
            "data", "sync",
            "--symbols", "BTCUSDT",
            "--config", str(config),
        ])
        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Cannot connect" in output or "Connection refused" in output
