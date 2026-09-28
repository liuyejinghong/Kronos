# ruff: noqa: RUF001 -- Chinese user-facing strings use fullwidth punctuation.
"""Unit tests for the deterministic conversation intent parser (P14)."""

from __future__ import annotations

import pytest

from kronos.conversation.intents import (
    ATR_PARAM,
    MULTIPLIER_PARAM,
    PendingAdjustment,
    parse_intent,
)


def _ids(parsed: ParsedIntentLike) -> tuple[str, str]:
    return (parsed.kind, parsed.status)


class ParsedIntentLike:
    pass


# ---------------------------------------------------------------- adjust_param


def test_multiplier_change_with_decimal_resolves() -> None:
    parsed = parse_intent("把倍数改成 2.0")
    assert (parsed.kind, parsed.status) == ("adjust_param", "resolved")
    assert parsed.param_overrides == {MULTIPLIER_PARAM: 2.0}
    assert parsed.confidence == "deterministic"


def test_multiplier_change_without_space_resolves() -> None:
    parsed = parse_intent("倍数改成2")
    assert parsed.status == "resolved"
    assert parsed.param_overrides == {MULTIPLIER_PARAM: 2.0}


def test_multiplier_english_resolves() -> None:
    parsed = parse_intent("volatility multiplier set to 2")
    assert parsed.status == "resolved"
    assert parsed.param_overrides == {MULTIPLIER_PARAM: 2.0}


def test_atr_change_resolves() -> None:
    parsed = parse_intent("把 ATR 改成 20")
    assert (parsed.kind, parsed.status) == ("adjust_param", "resolved")
    assert parsed.param_overrides == {ATR_PARAM: 20.0}


def test_atr_with_redundant_period_word_resolves() -> None:
    parsed = parse_intent("ATR 周期 改成 20")
    assert parsed.status == "resolved"
    assert parsed.param_overrides == {ATR_PARAM: 20.0}


def test_both_params_in_one_message_resolve_together() -> None:
    parsed = parse_intent("倍数改成 2，ATR 改成 30")
    assert parsed.status == "resolved"
    assert parsed.param_overrides == {MULTIPLIER_PARAM: 2.0, ATR_PARAM: 30.0}


def test_multiplier_out_of_range_clarifies_with_range() -> None:
    parsed = parse_intent("倍数改成 50")
    assert (parsed.kind, parsed.status) == ("adjust_param", "needs_clarification")
    assert parsed.param_overrides == {}
    assert parsed.clarification_question is not None
    assert "0 到 20" in parsed.clarification_question
    assert parsed.pending == PendingAdjustment(param=MULTIPLIER_PARAM)


def test_multiplier_zero_clarifies() -> None:
    assert parse_intent("倍数改成 0").status == "needs_clarification"


def test_atr_out_of_range_clarifies() -> None:
    parsed = parse_intent("ATR 改成 5000")
    assert parsed.status == "needs_clarification"
    assert parsed.pending == PendingAdjustment(param=ATR_PARAM)
    assert parsed.clarification_question is not None
    assert "2 到 1000" in parsed.clarification_question


def test_atr_non_integer_clarifies() -> None:
    parsed = parse_intent("ATR 改成 20.5")
    assert parsed.status == "needs_clarification"
    assert parsed.pending == PendingAdjustment(param=ATR_PARAM)


# ------------------------------------------------- bare value / pending context


def test_bare_number_with_change_verb_clarifies_and_pends_value() -> None:
    parsed = parse_intent("改成 2")
    assert (parsed.kind, parsed.status) == ("adjust_param", "needs_clarification")
    assert parsed.clarification_question is not None
    assert "哪个参数" in parsed.clarification_question
    assert parsed.pending == PendingAdjustment(value=2.0)


def test_pending_value_with_param_reply_resolves() -> None:
    first = parse_intent("改成 2")
    assert first.pending is not None
    second = parse_intent("倍数", pending_value=first.pending.value)
    assert (second.kind, second.status) == ("adjust_param", "resolved")
    assert second.param_overrides == {MULTIPLIER_PARAM: 2.0}


