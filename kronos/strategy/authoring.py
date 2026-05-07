"""Natural-language strategy authoring for Kronos v0.4.3."""
# ruff: noqa: RUF001

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.llm import (
    DEEPSEEK_PROVIDER_NAME,
    DeepSeekLLMProvider,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
)
from kronos.agent.roles import DEEPSEEK_V4_PRO
from kronos.agent.secrets import LocalSecretStore
from kronos.agent.types import AgentPromptVersionId, AgentRoleId
from kronos.strategy.config import StrategyConfig, default_r_breaker_config, write_strategy_config

_DEFAULT_OUTPUT_DIR = Path.home() / ".kronos" / "strategy_drafts"
_PROMPT_VERSION = "strategy-authoring-v1"
_SUPPORTED_TEMPLATE_SLUG = "r_breaker"
_SUPPORTED_TEMPLATE_LABEL = "R-breaker 日内突破"
_VALID_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
_SAFE_DRAFT_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$")
_KNOWN_SYMBOL_BASES = {
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "ADA",
    "DOGE",
    "AVAX",
    "LTC",
    "LINK",
    "SUI",
    "OP",
    "ARB",
    "DOT",
    "UNI",
    "ATOM",
    "TON",
    "NEAR",
    "PEPE",
}


class StrategyDraftStatus(StrEnum):
    """Lifecycle state for one strategy draft attempt."""

    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED_TEMPLATE = "unsupported_template"


class StrategyDraftSource(StrEnum):
    """Where the final draft judgment came from."""

    RULES = "rules"
    AI = "ai"


class StrategyDraftAnalysis(BaseModel):
    """Structured interpretation of one natural-language strategy idea."""

    model_config = ConfigDict(extra="forbid")

    status: StrategyDraftStatus
    template_slug: str
    template_label: str
    intent: str
    strategy_name: str
    symbols: list[str] = Field(default_factory=list)
    timeframe: str | None = None
    key_parameters: dict[str, str] = Field(default_factory=dict)
    default_assumptions: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    next_action: str = "先补齐信息，再继续起草"
    source: StrategyDraftSource = StrategyDraftSource.RULES
    prompt_version: str = _PROMPT_VERSION
    model_provider: str | None = None
    model_name: str | None = None
    llm_attempted: bool = False
    llm_status: str | None = None
    llm_error: str | None = None


