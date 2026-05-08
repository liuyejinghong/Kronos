# ruff: noqa: RUF001
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
        "zh": "第 1 步 / 检查本地数据…",
        "en": "Step 1 / Checking local data…",
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
        "zh": "第 3 步 / 正在运行最小研究循环（R-breaker × BTCUSDT）…",
        "en": "Step 3 / Running minimal research cycle (R-breaker × BTCUSDT)…",
    },
    "quickstart.registering_strategies": {
        "zh": "第 2 步 / 正在注册内置策略…",
        "en": "Step 2 / Registering built-in strategies…",
    },
    "quickstart.strategies_evaluated": {
        "zh": "个策略已评估",
        "en": " strategies evaluated",
    },
    "quickstart.report_at": {
        "zh": "研究报告",
        "en": "Report",
    },
    "quickstart.report_latest_hint": {
        "zh": "直接查看最新报告",
        "en": "Read the latest report directly",
    },
    "quickstart.research_skipped": {
        "zh": "跳过研究（{exc}）",
        "en": "Research skipped ({exc})",
    },
    "quickstart.trust_title": {
        "zh": "快速开始结果",
        "en": "Quickstart Result",
    },
    "quickstart.benchmark": {
        "zh": "市场基准",
        "en": "Market Benchmark",
    },
    "quickstart.benchmark_period": {
        "zh": "数据周期",
        "en": "Period",
    },
    "quickstart.days": {
        "zh": "天",
        "en": "days",
    },
    "quickstart.benchmark_buyhold": {
        "zh": "同期持有 BTC",
        "en": "Buy & hold BTC",
    },
    "quickstart.benchmark_note": {
        "zh": "（策略收益需扣除手续费后才能与此对比）",
        "en": "(strategy returns must deduct fees before comparison)",
    },
    "quickstart.benchmark_synthetic": {
        "zh": "使用模拟数据，无法提供可信基准对比。同步真实行情后可查看。",
        "en": "Using synthetic data — no reliable benchmark available. Sync real market data to compare.",
    },
    "quickstart.next_steps_docker": {
        "zh": (
            "Docker 环境下，下一步先做这件事：\n"
            "  1. 读最新报告: docker compose run --rm kronos uv run kronos report latest\n"
            "读完结论后再继续：\n"
            "  · 起草策略想法: docker compose run --rm kronos uv run kronos strategy draft --prompt \"我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期\"\n"
            "  · 同步真实数据: docker compose run --rm kronos uv run kronos data sync --symbols BTCUSDT --since 2026-01-01\n"
            "  · 进入 Agent: docker compose run --rm kronos uv run kronos agent start\n"
            "  · 当前版本只输出研究报告，不会启动模拟盘或真实下单。"
        ),
        "en": (
            "In Docker, do this first:\n"
            "  1. Read latest report: docker compose run --rm kronos uv run kronos report latest\n"
            "After you understand the conclusion:\n"
            "  · Draft strategy idea: docker compose run --rm kronos uv run kronos strategy draft --prompt \"I want BTCUSDT R-breaker intraday breakout on 15m\"\n"
            "  · Sync real data: docker compose run --rm kronos uv run kronos data sync --symbols BTCUSDT --since 2026-01-01\n"
            "  · Enter Agent: docker compose run --rm kronos uv run kronos agent start\n"
            "  · This version only writes research reports; it does not start paper trading or live orders."
        ),
    },
    "quickstart.no_benchmark_data": {
        "zh": "无法计算（数据不足）",
        "en": "Cannot compute (insufficient data)",
    },
    "quickstart.strategies_promoted_label": {
        "zh": "通过验证",
        "en": "Passed validation",
    },
    "quickstart.verdict_none_promoted": {
        "zh": "当前没有策略通过验证。这在首次运行中很常见：",
        "en": "No strategies passed validation. This is common on first run:",
    },
    "quickstart.verdict_none_reason": {
        "zh": "策略需要足够长的真实数据才能形成可信结论。sample 数据只是演示流程，建议用 kronos data sync 拉取真实行情后重跑。",
        "en": "Strategies need sufficient real data for reliable conclusions. Sample data demonstrates the flow — sync real data with kronos data sync and re-run.",
    },
    "quickstart.verdict_promoted": {
        "zh": "有策略通过了验证！查看报告了解详情。",
        "en": "Strategies passed validation! Check the report for details.",
    },
    "quickstart.no_evaluation": {
        "zh": "没有完成策略评估。检查数据和策略配置后重试。",
        "en": "No strategies were evaluated. Check data and strategy config, then retry.",
    },
    "quickstart.what_next_title": {
        "zh": "接下来可以做什么",
        "en": "What to do next",
    },
    "quickstart.complete": {
        "zh": "快速开始完成！",
        "en": "Quickstart complete!",
    },
    "quickstart.next_steps": {
        "zh": (
            "下一步先做这件事：\n"
            "  1. 直接查看最新报告：kronos report latest\n"
            "读完结论后再继续：\n"
            "  · 起草策略想法：kronos strategy draft --prompt \"我想做 BTCUSDT 的 R-breaker 日内突破, 15m 周期\"\n"
            "  · 同步真实数据：kronos data sync --symbols BTCUSDT,ETHUSDT --since 2026-01-01\n"
            "  · 启动 Web 工作台：cd web && npm run dev\n"
            "  · 当前版本只输出研究报告，不会启动模拟盘或真实下单。"
        ),
        "en": (
            "Do this first:\n"
            "  1. Read the latest report directly: kronos report latest\n"
            "After you understand the conclusion:\n"
            "  · Draft strategy idea: kronos strategy draft --prompt \"I want BTCUSDT R-breaker intraday breakout on 15m\"\n"
            "  · Sync real data: kronos data sync --symbols BTCUSDT,ETHUSDT --since 2026-01-01\n"
            "  · Start Web workbench: cd web && npm run dev\n"
            "  · This version only writes research reports; it does not start paper trading or live orders."
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
    # Conversational Agent
    "conv.greeting": {
        "zh": "你好！我是 Kronos，一个加密货币量化研究助手。",
        "en": "Hello! I'm Kronos, a crypto quantitative research assistant.",
    },
    "conv.what_i_can_do": {
        "zh": "我可以帮你把策略想法起草成配置，分析历史表现，或者继续推进新的研究方向。",
        "en": "I can draft strategy ideas into configs, analyze historical performance, or help you continue research directions.",
    },
    "conv.assistant_focus": {
        "zh": "我先判断当前结果能不能信，再给你最短的下一步。",
        "en": "I'll first judge whether the current result is reliable, then give you the shortest next step.",
    },
    "conv.checking_env": {
        "zh": "正在检查你的环境…",
        "en": "Checking your environment…",
    },
    "conv.first_time_no_data": {
        "zh": "你还没有行情数据。先选一条最短路径：",
        "en": "You don't have market data yet. Pick the shortest path:",
    },
    "conv.gen_sample": {
        "zh": "生成 7 天 BTC 模拟数据，先体验一下",
        "en": "Generate 7 days of BTC sample data to try things out",
    },
    "conv.connect_exchange": {
        "zh": "连接交易所拉取真实数据",
        "en": "Connect to an exchange for real data",
    },
    "conv.look_around": {
        "zh": "先随便看看，等会儿再弄数据",
        "en": "Just look around for now",
    },
    "conv.exchange_hint": {
        "zh": "运行 kronos data sync --symbols BTCUSDT --since 2026-01-01 从 Binance 拉取公开行情。需要网络连接，不需要 API Key。",
        "en": "Run kronos data sync --symbols BTCUSDT --since 2026-01-01 to pull public Binance market data. Requires network access, no API key.",
    },
    "conv.first_time_has_data": {
        "zh": "你已经有一些数据了（{syms} 等），可以直接开始。",
        "en": "You already have some data ({syms} and more). Ready to start.",
    },
    "conv.model_ready_short": {"zh": "AI 模型已就绪", "en": "AI model ready"},
    "conv.model_not_ready_short": {"zh": "AI 模型未配置", "en": "AI model not configured"},
    "conv.start_research": {
        "zh": "直接看当前结果",
        "en": "View current results",
    },
    "conv.browse_strategies": {
        "zh": "看看策略池",
        "en": "Browse the strategy pool",
    },
    "conv.draft_strategy": {
        "zh": "描述想法，先起草配置",
        "en": "Describe an idea and draft a config",
    },
    "conv.configure_model": {
        "zh": "怎么配置 AI 模型？",
        "en": "How do I configure the AI model?",
    },
    "conv.welcome_back": {
        "zh": "欢迎回来。当前环境: {syms} | {model}。",
        "en": "Welcome back. Environment: {syms} | {model}.",
    },
    "conv.last_run": {
        "zh": "上次运行: {run}",
        "en": "Last run: {run}",
    },
    "conv.continue_last": {
        "zh": "继续上次",
        "en": "Continue last run",
    },
    "conv.new_research": {
        "zh": "开新一轮",
        "en": "Start a new run",
    },
    "conv.review_strategies": {
        "zh": "看策略池",
        "en": "Review the pool",
    },
    "conv.just_browse": {
        "zh": "先看看",
        "en": "Browse first",
    },
    "conv.generating_data": {
        "zh": "好的，先生成 7 天 BTC sample 数据…",
        "en": "OK, generating 7 days of BTC sample data first…",
    },
    "conv.data_generated": {
        "zh": "数据已就绪 — {bars} 根 K 线。先看结果，再决定下一步。",
        "en": "Data ready — {bars} bars. View the result first, then choose the next step.",
    },
    "conv.synthetic": {"zh": "模拟数据", "en": "synthetic"},
    "conv.no_strategies": {
        "zh": "你还没有定义任何策略。Kronos 不会预装别人的策略。",
        "en": "You haven't defined any strategies yet. Kronos doesn't ship pre-loaded strategies.",
    },
    "conv.no_strategies_how": {
        "zh": "你可以先用自然语言描述想法。Kronos 会生成概要和 TOML 草案，然后按三步推进。",
        "en": "You can describe an idea in natural language first. Kronos will write a summary and TOML draft, then guide you through three gates.",
    },
    "conv.no_strategies_example": {
        "zh": "要先起草一个 R-breaker 策略吗？",
        "en": "Want to draft an R-breaker strategy first?",
    },
    "conv.create_first": {
        "zh": "好的，我来描述策略想法",
        "en": "Yes, I'll describe my strategy idea",
    },
    "conv.got_it": {
        "zh": "明白了",
        "en": "Got it",
    },
    "conv.research_no_candidates": {
        "zh": "你还没有定义任何策略。先把策略想法起草成配置，再进入研究验证。",
        "en": "You haven't defined any strategies yet. Draft an idea into a config before research validation.",
    },
    "conv.strategy_draft_title": {
        "zh": "请描述你的策略想法。",
        "en": "Describe your strategy idea.",
    },
    "conv.strategy_draft_hint": {
        "zh": "当前首版支持 R-breaker 日内突破。请说清楚品种和周期，例如：我想做 BTCUSDT 的 R-breaker 日内突破，15m 周期。",
        "en": "This first version supports R-breaker intraday breakout. Include symbols and timeframe, for example: I want BTCUSDT R-breaker intraday breakout on 15m.",
    },
    "conv.strategy_draft_empty": {
        "zh": "没有收到策略描述，先不生成草案。",
        "en": "No strategy description received, so no draft was generated.",
    },
    "conv.strategy_draft_failed": {
        "zh": "策略起草失败：{err}",
        "en": "Strategy draft failed: {err}",
    },
    "conv.strategies_title": {
        "zh": "这里有 {n} 个策略，按关注度排列：",
        "en": "Here are {n} strategies, ranked by relevance:",
    },
    "conv.strategies_active": {
        "zh": "🔥 值得关注的:",
        "en": "🔥 Worth your attention:",
    },
    "conv.strategies_archived": {
        "zh": "📦 还有 {n} 个已验证过的策略（不太适合当前市场）",
        "en": "📦 {n} more have been validated (less suitable for current market)",
    },
    "conv.strategies_prompt": {
        "zh": "先确认数据覆盖，再判断哪些策略值得继续。",
        "en": "Check data coverage first, then decide which strategies deserve follow-up.",
    },
    "conv.pick_strategy": {
        "zh": "选一个策略，帮我分析",
        "en": "Pick a strategy to analyze",
    },
    "conv.run_on_all": {
        "zh": "全部跑一遍看看",
        "en": "Run analysis on all of them",
    },
    "conv.back": {"zh": "返回", "en": "Go back"},
    "conv.research_start": {
        "zh": "好的，我来帮你做一轮策略分析。",
        "en": "OK, let me run a strategy analysis for you.",
    },
    "conv.no_data_gen": {
        "zh": "需要一些数据，正在生成…",
        "en": "Need some data, generating…",
    },
    "conv.research_no_symbols": {
        "zh": "没有找到可用的交易品种。请先准备数据。",
        "en": "No trading symbols found. Please prepare data first.",
    },
    "conv.research_which_symbols": {
        "zh": "可用的交易品种: {syms}。你想在哪些上面跑？（逗号分隔，回车用默认）",
        "en": "Available symbols: {syms}. Which ones to analyze? (comma-separated, Enter for default)",
    },
    "conv.research_using_only": {
        "zh": "只有 {sym} 有数据，那我就分析这个。",
        "en": "Only {sym} has data, analyzing that.",
    },
    "conv.research_goal": {
        "zh": "你有什么特别想研究的吗？（回车跳过）",
        "en": "Anything specific you want to research? (Enter to skip)",
    },
    "conv.research_goal_default": {
        "zh": "看看哪些策略值得继续关注",
        "en": "Find which strategies are worth following up",
    },
    "conv.research_running": {
        "zh": "开始分析…",
        "en": "Starting analysis…",
    },
    "conv.loading_data": {
        "zh": "  加载数据…",
        "en": "  Loading data…",
    },
    "conv.computing": {
        "zh": "  计算信号…",
        "en": "  Computing signals…",
    },
    "conv.validating": {
        "zh": "  验证结果…",
        "en": "  Validating results…",
    },
    "conv.research_done": {
        "zh": "分析完成！",
        "en": "Analysis complete!",
    },
    "conv.strategies_evaluated": {
        "zh": "个策略已评估",
        "en": " strategies evaluated",
    },
    "conv.strategies_promoted": {
        "zh": "个通过验证",
        "en": " passed validation",
    },
    "conv.report_at": {
        "zh": "完整报告",
        "en": "Full report",
    },
    "conv.research_next": {
        "zh": "先阅读报告里的失败原因，再决定同步数据、改参数或放弃。",
        "en": "Read the report's failure reasons before syncing more data, tuning parameters, or retiring the idea.",
    },
    "conv.open_web": {
        "zh": "打开 Web 工作台看完整报告",
        "en": "Open Web workbench for full report",
    },
    "conv.another_run": {
        "zh": "换个币种再跑一次",
        "en": "Run again with different symbols",
    },
    "conv.done": {
        "zh": "今天就到这",
        "en": "That's enough for today",
    },
    "conv.tune_params": {
        "zh": "调整 R-breaker 参数再跑一次",
        "en": "Tune R-breaker parameters and re-run",
    },
    "conv.another_symbol": {
        "zh": "换个币种再跑一次",
        "en": "Run on a different symbol",
    },
    "conv.tuning_title": {
        "zh": "参数调整指南",
        "en": "Parameter Tuning Guide",
    },
    "conv.tuning_params": {
        "zh": "R-breaker 可调参数: volatility_multiplier (突破倍数, 默认1.5), atr_period (ATR周期, 默认14), universe.symbols, universe.timeframe",
        "en": "R-breaker params: volatility_multiplier (default 1.5), atr_period (default 14), universe.symbols, universe.timeframe",
    },
    "conv.tuning_how": {
        "zh": "先用 kronos strategy init-r-breaker 生成 TOML；改完参数后，用 smoke-test 空跑确认信号能算出来，通过后再 register 进入候选池。",
        "en": "Create TOML with kronos strategy init-r-breaker first. After editing params, use smoke-test as a dry run, then register it into the candidate pool after it passes.",
    },
    "conv.tuning_example": {
        "zh": "常见调整: 震荡市 → 降低 volatility_multiplier (1.0-1.2) / 趋势市 → 提高 volatility_multiplier (1.8-2.5)",
        "en": "Common: reduce volatility_multiplier (1.0-1.2) in range-bound / increase volatility_multiplier (1.8-2.5) in trending",
    },
    "conv.explore_title": {
        "zh": "好的，先看看有什么。",
        "en": "OK, let's see what's here.",
    },
    "conv.explore_line1": {
        "zh": "系统里有 {n} 个策略模板，是从传统市场迁移过来的。",
        "en": "The system has {n} strategy templates, migrated from traditional markets.",
    },
    "conv.explore_line2": {
        "zh": "数据: {syms}",
        "en": "Data: {syms}",
    },
    "conv.explore_line3": {
        "zh": "AI 模型: {model}",
        "en": "AI model: {model}",
    },
    "conv.yes": {"zh": "已配置", "en": "configured"},
    "conv.no": {"zh": "未配置", "en": "not configured"},
    "conv.explore_prompt": {
        "zh": "准备好开始了吗？",
        "en": "Ready to get started?",
    },
    "conv.ready_try": {
        "zh": "准备好了，帮我准备数据开始吧",
        "en": "Ready, help me get data and start",
    },
    "conv.not_now": {
        "zh": "下次再说",
        "en": "Maybe next time",
    },
    "conv.model_config_title": {
        "zh": "要使用 AI 驱动的策略分析，需要 DeepSeek API Key。",
        "en": "AI-driven strategy analysis requires a DeepSeek API Key.",
    },
    "conv.model_config_how": {
        "zh": "获取方式: 访问 platform.deepseek.com → API Keys → 创建 → 复制 Key",
        "en": "Get one: visit platform.deepseek.com → API Keys → Create → Copy key",
    },
    "conv.model_config_or": {
        "zh": "然后通过 Web 工作台的设置页面保存，或者运行: kronos agent configure --provider deepseek --api-key YOUR_KEY",
        "en": "Then save via Web workbench Settings, or run: kronos agent configure --provider deepseek --api-key YOUR_KEY",
    },
    "conv.continue_anyway": {
        "zh": "先不管，继续用确定性分析",
        "en": "Continue with deterministic analysis only",
    },
    "conv.research_failed": {
        "zh": "分析过程中出错了: {err}。请检查数据和配置，然后重试。",
        "en": "Analysis failed: {err}. Check your data and config, then retry.",
    },
    "conv.goodbye": {
        "zh": "再见！需要分析策略的时候随时回来。",
        "en": "Goodbye! Come back anytime you want to analyze strategies.",
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
