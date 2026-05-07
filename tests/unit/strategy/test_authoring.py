"""Unit tests for natural-language strategy authoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kronos.strategy.authoring import StrategyDraftStatus, draft_strategy
from kronos.strategy.config import load_strategy_config


class TestStrategyAuthoring:
    def test_drafts_supported_r_breaker_to_toml_and_trace(self, tmp_path: Path) -> None:
        result = draft_strategy(
            "我想做 BTCUSDT 和 ETHUSDT 的 R-breaker 日内突破, 15m 周期",
            output_dir=tmp_path,
            strategy_id="my_breaker",
        )

        assert result.status == StrategyDraftStatus.READY
        assert result.draft_path is not None
        assert result.artifact_paths["strategy_toml"] == result.draft_path
        assert Path(result.summary_path).exists()
        assert Path(result.trace_path).exists()

        config = load_strategy_config(result.draft_path)
        assert config.strategy.id == "my_breaker"
        assert config.strategy.kind == "r_breaker"
        assert config.universe.symbols == ["BTCUSDT", "ETHUSDT"]
        assert config.universe.timeframe == "15m"
        assert config.params.atr_period == 14
        assert config.params.volatility_multiplier == 1.5

        trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
        assert trace["analysis"]["status"] == "ready"
        assert trace["analysis"]["model_provider"] is None
        assert trace["prompt_version"] == "strategy-authoring-v1"
        assert trace["artifacts"]["draft_path"] == result.draft_path

    def test_needs_clarification_without_symbol_or_timeframe(self, tmp_path: Path) -> None:
        result = draft_strategy("我想做一个日内突破策略", output_dir=tmp_path)

        assert result.status == StrategyDraftStatus.NEEDS_CLARIFICATION
        assert result.draft_path is None
        assert Path(result.summary_path).exists()
        assert Path(result.trace_path).exists()
        assert "品种" in result.analysis.unresolved_items
        assert "周期" in result.analysis.unresolved_items

    def test_rejects_unsupported_template_without_toml(self, tmp_path: Path) -> None:
        result = draft_strategy("我想做 BTCUSDT 1h 均线金叉策略", output_dir=tmp_path)

        assert result.status == StrategyDraftStatus.UNSUPPORTED_TEMPLATE
        assert result.draft_path is None
        assert result.analysis.unsupported_reason is not None
        assert "R-breaker" in result.analysis.unsupported_reason
        assert Path(result.summary_path).exists()
        assert Path(result.trace_path).exists()
        assert result.analysis.key_parameters == {}
        assert result.analysis.default_assumptions == []

    def test_rejects_unsafe_draft_id_before_writing_artifacts(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="strategy_id"):
            draft_strategy(
                "我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期",
                output_dir=tmp_path,
                strategy_id="../bad",
            )

        assert not list(tmp_path.iterdir())
