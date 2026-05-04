"""Minimal bilingual i18n support for CLI and quickstart output.

Language is resolved from, in priority order:
1. ``--lang`` CLI option
2. ``KRONOS_LANG`` environment variable
3. ``[runtime] lang`` config setting
4. Default: ``"zh"``
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kronos.common.config import KronosConfig

SUPPORTED_LANGS = ("zh", "en")
_DEFAULT_LANG = "zh"
_current_lang: str | None = None

STRINGS: dict[str, dict[str, str]] = {
    # CLI top-level
    "cli.app.help": {
        "zh": "Kronos — 加密货币量化研究系统",
        "en": "Kronos — crypto-native quantitative research system",
    },
    "cli.data.help": {
        "zh": "数据管理命令",
        "en": "Data management commands",
    },
    "cli.research.help": {
        "zh": "研究工作流命令",
        "en": "Research workflow commands",
    },
    "cli.run.help": {
        "zh": "系统级 Kronos 运行命令",
        "en": "System-level Kronos run commands",
    },
    "cli.agent.help": {
        "zh": "Kronos Agent MVP 命令",
        "en": "Kronos Agent MVP commands",
    },
    # Quickstart
    "quickstart.title": {
        "zh": "Kronos 快速开始",
        "en": "Kronos Quickstart",
    },
    "quickstart.checking_data": {
        "zh": "正在检查本地数据…",
        "en": "Checking local data…",
    },
    "quickstart.generating_sample": {
        "zh": "未找到本地数据，正在生成 7 天 BTCUSDT sample 数据（标记为 synthetic）…",
        "en": "No local data found. Generating 7-day BTCUSDT sample data (marked as synthetic)…",
    },
    "quickstart.sample_ready": {
        "zh": "Sample 数据已生成：{path}",
        "en": "Sample data generated: {path}",
    },
    "quickstart.data_found": {
        "zh": "已找到本地数据，跳过生成。",
        "en": "Local data found, skipping generation.",
    },
    "quickstart.running_research": {
        "zh": "正在运行研究循环（最小窗口，快速验证）…",
        "en": "Running research cycle (minimal window, fast validation)…",
    },
    "quickstart.complete": {
        "zh": "快速开始完成！",
        "en": "Quickstart complete!",
    },
    "quickstart.next_steps": {
        "zh": (
            "下一步：\n"
            "  1. 启动 Web 工作台：cd web && npm run dev\n"
            "  2. 打开浏览器：http://127.0.0.1:3000\n"
            "  3. 配置 DeepSeek API Key 以启用 Agent 研究\n"
            "  4. 同步真实数据：kronos data sync --symbols BTCUSDT,ETHUSDT\n"
            "  5. 运行完整研究：kronos run today"
        ),
        "en": (
            "Next steps:\n"
            "  1. Start Web workbench: cd web && npm run dev\n"
            "  2. Open browser: http://127.0.0.1:3000\n"
            "  3. Configure DeepSeek API Key to enable Agent research\n"
            "  4. Sync real data: kronos data sync --symbols BTCUSDT,ETHUSDT\n"
            "  5. Run full research: kronos run today"
        ),
    },
    "quickstart.report_ready": {
        "zh": "研究报告已生成：{path}",
        "en": "Research report generated: {path}",
    },
    # Config
    "config.auto_discovered": {
        "zh": "自动发现配置：{path}",
        "en": "Auto-discovered config: {path}",
    },
    "config.not_found": {
        "zh": "未找到配置文件，使用内置默认值。",
        "en": "No config file found, using built-in defaults.",
    },
    # Data seed
    "seed.generating": {
        "zh": "正在为 {symbol} 生成 {days} 天 sample 数据…",
        "en": "Generating {days}-day sample data for {symbol}…",
    },
    "seed.written": {
        "zh": "已写入 {bars} 根 K 线到 {path}",
        "en": "Wrote {bars} bars to {path}",
    },
    # Console REPL
    "console.banner_title": {
        "zh": "║         Kronos Agent — 交互模式          ║",
        "en": "║        Kronos Agent — Interactive        ║",
    },
    "console.banner_hint": {
        "zh": "║    输入数字选择，Ctrl+C 退出             ║",
        "en": "║    Type a number, Ctrl+C to quit         ║",
    },
    "console.env_status": {
        "zh": "环境状态",
        "en": "Environment",
    },
    "console.data_available": {
        "zh": "本地数据: {count} 个币种, {bars} 根 K 线",
        "en": "Local data: {count} symbols, {bars} bars",
    },
    "console.synthetic": {
        "zh": "sample",
        "en": "sample",
    },
    "console.and_more": {
        "zh": "...及其他 {n} 个币种",
        "en": "...and {n} more",
    },
    "console.no_data": {
        "zh": "未找到本地数据",
        "en": "No local data found",
    },
    "console.no_data_hint": {
        "zh": "运行 kronos quickstart 生成 sample 数据，或 kronos data sync 拉取真实行情",
        "en": "Run kronos quickstart for sample data, or kronos data sync for real data",
    },
    "console.model_ready": {
        "zh": "已配置",
        "en": "Configured",
    },
    "console.model_not_configured": {
        "zh": "未配置（Agent 研究功能受限）",
        "en": "Not configured (research features limited)",
    },
    "console.past_runs": {
        "zh": "历史运行: {n} 次",
        "en": "Past runs: {n}",
    },
    "console.no_past_runs": {
        "zh": "尚无历史运行记录",
        "en": "No past runs yet",
    },
    "console.menu_prompt": {
        "zh": "你想做什么？",
        "en": "What would you like to do?",
    },
    "console.menu_market": {
        "zh": "查看可用行情数据",
        "en": "View available market data",
    },
    "console.menu_research": {
        "zh": "开始一轮研究",
        "en": "Start a research cycle",
    },
    "console.menu_candidates": {
        "zh": "查看候选策略池",
        "en": "View candidate strategy pool",
    },
    "console.menu_settings": {
        "zh": "配置模型",
        "en": "Configure models",
    },
    "console.menu_history": {
        "zh": "查看历史运行",
        "en": "View run history",
    },
    "console.menu_exit": {
        "zh": "退出",
        "en": "Exit",
    },
    "console.goodbye": {
        "zh": "再见！",
        "en": "Goodbye!",
    },
    "console.invalid_choice": {
        "zh": "无效选择，请重试。",
        "en": "Invalid choice, try again.",
    },
    "console.market_title": {
        "zh": "可用行情数据",
        "en": "Available Market Data",
    },
    "console.market_next": {
        "zh": "💡 更多币种: kronos data sync --symbols BTCUSDT,ETHUSDT",
        "en": "💡 More symbols: kronos data sync --symbols BTCUSDT,ETHUSDT",
    },
    "console.research_title": {
        "zh": "开始一轮研究",
        "en": "Start a Research Cycle",
    },
    "console.research_gen_data": {
        "zh": "未找到数据，正在生成 sample…",
        "en": "No data found, generating sample…",
    },
    "console.research_data_ready": {
        "zh": "Sample 数据就绪",
        "en": "Sample data ready",
    },
    "console.research_available_symbols": {
        "zh": "可用币种",
        "en": "Available symbols",
    },
    "console.research_select_symbols": {
        "zh": "选择币种（逗号分隔，回车默认前三个）",
        "en": "Select symbols (comma-separated, Enter for default)",
    },
    "console.research_using": {
        "zh": "使用",
        "en": "Using",
    },
    "console.research_goal_prompt": {
        "zh": "研究目标（可选，回车跳过）",
        "en": "Research goal (optional, Enter to skip)",
    },
    "console.research_confirm": {
        "zh": "确认",
        "en": "Confirm",
    },
    "console.research_symbols_label": {
        "zh": "币种",
        "en": "Symbols",
    },
    "console.research_goal_label": {
        "zh": "目标",
        "en": "Goal",
    },
    "console.research_default_goal": {
        "zh": "评估候选因子，找出下一轮最值得验证的方向",
        "en": "Evaluate candidate factors, find next research direction",
    },
    "console.research_proceed": {
        "zh": "开始运行",
        "en": "Proceed",
    },
    "console.research_cancelled": {
        "zh": "已取消。",
        "en": "Cancelled.",
    },
    "console.research_running": {
        "zh": "研究运行中",
        "en": "Research running",
    },
    "console.research_failed": {
        "zh": "研究失败",
        "en": "Research failed",
    },
    "console.research_done": {
        "zh": "研究完成",
        "en": "Research complete",
    },
    "console.research_evaluated": {
        "zh": "评估候选",
        "en": "Evaluated",
    },
    "console.research_promoted": {
        "zh": "晋升",
        "en": "Promoted",
    },
    "console.research_report": {
        "zh": "报告",
        "en": "Report",
    },
    "console.research_next_hint": {
        "zh": "下一步: 打开 Web 工作台查看完整报告 → cd web && npm run dev",
        "en": "Next: Open Web workbench → cd web && npm run dev",
    },
    "console.candidates_title": {
        "zh": "候选策略池",
        "en": "Candidate Strategy Pool",
    },
    "console.candidates_count": {
        "zh": "共 {n} 个候选策略",
        "en": "{n} candidate strategies",
    },
    "console.candidates_hint": {
        "zh": "💡 更多详情: 打开 Web 工作台 → 候选池页面",
        "en": "💡 More details: Open Web workbench → Candidates page",
    },
    "console.no_candidates": {
        "zh": "暂无可研究候选。",
        "en": "No candidates available.",
    },
    "console.settings_title": {
        "zh": "模型配置",
        "en": "Model Settings",
    },
    "console.model_config_hint": {
        "zh": "在 Web 设置页或 ~/.kronos/ 中保存 API Key 以启用 Agent 研究",
        "en": "Save API Key in Web settings or ~/.kronos/ to enable Agent research",
    },
    "console.roles_title": {
        "zh": "Agent 角色",
        "en": "Agent Roles",
    },
    "console.history_title": {
        "zh": "历史运行",
        "en": "Run History",
    },
}


def set_lang(lang: str) -> None:
    """Set the active language for the current process."""
    global _current_lang
    normalized = lang.strip().lower()[:2]
    if normalized not in SUPPORTED_LANGS:
        normalized = _DEFAULT_LANG
    _current_lang = normalized


def get_lang() -> str:
    """Return the active language code."""
    if _current_lang is not None:
        return _current_lang
    return _resolve_lang(None)


def _resolve_lang(config: KronosConfig | None) -> str:
    lang = os.environ.get("KRONOS_LANG", "").strip().lower()[:2]
    if lang in SUPPORTED_LANGS:
        return lang
    if config is not None:
        lang = config.runtime.lang.strip().lower()[:2]
        if lang in SUPPORTED_LANGS:
            return lang
    return _DEFAULT_LANG


def t(key: str, **fmt: object) -> str:
    """Return the translation for *key* in the active language."""
    lang = _current_lang or _resolve_lang(None)
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get(_DEFAULT_LANG, key)
    if fmt:
        text = text.format(**{k: str(v) for k, v in fmt.items()})
    return text


def init_i18n(*, cli_lang: str | None = None, config: KronosConfig | None = None) -> str:
    """Resolve and set the active language. Returns the resolved language code."""
    if cli_lang:
        resolved = cli_lang.strip().lower()[:2]
    elif os.environ.get("KRONOS_LANG"):
        resolved = os.environ["KRONOS_LANG"].strip().lower()[:2]
    elif config is not None:
        resolved = config.runtime.lang.strip().lower()[:2]
    else:
        resolved = _DEFAULT_LANG
    if resolved not in SUPPORTED_LANGS:
        resolved = _DEFAULT_LANG
    set_lang(resolved)
    return resolved
