# ruff: noqa: RUF001
"""Auto-run orchestration for repeatable product-facing research cycles."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kronos.common.errors import DataError
from kronos.data.storage.query import coverage
from kronos.data.sync import sync_all
from kronos.research.experiments.artifacts import experiment_root
from kronos.research.watchlist_evidence import (
    WatchlistEvidenceReviewResult,
    run_watchlist_evidence_review,
)
from kronos.research.workbench import ResearchWorkbenchResult, run_research_workbench

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from kronos.factor.candidates import CandidateFactorSpec
    from kronos.factor.registry import FactorRegistry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research.promotion import PromotionCriteria


@dataclass(frozen=True)
class AutoRunCycleResult:
    """Result wrapper for one automatic research cycle."""

    run_id: str
    started_at: str
    finished_at: str
    symbols: list[str]
    timeframe: str
    sync_requested: bool
    sync_results: dict[str, dict[str, int]]
    data_coverage: list[dict[str, Any]]
    workbench: ResearchWorkbenchResult
    evidence_reviews: list[WatchlistEvidenceReviewResult]
    evidence_blockers: list[dict[str, str]]
    artifact_paths: dict[str, str]

    def summary(self) -> dict[str, Any]:
        workbench_summary = self.workbench.summary()
        return {
            "run_id": self.run_id,
            "readiness": workbench_summary["readiness"],
            "evaluated": workbench_summary["evaluated"],
            "promoted": workbench_summary["promoted"],
            "not_promoted": workbench_summary["not_promoted"],
            "skipped": workbench_summary["skipped"],
            "watchlist": workbench_summary["watchlist"],
            "sync_requested": self.sync_requested,
            "evidence_reviews": len(self.evidence_reviews),
            "evidence_blockers": len(self.evidence_blockers),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "sync_requested": self.sync_requested,
            "sync_results": self.sync_results,
            "data_coverage": self.data_coverage,
            "workbench": self.workbench.to_dict(),
            "evidence_reviews": [review.to_dict() for review in self.evidence_reviews],
            "evidence_blockers": self.evidence_blockers,
            "artifact_paths": self.artifact_paths,
        }


def run_auto_research_cycle(
    *,
    registry: FactorRegistry,
    symbols: list[str],
    data_base_path: str | Path,
    output_base_path: str | Path,
    run_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    candidate_specs: Sequence[CandidateFactorSpec],
    watchlist_candidate_specs: Sequence[CandidateFactorSpec],
    factor_versions: Mapping[str, str] | None = None,
    timeframe: str = "1m",
    since: str | int | None = None,
    until: str | int | None = None,
    validation_config: ValidationConfig | None = None,
    criteria: PromotionCriteria | None = None,
    train_size: int = 720,
    validation_size: int = 360,
    test_size: int = 360,
    step_size: int | None = 360,
    sync_data: bool = False,
    sync_since: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
    min_history_days: int = 90,
) -> AutoRunCycleResult:
    """Run one deterministic research cycle and write a daily report.

    The cycle is intentionally one-shot: callers can schedule it with cron,
    launchd, or another runner without giving Kronos trading authority.
    """
    if not symbols:
        raise DataError("auto research cycle requires at least one symbol")
    if not candidate_specs:
        raise DataError("auto research cycle requires at least one candidate")

    output_path = Path(output_base_path)
    data_path = Path(data_base_path)
    run_root = experiment_root(output_path, run_id)
    started_at = _now_iso()
    sync_results: dict[str, dict[str, int]] = {}
    if sync_data:
        sync_results = sync_all(
            symbols,
            base_path=data_path,
            since=sync_since,
            max_retries=max_retries,
            request_interval_ms=request_interval_ms,
        )
    data_coverage = _data_coverage_snapshot(symbols, data_path, timeframe)

    workbench = run_research_workbench(
        registry=registry,
        symbols=symbols,
        data_base_path=data_path,
        output_base_path=output_path,
        batch_id=f"{run_id}-workbench",
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot={
            **config_snapshot,
            "command": "research auto-run",
            "auto_run_id": run_id,
            "auto_run_stage": "workbench",
            "sync_data": sync_data,
        },
        candidate_specs=candidate_specs,
        factor_versions=factor_versions,
        timeframe=timeframe,
        since=since,
        until=until,
        validation_config=validation_config,
        criteria=criteria,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=step_size,
    )

    evidence_reviews: list[WatchlistEvidenceReviewResult] = []
    evidence_blockers: list[dict[str, str]] = []
    for candidate_spec in watchlist_candidate_specs:
        try:
            evidence_reviews.append(
                run_watchlist_evidence_review(
                    registry=registry,
                    symbols=symbols,
                    data_base_path=data_path,
                    output_base_path=output_path,
                    batch_id=f"{run_id}-evidence-{candidate_spec.candidate_id}",
                    candidate_spec=candidate_spec,
                    data_snapshot_id=data_snapshot_id,
                    config_snapshot={
                        **config_snapshot,
                        "command": "research auto-run",
                        "auto_run_id": run_id,
                        "auto_run_stage": "watchlist_evidence",
                        "sync_data": sync_data,
                    },
                    factor_versions=factor_versions,
                    timeframe=timeframe,
                    since=since,
                    until=until,
                    validation_config=validation_config,
                    min_history_days=min_history_days,
                )
            )
        except DataError as exc:
            evidence_blockers.append({
                "candidate_id": candidate_spec.candidate_id,
                "factor_name": candidate_spec.implementation_name or "",
                "error": str(exc),
            })

    summary_path = run_root / "auto_run_summary.json"
    report_path = run_root / "auto_run_report.md"
    artifact_paths = {
        "auto_run_summary": str(summary_path),
        "auto_run_report": str(report_path),
        "workbench_report": workbench.artifact_paths["pm_report"],
        "workbench_summary": workbench.artifact_paths["workbench_summary"],
    }
    if evidence_reviews:
        artifact_paths["first_evidence_report"] = evidence_reviews[0].artifact_paths[
            "evidence_report"
        ]
    finished_at = _now_iso()
    result = AutoRunCycleResult(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        symbols=symbols,
        timeframe=timeframe,
        sync_requested=sync_data,
        sync_results=sync_results,
        data_coverage=data_coverage,
        workbench=workbench,
        evidence_reviews=evidence_reviews,
        evidence_blockers=evidence_blockers,
        artifact_paths=artifact_paths,
    )
    summary_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _write_auto_run_report(result, report_path)
    return result


def _write_auto_run_report(result: AutoRunCycleResult, path: Path) -> None:
    summary = result.summary()
    lines = [
        f"# Kronos 自动研究日报：{result.run_id}",
        "",
        "## 一句话结论",
        "",
        _headline(result),
        "",
        "## 本次程序运行",
        "",
        f"- 运行开始：{result.started_at}",
        f"- 运行完成：{result.finished_at}",
        f"- 程序耗时：{_duration_text(result.started_at, result.finished_at)}",
        "- 说明：这里的运行时间只是程序执行耗时，不是研究样本长度。",
        f"- 币种池：{', '.join(result.symbols)}",
        f"- 研究数据粒度：{result.timeframe} K 线",
        f"- 是否同步数据：{'是' if result.sync_requested else '否'}",
        f"- 评估完成：{summary['evaluated']}",
        f"- 通过晋升：{summary['promoted']}",
        f"- 未通过：{summary['not_promoted']}",
        f"- 跳过：{summary['skipped']}",
        f"- 观察名单：{summary['watchlist']}",
        "",
        "## 数据同步",
        "",
    ]
    if result.sync_requested:
        lines.extend(_sync_result_lines(result.sync_results))
    else:
        lines.append("- 本次使用本地已有数据，没有触发外部数据同步。")

    lines.extend([
        "",
        "## 研究数据样本",
        "",
    ])
    if result.data_coverage:
        for row in result.data_coverage:
            lines.append(
                f"- {row['symbol']} / {row['dataset_label']}：{row['from']} -> "
                f"{row['to']}，{row['bars']} 条，约 {row['span_days']} 天"
            )
    else:
        lines.append("- 未读取到数据覆盖信息，请打开工作台报告检查。")

    lines.extend([
        "",
        "## 研究工作台结果",
        "",
        f"- 工作台状态：{summary['readiness']}",
        f"- 中文研究报告：{result.workbench.artifact_paths['pm_report']}",
        f"- 候选处置清单：{result.workbench.artifact_paths['candidate_disposition_report']}",
        f"- 观察名单复盘：{result.workbench.artifact_paths['watchlist_review_report']}",
        "",
        "## 观察名单补证据",
        "",
    ])
    if result.evidence_reviews:
        for review in result.evidence_reviews:
            review_summary = review.summary()
            lines.extend([
                f"### {review.candidate_title}",
                "",
                f"- 历史状态：{review_summary['history_status']}",
                f"- 支持切片：{review_summary['supportive_slices']}",
                f"- 弱正向切片：{review_summary['weak_positive_slices']}",
                f"- 专项报告：{review.artifact_paths['evidence_report']}",
                "",
            ])
    else:
        lines.append("- 本次没有生成观察名单补证据报告。")

    if result.evidence_blockers:
        lines.extend(["", "## 补证据阻塞", ""])
        for blocker in result.evidence_blockers:
            lines.append(
                f"- {blocker['candidate_id']} / {blocker['factor_name']}：{blocker['error']}"
            )

    lines.extend([
        "",
        "## 现在可以做什么",
        "",
        "- 每次运行后直接阅读本日报，必要时再打开下游研究报告。",
        "- 把本入口接到系统定时器后，可形成每日研究更新。",
        "- 本入口只产生研究证据和报告，不会自动下单。",
        "",
        "## 建议下一步",
        "",
        _next_step(result),
        "",
        "## 产物位置",
        "",
        f"- 自动运行摘要：{result.artifact_paths['auto_run_summary']}",
        f"- 自动运行日报：{result.artifact_paths['auto_run_report']}",
        f"- 工作台报告：{result.artifact_paths['workbench_report']}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _headline(result: AutoRunCycleResult) -> str:
    summary = result.summary()
    if summary["promoted"] > 0:
        return "本次自动研究发现候选可以进入深度研究，但仍不是交易结论。"
    if result.evidence_blockers:
        return "本次工作台已运行，但观察名单补证据存在阻塞，需要先修复输入证据。"
    if result.evidence_reviews:
        return "本次自动研究已完成工作台和观察名单补证据，当前仍没有候选进入组合或实盘。"
    return "本次自动研究已完成工作台跑批，当前没有候选进入组合或实盘。"


def _next_step(result: AutoRunCycleResult) -> str:
    summary = result.summary()
    if summary["promoted"] > 0:
        return "- 对晋升候选做更长历史、多币种、组合和风控验证。"
    if result.evidence_blockers:
        return "- 先处理补证据阻塞，再重新运行自动研究循环。"
    if result.evidence_reviews:
        all_history_ready = all(
            review.history_status == "enough_history" for review in result.evidence_reviews
        )
        supportive_slices = sum(
            review.summary()["supportive_slices"] for review in result.evidence_reviews
        )
        weak_positive_slices = sum(
            review.summary()["weak_positive_slices"] for review in result.evidence_reviews
        )
        unsupported = [
            review.candidate_title
            for review in result.evidence_reviews
            if review.summary()["supportive_slices"] == 0
            and review.summary()["weak_positive_slices"] == 0
        ]
        if all_history_ready and supportive_slices == 0 and weak_positive_slices == 0:
            return "- 90 天复验已完成且没有支持切片；建议进入退休评审，不继续做参数微调。"
        if all_history_ready and weak_positive_slices > 0:
            suffix = (
                f"；{', '.join(unsupported)} 可进入退休评审。"
                if unsupported
                else "。"
            )
            return (
                "- 90 天复验已完成但只看到局部弱信号；保留弱信号候选为观察或状态过滤评估，"
                f"暂不进入组合层{suffix}"
            )
        return "- 继续补足 90 天以上历史，再复验观察名单候选是否仍有稳定弱信号。"
    if summary["watchlist"] > 0:
        return "- 对观察名单候选运行补证据专项报告。"
    return "- 产品评审未通过候选，确认哪些进入退休，哪些需要重新设计。"


def _sync_result_lines(sync_results: dict[str, dict[str, int]]) -> list[str]:
    if not sync_results:
        return ["- 已请求同步，但没有写入新数据。"]
    return [
        "- "
        f"{symbol}：K线 {counts.get('klines', 0)}，"
        f"funding {counts.get('funding', 0)}，OI {counts.get('oi', 0)}"
        for symbol, counts in sync_results.items()
    ]


def _data_coverage_snapshot(
    symbols: list[str],
    base_path: Path,
    timeframe: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    kline_dataset = f"klines_{timeframe}"
    for symbol in symbols:
        for dataset, label in [(kline_dataset, f"{timeframe} K线"), ("funding", "资金费率")]:
            for info in coverage(symbol, base_path=base_path, datasets=[dataset]):
                span_days = round((info.max_event_time - info.min_event_time) / 86_400_000, 2)
                rows.append({
                    "symbol": info.symbol,
                    "dataset": info.dataset,
                    "dataset_label": label,
                    "from": _format_epoch_ms(info.min_event_time),
                    "to": _format_epoch_ms(info.max_event_time),
                    "bars": info.bar_count,
                    "span_days": span_days,
                })
    return rows


def _duration_text(started_at: str, finished_at: str) -> str:
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return "未知"
    seconds = max(0, int((finished - started).total_seconds()))
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes} 分 {remaining_seconds} 秒"
    return f"{remaining_seconds} 秒"


def _format_epoch_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
