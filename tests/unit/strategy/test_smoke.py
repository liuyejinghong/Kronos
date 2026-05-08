"""Unit tests for strategy smoke tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kronos.data.seed import generate_sample_klines
from kronos.strategy.config import default_r_breaker_config
from kronos.strategy.smoke import run_strategy_smoke_test

if TYPE_CHECKING:
    from pathlib import Path


class TestStrategySmoke:
    def test_smoke_test_passes_with_sample_data(self, tmp_path: Path) -> None:
        data_path = tmp_path / "data"
        generate_sample_klines("BTCUSDT", base_path=data_path, days=7)
        config = default_r_breaker_config(symbols=["BTCUSDT"], timeframe="15m")

        result = run_strategy_smoke_test(config, data_base_path=data_path)

        assert result.passed is True
        assert result.failed_symbols == []
        assert len(result.results) == 1
        assert result.results[0].reason_code == "ok"
        assert result.results[0].rows >= 256
        assert result.results[0].valid_signal_count > 0
        assert "不会" not in result.results[0].message_zh

    def test_smoke_test_fails_without_data(self, tmp_path: Path) -> None:
        config = default_r_breaker_config(symbols=["BTCUSDT"], timeframe="15m")

        result = run_strategy_smoke_test(config, data_base_path=tmp_path / "missing")

        assert result.passed is False
        assert result.failed_symbols == ["BTCUSDT"]
        assert result.results[0].reason_code == "missing_data"
        assert "本地没有" in result.results[0].message_zh
