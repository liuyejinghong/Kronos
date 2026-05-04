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