def test_pending_param_with_value_reply_resolves() -> None:
    second = parse_intent("2.5", pending_param=MULTIPLIER_PARAM)
    assert second.status == "resolved"
    assert second.param_overrides == {MULTIPLIER_PARAM: 2.5}


def test_pending_param_reply_without_number_reclarifies() -> None:
    second = parse_intent("", pending_param=MULTIPLIER_PARAM)
    assert second.status == "needs_clarification"


def test_vague_direction_clarifies() -> None:
    parsed = parse_intent("更激进一点")
    assert (parsed.kind, parsed.status) == ("adjust_param", "needs_clarification")
    assert parsed.clarification_question is not None
    assert "波动率倍数" in parsed.clarification_question
    assert parsed.pending is None


def test_vague_english_direction_clarifies() -> None:
    assert parse_intent("be more aggressive").kind == "ask_verdict"  # out of frozen grammar


# --------------------------------------------------------------- keep-guard TF


def test_atr_adjust_with_kept_timeframe_does_not_switch() -> None:
    parsed = parse_intent("ATR 改成 20，时间还是 15m")
    assert parsed.status == "resolved"
    assert parsed.param_overrides == {ATR_PARAM: 20.0}
    assert parsed.timeframe is None
    assert parsed.kept_timeframe == "15m"
    assert "15m" in parsed.echo_text


def test_timeframe_word_does_not_become_atr_number() -> None:
    parsed = parse_intent("把周期改成1h")
    assert (parsed.kind, parsed.status) == ("switch_timeframe", "resolved")
    assert parsed.param_overrides == {}
    assert parsed.timeframe == "1h"


def test_chinese_timeframe_literal_switches() -> None:
    parsed = parse_intent("周期改成15分钟")
    assert parsed.status == "resolved"
    assert parsed.timeframe == "15m"
    assert parsed.param_overrides == {}


def test_timeframe_switch_with_verb_resolves() -> None:
    parsed = parse_intent("改用 1h")
    assert (parsed.kind, parsed.status) == ("switch_timeframe", "resolved")
    assert parsed.timeframe == "1h"


def test_bare_timeframe_literal_switches() -> None:
    assert parse_intent("1h").timeframe == "1h"
    assert parse_intent("换成15m").timeframe == "15m"


def test_tf_or_question_clarifies() -> None:
    parsed = parse_intent("15m还是1h？")
    assert (parsed.kind, parsed.status) == ("switch_timeframe", "needs_clarification")
    assert parsed.clarification_question is not None
    assert "15m" in parsed.clarification_question and "1h" in parsed.clarification_question


def test_unsupported_tf_choice_clarifies() -> None:
    parsed = parse_intent("1小时还是1天？")
    assert parsed.status == "needs_clarification"
    assert parsed.clarification_question is not None
    assert "15m" in parsed.clarification_question


def test_unsupported_tf_unit_clarifies() -> None:
    parsed = parse_intent("换成4h")
    assert (parsed.kind, parsed.status) == ("switch_timeframe", "needs_clarification")
    assert parsed.timeframe is None


# -------------------------------------------------------------- switch_symbol


def test_symbol_switch_with_verb_resolves() -> None:
    parsed = parse_intent("换成ETHUSDT")
    assert (parsed.kind, parsed.status) == ("switch_symbol", "resolved")
    assert parsed.symbol == "ETHUSDT"


def test_symbol_alone_resolves() -> None:
    parsed = parse_intent("ETHUSDT")
    assert parsed.status == "resolved"
    assert parsed.symbol == "ETHUSDT"


def test_bare_base_symbol_with_verb_normalizes() -> None:
    parsed = parse_intent("换成 ETH")
    assert parsed.status == "resolved"
    assert parsed.symbol == "ETHUSDT"


def test_lowercase_symbol_switch_resolves() -> None:
    parsed = parse_intent("switch to solusdt")
    assert parsed.status == "resolved"
    assert parsed.symbol == "SOLUSDT"


def test_symbol_inside_prose_without_verb_does_not_switch() -> None:
    parsed = parse_intent("BTCUSDT 的历史数据有多少")
    assert parsed.symbol is None
    assert parsed.kind == "ask_verdict"


# ------------------------------------------------------------------ collisions


