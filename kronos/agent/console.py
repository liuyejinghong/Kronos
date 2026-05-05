"""Interactive Agent REPL — `kronos agent start`.

Zero new dependencies. Uses ``input()`` + ``typer.echo()``.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from kronos.common.config import KronosConfig, load_config
from kronos.common.i18n import get_lang, t

if TYPE_CHECKING:
    pass


class AgentConsole:
    """State-machine driven interactive Agent REPL."""

    def __init__(
        self,
        *,
        config: KronosConfig,
        config_path: str | None = None,
    ) -> None:
        self.cfg = config
        self.config_path = config_path
        self.data_path = Path(config.data.base_path)
        self.runtime_path = Path("reports/agent_runtime")
        self.lang = get_lang()
        self.symbols: list[str] = []
        self._running = True

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._print_banner()
        self._welcome()
        while self._running:
            try:
                self._menu()
            except KeyboardInterrupt:
                self._println("")
                self._println(self._T("console.goodbye"))
                break
            except EOFError:
                break

    # ------------------------------------------------------------------
    # Banner + Welcome
    # ------------------------------------------------------------------

    def _print_banner(self) -> None:
        self._println("")
        self._println("╔══════════════════════════════════════════╗")
        self._println(self._T("console.banner_title"))
        self._println(self._T("console.banner_hint"))
        self._println("╚══════════════════════════════════════════╝")
        self._println("")

    def _welcome(self) -> None:
        self._println(f"📊 {self._T('console.env_status')}")
        self._println("")

        # Data — lightweight: only list dirs, no data reads
        symbols = self._list_symbols()
        if symbols:
            self.symbols = symbols
            self._println(f"  ✅ {self._T('console.data_available', count=len(symbols), bars='?')}")
            for sym in symbols[:10]:
                self._println(f"     {sym}")
            if len(symbols) > 10:
                self._println(f"     ... {self._T('console.and_more', n=len(symbols)-10)}")
        else:
            self._println(f"  📭 {self._T('console.no_data')}")
            self._println(f"     {self._T('console.no_data_hint')}")
        self._println("")

        # Model
        configured = self._check_deepseek()
        if configured:
            self._println(f"  ✅ DeepSeek: {self._T('console.model_ready')}")
        else:
            self._println(f"  ⚠️  DeepSeek: {self._T('console.model_not_configured')}")
        self._println("")

        # Runs
        runs = self._list_runs()
        if runs:
            self._println(f"  📋 {self._T('console.past_runs', n=len(runs))}")
        else:
            self._println(f"  📋 {self._T('console.no_past_runs')}")
        self._println("")

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------

    def _menu(self) -> None:
        self._println(self._T("console.menu_prompt"))
        self._println("")
        self._println("  [1] 📈 " + self._T("console.menu_market"))
        self._println("  [2] 🔬 " + self._T("console.menu_research"))
        self._println("  [3] 📋 " + self._T("console.menu_candidates"))
        self._println("  [4] ⚙️  " + self._T("console.menu_settings"))
        self._println("  [5] 📜 " + self._T("console.menu_history"))
        self._println("  [0] 🚪 " + self._T("console.menu_exit"))
        self._println("")

        choice = self._input("> ").strip()
        self._println("")

        if choice == "1":
            self._market()
        elif choice == "2":
            self._research_flow()
        elif choice == "3":
            self._candidates()
        elif choice == "4":
            self._settings()
        elif choice == "5":
            self._history()
        elif choice == "0":
            self._running = False
            self._println(self._T("console.goodbye"))
        else:
            self._println(self._T("console.invalid_choice"))
            self._println("")

    # ------------------------------------------------------------------
    # Sub-flows
    # ------------------------------------------------------------------

    def _market(self) -> None:
        """Show available market data."""
        self._println(f"📈 {self._T('console.market_title')}")
        self._println("")

        symbols = self._list_symbols()
        if not symbols:
            self._println(self._T("console.no_data"))
            self._println(f"  → {self._T('console.no_data_hint')}")
            self._println("")
            return

        for sym in symbols[:10]:
            bars = self._bar_count(sym)
            synthetic = self._is_synthetic(sym)
            tag = f" [{self._T('console.synthetic')}]" if synthetic else ""
            self._println(f"  {sym}: {bars:,} bars{tag}")

        self._println("")
        self._println(self._T("console.market_next"))
        self._println("")

    def _research_flow(self) -> None:
        """Guide user through setting up and running a research cycle."""
        from kronos.data.seed import generate_sample_klines, has_any_data

        self._println(f"🔬 {self._T('console.research_title')}")
        self._println("")

        # Step 1: ensure data
        if not has_any_data(self.data_path):
            self._println(f"  ⏳ {self._T('console.research_gen_data')}")
            generate_sample_klines("BTCUSDT", base_path=self.data_path, days=7)
            self.symbols = self._list_symbols()
            self._println(f"  ✅ {self._T('console.research_data_ready')}")
            self._println("")

        # Step 2: choose symbols
        symbols = self._list_symbols()
        if not symbols:
            self._println(self._T("console.no_data"))
            return

        self._println(f"  {self._T('console.research_available_symbols')}: {', '.join(symbols)}")
        choice = self._input(f"  {self._T('console.research_select_symbols')} [{','.join(symbols[:3])}]: ").strip()
        if choice:
            selected = [s.strip() for s in choice.split(",") if s.strip() in symbols]
        else:
            selected = symbols[:3]
        self._println(f"  → {self._T('console.research_using')}: {', '.join(selected)}")
        self._println("")

        # Step 3: goal
        goal = self._input(f"  {self._T('console.research_goal_prompt')}: ").strip()
        self._println("")

        # Step 4: confirm
        self._println(f"  ═══ {self._T('console.research_confirm')} ═══")
        self._println(f"  {self._T('console.research_symbols_label')}: {', '.join(selected)}")
        self._println(f"  {self._T('console.research_goal_label')}: {goal or self._T('console.research_default_goal')}")
        self._println("")
        ok = self._input(f"  {self._T('console.research_proceed')} [Y/n]: ").strip().lower()
        if ok and ok != "y":
            self._println(f"  {self._T('console.research_cancelled')}")
            self._println("")
            return

        # Step 5: run
        self._println("")
        self._println(f"  ⏳ {self._T('console.research_running')} …")
        self._println("")

        try:
            from kronos.factor.bootstrap import registry
            from kronos.factor.validation.thresholds import ValidationConfig
            from kronos.research import PromotionCriteria, run_auto_research_cycle

            run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-agent-console")
            result = run_auto_research_cycle(
                registry=registry,
                symbols=selected,
                data_base_path=self.data_path,
                output_base_path=Path("reports/research"),
                run_id=run_id,
                git_commit="agent-console",
                data_snapshot_id="console",
                config_snapshot={"command": "agent start", "symbols": selected},
                candidate_specs=[],
                watchlist_candidate_specs=[],
                timeframe="1m",
                since=None,
                until=None,
                validation_config=ValidationConfig(periods=[1, 5]),
                criteria=PromotionCriteria(),
                train_size=120,
                validation_size=40,
                test_size=40,
                step_size=40,
                sync_data=False,
                min_history_days=1,
            )
        except Exception as exc:
            self._println(f"  ❌ {self._T('console.research_failed')}: {exc}")
            self._println("")
            return

        self._println(f"  ✅ {self._T('console.research_done')}")
        self._println(f"     Run ID: {run_id}")
        summary = result.summary()
        self._println(f"     {self._T('console.research_evaluated')}: {summary.get('evaluated', '—')}")
        self._println(f"     {self._T('console.research_promoted')}: {summary.get('promoted', '—')}")
        if result.artifact_paths.get("auto_run_report"):
            self._println(f"     {self._T('console.research_report')}: {result.artifact_paths['auto_run_report']}")
        self._println("")
        self._println(f"  💡 {self._T('console.research_next_hint')}")
        self._println("")

    def _candidates(self) -> None:
        """Show current candidate pool."""
        from kronos.factor.candidates import list_candidate_factors

        self._println(f"📋 {self._T('console.candidates_title')}")
        self._println("")

        candidates = list_candidate_factors()
        if not candidates:
            self._println(self._T("console.no_candidates"))
            self._println("")
            return

        self._println(f"  {self._T('console.candidates_count', n=len(candidates))}")
        self._println("")
        _STATE_LABELS: dict[str, str] = {
            "material_intake": "材料进入", "migration_review": "迁移审查",
            "hypothesis": "假设生成", "experiment_planned": "实验计划",
            "validating": "验证中", "agent_analysis": "Agent 分析",
            "committee_scoring": "投委会评分", "observe": "观察",
            "redesign": "候选改造", "simulate": "模拟盘",
            "live_approval_required": "待实盘审批", "retired": "淘汰",
        }
        for c in candidates[:10]:
            raw_state = c.lifecycle_state.value if c.lifecycle_state else ""
            state_label = _STATE_LABELS.get(raw_state, raw_state) if raw_state else "—"
            self._println(f"  {c.migration_rank:2d}. {c.title}  [{c.family}]  → {state_label}")
        self._println("")
        self._println(f"  💡 {self._T('console.candidates_hint')}")
        self._println("")

    def _settings(self) -> None:
        """Show and guide model configuration."""
        self._println(f"⚙️  {self._T('console.settings_title')}")
        self._println("")

        configured = self._check_deepseek()

        if configured:
            self._println(f"  ✅ DeepSeek: {self._T('console.model_ready')}")
        else:
            self._println(f"  ⚠️  DeepSeek: {self._T('console.model_not_configured')}")
            self._println(f"     {self._T('console.model_config_hint')}")

        # Show roles
        from kronos.agent.roles import default_agent_roles
        self._println("")
        self._println(f"  {self._T('console.roles_title')}:")
        for role in default_agent_roles():
            self._println(f"     {role.name_zh} → {role.model_name}")
        self._println("")

    def _history(self) -> None:
        """Show past experiment runs."""
        self._println(f"📜 {self._T('console.history_title')}")
        self._println("")

        runs = self._list_runs()
        if not runs:
            self._println(self._T("console.no_past_runs"))
            self._println("")
            return

        for run_dir in sorted(runs, reverse=True)[:10]:
            summary_file = run_dir / "auto_run_summary.json"
            report_file = run_dir / "auto_run_report.md"
            ts = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M") if run_dir.exists() else "?"
            has_report = "📄" if report_file.exists() or summary_file.exists() else "  "
            self._println(f"  {has_report} {run_dir.name}  ({ts})")
        self._println("")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _list_symbols(self) -> list[str]:
        """Discover symbols from curated data directory."""
        root = self.data_path / "curated"
        if not root.exists():
            return []
        return sorted(
            p.name for p in root.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )

    def _bar_count(self, symbol: str) -> int:
        """Quick bar count using coverage()."""
        from kronos.data.storage.query import coverage as cov
        infos = cov(symbol, base_path=self.data_path, datasets=["klines_1m"])
        return infos[0].bar_count if infos else 0

    def _is_synthetic(self, symbol: str) -> bool:
        """Check if data is synthetic (sample, not real)."""
        try:
            from kronos.data.storage.query import load
            df = load(symbol, base_path=self.data_path, timeframe="1m")
            if df.empty:
                return False
            return str(df["venue"].iloc[0]) == "synthetic"
        except Exception:
            return False

    def _check_deepseek(self) -> bool:
        """Check if DeepSeek API key is configured."""
        try:
            from kronos.agent.secrets import LocalSecretStore
            status = LocalSecretStore().get_status("deepseek")
            return status.configured
        except Exception:
            return False

    def _list_runs(self) -> list[Path]:
        """List past experiment run directories."""
        exp_root = Path("reports/research/experiments")
        if not exp_root.exists():
            return []
        return sorted(
            p for p in exp_root.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )

    def _input(self, prompt: str) -> str:
        """Thin wrapper around input() for testability."""
        # Use sys.stdin directly for test compatibility
        import sys
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return sys.stdin.readline().rstrip("\n")

    def _println(self, text: str = "") -> None:
        """Print a line, no markup."""
        import typer
        typer.echo(text)

    def _T(self, key: str, **fmt: object) -> str:
        """Translate with formatting."""
        return t(key, **fmt)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def start_agent_console(
    *,
    config_path: str | None = None,
) -> None:
    """Launch the interactive Agent console."""
    cfg = load_config(config_path)
    console = AgentConsole(config=cfg, config_path=config_path)
    console.run()
