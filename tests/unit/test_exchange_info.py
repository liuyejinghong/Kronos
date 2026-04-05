"""Unit tests for exchange info loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kronos.common.errors import DataError
from kronos.data.loaders.exchange_info import (
    SymbolInfo,
    get_onboard_date,
    load_exchange_info,
    save_exchange_info,
    validate_symbol,
)

if TYPE_CHECKING:
    from pathlib import Path


def _sample_symbols() -> list[SymbolInfo]:
    """Create sample symbol info for testing."""
    return [
        SymbolInfo(
            symbol="BTCUSDT",
            onboard_date=1569398400000,  # 2019-09-25
            price_precision=2,
            quantity_precision=3,
            tick_size=0.10,
            step_size=0.001,
            status="TRADING",
            contract_type="PERPETUAL",
        ),
        SymbolInfo(
            symbol="ETHUSDT",
            onboard_date=1569398400000,
            price_precision=2,
            quantity_precision=3,
            tick_size=0.01,
            step_size=0.001,
            status="TRADING",
            contract_type="PERPETUAL",
        ),
    ]


class TestSaveAndLoad:
    """Tests for save/load exchange info."""

    def test_save_creates_parquet(self, tmp_path: Path) -> None:
        symbols = _sample_symbols()
        path = save_exchange_info(symbols, tmp_path)
        assert path.exists()
        assert path.name == "exchange_info.parquet"

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        symbols = _sample_symbols()
        save_exchange_info(symbols, tmp_path)
        table = load_exchange_info(tmp_path)
        assert table.num_rows == 2
        assert "BTCUSDT" in table.column("symbol").to_pylist()
        assert "ETHUSDT" in table.column("symbol").to_pylist()

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match=r"cache not found"):
            load_exchange_info(tmp_path)

    def test_save_has_ingested_at(self, tmp_path: Path) -> None:
        symbols = _sample_symbols()
        save_exchange_info(symbols, tmp_path)
        table = load_exchange_info(tmp_path)
        ingested_at_values = table.column("ingested_at").to_pylist()
        assert all(v > 0 for v in ingested_at_values)

    def test_save_preserves_precision(self, tmp_path: Path) -> None:
        symbols = _sample_symbols()
        save_exchange_info(symbols, tmp_path)
        table = load_exchange_info(tmp_path)
        tick_sizes = table.column("tick_size").to_pylist()
        assert tick_sizes[0] == pytest.approx(0.10)
        assert tick_sizes[1] == pytest.approx(0.01)


class TestValidateSymbol:
    """Tests for symbol validation."""

    def test_valid_symbol(self, tmp_path: Path) -> None:
        save_exchange_info(_sample_symbols(), tmp_path)
        assert validate_symbol("BTCUSDT", tmp_path) is True

    def test_invalid_symbol(self, tmp_path: Path) -> None:
        save_exchange_info(_sample_symbols(), tmp_path)
        assert validate_symbol("FAKECOIN", tmp_path) is False

    def test_no_cache_returns_false(self, tmp_path: Path) -> None:
        assert validate_symbol("BTCUSDT", tmp_path) is False


class TestGetOnboardDate:
    """Tests for onboard date lookup."""

    def test_known_symbol(self, tmp_path: Path) -> None:
        save_exchange_info(_sample_symbols(), tmp_path)
        date = get_onboard_date("BTCUSDT", tmp_path)
        assert date == 1569398400000

    def test_unknown_symbol(self, tmp_path: Path) -> None:
        save_exchange_info(_sample_symbols(), tmp_path)
        assert get_onboard_date("FAKECOIN", tmp_path) is None

    def test_no_cache_returns_none(self, tmp_path: Path) -> None:
        assert get_onboard_date("BTCUSDT", tmp_path) is None
