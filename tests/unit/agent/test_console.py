"""Tests for user-facing Agent console copy."""

from __future__ import annotations

from dataclasses import dataclass

from kronos.agent.console import AgentConsole
from kronos.common.config import KronosConfig


@dataclass(frozen=True)
class _FakeResult:
    timeframe: str
    data_coverage: list[dict[str, object]]

    def summary(self) -> dict[str, int]:
        return {
            "evaluated": 1,
            "promoted": 0,
        }


def _console() -> AgentConsole:
    return AgentConsole(config=KronosConfig())


def test_strategy_context_line_uses_real_candidate_count_for_sample_data() -> None:
    console = _console()
    console.ctx.synthetic_data = True
    console.ctx.data_span_days = 7.0

    line = console._strategy_context_line(1)

    assert "1 个策略" in line
    assert "sample 数据" in line
    assert "不足以判断策略是否赚钱" in line
    assert "{n}" not in line
    assert "90 天" not in line


def test_research_next_line_does_not_use_legacy_fixed_copy_for_sample_data() -> None:
    console = _console()
    console.ctx.synthetic_data = True
    result = _FakeResult(
        timeframe="1m",
        data_coverage=[{
            "dataset": "klines_1m",
            "span_days": 7.0,
        }],
    )

    line = console._research_next_line(result, 1)  # type: ignore[arg-type]

    assert "1m" in line
    assert "约 7.0 天" in line
    assert "sample" in line
    assert "同步真实行情" in line
    assert "12 个旧策略" not in line
    assert "90 天" not in line


def test_strategy_context_line_is_shorter_for_sample_data() -> None:
    console = _console()
    console.ctx.synthetic_data = True
    console.ctx.data_span_days = 7.0

    line = console._strategy_context_line(2)

    assert "sample 数据" in line
    assert "不能判断策略是否赚钱" not in line
    assert "先同步真实行情, 再做正式验证" in line