def test_param_and_symbol_collision_clarifies() -> None:
    parsed = parse_intent("倍数改成2，换成ETHUSDT")
    assert parsed.status == "needs_clarification"
    assert parsed.param_overrides == {}
    assert parsed.symbol is None
    assert parsed.clarification_question is not None


def test_param_and_timeframe_collision_clarifies() -> None:
    parsed = parse_intent("倍数改成2并换成1h")
    assert parsed.status == "needs_clarification"


# ---------------------------------------------------------- evidence & verdict


def test_why_question_is_evidence_question() -> None:
    parsed = parse_intent("为什么不如持有")
    assert (parsed.kind, parsed.status) == ("evidence_question", "resolved")
    assert parsed.echo_text != ""


def test_evidence_keyword_maps_to_evidence_question() -> None:
    assert parse_intent("依据是什么").kind == "evidence_question"
    assert parse_intent("凭什么").kind == "evidence_question"
    assert parse_intent("给我看证据").kind == "evidence_question"


def test_plain_question_defaults_to_ask_verdict() -> None:
    parsed = parse_intent("现在结论如何")
    assert (parsed.kind, parsed.status) == ("ask_verdict", "resolved")


def test_greeting_defaults_to_ask_verdict() -> None:
    assert parse_intent("你好").kind == "ask_verdict"


def test_empty_input_clarifies() -> None:
    parsed = parse_intent("   ")
    assert parsed.status == "needs_clarification"
    assert parsed.clarification_question is not None


# ------------------------------------------------------------------ refusals


def test_live_trading_switch_refused() -> None:
    parsed = parse_intent("把实盘打开")
    assert (parsed.kind, parsed.status) == ("out_of_scope", "refused")
    assert parsed.refusal_reason == "live_trading"


def test_order_request_refused() -> None:
    assert parse_intent("帮我下单").refusal_reason == "live_trading"


def test_mainnet_request_refused() -> None:
    assert parse_intent("切到主网").refusal_reason == "live_trading"


def test_grid_strategy_refused_as_unsupported_template() -> None:
    parsed = parse_intent("写个网格策略")
    assert parsed.refusal_reason == "unsupported_template"


def test_arbitrary_code_refused() -> None:
    assert parse_intent("任意代码").refusal_reason == "unsupported_template"


def test_refusal_wins_over_adjustment_reading() -> None:
    parsed = parse_intent("实盘模式下把倍数改成 2")
    assert parsed.kind == "out_of_scope"
    assert parsed.status == "refused"


# ---------------------------------------------------------------------- misc


def test_prose_number_does_not_become_param() -> None:
    parsed = parse_intent("周期参数见文档第 20 页")
    assert parsed.kind == "ask_verdict"
    assert parsed.param_overrides == {}


def test_every_result_carries_deterministic_confidence() -> None:
    for text in ("把倍数改成 2.0", "更激进一点", "把实盘打开", "现在结论如何", ""):
        assert parse_intent(text).confidence == "deterministic"


def test_echo_text_present_for_ui() -> None:
    for text in ("把倍数改成 2.0", "换成ETHUSDT", "改用 1h", "更激进一点", "把实盘打开"):
        assert parse_intent(text).echo_text != ""


def test_unknown_param_names_focus_the_supported_set() -> None:
    """An unsupported parameter request clarifies with the supported set."""
    parsed = parse_intent("止损改成 5")
    assert parsed.param_overrides == {}
    assert parsed.status == "needs_clarification"
    assert parsed.clarification_question is not None
    assert "波动率倍数" in parsed.clarification_question
    assert "ATR" in parsed.clarification_question


@pytest.mark.parametrize(
    ("text", "kind", "status"),
    [
        ("把倍数改成 2.0", "adjust_param", "resolved"),
        ("换成ETHUSDT", "switch_symbol", "resolved"),
        ("改用 1h", "switch_timeframe", "resolved"),
        ("为什么不如持有", "evidence_question", "resolved"),
        ("把实盘打开", "out_of_scope", "refused"),
        ("更激进一点", "adjust_param", "needs_clarification"),
        ("现在结论如何", "ask_verdict", "resolved"),
    ],
)
def test_grammar_table(text: str, kind: str, status: str) -> None:
    parsed = parse_intent(text)
    assert parsed.kind == kind
    assert parsed.status == status
