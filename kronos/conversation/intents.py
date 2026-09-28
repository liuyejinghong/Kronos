# ruff: noqa: RUF001 -- Chinese user-facing strings use fullwidth punctuation.
"""Deterministic intent parser for the strategy conversation (package P14).

Grammar scope (frozen for v0.5.0, spec ``conversation-web``):

- ``ask_verdict``   — default: any utterance that asks about the current
  conclusion without an actionable change ("现在结论如何").
- ``adjust_param``  — explicit value + explicit parameter: "倍数改成 2.0",
  "ATR 改成 20". Parameters are exactly the two ``VariantParams`` fields:
  ``volatility_multiplier`` via 倍数/乘数/multiplier, ``atr_period`` via
  ATR/周期/period. A bare 周期 never means the signal timeframe: timeframe
  literals are extracted first and can never satisfy a parameter number.
- ``switch_symbol`` — a BTCUSDT/ETHUSDT/SOLUSDT mention (with a switch verb
  or as the whole message), normalized to the full ``<XXX>USDT`` id.
- ``switch_timeframe`` — 换成/改用 15m|1h (aliases 15分钟/15min/1小时/60分钟);
  supported literals are ONLY 15m and 1h (D-20260928-002). "时间还是 15m"
  is a KEEP mention, never a switch.
- ``evidence_question`` — 为什么/依据/证据/凭什么: read the current verdict,
  never start a new task.
- ``out_of_scope``  — 实盘/下单/主网 (live trading) and 任意代码/网格策略 etc.
  (unsupported template) → refused. Refusal always wins over every other
  reading, so injected text cannot escalate privileges.

Ambiguity rules:
- vague direction ("更激进一点") or a bare number with a change verb
  ("改成 2") → ``needs_clarification`` with ONE focused question; the bare
  value (or bare parameter, when the value came first) is returned as
  ``pending`` so the service can resolve the user's follow-up answer.
- a supported timeframe literal directly followed by 还是/or ("15m还是1h")
  → clarify; unsupported timeframe units (1天/4h/周线…) also clarify with
  the supported list.
- values outside the ``VariantParams`` ranges clarify with the range; a
  non-integer ATR value clarifies.
- two different change dimensions in one message (param + symbol etc.)
  clarify: one dimension per turn.

Every result carries ``confidence="deterministic"`` (this module never calls
a model) and an ``echo_text`` for UI display. The LLM-assisted fallback for
ambiguous utterances is a LATER hook around :func:`parse_intent` (documented
in :mod:`kronos.conversation.service`), not wired here.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

type IntentKind = Literal[
    "ask_verdict",
    "adjust_param",
    "switch_symbol",
    "switch_timeframe",
    "evidence_question",
    "out_of_scope",
]
type IntentStatus = Literal["resolved", "needs_clarification", "refused"]
type RefusalReason = Literal["live_trading", "unsupported_template"]
type ActionKind = Literal["adjust_param", "switch_symbol", "switch_timeframe"]

CONFIDENCE_DETERMINISTIC: Final[Literal["deterministic"]] = "deterministic"

MULTIPLIER_PARAM: Final[str] = "volatility_multiplier"
ATR_PARAM: Final[str] = "atr_period"

#: Symbols the conversation can switch to (v0.5.0 whitelist).
KNOWN_SYMBOLS: Final[tuple[str, ...]] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SUPPORTED_TIMEFRAMES: Final[tuple[str, ...]] = ("15m", "1h")

#: VariantParams ranges (mirrors ``kronos.strategy.spec.VariantParams`` bounds).
MULTIPLIER_RANGE: Final[tuple[float, float]] = (0.0, 20.0)
ATR_RANGE: Final[tuple[int, int]] = (2, 1000)

_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"\d+(?:\.\d+)?")
_CHANGE_VERB_RE: Final[re.Pattern[str]] = re.compile(
    r"改成|改为|调成|调到|调整为|设置为|设为|换成|换到|换为|改到|改作|set|change",
    re.IGNORECASE,
)
#: ASCII boundaries only: ``\b`` treats CJK characters as word characters, so
#: "换成ETHUSDT" would never match a \b-anchored symbol.
_ASCII_L: Final[str] = r"(?<![A-Za-z0-9])"
_ASCII_R: Final[str] = r"(?![A-Za-z0-9])"
_SYMBOL_RE: Final[re.Pattern[str]] = re.compile(
    _ASCII_L
    + r"(BTCUSDT|ETHUSDT|SOLUSDT)"
    + _ASCII_R
    + r"|"
    + _ASCII_L
    + r"(BTC|ETH|SOL)USDT"
    + _ASCII_R,
    re.IGNORECASE,
)
_BARE_SYMBOL_RE: Final[re.Pattern[str]] = re.compile(
    _ASCII_L + r"(BTC|ETH|SOL)" + _ASCII_R + r"(?:合约|永续)?", re.IGNORECASE
)
_SWITCH_SYMBOL_VERB_RE: Final[re.Pattern[str]] = re.compile(
    r"换成|换到|换为|切换到|切到|切至|改用|switch to", re.IGNORECASE
)
_TIMEFRAME_SWITCH_VERB_RE: Final[re.Pattern[str]] = re.compile(
    r"换成|换到|换为|切换到|切到|切至|改用|改成|改为|调到|switch to", re.IGNORECASE
)
_TIMEFRAME_KEEP_RE: Final[re.Pattern[str]] = re.compile(
    r"还是|保持|仍是|仍用|依旧|继续用|不变|stay|keep"
)
_TIMEFRAME_OR_QUESTION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:15\s?分钟|15m|1\s?小时|1h)\s*(?:还是|\bor\b)", re.IGNORECASE
)
_TF_LITERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"15\s?分钟|15\s?min(?:ute)?s?|15m|60\s?分钟|1\s?小时|1\s?hour|1h", re.IGNORECASE
)
_UNSUPPORTED_TF_UNIT_RE: Final[re.Pattern[str]] = re.compile(
    _ASCII_L
    + r"(?:4h|30m|5m|1d|1w)"
    + _ASCII_R
    + r"|1天|1日|日线|天图|周线|1周|4小时|30分钟|5分钟",
    re.IGNORECASE,
)
_EVIDENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"为什么|依据|证据|凭什么|why|evidence|based on", re.IGNORECASE
)
_DIRECTION_RE: Final[re.Pattern[str]] = re.compile(
    r"更激进|激进一点|激进些|更保守|保守一点|宽松一点|收紧一点|更敏感|更钝|更松|更紧"
)
_LIVE_SCOPE_RE: Final[re.Pattern[str]] = re.compile(
    r"实盘|主网|下单|真实交易|真钱|真金白银|place.{0,8}order|live trad|mainnet|real money",
    re.IGNORECASE,
)
_UNSUPPORTED_TEMPLATE_RE: Final[re.Pattern[str]] = re.compile(
    r"任意代码|写代码|写个策略|自定义策略|网格|马丁|海龟|做市|网格策略|"
    r"grid strateg|martingale|turtle|any python|python ?代码|任意python",
    re.IGNORECASE,
)
_PARAM_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (MULTIPLIER_PARAM, re.compile(r"倍数|乘数|multiplier", re.IGNORECASE)),
    (ATR_PARAM, re.compile(r"\bATR\b|atr|周期|period", re.IGNORECASE)),
)
_PARAM_WORD_STRIP_RE: Final[re.Pattern[str]] = re.compile(
    r"倍数|乘数|multiplier|\bATR\b|atr|周期|period", re.IGNORECASE
)

_EMPTY_INPUT_QUESTION: Final[str] = "请输入你的问题或指令，例如「当前结论如何」「把倍数改成 2.0」。"
_MULTIPLIER_QUESTION: Final[str] = (
    "要把波动率倍数改成多少？请给出 0 到 20 之间的数值（当前唯一支持的模板为 Kronos 阈值变体）。"
)
_ATR_QUESTION: Final[str] = (
    "要把 ATR 周期改成多少？请给出 2 到 1000 之间的整数（按信号 bar 数计）。"
)
_ONE_DIMENSION_QUESTION: Final[str] = "一次请只修改一个维度：调参数、换标的或换周期，选一个先来。"
_TIMEFRAME_SUPPORTED_QUESTION: Final[str] = "当前版本只支持 15m 与 1h 两个周期，请选择其一。"


class PendingAdjustment(BaseModel):
    """Half-specified adjustment returned with a clarification.

    The service stores it (as JSON on the session row) and hands the fields
    back to :func:`parse_intent` on the user's next message, so
    "改成 2" → “倍数” and “倍数” → "2.5" both resolve deterministically.
    """

    model_config = ConfigDict(extra="forbid")

    param: str | None = None
    value: float | None = None


class ParsedIntent(BaseModel):
    """Deterministic parse result for one user utterance."""

    model_config = ConfigDict(extra="forbid")

    kind: IntentKind
    status: IntentStatus
    confidence: Literal["deterministic"] = CONFIDENCE_DETERMINISTIC
    echo_text: str
    param_overrides: dict[str, float] = Field(default_factory=dict)
    symbol: str | None = None
    timeframe: str | None = None
    kept_timeframe: str | None = None
    refusal_reason: RefusalReason | None = None
    clarification_question: str | None = None
    pending: PendingAdjustment | None = None


def parse_intent(
    text: str,
    *,
    pending_param: str | None = None,
    pending_value: float | None = None,
) -> ParsedIntent:
    """Parse one utterance against the frozen grammar. Pure function.

    ``pending_param`` / ``pending_value`` carry the half-specified adjustment
    from the previous clarification turn (see :class:`PendingAdjustment`).
    """
    raw = text.strip()
    if not raw:
        return ParsedIntent(
            kind="ask_verdict",
            status="needs_clarification",
            echo_text="请输入你的问题或指令。",
            clarification_question=_EMPTY_INPUT_QUESTION,
        )

    # 1. Refusals always win: injected or casual escalation cannot reach the
    #    tool layer through any other reading.
    if _LIVE_SCOPE_RE.search(raw):
        return ParsedIntent(
            kind="out_of_scope",
            status="refused",
            echo_text="已拒绝：本版本仅支持研究与回测，无任何实盘/下单/主网权限。",
            refusal_reason="live_trading",
        )
    if _UNSUPPORTED_TEMPLATE_RE.search(raw):
        return ParsedIntent(
            kind="out_of_scope",
            status="refused",
            echo_text=(
                "已拒绝：当前版本仅支持 Kronos 阈值变体（kronos_threshold_v1），"
                "不支持自定义代码或其他策略模板。"
            ),
            refusal_reason="unsupported_template",
        )

    # 2. "15m还是1h" selection questions clarify before any switch reading.
    if _TIMEFRAME_OR_QUESTION_RE.search(raw):
        return ParsedIntent(
            kind="switch_timeframe",
            status="needs_clarification",
            echo_text="周期需要二选一。",
            clarification_question=_TIMEFRAME_SUPPORTED_QUESTION,
        )

    # 3. Timeframe literals: switch (verb before, or bare mention), keep
    #    (guard words before), or ignored (informational mention). All literal
    #    spans are then blanked so "周期改成1h" can never feed its "1" to the
    #    ATR-period number scan.
    switched_timeframe: str | None = None
    kept_timeframe: str | None = None
    working = raw
    for match in _TF_LITERAL_RE.finditer(raw):
        canonical = _canonical_timeframe(match.group(0))
        if canonical is None:  # pragma: no cover - regex only emits mapped literals
            continue
        prefix = raw[max(0, match.start() - 12) : match.start()]
        if _TIMEFRAME_KEEP_RE.search(prefix):
            kept_timeframe = canonical
        elif _TIMEFRAME_SWITCH_VERB_RE.search(prefix) or _is_bare_mention(raw, match):
            switched_timeframe = canonical
        working = working.replace(match.group(0), " ")

    # 4. Symbol detection (explicit switch verb, or the symbol is the message).
    symbol = _detect_symbol(raw)

    # 5. Pending-context merge: a bare value completes a named parameter and
    #    vice versa (deterministic follow-up to our own focused question).
    param_overrides: dict[str, float] = {}
    clarification: str | None = None
    pending: PendingAdjustment | None = None
    pending_param = pending_param if pending_param in (MULTIPLIER_PARAM, ATR_PARAM) else None

    if pending_param is not None:
        bare = _NUMBER_RE.search(working)
        if bare is not None:
            value = float(bare.group(0))
            clarification = _build_override_issue(pending_param, value)
            if clarification is None:
                param_overrides[pending_param] = value
            else:
                pending = PendingAdjustment(param=pending_param)
            working = _NUMBER_RE.sub(" ", working, count=1)
    elif pending_value is not None:
        named = _named_param(working)
        if named is not None:
            clarification = _build_override_issue(named, pending_value)
            if clarification is None:
                param_overrides[named] = pending_value
            else:
                pending = PendingAdjustment(param=named)
        working = _PARAM_WORD_STRIP_RE.sub(" ", working)

    # 6. Explicit parameter keyword + nearby number → resolved adjustment.
    if not param_overrides and clarification is None:
        param_overrides = _extract_param_overrides(working)
        for param, value in param_overrides.items():
            issue = _range_issue(param, value) or _integer_issue(param, value)
            if issue is not None:
                clarification = issue
                pending = PendingAdjustment(param=param)
                param_overrides = {}
                break

    # 7. Unsupported timeframe units with nothing resolved → clarify (before
    #    the bare-number rule so "换成4h" asks about timeframes, not params).
    if (
        clarification is None
        and not param_overrides
        and not _has_switch_action(symbol, switched_timeframe)
        and _UNSUPPORTED_TF_UNIT_RE.search(raw)
    ):
        return ParsedIntent(
            kind="switch_timeframe",
            status="needs_clarification",
            echo_text="提到的周期不在支持范围内。",
            clarification_question=_TIMEFRAME_SUPPORTED_QUESTION,
            kept_timeframe=kept_timeframe,
        )

    # 8. Bare number with a change verb, or a vague direction → clarify.
    if (
        not param_overrides
        and clarification is None
        and not _has_switch_action(symbol, switched_timeframe)
    ):
        bare = _NUMBER_RE.search(working)
        if bare is not None and _CHANGE_VERB_RE.search(working):
            value = float(bare.group(0))
            clarification = f"要把哪个参数改成 {_format_number(value)}？波动率倍数还是 ATR 周期？"
            pending = PendingAdjustment(value=value)
        elif _DIRECTION_RE.search(working):
            clarification = (
                "「更激进/更保守」需要落到具体参数：请说明要调整波动率倍数（0-20）"
                "还是 ATR 周期（2-1000），以及目标值。"
            )

    # 9. Compose the single resolved action, or clarify on collisions.
    if clarification is not None:
        return ParsedIntent(
            kind="adjust_param",
            status="needs_clarification",
            echo_text="需要澄清后再执行。",
            kept_timeframe=kept_timeframe,
            clarification_question=clarification,
            pending=pending,
        )

    actions: list[ActionKind] = []
    if param_overrides:
        actions.append("adjust_param")
    if switched_timeframe is not None:
        actions.append("switch_timeframe")
    if symbol is not None:
        actions.append("switch_symbol")
    if len(actions) > 1:
        return ParsedIntent(
            kind="adjust_param",
            status="needs_clarification",
            echo_text="一次只能修改一个维度，请分开说明。",
            kept_timeframe=kept_timeframe,
            clarification_question=_ONE_DIMENSION_QUESTION,
        )
    if actions:
        return _resolved_intent(
            actions[0],
            param_overrides=param_overrides,
            symbol=symbol,
            timeframe=switched_timeframe,
            kept_timeframe=kept_timeframe,
        )

    # 10. Evidence question vs default verdict question.
    if _EVIDENCE_RE.search(raw):
        return ParsedIntent(
            kind="evidence_question",
            status="resolved",
            echo_text="证据问答：读取当前结论的证据作答，不触发新回测。",
            kept_timeframe=kept_timeframe,
        )
    return ParsedIntent(
        kind="ask_verdict",
        status="resolved",
        echo_text="结论问答：读取当前修订与最新结论作答。",
        kept_timeframe=kept_timeframe,
    )


def _is_bare_mention(text: str, match: re.Match[str]) -> bool:
    """True when the timeframe literal is (essentially) the whole message."""
    remainder = (text[: match.start()] + text[match.end() :]).strip()
    return remainder == "" or re.fullmatch(r"[?？!！。.\s]+", remainder) is not None


def _canonical_timeframe(literal: str) -> str | None:
    """Map a matched literal to ``15m`` / ``1h``; unknown → ``None``."""
    compact = re.sub(r"\s+", "", literal).lower()
    if compact.startswith("15"):
        return "15m"
    if compact.startswith("60") or compact.startswith("1"):
        return "1h"
    return None


def _detect_symbol(raw: str) -> str | None:
    match = _SYMBOL_RE.search(raw)
    if match is not None:
        base = (match.group(1) or match.group(2)).upper()
        prefix = raw[max(0, match.start() - 12) : match.start()]
        if _SWITCH_SYMBOL_VERB_RE.search(prefix) or _SYMBOL_RE.sub("", raw).strip() == "":
            return base if base.endswith("USDT") else f"{base}USDT"
        return None
    bare = _BARE_SYMBOL_RE.search(raw)
    if bare is not None:
        prefix = raw[max(0, bare.start() - 12) : bare.start()]
        if _SWITCH_SYMBOL_VERB_RE.search(prefix):
            return f"{bare.group(1).upper()}USDT"
    return None


def _named_param(text: str) -> str | None:
    for param, pattern in _PARAM_PATTERNS:
        if pattern.search(text):
            return param
    return None


def _extract_param_overrides(working: str) -> dict[str, float]:
    """Find explicit (parameter keyword + nearby number) pairs.

    The number must sit within 6 characters of the keyword OR after a change
    verb within the 12-char window (covers "ATR 周期 改成 20"), so prose like
    "周期参数见文档第 20 页" does not match.
    """
    overrides: dict[str, float] = {}
    remaining = working
    for param, pattern in _PARAM_PATTERNS:
        for match in pattern.finditer(remaining):
            window = remaining[match.end() : match.end() + 12]
            number = _NUMBER_RE.search(window)
            if number is None:
                continue
            between = window[: number.start()]
            if number.start() > 6 and not _CHANGE_VERB_RE.search(between):
                continue
            value_str = number.group(0)
            overrides[param] = float(value_str)
            consumed_end = match.end() + number.end()
            remaining = remaining[: match.start()] + " " + remaining[consumed_end:]
            break
    return overrides


def _build_override_issue(param: str, value: float) -> str | None:
    """Validate a pending merge; returns the focused question when invalid."""
    if param == ATR_PARAM and value != int(value):
        return _ATR_QUESTION
    return _range_issue(param, value)


def _integer_issue(param: str, value: float) -> str | None:
    if param == ATR_PARAM and value != int(value):
        return _ATR_QUESTION
    return None


def _range_issue(param: str, value: float) -> str | None:
    if param == MULTIPLIER_PARAM:
        low, high = MULTIPLIER_RANGE
        if not low < value <= high:
            return _MULTIPLIER_QUESTION
        return None
    low, high = ATR_RANGE
    if not low <= value <= high:
        return _ATR_QUESTION
    return None


def _has_switch_action(symbol: str | None, timeframe: str | None) -> bool:
    return symbol is not None or timeframe is not None


def _format_number(value: float) -> str:
    return f"{value:g}"


def _resolved_intent(
    kind: ActionKind,
    *,
    param_overrides: dict[str, float],
    symbol: str | None,
    timeframe: str | None,
    kept_timeframe: str | None,
) -> ParsedIntent:
    if kind == "adjust_param":
        parts = [
            f"{param} → {_format_number(value)}" for param, value in sorted(param_overrides.items())
        ]
        echo = "调整参数：" + "，".join(parts)
    elif kind == "switch_timeframe":
        assert timeframe is not None
        echo = f"切换周期：信号周期 → {timeframe}"
    else:
        assert symbol is not None
        echo = f"切换标的：交易标的 → {symbol}"
    if kept_timeframe is not None:
        echo += f"（{kept_timeframe} 周期保持不变）"
    return ParsedIntent(
        kind=kind,
        status="resolved",
        echo_text=echo,
        param_overrides=param_overrides,
        symbol=symbol,
        timeframe=timeframe,
        kept_timeframe=kept_timeframe,
    )