class StrategyDraftResult(BaseModel):
    """One end-to-end draft attempt with persisted artifacts."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    analysis: StrategyDraftAnalysis
    summary_path: str
    trace_path: str
    draft_path: str | None = None
    strategy_config: StrategyConfig | None = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)

    @property
    def status(self) -> StrategyDraftStatus:
        return self.analysis.status

    def summary_lines(self) -> list[str]:
        """Return product-facing summary lines for CLI output."""
        lines = [
            "--- Strategy Draft ---",
            f"status: {self._status_label()}",
            f"intent: {self.analysis.intent}",
            f"template: {self.analysis.template_label}",
        ]
        if self.analysis.symbols:
            lines.append(f"symbols: {', '.join(self.analysis.symbols)}")
        else:
            lines.append("symbols: 未确定")
        lines.append(f"timeframe: {self.analysis.timeframe or '未确定'}")
        if self.analysis.key_parameters:
            params = ", ".join(f"{key}={value}" for key, value in self.analysis.key_parameters.items())
            lines.append(f"key_parameters: {params}")
        if self.analysis.default_assumptions:
            lines.append(f"default_assumptions: {'; '.join(self.analysis.default_assumptions)}")
        if self.analysis.unresolved_items:
            lines.append(f"unresolved: {'; '.join(self.analysis.unresolved_items)}")
        else:
            lines.append("unresolved: 无")
        if self.analysis.clarification_questions:
            lines.append("clarification_questions:")
            for question in self.analysis.clarification_questions:
                lines.append(f"  - {question}")
        if self.analysis.unsupported_reason:
            lines.append(f"unsupported_reason: {self.analysis.unsupported_reason}")
        lines.append(f"summary_md: {self.summary_path}")
        lines.append(f"trace_json: {self.trace_path}")
        if self.draft_path is not None:
            lines.append(f"draft_toml: {self.draft_path}")
        return lines

    def next_commands(self, command_prefix: str) -> list[str]:
        """Return copyable follow-up commands for the generated draft."""
        if self.draft_path is None:
            return []
        return [
            f"{command_prefix} strategy validate {self.draft_path}",
            f"{command_prefix} strategy smoke-test {self.draft_path}",
            f"{command_prefix} strategy register {self.draft_path}",
        ]

    def next_step_lines(self, command_prefix: str) -> list[str]:
        """Return trader-facing next steps with copyable commands."""
        commands = self.next_commands(command_prefix)
        if not commands:
            return []
        return [
            "下一步: 先把草案当作研究配置, 不要当成可交易策略.",
            f"1. 检查配置是否完整: {commands[0]}",
            f"2. 用本地数据空跑确认信号能算出来: {commands[1]}",
            f"3. 空跑通过后再进入候选池, 让 Agent 和报告能看到它: {commands[2]}",
        ]

    def _status_label(self) -> str:
        if self.analysis.status == StrategyDraftStatus.READY:
            return "已生成草案"
        if self.analysis.status == StrategyDraftStatus.NEEDS_CLARIFICATION:
            return "需要澄清"
        return "当前模板不支持"


class _LLMAnalysisPayload(BaseModel):
    """Structured JSON payload requested from the model."""

    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    intent: str | None = None
    template_slug: str | None = None
    template_label: str | None = None
    strategy_name: str | None = None
    symbols: list[str] = Field(default_factory=list)
    timeframe: str | None = None
    key_parameters: dict[str, str] = Field(default_factory=dict)
    default_assumptions: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    next_action: str | None = None


def default_strategy_draft_dir() -> Path:
    """Return the default local draft directory."""
    return _DEFAULT_OUTPUT_DIR


def draft_strategy(
    prompt: str,
    *,
    output_dir: str | Path | None = None,
    strategy_id: str | None = None,
    overwrite: bool = False,
    use_ai: bool = False,
) -> StrategyDraftResult:
    """Turn one natural-language strategy idea into a draft package."""
    normalized_prompt = _normalize_text(prompt)
    if not normalized_prompt:
        raise ValueError("prompt is required.")

    ai_analysis = _maybe_analyze_with_llm(normalized_prompt) if use_ai else None
    analysis = _build_analysis(normalized_prompt, ai_analysis)
    draft_id = _validate_draft_id(strategy_id or _build_draft_id(analysis, normalized_prompt))
    draft_root = Path(output_dir).expanduser() if output_dir is not None else default_strategy_draft_dir()
    draft_root.mkdir(parents=True, exist_ok=True)

    summary_path = draft_root / f"{draft_id}.summary.md"
    trace_path = draft_root / f"{draft_id}.trace.json"
    draft_path: str | None = None
    strategy_config: StrategyConfig | None = None

    if analysis.status == StrategyDraftStatus.READY:
        strategy_config = _build_strategy_config(analysis, draft_id)
        draft_path = str(
            write_strategy_config(
                strategy_config,
                directory=draft_root,
                overwrite=overwrite,
            ).resolve()
        )

    summary_path.write_text(
        _render_summary_markdown(
            draft_id=draft_id,
            analysis=analysis,
            draft_path=draft_path,
            summary_path=str(summary_path.resolve()),
            trace_path=str(trace_path.resolve()),
        ),
        encoding="utf-8",
    )
    trace_payload = _render_trace_payload(
        draft_id=draft_id,
        prompt=normalized_prompt,
        analysis=analysis,
        summary_path=str(summary_path.resolve()),
        trace_path=str(trace_path.resolve()),
        draft_path=draft_path,
        strategy_config=strategy_config,
        ai_analysis=ai_analysis,
    )
    trace_path.write_text(
        json.dumps(trace_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    artifact_paths = {
        "strategy_summary": str(summary_path.resolve()),
        "strategy_trace": str(trace_path.resolve()),
    }
    if draft_path is not None:
        artifact_paths["strategy_toml"] = draft_path

    return StrategyDraftResult(
        draft_id=draft_id,
        analysis=analysis,
        summary_path=str(summary_path.resolve()),
        trace_path=str(trace_path.resolve()),
        draft_path=draft_path,
        strategy_config=strategy_config,
        artifact_paths=artifact_paths,
    )


def _build_analysis(prompt: str, ai_analysis: StrategyDraftAnalysis | None) -> StrategyDraftAnalysis:
    supported = _is_r_breaker_prompt(prompt)
    unsupported_reason = _unsupported_reason(prompt) if not supported else None
    template_slug = _SUPPORTED_TEMPLATE_SLUG if supported else "unsupported"
    template_label = _SUPPORTED_TEMPLATE_LABEL if supported else "当前版本只支持 R-breaker"
    intent = ai_analysis.intent if ai_analysis and ai_analysis.intent else _compress_prompt(prompt)
    strategy_name = ai_analysis.strategy_name if ai_analysis and ai_analysis.strategy_name else _SUPPORTED_TEMPLATE_LABEL
    symbols = ai_analysis.symbols if ai_analysis and ai_analysis.symbols else _parse_symbols(prompt)
    timeframe = ai_analysis.timeframe if ai_analysis else _parse_timeframe(prompt)
    key_parameters = (
        ai_analysis.key_parameters if ai_analysis and ai_analysis.key_parameters else {
            "atr_period": "14",
            "volatility_multiplier": "1.5",
        }
    )
    default_assumptions = list(
        ai_analysis.default_assumptions if ai_analysis and ai_analysis.default_assumptions else [
            "先按 R-breaker 模板起草",
            "ATR 周期先用 14",
            "突破倍数先用 1.5",
        ]
    )
    unresolved_items = list(ai_analysis.unresolved_items if ai_analysis else [])
    clarification_questions = list(ai_analysis.clarification_questions if ai_analysis else [])
    next_action = ai_analysis.next_action if ai_analysis and ai_analysis.next_action else "先补齐信息，再继续起草"

    if supported:
        missing: list[str] = []
        if not symbols:
            missing.append("品种")
            clarification_questions.append("你要先做哪个品种？例如 BTCUSDT 或 ETHUSDT。")
        if timeframe is None:
            missing.append("周期")
            clarification_questions.append("你要用什么周期？例如 15m、1h 或 4h。")
        unresolved_items = _dedupe_keep_order([*unresolved_items, *missing])
        if unresolved_items:
            status = StrategyDraftStatus.NEEDS_CLARIFICATION
            next_action = "把未确定项补齐后，再运行一次起草"
        else:
            status = StrategyDraftStatus.READY
            next_action = "先 validate，再 smoke-test，再 register"
        return StrategyDraftAnalysis(
            status=status,
            template_slug=template_slug,
            template_label=template_label,
            intent=intent,
            strategy_name=strategy_name,
            symbols=symbols,
            timeframe=timeframe,
            key_parameters=key_parameters,
            default_assumptions=default_assumptions,
            unresolved_items=_dedupe_keep_order(unresolved_items),
            clarification_questions=_dedupe_keep_order(clarification_questions),
            next_action=next_action,
            source=ai_analysis.source if ai_analysis is not None else StrategyDraftSource.RULES,
            prompt_version=_PROMPT_VERSION,
            model_provider=ai_analysis.model_provider if ai_analysis else None,
            model_name=ai_analysis.model_name if ai_analysis else None,
            llm_attempted=bool(ai_analysis and ai_analysis.llm_attempted),
            llm_status=ai_analysis.llm_status if ai_analysis else None,
            llm_error=ai_analysis.llm_error if ai_analysis else None,
        )

    unresolved_items = _dedupe_keep_order([
        *unresolved_items,
        "当前版本只支持 R-breaker；这段描述没有落到现有模板",
    ])
    clarification_questions = _dedupe_keep_order([
        *clarification_questions,
        "如果你想做的是日内突破，请把品种和周期说清楚；如果你想做的是均线 / RSI / 均值回归，当前版本还没接。",
    ])
    return StrategyDraftAnalysis(
        status=StrategyDraftStatus.UNSUPPORTED_TEMPLATE,
        template_slug=template_slug,
        template_label=template_label,
        intent=intent,
        strategy_name=ai_analysis.strategy_name if ai_analysis and ai_analysis.strategy_name else "未支持模板",
        symbols=symbols,
        timeframe=timeframe,
        key_parameters={},
        default_assumptions=[],
        unresolved_items=unresolved_items,
        clarification_questions=clarification_questions,
        unsupported_reason=unsupported_reason,
        next_action="当前版本只支持 R-breaker；先换成支持范围内的描述，或者等待后续模板",
        source=ai_analysis.source if ai_analysis is not None else StrategyDraftSource.RULES,
        prompt_version=_PROMPT_VERSION,
        model_provider=ai_analysis.model_provider if ai_analysis else None,
        model_name=ai_analysis.model_name if ai_analysis else None,
        llm_attempted=bool(ai_analysis and ai_analysis.llm_attempted),
        llm_status=ai_analysis.llm_status if ai_analysis else None,
        llm_error=ai_analysis.llm_error if ai_analysis else None,
    )


def _build_strategy_config(analysis: StrategyDraftAnalysis, draft_id: str) -> StrategyConfig:
    config = default_r_breaker_config(
        strategy_id=draft_id,
        name=analysis.strategy_name,
        symbols=analysis.symbols,
        timeframe=analysis.timeframe or "15m",
    )
    atr_period = analysis.key_parameters.get("atr_period", "14")
    volatility_multiplier = analysis.key_parameters.get("volatility_multiplier", "1.5")
    return config.model_copy(
        update={
            "params": config.params.model_copy(
                update={
                    "atr_period": int(float(atr_period)),
                    "volatility_multiplier": float(volatility_multiplier),
                }
            )
        }
    )


def _maybe_analyze_with_llm(prompt: str) -> StrategyDraftAnalysis | None:
    secret_store = LocalSecretStore()
    status = secret_store.get_status(DEEPSEEK_PROVIDER_NAME)
    if not status.configured:
        return None

    provider = DeepSeekLLMProvider(secret_store=secret_store)
    request = LLMRequest(
        role_id=AgentRoleId("strategy_author"),
        prompt_version=AgentPromptVersionId(_PROMPT_VERSION),
        model_provider=DEEPSEEK_PROVIDER_NAME,
        model_name=DEEPSEEK_V4_PRO,
        messages=[
            LLMMessage(
                role=LLMMessageRole.SYSTEM,
                content=(
                    "你是 Kronos 的策略起草器。"
                    "只能输出 JSON，不要解释。"
                    "当前首版只支持 R-breaker 日内突破。"
                    "如果可以映射到该模板，返回 status=ready 或 needs_clarification。"
                    "如果明显是其他模板，返回 status=unsupported_template。"
                    "字段必须包括 intent, template_slug, template_label, strategy_name,"
                    " symbols, timeframe, key_parameters, default_assumptions,"
                    " unresolved_items, clarification_questions, unsupported_reason, next_action。"
                ),
            ),
            LLMMessage(role=LLMMessageRole.USER, content=prompt),
        ],
        temperature=0.0,
        max_tokens=900,
    )
    response = provider.complete(request)
    if response.content is None:
        return None
    try:
        payload = _extract_json_payload(response.content)
        analysis = _LLMAnalysisPayload.model_validate(payload)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return StrategyDraftAnalysis(
            status=StrategyDraftStatus.NEEDS_CLARIFICATION,
            template_slug="unsupported",
            template_label="当前版本只支持 R-breaker",
            intent=_compress_prompt(prompt),
            strategy_name=_SUPPORTED_TEMPLATE_LABEL,
            unsupported_reason=f"AI 返回内容无法解析: {exc}",
            llm_attempted=True,
            llm_status=str(response.status),
            llm_error=str(exc),
            source=StrategyDraftSource.RULES,
        )

    return StrategyDraftAnalysis(
        status=_coerce_status(analysis.status, prompt),
        template_slug=analysis.template_slug or _template_slug_for_prompt(prompt),
        template_label=analysis.template_label or _SUPPORTED_TEMPLATE_LABEL,
        intent=analysis.intent or _compress_prompt(prompt),
        strategy_name=analysis.strategy_name or _SUPPORTED_TEMPLATE_LABEL,
        symbols=_dedupe_keep_order(analysis.symbols),
        timeframe=_normalize_timeframe(analysis.timeframe),
        key_parameters={str(key): str(value) for key, value in analysis.key_parameters.items()},
        default_assumptions=_dedupe_keep_order(analysis.default_assumptions),
        unresolved_items=_dedupe_keep_order(analysis.unresolved_items),
        clarification_questions=_dedupe_keep_order(analysis.clarification_questions),
        unsupported_reason=analysis.unsupported_reason,
        next_action=analysis.next_action or "先补齐信息，再继续起草",
        source=StrategyDraftSource.AI,
        prompt_version=_PROMPT_VERSION,
        model_provider=DEEPSEEK_PROVIDER_NAME,
        model_name=DEEPSEEK_V4_PRO,
        llm_attempted=True,
        llm_status=str(response.status),
    )


def _coerce_status(raw_status: str | None, prompt: str) -> StrategyDraftStatus:
    if raw_status:
        normalized = raw_status.strip().lower()
        if normalized == StrategyDraftStatus.READY.value:
            return StrategyDraftStatus.READY
        if normalized in {
            StrategyDraftStatus.NEEDS_CLARIFICATION.value,
            "clarify",
            "need_clarification",
        }:
            return StrategyDraftStatus.NEEDS_CLARIFICATION
        if normalized == StrategyDraftStatus.UNSUPPORTED_TEMPLATE.value:
            return StrategyDraftStatus.UNSUPPORTED_TEMPLATE
    if _is_r_breaker_prompt(prompt):
        return StrategyDraftStatus.READY if _parse_symbols(prompt) and _parse_timeframe(prompt) else StrategyDraftStatus.NEEDS_CLARIFICATION
    if _unsupported_reason(prompt) is not None:
        return StrategyDraftStatus.UNSUPPORTED_TEMPLATE
    return StrategyDraftStatus.NEEDS_CLARIFICATION


def _render_summary_markdown(
    *,
    draft_id: str,
    analysis: StrategyDraftAnalysis,
    draft_path: str | None,
    summary_path: str,
    trace_path: str,
) -> str:
    lines = [
        f"# Kronos 策略起草 `{draft_id}`",
        "",
        f"- 状态: {analysis.status.value}",
        f"- 意图: {analysis.intent}",
        f"- 模板: {analysis.template_label}",
        f"- 品种: {', '.join(analysis.symbols) if analysis.symbols else '未确定'}",
        f"- 周期: {analysis.timeframe or '未确定'}",
        f"- 关键参数: {', '.join(f'{k}={v}' for k, v in analysis.key_parameters.items())}",
        f"- 默认假设: {'; '.join(analysis.default_assumptions)}",
        f"- 未确定项: {'; '.join(analysis.unresolved_items) if analysis.unresolved_items else '无'}",
    ]
    if analysis.clarification_questions:
        lines.extend(["", "## 澄清问题"])
        for question in analysis.clarification_questions:
            lines.append(f"- {question}")
    if analysis.unsupported_reason:
        lines.extend(["", "## 不支持原因", f"- {analysis.unsupported_reason}"])
    lines.extend(
        [
            "",
            "## 追溯信息",
            f"- prompt_version: {analysis.prompt_version}",
            f"- model_provider: {analysis.model_provider or 'rules'}",
            f"- model_name: {analysis.model_name or '-'}",
            f"- summary_path: {summary_path}",
            f"- trace_path: {trace_path}",
        ]
    )
    if draft_path is not None:
        lines.append(f"- draft_path: {draft_path}")
    lines.extend(["", f"- next_action: {analysis.next_action}"])
    return "\n".join(lines) + "\n"


def _render_trace_payload(
    *,
    draft_id: str,
    prompt: str,
    analysis: StrategyDraftAnalysis,
    summary_path: str,
    trace_path: str,
    draft_path: str | None,
    strategy_config: StrategyConfig | None,
    ai_analysis: StrategyDraftAnalysis | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "draft_id": draft_id,
        "prompt": prompt,
        "prompt_version": analysis.prompt_version,
        "analysis": analysis.model_dump(mode="json"),
        "artifacts": {
            "summary_path": summary_path,
            "trace_path": trace_path,
        },
    }
    if draft_path is not None:
        payload["artifacts"]["draft_path"] = draft_path
    if strategy_config is not None:
        payload["strategy_config"] = strategy_config.model_dump(mode="json")
    if ai_analysis is not None:
        payload["ai_analysis"] = ai_analysis.model_dump(mode="json")
    return payload


def _build_draft_id(analysis: StrategyDraftAnalysis, prompt: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    template = analysis.template_slug or _template_slug_for_prompt(prompt)
    return f"draft_{template}_{timestamp}"


def _validate_draft_id(draft_id: str) -> str:
    if not _SAFE_DRAFT_ID.match(draft_id):
        raise ValueError(
            "strategy_id must start with a letter and contain only letters, "
            "numbers, underscores, or hyphens"
        )
    return draft_id


def _extract_json_payload(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM response does not contain a JSON object.")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON must be an object.")
    return payload


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split())


def _compress_prompt(prompt: str, max_len: int = 120) -> str:
    compact = _normalize_text(prompt)
    return compact if len(compact) <= max_len else compact[: max_len - 1].rstrip() + "…"


def _template_slug_for_prompt(prompt: str) -> str:
    if _is_r_breaker_prompt(prompt):
        return _SUPPORTED_TEMPLATE_SLUG
    return "unsupported"


def _is_r_breaker_prompt(prompt: str) -> bool:
    normalized = prompt.lower()
    if any(keyword in normalized for keyword in ("r-breaker", "r breaker", "rbreaker", "r_breaker")):
        return True
    if "日内突破" in prompt or "开盘突破" in prompt or "前一日" in prompt:
        return True
    if "日内" in prompt and "突破" in prompt:
        return True
    return "pivot" in normalized and "break" in normalized


def _unsupported_reason(prompt: str) -> str | None:
    normalized = prompt.lower()
    markers = (
        "均线",
        "金叉",
        "死叉",
        "rsi",
        "boll",
        "bollinger",
        "布林",
        "均值回归",
        "网格",
        "套利",
        "对冲",
        "多因子",
        "趋势跟踪",
        "量价",
    )
    if any(marker in normalized for marker in markers):
        return "当前首版只支持 R-breaker 日内突破，不支持这类模板。"
    return None


def _parse_symbols(prompt: str) -> list[str]:
    upper = prompt.upper()
    raw_tokens = re.findall(r"\b[A-Z0-9]{2,12}\b", upper)
    symbols: list[str] = []
    for token in raw_tokens:
        if token.endswith(("M", "H", "D")) and token[:-1].isdigit():
            continue
        if token in _valid_timeframe_set():
            continue
        if token.endswith("USDT") or token.endswith("USDC") or token.endswith("USD"):
            base = token[:-4] if token.endswith("USDT") else token[:-4] if token.endswith("USDC") else token[:-3]
            if base in _KNOWN_SYMBOL_BASES:
                symbols.append(token)
            continue
        if token in _KNOWN_SYMBOL_BASES:
            symbols.append(f"{token}USDT")
    return _dedupe_keep_order(symbols)


def _parse_timeframe(prompt: str) -> str | None:
    normalized = prompt.lower()
    mapping = {
        "15m": ("15m", "15分钟", "15 分钟", "15min"),
        "30m": ("30m", "30分钟", "30 分钟", "30min"),
        "4h": ("4h", "4小时", "4 小时", "4hr", "240m"),
        "1h": ("1h", "1小时", "1 小时", "1hr", "60m"),
        "5m": ("5m", "5分钟", "5 分钟", "5min"),
        "1m": ("1m", "1分钟", "1 分钟", "1min", "1m周期"),
        "1d": ("1d", "1天", "一天", "日线", "日k", "日K"),
    }
    for timeframe, tokens in mapping.items():
        if any(token.lower() in normalized for token in tokens):
            return timeframe
    return None


def _normalize_timeframe(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in _valid_timeframe_set():
        return lowered
    return _parse_timeframe(lowered)


def _valid_timeframe_set() -> set[str]:
    return set(_VALID_TIMEFRAMES)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
