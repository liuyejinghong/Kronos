"""Conversational Agent REPL — `kronos agent start`.

Zero new dependencies. Context-aware, proactive, user-centric dialogue.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from kronos.common.config import KronosConfig, load_config
from kronos.common.i18n import get_lang, t
from kronos.common.log import get_logger

if TYPE_CHECKING:
    from kronos.research.auto_runner import AutoRunCycleResult

log = get_logger("kronos.agent.console")

# ------------------------------------------------------------------
# Conversation context (remembers what happened)
# ------------------------------------------------------------------


@dataclass
class ConversationContext:
    has_data: bool = False
    has_model: bool = False
    synthetic_data: bool = False
    data_span_days: float | None = None
    data_symbols: list[str] = field(default_factory=list)
    selected_symbols: list[str] = field(default_factory=list)
    selected_strategy: str | None = None
    last_run_id: str | None = None
    turn_count: int = 0
    is_first_time: bool = True
    deepseek_configured: bool = False

    _past_runs: list[Path] = field(default_factory=list)

    def mark_turn(self) -> int:
        self.turn_count += 1
        return self.turn_count


class AgentConsole:
    """Conversational Agent — speaks to the user, remembers context, guides."""

    def __init__(self, *, config: KronosConfig, config_path: str | None = None) -> None:
        self.cfg = config
        self.data_path = Path(config.data.base_path)
        self.lang = get_lang()
        self.ctx = ConversationContext()
        self._scanned = False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            self._greeting()
            self._scan_env()
            self._loop()
        except KeyboardInterrupt:
            self._say("")
            self._say(self._t("conv.goodbye"))
        except EOFError:
            pass

    # ------------------------------------------------------------------
    # Environment scan
    # ------------------------------------------------------------------

    def _scan_env(self) -> None:
        """Lightweight env scan — only list dirs, no data reads."""
        root = self.data_path / "curated"
        if root.exists():
            symbols = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
            if symbols:
                self.ctx.has_data = True
                self.ctx.data_symbols = symbols
                # Quick synthetic check: only read 1 row from first symbol
                try:
                    from kronos.data.storage.query import load
                    df = load(symbols[0], base_path=self.data_path, timeframe="1m")
                    if not df.empty and str(df.iloc[0].get("venue", "")) == "synthetic":
                        self.ctx.synthetic_data = True
                    if not df.empty:
                        span_ms = int(df["event_time"].max()) - int(df["event_time"].min())
                        self.ctx.data_span_days = round(span_ms / 86_400_000, 2)
                except Exception as exc:
                    log.warning(
                        "agent_console.data_scan_failed",
                        symbol=symbols[0],
                        error_type=type(exc).__name__,
                    )

        try:
            from kronos.agent.secrets import LocalSecretStore
            self.ctx.deepseek_configured = LocalSecretStore().get_status("deepseek").configured
        except Exception as exc:
            log.warning(
                "agent_console.secret_scan_failed",
                error_type=type(exc).__name__,
            )
        self.ctx.has_model = self.ctx.deepseek_configured

        exp_root = Path("reports/research/experiments")
        if exp_root.exists():
            self.ctx._past_runs = sorted(
                p for p in exp_root.iterdir() if p.is_dir() and not p.name.startswith(".")
            )
        self.ctx.is_first_time = not _first_run_marker().exists()

        self._scanned = True

    # ------------------------------------------------------------------
    # Greeting
    # ------------------------------------------------------------------

    def _greeting(self) -> None:
        self._say("")
        self._say("Kronos Agent")
        self._say("")
        self._say(self._t("conv.greeting"))
        self._say(self._t("conv.what_i_can_do"))
        self._say("")
        self._say(self._t("conv.checking_env"))

    # ------------------------------------------------------------------
    # Main loop — always conversational, never a raw menu
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        if self.ctx.is_first_time:
            self._first_time_flow()
            self._mark_first_run_complete()
        else:
            self._returning_flow()

    def _first_time_flow(self) -> None:
        """Guide a new user through setup."""
        self._say("")
        if not self.ctx.has_data:
            self._say(self._t("conv.first_time_no_data"))
            self._say("")
            self._say("  [1] " + self._t("conv.gen_sample"))
            self._say("  [2] " + self._t("conv.connect_exchange"))
            self._say("  [3] " + self._t("conv.look_around"))
            self._say("")
            c = self._ask()
            if c == "1":
                self._generate_sample_data()
                self._research_flow()
            elif c == "2":
                self._say(self._t("conv.exchange_hint"))
                self._say("")
            elif c == "3":
                self._look_around()
            else:
                self._research_flow()
        else:
            self._say(self._t("conv.first_time_has_data", syms=", ".join(self.ctx.data_symbols[:3])))
            tag = f" [{self._t('conv.synthetic')}]" if self.ctx.synthetic_data else ""
            span = f", 约 {self.ctx.data_span_days} 天" if self.ctx.data_span_days else ""
            self._say(
                f"  [{self.ctx.data_symbols[0]}{tag}{span}]"
                if self.ctx.synthetic_data
                else f"  [{', '.join(self.ctx.data_symbols[:3])}{span}]"
            )
            if self.ctx.deepseek_configured:
                self._say(self._t("conv.model_ready_short"))
            else:
                self._say(self._t("conv.model_not_ready_short"))
            self._say("")
            self._say("  [1] " + self._t("conv.start_research"))
            self._say("  [2] " + self._t("conv.browse_strategies"))
            self._say("  [3] " + self._t("conv.configure_model"))
            self._say("")
            c = self._ask()
            if c == "1":
                self._research_flow()
            elif c == "2":
                self._browse_strategies()
            elif c == "3":
                self._configure_model()
            elif c == "4":
                self._research_flow()
            else:
                self._browse_strategies()

    def _returning_flow(self) -> None:
        """Pick up where the user left off."""
        self._say("")
        latest = self.ctx._past_runs[-1].name if self.ctx._past_runs else None
        data_str = ", ".join(self.ctx.data_symbols[:3])
        model_str = self._t("conv.model_ready_short") if self.ctx.deepseek_configured else self._t("conv.model_not_ready_short")
        self._say(self._t("conv.welcome_back", syms=data_str, model=model_str))
        if latest:
            self._say(self._t("conv.last_run", run=latest))
        self._say("")
        self._say("  [1] " + self._t("conv.continue_last"))
        self._say("  [2] " + self._t("conv.new_research"))
        self._say("  [3] " + self._t("conv.review_strategies"))
        self._say("  [4] " + self._t("conv.just_browse"))
        self._say("")
        c = self._ask()
        if c in {"1", "2"}:
            self._research_flow()
        elif c == "3":
            self._browse_strategies()
        else:
            self._look_around()

    # ------------------------------------------------------------------
    # Flow: Generate sample data
    # ------------------------------------------------------------------

    def _generate_sample_data(self) -> None:
        from kronos.data.seed import generate_sample_klines
        self._say("")
        self._say(self._t("conv.generating_data"))
        bars = generate_sample_klines("BTCUSDT", base_path=self.data_path, days=7)
        self._say(self._t("conv.data_generated", bars=bars))
        self.ctx.has_data = True
        self.ctx.synthetic_data = True
        self.ctx.data_symbols = ["BTCUSDT"]
        self.ctx.is_first_time = False

    # ------------------------------------------------------------------
    # Flow: Browse strategies (trader-friendly language!)
    # ------------------------------------------------------------------

    def _browse_strategies(self) -> None:
        from kronos.factor.candidates import list_candidate_factors

        candidates = list_candidate_factors()
        if not candidates:
            self._say("")
            self._say(self._t("conv.no_strategies"))
            self._say("")
            self._say(self._t("conv.no_strategies_how"))
            self._say("")
            self._say(self._t("conv.no_strategies_example"))
            self._say("")
            self._say("  [1] " + self._t("conv.create_first"))
            self._say("  [2] " + self._t("conv.back"))
            self._say("")
            c = self._ask()
            if c == "1":
                self._show_strategy_example()
            else:
                self._first_time_flow()
            return

        # Group by lifecycle for trader-friendly display
        active = [c for c in candidates if c.lifecycle_state and c.lifecycle_state.value in ("observe", "redesign", "hypothesis", "experiment_planned", "validating")]
        archived = [c for c in candidates if c.lifecycle_state and c.lifecycle_state.value in ("retired",)]

        self._say("")
        self._say(self._t("conv.strategies_title", n=len(candidates)))
        self._say("")

        if active:
            self._say(self._t("conv.strategies_active"))
            for candidate in active:
                desc = self._describe_strategy(
                    candidate.title or candidate.candidate_id,
                    candidate.family,
                )
                state = (
                    _STATE_LABEL_ZH.get(candidate.lifecycle_state.value, "—")
                    if candidate.lifecycle_state else "—"
                )
                self._say(f"  #{candidate.migration_rank} {desc}  [{state}]")
            self._say("")

        if archived:
            n = len(archived)
            self._say(self._t("conv.strategies_archived", n=n))
            self._say("")
            # Show first 3 archived as examples
            for candidate in archived[:3]:
                desc = self._describe_strategy(
                    candidate.title or candidate.candidate_id,
                    candidate.family,
                )
                state = (
                    _STATE_LABEL_ZH.get(candidate.lifecycle_state.value, "—")
                    if candidate.lifecycle_state else "—"
                )
                self._say(f"  #{candidate.migration_rank} {desc}  [{state}]")

        self._say("")
        self._say(self._strategy_context_line(len(candidates)))
        self._say("")
        self._say("  [1] " + self._t("conv.pick_strategy"))
        self._say("  [2] " + self._t("conv.run_on_all"))
        self._say("  [3] " + self._t("conv.back"))
        self._say("")
        choice = self._ask()
        if choice in {"1", "2"}:
            self.ctx.selected_strategy = active[0].candidate_id if active else candidates[0].candidate_id
            self._research_flow()
        else:
            self._returning_flow()

    def _show_strategy_example(self) -> None:
        """Show the user how to create their first strategy."""
        self._say("")
        self._say("# 在你的 Python 脚本或 Jupyter Notebook 中:")
        self._say("")
        self._say("from kronos.factor.candidates import CandidateFactorSpec, register_candidate")
        self._say("")
        self._say("register_candidate(CandidateFactorSpec(")
        self._say('    candidate_id="my_first_strategy",')
        self._say('    family="trend_momentum",')
        self._say('    title="我的第一个策略",')
        self._say('    source_strategies=("BTCUSDT",),')
        self._say("    migration_rank=1,")
        self._say('    implementation_name="my_strategy_impl",')
        self._say("))")
        self._say("")
        self._say(self._t("conv.example_note"))
        self._say("")
        self._say("  [1] " + self._t("conv.got_it"))
        self._say("")
        self._ask()
        self._say(self._t("conv.strategies_empty_done"))
        self._say("")

    def _describe_strategy(self, title: str, family: str) -> str:
        """Translate internal factor names to trader-friendly descriptions."""
        desc_map: dict[str, str] = {
            "指标 spread regime": "趋势强弱判断 — 用技术指标差值判断市场方向",
            "信号持续性密度": "信号可靠性检测 — 好信号应该持续一段时间",
            "趋势回撤容忍度": "回调承受力 — 判断市场回调是洗盘还是反转",
            "bar 内收盘位置压力": "日内力量对比 — 收盘价靠近高低点说明什么",
            "body-energy 累积": "能量累积 — 跟踪大阳线/大阴线的后续效应",
            "趋势内回踩入场": "趋势回踩 — 在上升趋势回调时入场",
            "midpoint-power 不对称": "买卖力量不对称 — 价格在中点以上的时间占比",
            "range-chop 过滤器": "震荡识别 — 过滤掉横盘无方向的行情",
            "band 位置条件化": "布林带位置 — 价格在带宽中的位置含义",
            "volume drought 过滤器": "缩量识别 — 成交量萎缩往往预示变盘",
            "move-density 因子": "波动密度 — 大波动的聚集程度",
            "多时间框架确认": "多周期确认 — 大小周期方向一致时才入场",
        }
        return desc_map.get(title, title)

    # ------------------------------------------------------------------
    # Flow: Research
    # ------------------------------------------------------------------

    def _research_flow(self) -> None:
        from kronos.data.seed import generate_sample_klines, has_any_data

        self._say("")
        self._say(self._t("conv.research_start"))
        self._say("")

        # Ensure data
        if not has_any_data(self.data_path):
            self._say(self._t("conv.no_data_gen"))
            generate_sample_klines("BTCUSDT", base_path=self.data_path, days=7)
            self.ctx.has_data = True
            self.ctx.synthetic_data = True
            self.ctx.data_symbols = ["BTCUSDT"]

        # Select symbols
        syms = self.ctx.data_symbols or self._list_symbols()
        if not syms:
            self._say(self._t("conv.research_no_symbols"))
            return
        if len(syms) > 1:
            self._say(self._t("conv.research_which_symbols", syms=", ".join(syms[:5])))
            choice = self._input(f"[{','.join(syms[:3])}]: ").strip()
            selected = [s.strip() for s in choice.split(",") if s.strip() in syms] if choice else syms[:3]
        else:
            selected = syms[:1]
            self._say(self._t("conv.research_using_only", sym=selected[0]))
        self.ctx.selected_symbols = selected
        self._say(f"  → {', '.join(selected)}")
        self._say("")

        # Goal
        self._say(self._t("conv.research_goal"))
        self._input(f"  [{self._t('conv.research_goal_default')}]: ").strip()
        self._say("")

        # Run
        self._say(self._t("conv.research_running"))
        self._say(f"  {self._t('conv.loading_data')}")
        self._say(f"  {self._t('conv.computing')}")
        self._say(f"  {self._t('conv.validating')}")
        self._say("")

        try:
            from kronos.factor.bootstrap import registry
            from kronos.factor.candidates import list_candidate_factors
            from kronos.factor.validation.thresholds import ValidationConfig
            from kronos.research import PromotionCriteria, run_auto_research_cycle

            candidates = list_candidate_factors()
            if not candidates:
                self._say(self._t("conv.research_no_candidates"))
                self._browse_strategies()
                return
            watchlist = [c for c in candidates if c.lifecycle_state and c.lifecycle_state.value in ("observe", "redesign")]
            # Use 3 candidates max for interactive speed
            active = watchlist if watchlist else candidates[:3]

            run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-console")
            result = run_auto_research_cycle(
                registry=registry,
                symbols=selected[:2],  # Max 2 symbols for speed
                data_base_path=self.data_path,
                output_base_path=Path("reports/research"),
                run_id=run_id,
                git_commit="agent-console",
                data_snapshot_id="console",
                config_snapshot={
                    "command": "agent start",
                    "symbols": selected,
                    "data_snapshot_id": "console",
                    "data_kind": "synthetic" if self.ctx.synthetic_data else "local",
                },
                candidate_specs=active,
                watchlist_candidate_specs=watchlist,
                timeframe="1m",
                since=None,
                until=None,
                validation_config=ValidationConfig(periods=[1, 5]),
                criteria=PromotionCriteria(),
                train_size=60,
                validation_size=20,
                test_size=20,
                step_size=20,
                sync_data=False,
                min_history_days=7,
            )
        except Exception as exc:
            self._say(self._t("conv.research_failed", err=str(exc)))
            return

        self.ctx.last_run_id = run_id
        self._say(self._t("conv.research_done"))
        summary = result.summary()
        evaluated = summary.get("evaluated", 0)
        promoted = summary.get("promoted", 0)
        self._say(
            f"  {evaluated} {self._t('conv.strategies_evaluated')}, "
            f"{promoted} {self._t('conv.strategies_promoted')}"
        )
        if result.artifact_paths.get("auto_run_report"):
            self._say(f"  {self._t('conv.report_at')}: {result.artifact_paths['auto_run_report']}")
        self._say("")
        self._say(self._research_next_line(result, len(active)))
        self._say("")
        self._say("  [1] " + self._t("conv.tune_params"))
        self._say("  [2] " + self._t("conv.another_symbol"))
        self._say("  [3] " + self._t("conv.open_web"))
        self._say("  [4] " + self._t("conv.done"))
        self._say("")
        c = self._ask()
        if c == "1":
            self._show_tuning_guide()
            self._returning_flow()
        elif c in {"2", "3"}:
            self._returning_flow()
        else:
            self._say(self._t("conv.goodbye"))
            sys.exit(0)

    # ------------------------------------------------------------------
    # Flow: Look around / explore
    # ------------------------------------------------------------------

    def _look_around(self) -> None:
        from kronos.factor.candidates import list_candidate_factors
        candidates = list_candidate_factors()
        self._say("")
        self._say(self._t("conv.explore_title"))
        self._say("")
        self._say(self._t("conv.explore_line1", n=len(candidates)))
        self._say(self._t("conv.explore_line2", syms=", ".join(self.ctx.data_symbols) if self.ctx.data_symbols else "无"))
        self._say(self._t("conv.explore_line3", model=self._t("conv.yes") if self.ctx.deepseek_configured else self._t("conv.no")))
        self._say("")
        self._say(self._t("conv.explore_prompt"))
        self._say("")
        self._say("  [1] " + self._t("conv.ready_try"))
        self._say("  [2] " + self._t("conv.not_now"))
        self._say("")
        c = self._ask()
        if c == "1":
            self._first_time_flow()
        else:
            self._say(self._t("conv.goodbye"))
            sys.exit(0)

    def _configure_model(self) -> None:
        self._say("")
        self._say(self._t("conv.model_config_title"))
        self._say("")
        self._say(self._t("conv.model_config_how"))
        self._say(self._t("conv.model_config_or"))
        self._say("")
        self._say("  [1] " + self._t("conv.continue_anyway"))
        self._say("  [2] " + self._t("conv.back"))
        self._say("")
        c = self._ask()
        if c == "1":
            self._research_flow()
        else:
            self._first_time_flow()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _say(self, text: str = "") -> None:
        import typer
        typer.echo(text)

    def _ask(self) -> str:
        return self._input("  > ").strip()

    def _input(self, prompt: str) -> str:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return sys.stdin.readline().rstrip("\n")

    def _show_tuning_guide(self) -> None:
        """Show the user how to tune R-breaker parameters."""
        self._say("")
        self._say(self._t("conv.tuning_title"))
        self._say("")
        self._say(self._t("conv.tuning_params"))
        self._say("")
        self._say(self._t("conv.tuning_how"))
        self._say("")
        self._say(self._t("conv.tuning_example"))
        self._say("")

    def _strategy_context_line(self, candidate_count: int) -> str:
        span = self.ctx.data_span_days
        if self.ctx.synthetic_data:
            days = f"约 {span} 天" if span is not None else "短窗口"
            return (
                f"当前有 {candidate_count} 个策略。你现在看到的是 {days} sample 数据，"
                "只适合确认流程能跑通，不能判断策略是否赚钱。同步真实行情后再做正式验证。"
            )
        if span is not None and span < 90:
            return (
                f"当前有 {candidate_count} 个策略。本地真实数据约 {span} 天，样本仍偏短；"
                "可以先做试算，但不要把它当成 90 天验证结论。"
            )
        if span is not None:
            return (
                f"当前有 {candidate_count} 个策略。本地数据约 {span} 天，"
                "可以进入较完整的历史验证，但仍不会自动下单。"
            )
        return f"当前有 {candidate_count} 个策略。先确认数据覆盖，再判断哪些值得继续。"

    def _research_next_line(
        self,
        result: AutoRunCycleResult,
        candidate_count: int,
    ) -> str:
        summary = result.summary()
        evaluated = int(summary.get("evaluated", 0))
        promoted = int(summary.get("promoted", 0))
        span = self._result_span_days(result)
        timeframe = result.timeframe
        data_label = "sample 数据" if self.ctx.synthetic_data else "本地数据"
        if promoted > 0:
            return (
                f"本轮用 {data_label}（{timeframe}，约 {span} 天）评估了 {evaluated} 个策略，"
                f"{promoted} 个进入深度研究；这仍不是模拟盘或实盘结论。"
            )
        if self.ctx.synthetic_data:
            return (
                f"本轮用 {data_label}（{timeframe}，约 {span} 天）评估了 {evaluated} 个策略，"
                "0 个通过验证。sample 只证明流程能跑通，下一步应先同步真实行情，再重新验证。"
            )
        if span < 90:
            return (
                f"本轮用 {data_label}（{timeframe}，约 {span} 天）评估了 {evaluated} 个策略，"
                "0 个通过验证。样本仍短，建议补足更长历史后再判断是否调参或放弃。"
            )
        return (
            f"本轮用 {data_label}（{timeframe}，约 {span} 天）评估了 {evaluated} 个策略，"
            f"0 个通过验证。先阅读报告中的失败原因，再决定是否改造这 {candidate_count} 个候选。"
        )

    def _result_span_days(self, result: AutoRunCycleResult) -> float:
        spans = [
            float(row.get("span_days", 0.0))
            for row in result.data_coverage
            if row.get("dataset", "").startswith("klines_")
        ]
        if spans:
            return round(max(spans), 2)
        return self.ctx.data_span_days or 0.0

    def _mark_first_run_complete(self) -> None:
        _first_run_marker().parent.mkdir(parents=True, exist_ok=True)
        _first_run_marker().touch()

    def _list_symbols(self) -> list[str]:
        root = self.data_path / "curated"
        if not root.exists():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))

    def _t(self, key: str, **fmt: object) -> str:
        return t(key, **fmt)


# ------------------------------------------------------------------
# Labels
# ------------------------------------------------------------------

_STATE_LABEL_ZH: dict[str, str] = {
    "material_intake": "材料进入", "migration_review": "迁移审查",
    "hypothesis": "假设生成", "experiment_planned": "实验计划",
    "validating": "验证中", "agent_analysis": "Agent 分析",
    "committee_scoring": "投委会评分", "observe": "观察",
    "redesign": "候选改造", "simulate": "模拟盘",
    "live_approval_required": "待实盘审批", "retired": "已验证",
    "": "—",
}
_FAMILY_LABEL_ZH: dict[str, str] = {
    "trend_momentum": "趋势类", "volatility_path": "波动类",
    "mean_reversion": "反转类", "volume_liquidity": "量价类",
    "derivatives": "衍生品类",
}

# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _first_run_marker() -> Path:
    return Path.home() / ".kronos" / ".first_run_completed"


def start_agent_console(*, config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    AgentConsole(config=cfg, config_path=config_path).run()
