# ruff: noqa: RUF001
"""Product-facing research workbench orchestration."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kronos.data.storage.query import coverage
from kronos.research.experiments.artifacts import experiment_root
from kronos.research.knowledge_base import (
    add_candidate_disposition_entry,
    add_watchlist_review_entry,
)
from kronos.research.promotion import (
    CandidatePromotionBatchResult,
    PromotionCriteria,
    PromotionDecision,
    run_market_data_promotion_batch,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from kronos.factor.candidates import CandidateFactorSpec
    from kronos.factor.registry import FactorRegistry
    from kronos.factor.validation.thresholds import ValidationConfig


class FailureReasonCategory(StrEnum):
    """PM-facing failure reason buckets for migrated legacy candidates."""

    DATA_INSUFFICIENCY = "data_insufficiency"
    MIGRATION_INVALIDATION = "migration_invalidation"
    UNSTABLE_PARAMETERS = "unstable_parameters"
    MARKET_MECHANISM_MISMATCH = "market_mechanism_mismatch"
    REPORT_QUALITY_GAP = "report_quality_gap"


class CandidateDispositionStatus(StrEnum):
    """Product-facing candidate disposition states."""

    DEEPER_RESEARCH = "deeper_research"
    WATCHLIST = "watchlist"
    RETIREMENT_RECOMMENDED = "retirement_recommended"
    BLOCKED = "blocked"


class WatchlistReviewAction(StrEnum):
    """Second-pass action for a weak-signal watchlist candidate."""

    EXTEND_EVIDENCE = "extend_evidence"
    REDESIGN_CANDIDATE = "redesign_candidate"
    RETIRE_IF_UNCHANGED = "retire_if_unchanged"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class FailureReasonGroup:
    """A PM-facing failure category and the candidates assigned to it."""

    category: FailureReasonCategory
    label_zh: str
    description_zh: str
    items: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": str(self.category),
            "label_zh": self.label_zh,
            "description_zh": self.description_zh,
            "items": self.items,
        }


@dataclass(frozen=True)
class CandidateDisposition:
    """PM-facing recommendation for what to do with one candidate next."""

    candidate_id: str
    candidate_title: str
    factor_name: str
    status: CandidateDispositionStatus
    status_label_zh: str
    recommendation_zh: str
    rationale_zh: str
    reasons: list[str]
    metrics: dict[str, Any]
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_title": self.candidate_title,
            "factor_name": self.factor_name,
            "status": str(self.status),
            "status_label_zh": self.status_label_zh,
            "recommendation_zh": self.recommendation_zh,
            "rationale_zh": self.rationale_zh,
            "reasons": self.reasons,
            "metrics": self.metrics,
            "run_id": self.run_id,
        }


@dataclass(frozen=True)
class WatchlistReview:
    """PM-facing second-pass review plan for a watchlist candidate."""

    candidate_id: str
    candidate_title: str
    factor_name: str
    action: WatchlistReviewAction
    action_label_zh: str
    priority: int
    priority_label_zh: str
    rationale_zh: str
    next_evidence_zh: list[str]
    risks_zh: list[str]
    metrics: dict[str, Any]
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_title": self.candidate_title,
            "factor_name": self.factor_name,
            "action": str(self.action),
            "action_label_zh": self.action_label_zh,
            "priority": self.priority,
            "priority_label_zh": self.priority_label_zh,
            "rationale_zh": self.rationale_zh,
            "next_evidence_zh": self.next_evidence_zh,
            "risks_zh": self.risks_zh,
            "metrics": self.metrics,
            "run_id": self.run_id,
        }


@dataclass(frozen=True)
class ResearchWorkbenchResult:
    """Product-facing wrapper around a candidate promotion batch."""

    batch: CandidatePromotionBatchResult
    readiness: str
    failure_groups: list[FailureReasonGroup]
    candidate_dispositions: list[CandidateDisposition]
    watchlist_reviews: list[WatchlistReview]
    artifact_paths: dict[str, str]

    def summary(self) -> dict[str, Any]:
        return {
            **self.batch.summary(),
            "readiness": self.readiness,
            "watchlist": len(self.watchlist_reviews),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch": self.batch.to_dict(),
            "summary": self.summary(),
            "failure_groups": [group.to_dict() for group in self.failure_groups],
            "candidate_dispositions": [
                disposition.to_dict() for disposition in self.candidate_dispositions
            ],
            "watchlist_reviews": [review.to_dict() for review in self.watchlist_reviews],
            "artifact_paths": self.artifact_paths,
        }


FAILURE_LABELS: dict[FailureReasonCategory, tuple[str, str]] = {
    FailureReasonCategory.DATA_INSUFFICIENCY: (
        "数据不足",
        "数据覆盖、窗口数量或可用证据不足，当前还不能形成可靠产品判断。",
    ),
    FailureReasonCategory.MIGRATION_INVALIDATION: (
        "迁移失效",
        "旧 A 股 / 期货假设迁移到 crypto 后，基础验证没有通过。",
    ),
    FailureReasonCategory.UNSTABLE_PARAMETERS: (
        "参数不稳",
        "候选只在少数窗口有效，或跨窗口表现衰减明显。",
    ),
    FailureReasonCategory.MARKET_MECHANISM_MISMATCH: (
        "市场机制不适配",
        "样本外表现没有覆盖交易成本、24/7 波动或 crypto 市场结构变化。",
    ),
    FailureReasonCategory.REPORT_QUALITY_GAP: (
        "报告或实现缺口",
        "实现映射、验证证据或实验记录不完整，需要补齐后再判断。",
    ),
}

READINESS_ZH: dict[str, str] = {
    "ready_for_deeper_research": "有候选可以进入下一轮深度研究，但还不能视为可交易策略。",
    "no_candidate_ready": "本批没有候选达到下一阶段标准，暂不建议进入组合或实盘。",
    "blocked_by_data_or_setup": "本批主要卡在数据、实现或证据准备，尚未形成有效研究结论。",
    "no_result": "本批没有形成有效结果。",
}

DISPOSITION_LABELS: dict[CandidateDispositionStatus, str] = {
    CandidateDispositionStatus.DEEPER_RESEARCH: "进入深度研究",
    CandidateDispositionStatus.WATCHLIST: "观察名单",
    CandidateDispositionStatus.RETIREMENT_RECOMMENDED: "建议退休",
    CandidateDispositionStatus.BLOCKED: "阻塞待补证据",
}

WATCHLIST_ACTION_LABELS: dict[WatchlistReviewAction, str] = {
    WatchlistReviewAction.EXTEND_EVIDENCE: "优先补证据",
    WatchlistReviewAction.REDESIGN_CANDIDATE: "候选改造评估",
    WatchlistReviewAction.RETIRE_IF_UNCHANGED: "不改善则退休",
    WatchlistReviewAction.BLOCKED: "阻塞待补证据",
}

WATCHLIST_PRIORITY_LABELS: dict[int, str] = {
    1: "高",
    2: "中",
    3: "低",
    4: "阻塞",
}


def run_research_workbench(
    *,
    registry: FactorRegistry,
    symbols: list[str],
    data_base_path: str | Path,
    output_base_path: str | Path,
    batch_id: str,
    git_commit: str,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    candidate_specs: Sequence[CandidateFactorSpec],
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
) -> ResearchWorkbenchResult:
    """Run a fixed product-facing research workflow and write PM-readable artifacts."""
    batch = run_market_data_promotion_batch(
        registry=registry,
        symbols=symbols,
        data_base_path=data_base_path,
        output_base_path=output_base_path,
        batch_id=batch_id,
        git_commit=git_commit,
        data_snapshot_id=data_snapshot_id,
        config_snapshot={
            **config_snapshot,
            "command": "research workbench",
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
    failure_groups = group_failure_reasons(batch, candidate_specs)
    candidate_dispositions = build_candidate_dispositions(batch, candidate_specs)
    watchlist_reviews = build_watchlist_reviews(candidate_dispositions)
    readiness = _readiness(batch)
    run_root = experiment_root(output_base_path, batch.batch_id)
    pm_report_path = run_root / "research_workbench_report.md"
    failure_groups_path = run_root / "failure_reason_groups.json"
    candidate_dispositions_path = run_root / "candidate_dispositions.json"
    candidate_disposition_report_path = run_root / "candidate_disposition_report.md"
    watchlist_reviews_path = run_root / "watchlist_reviews.json"
    watchlist_review_report_path = run_root / "watchlist_review_report.md"
    workbench_summary_path = run_root / "research_workbench_summary.json"

    context = {
        "symbols": symbols,
        "timeframe": timeframe,
        "since": since,
        "until": until,
        "data_snapshot_id": data_snapshot_id,
        "candidate_count": len(candidate_specs),
        "coverage": _coverage_snapshot(symbols, Path(data_base_path)),
    }
    failure_groups_path.write_text(
        json.dumps(
            _json_safe([group.to_dict() for group in failure_groups]),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    _write_pm_report(
        batch=batch,
        candidate_specs=candidate_specs,
        readiness=readiness,
        failure_groups=failure_groups,
        candidate_dispositions=candidate_dispositions,
        watchlist_reviews=watchlist_reviews,
        context=context,
        path=pm_report_path,
    )
    candidate_dispositions_path.write_text(
        json.dumps(
            _json_safe([disposition.to_dict() for disposition in candidate_dispositions]),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    _write_candidate_disposition_report(candidate_dispositions, candidate_disposition_report_path)
    watchlist_reviews_path.write_text(
        json.dumps(
            _json_safe([review.to_dict() for review in watchlist_reviews]),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    _write_watchlist_review_report(watchlist_reviews, watchlist_review_report_path)
    _record_candidate_dispositions(
        candidate_dispositions,
        base_path=output_base_path,
        batch_id=batch.batch_id,
    )
    _record_watchlist_reviews(
        watchlist_reviews,
        base_path=output_base_path,
        batch_id=batch.batch_id,
    )
    artifact_paths = {
        **batch.artifact_paths,
        "pm_report": str(pm_report_path),
        "failure_groups": str(failure_groups_path),
        "candidate_dispositions": str(candidate_dispositions_path),
        "candidate_disposition_report": str(candidate_disposition_report_path),
        "watchlist_reviews": str(watchlist_reviews_path),
        "watchlist_review_report": str(watchlist_review_report_path),
        "workbench_summary": str(workbench_summary_path),
    }
    result = ResearchWorkbenchResult(
        batch=batch,
        readiness=readiness,
        failure_groups=failure_groups,
        candidate_dispositions=candidate_dispositions,
        watchlist_reviews=watchlist_reviews,
        artifact_paths=artifact_paths,
    )
    workbench_summary_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return result


def group_failure_reasons(
    batch: CandidatePromotionBatchResult,
    candidate_specs: Sequence[CandidateFactorSpec],
) -> list[FailureReasonGroup]:
    """Group batch failures into PM-readable categories."""
    groups = {
        category: FailureReasonGroup(
            category=category,
            label_zh=FAILURE_LABELS[category][0],
            description_zh=FAILURE_LABELS[category][1],
            items=[],
        )
        for category in FailureReasonCategory
    }
    specs_by_factor = {
        spec.implementation_name: spec
        for spec in candidate_specs
        if spec.implementation_name is not None
    }
    specs_by_candidate = {spec.candidate_id: spec for spec in candidate_specs}

    for decision in batch.decisions:
        if decision.promoted:
            continue
        spec = specs_by_factor.get(decision.factor_name)
        item = _decision_failure_item(decision, spec)
        for category in _classify_decision_failure(decision):
            groups[category].items.append(item)

    for skipped in batch.skipped:
        spec = specs_by_candidate.get(skipped["candidate_id"])
        item = _skipped_failure_item(skipped, spec)
        groups[_classify_skipped_failure(skipped["reason"])].items.append(item)

    return [group for group in groups.values() if group.items]


def build_candidate_dispositions(
    batch: CandidatePromotionBatchResult,
    candidate_specs: Sequence[CandidateFactorSpec],
) -> list[CandidateDisposition]:
    """Build PM-facing candidate disposition recommendations."""
    specs_by_factor = {
        spec.implementation_name: spec
        for spec in candidate_specs
        if spec.implementation_name is not None
    }
    specs_by_candidate = {spec.candidate_id: spec for spec in candidate_specs}
    dispositions: list[CandidateDisposition] = []

    for decision in batch.decisions:
        spec = specs_by_factor.get(decision.factor_name)
        status = _decision_disposition_status(decision)
        dispositions.append(
            CandidateDisposition(
                candidate_id=spec.candidate_id if spec is not None else "",
                candidate_title=spec.title if spec is not None else decision.factor_name,
                factor_name=decision.factor_name,
                status=status,
                status_label_zh=DISPOSITION_LABELS[status],
                recommendation_zh=_disposition_recommendation(status),
                rationale_zh=_decision_disposition_rationale(decision),
                reasons=decision.reasons,
                metrics=decision.metrics,
                run_id=decision.run_id,
            )
        )

    for skipped in batch.skipped:
        spec = specs_by_candidate.get(skipped["candidate_id"])
        status = CandidateDispositionStatus.BLOCKED
        dispositions.append(
            CandidateDisposition(
                candidate_id=skipped["candidate_id"],
                candidate_title=spec.title if spec is not None else skipped["candidate_id"],
                factor_name=skipped["factor_name"],
                status=status,
                status_label_zh=DISPOSITION_LABELS[status],
                recommendation_zh=_disposition_recommendation(status),
                rationale_zh=_skipped_product_explanation(skipped["reason"]),
                reasons=[skipped["reason"]],
                metrics={},
                run_id=None,
            )
        )

    return dispositions


def build_watchlist_reviews(dispositions: Sequence[CandidateDisposition]) -> list[WatchlistReview]:
    """Build second-pass review plans for watchlist candidates."""
    reviews = [
        _build_watchlist_review(disposition)
        for disposition in dispositions
        if disposition.status == CandidateDispositionStatus.WATCHLIST
    ]
    return sorted(reviews, key=lambda review: (review.priority, review.candidate_id))


def _write_pm_report(
    *,
    batch: CandidatePromotionBatchResult,
    candidate_specs: Sequence[CandidateFactorSpec],
    readiness: str,
    failure_groups: list[FailureReasonGroup],
    candidate_dispositions: list[CandidateDisposition],
    watchlist_reviews: list[WatchlistReview],
    context: dict[str, Any],
    path: Path,
) -> None:
    summary = batch.summary()
    specs_by_factor = {
        spec.implementation_name: spec
        for spec in candidate_specs
        if spec.implementation_name is not None
    }
    lines = [
        f"# Kronos 研究工作台报告：{batch.batch_id}",
        "",
        "## 一句话结论",
        "",
        READINESS_ZH[readiness],
        "",
        "## 本次研究范围",
        "",
        f"- 币种池：{', '.join(context['symbols'])}",
        f"- 时间周期：{context['timeframe']}",
        f"- 候选数量：{context['candidate_count']}",
        f"- 评估完成：{summary['evaluated']}",
        f"- 通过晋升：{summary['promoted']}",
        f"- 未通过：{summary['not_promoted']}",
        f"- 跳过：{summary['skipped']}",
        f"- 数据快照：{context['data_snapshot_id']}",
        "",
        "## 数据覆盖",
        "",
    ]
    coverage_rows = context.get("coverage", [])
    if coverage_rows:
        for row in coverage_rows:
            lines.append(
                f"- {row['symbol']} / {row['dataset']}：{row['from']} -> "
                f"{row['to']}，{row['bars']} 条，缺口 {row['gaps']} 个"
            )
    else:
        lines.append("- 未读取到覆盖信息。")

    lines.extend(["", "## 候选结果", ""])
    if batch.decisions:
        for decision in batch.decisions:
            spec = specs_by_factor.get(decision.factor_name)
            title = spec.title if spec is not None else decision.factor_name
            status = "进入下一轮研究" if decision.promoted else "暂不进入下一轮"
            reason = "；".join(decision.reasons) if decision.reasons else "通过验证门槛"
            lines.extend([
                f"### {title}",
                "",
                f"- 对应因子：{decision.factor_name}",
                f"- 当前结论：{status}",
                f"- 产品解释：{_decision_product_explanation(decision)}",
                f"- 主要原因：{reason}",
                "",
            ])
    else:
        lines.append("- 没有候选完成评估。")

    watchlist = [
        decision for decision in batch.decisions
        if not decision.promoted and _validation_outcome(decision) == "review"
    ]
    if watchlist:
        lines.extend(["", "## 观察名单", ""])
        lines.append("这些候选没有通过晋升门槛，但不是完全失效结论，适合在下一轮复盘中优先检查。")
        lines.append("")
        for decision in watchlist:
            spec = specs_by_factor.get(decision.factor_name)
            title = spec.title if spec is not None else decision.factor_name
            mean_rank_ic = decision.metrics.get("mean_rank_ic")
            top_minus_bottom = decision.metrics.get("top_minus_bottom")
            lines.append(
                f"- {title}：弱信号，mean_rank_ic={_format_metric(mean_rank_ic)}，"
                f"top_minus_bottom={_format_metric(top_minus_bottom)}"
            )

    if batch.skipped:
        lines.extend(["", "## 未形成判断的候选", ""])
        for item in batch.skipped:
            lines.append(
                f"- {item['candidate_id']}：{_skipped_product_explanation(item['reason'])}"
            )

    lines.extend(["", "## 失败原因分层", ""])
    if failure_groups:
        for group in failure_groups:
            lines.extend([
                f"### {group.label_zh}",
                "",
                group.description_zh,
                "",
            ])
            for item in group.items:
                lines.append(
                    f"- {item['candidate_title']}：{item['product_explanation']}"
                )
            lines.append("")
    else:
        lines.append("- 本批没有失败或跳过项。")

    lines.extend(["", "## 候选处置清单", ""])
    if candidate_dispositions:
        for disposition in candidate_dispositions:
            lines.extend([
                f"### {disposition.candidate_title}",
                "",
                f"- 处置状态：{disposition.status_label_zh}",
                f"- 建议动作：{disposition.recommendation_zh}",
                f"- 判断依据：{disposition.rationale_zh}",
                "",
            ])
    else:
        lines.append("- 本批没有候选处置建议。")

    lines.extend(["", "## 观察名单二次复盘", ""])
    if watchlist_reviews:
        lines.append("这些候选只代表弱信号，下一步仍是研究复盘，不是交易或组合输入。")
        lines.append("")
        for review in watchlist_reviews:
            lines.extend([
                f"### {review.candidate_title}",
                "",
                f"- 当前建议：{review.action_label_zh}",
                f"- 优先级：{review.priority_label_zh}",
                f"- 复盘依据：{review.rationale_zh}",
                "- 下一步证据：",
            ])
            lines.extend([f"  - {item}" for item in review.next_evidence_zh])
            lines.append("")
    else:
        lines.append("- 本批没有观察名单候选。")

    lines.extend([
        "## 现在可以做什么",
        "",
        "- 可以把本报告作为本批候选是否继续研究的产品判断入口。",
        "- 可以用失败原因分层决定下一步是补数据、改候选，还是直接淘汰。",
        "- 可以复用同一个 workbench 入口跑不同币种池、时间窗口或候选子集。",
        "",
        "## 现在不应该做什么",
        "",
        "- 不应该把本报告直接当作实盘交易结论。",
        "- 不应该让未通过候选进入组合或风控主路径。",
        "- 不应该把旧 A 股 / 期货策略默认视为已经适配 crypto。",
        "",
        "## 建议下一步",
        "",
        _next_step_text(readiness),
        "",
        "## 产物位置",
        "",
        f"- 技术摘要：{batch.artifact_paths.get('summary', '-')}",
        f"- 技术复盘：{batch.artifact_paths.get('report', '-')}",
        f"- 决策 CSV：{batch.artifact_paths.get('decisions_csv', '-')}",
        "- 候选处置清单：见 `candidate_dispositions.json` 和 `candidate_disposition_report.md`",
        "- 观察名单二次复盘：见 `watchlist_reviews.json` 和 `watchlist_review_report.md`",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_candidate_disposition_report(
    dispositions: list[CandidateDisposition],
    path: Path,
) -> None:
    counts = {
        status: sum(disposition.status == status for disposition in dispositions)
        for status in CandidateDispositionStatus
    }
    lines = [
        "# 候选处置清单",
        "",
        "## 汇总",
        "",
    ]
    for status in CandidateDispositionStatus:
        lines.append(f"- {DISPOSITION_LABELS[status]}：{counts[status]}")

    lines.extend(["", "## 明细", ""])
    if not dispositions:
        lines.append("- 本批没有候选处置建议。")
    for disposition in dispositions:
        reason = "；".join(disposition.reasons) if disposition.reasons else "-"
        lines.extend([
            f"### {disposition.candidate_title}",
            "",
            f"- 对应因子：{disposition.factor_name or '-'}",
            f"- 处置状态：{disposition.status_label_zh}",
            f"- 建议动作：{disposition.recommendation_zh}",
            f"- 判断依据：{disposition.rationale_zh}",
            f"- 原始原因：{reason}",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")


def _write_watchlist_review_report(
    reviews: list[WatchlistReview],
    path: Path,
) -> None:
    counts = {
        action: sum(review.action == action for review in reviews)
        for action in WatchlistReviewAction
    }
    lines = [
        "# 观察名单二次复盘",
        "",
        "## 汇总",
        "",
        f"- 观察名单候选：{len(reviews)}",
    ]
    for action in WatchlistReviewAction:
        lines.append(f"- {WATCHLIST_ACTION_LABELS[action]}：{counts[action]}")

    lines.extend([
        "",
        "## 结论",
        "",
    ])
    if reviews:
        lines.append("观察名单候选仍不能进入组合层；本报告只决定下一步研究动作。")
    else:
        lines.append("本批没有观察名单候选，不需要二次复盘。")

    lines.extend(["", "## 明细", ""])
    if not reviews:
        lines.append("- 本批没有观察名单候选。")
    for review in reviews:
        lines.extend([
            f"### {review.candidate_title}",
            "",
            f"- 对应因子：{review.factor_name}",
            f"- 当前建议：{review.action_label_zh}",
            f"- 优先级：{review.priority_label_zh}",
            f"- 复盘依据：{review.rationale_zh}",
            "- 关键指标：",
            f"  - mean_rank_ic：{_format_metric(review.metrics.get('mean_rank_ic'))}",
            f"  - top_minus_bottom：{_format_metric(review.metrics.get('top_minus_bottom'))}",
            "  - walkforward_test_mean："
            f"{_format_metric(review.metrics.get('walkforward_test_mean'))}",
            "  - positive_window_ratio："
            f"{_format_metric(review.metrics.get('walkforward_positive_test_window_ratio'))}",
            "  - walkforward_window_count："
            f"{_format_metric(review.metrics.get('walkforward_window_count'))}",
            "- 下一步证据：",
        ])
        lines.extend([f"  - {item}" for item in review.next_evidence_zh])
        lines.append("- 风险提示：")
        lines.extend([f"  - {item}" for item in review.risks_zh])
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _record_candidate_dispositions(
    dispositions: list[CandidateDisposition],
    *,
    base_path: str | Path,
    batch_id: str,
) -> None:
    for disposition in dispositions:
        if disposition.status not in {
            CandidateDispositionStatus.RETIREMENT_RECOMMENDED,
            CandidateDispositionStatus.WATCHLIST,
        }:
            continue
        add_candidate_disposition_entry(
            title=f"Candidate disposition: {disposition.candidate_title}",
            summary=disposition.recommendation_zh,
            factor_name=disposition.factor_name or None,
            tags=[
                "candidate_disposition",
                str(disposition.status),
                disposition.candidate_id,
                disposition.factor_name,
            ],
            metadata=_json_safe({
                "batch_id": batch_id,
                "run_id": disposition.run_id,
                "candidate_id": disposition.candidate_id,
                "candidate_title": disposition.candidate_title,
                "factor_name": disposition.factor_name,
                "status": str(disposition.status),
                "recommendation_zh": disposition.recommendation_zh,
                "rationale_zh": disposition.rationale_zh,
                "reasons": disposition.reasons,
                "metrics": disposition.metrics,
            }),
            base_path=base_path,
        )


def _record_watchlist_reviews(
    reviews: list[WatchlistReview],
    *,
    base_path: str | Path,
    batch_id: str,
) -> None:
    for review in reviews:
        add_watchlist_review_entry(
            title=f"Watchlist review: {review.candidate_title}",
            summary=review.rationale_zh,
            factor_name=review.factor_name or None,
            tags=[
                "watchlist_review",
                str(review.action),
                review.candidate_id,
                review.factor_name,
            ],
            metadata=_json_safe({
                "batch_id": batch_id,
                "run_id": review.run_id,
                "candidate_id": review.candidate_id,
                "candidate_title": review.candidate_title,
                "factor_name": review.factor_name,
                "action": str(review.action),
                "action_label_zh": review.action_label_zh,
                "priority": review.priority,
                "priority_label_zh": review.priority_label_zh,
                "rationale_zh": review.rationale_zh,
                "next_evidence_zh": review.next_evidence_zh,
                "risks_zh": review.risks_zh,
                "metrics": review.metrics,
            }),
            base_path=base_path,
        )


def _classify_decision_failure(decision: PromotionDecision) -> list[FailureReasonCategory]:
    categories: set[FailureReasonCategory] = set()
    reason_text = " ".join(decision.reasons).lower()
    validation_outcome = _validation_outcome(decision)
    if validation_outcome == "review":
        categories.add(FailureReasonCategory.UNSTABLE_PARAMETERS)
    elif not decision.validation_passed:
        categories.add(FailureReasonCategory.MIGRATION_INVALIDATION)
    if "too few walk-forward windows" in reason_text or "decay mean" in reason_text:
        categories.add(FailureReasonCategory.UNSTABLE_PARAMETERS)
    if "walk-forward test mean" in reason_text:
        categories.add(FailureReasonCategory.MARKET_MECHANISM_MISMATCH)
    if "no test windows" in reason_text:
        categories.add(FailureReasonCategory.DATA_INSUFFICIENCY)
    if "leak audit" in reason_text:
        categories.add(FailureReasonCategory.REPORT_QUALITY_GAP)
    if not categories:
        categories.add(FailureReasonCategory.REPORT_QUALITY_GAP)
    return [category for category in FailureReasonCategory if category in categories]


def _classify_skipped_failure(reason: str) -> FailureReasonCategory:
    if reason in {"missing_validation_result", "missing_walkforward_result"}:
        return FailureReasonCategory.DATA_INSUFFICIENCY
    if reason in {"missing_implementation", "unregistered_factor"}:
        return FailureReasonCategory.REPORT_QUALITY_GAP
    if reason.startswith("promotion_error"):
        return FailureReasonCategory.REPORT_QUALITY_GAP
    return FailureReasonCategory.REPORT_QUALITY_GAP


def _decision_failure_item(
    decision: PromotionDecision,
    spec: CandidateFactorSpec | None,
) -> dict[str, Any]:
    return {
        "candidate_id": spec.candidate_id if spec is not None else "",
        "candidate_title": spec.title if spec is not None else decision.factor_name,
        "factor_name": decision.factor_name,
        "reasons": decision.reasons,
        "product_explanation": _decision_product_explanation(decision),
        "metrics": decision.metrics,
    }


def _skipped_failure_item(
    skipped: dict[str, str],
    spec: CandidateFactorSpec | None,
) -> dict[str, Any]:
    return {
        "candidate_id": skipped["candidate_id"],
        "candidate_title": spec.title if spec is not None else skipped["candidate_id"],
        "factor_name": skipped["factor_name"],
        "reasons": [skipped["reason"]],
        "product_explanation": _skipped_product_explanation(skipped["reason"]),
        "metrics": {},
    }


def _decision_disposition_status(decision: PromotionDecision) -> CandidateDispositionStatus:
    reason_text = " ".join(decision.reasons).lower()
    if decision.promoted:
        return CandidateDispositionStatus.DEEPER_RESEARCH
    if "leak audit" in reason_text:
        return CandidateDispositionStatus.BLOCKED
    if _validation_outcome(decision) == "review" or decision.validation_passed:
        return CandidateDispositionStatus.WATCHLIST
    return CandidateDispositionStatus.RETIREMENT_RECOMMENDED


def _disposition_recommendation(status: CandidateDispositionStatus) -> str:
    mapping = {
        CandidateDispositionStatus.DEEPER_RESEARCH: "进入更深研究，但仍需补充更长历史、多币种和组合风控验证。",
        CandidateDispositionStatus.WATCHLIST: "保留观察，先做二次复盘和候选改造评估，暂不进入组合层。",
        CandidateDispositionStatus.RETIREMENT_RECOMMENDED: "建议退休为失效假设，沉淀到知识库，避免短期重复研究。",
        CandidateDispositionStatus.BLOCKED: "先补数据、实现或证据，再重新判断，不做有效性结论。",
    }
    return mapping[status]


def _decision_disposition_rationale(decision: PromotionDecision) -> str:
    if decision.promoted:
        return "验证和 walk-forward 均通过。"
    if _validation_outcome(decision) == "review":
        return "基础验证出现弱信号，但未达到晋升门槛。"
    if decision.validation_passed and not decision.walkforward_passed:
        return "基础验证通过，但跨窗口稳定性不足。"
    if not decision.validation_passed:
        return "基础验证未通过，旧市场假设迁移到 crypto 后暂未成立。"
    return "证据不完整，需要补齐后再判断。"


def _build_watchlist_review(disposition: CandidateDisposition) -> WatchlistReview:
    action = _watchlist_action(disposition)
    priority = _watchlist_priority(action)
    return WatchlistReview(
        candidate_id=disposition.candidate_id,
        candidate_title=disposition.candidate_title,
        factor_name=disposition.factor_name,
        action=action,
        action_label_zh=WATCHLIST_ACTION_LABELS[action],
        priority=priority,
        priority_label_zh=WATCHLIST_PRIORITY_LABELS[priority],
        rationale_zh=_watchlist_rationale(disposition, action),
        next_evidence_zh=_watchlist_next_evidence(action),
        risks_zh=_watchlist_risks(action),
        metrics=disposition.metrics,
        run_id=disposition.run_id,
    )


def _watchlist_action(disposition: CandidateDisposition) -> WatchlistReviewAction:
    metrics = disposition.metrics
    if metrics.get("leak_audit_passed") is False:
        return WatchlistReviewAction.BLOCKED

    mean_rank_ic = _finite_number(metrics.get("mean_rank_ic"))
    top_minus_bottom = _finite_number(metrics.get("top_minus_bottom"))
    walkforward_test_mean = _finite_number(metrics.get("walkforward_test_mean"))
    positive_ratio = _finite_number(metrics.get("walkforward_positive_test_window_ratio"))

    positive_signal = mean_rank_ic > 0.0 and top_minus_bottom > 0.0
    stable_enough = walkforward_test_mean >= 0.0 and positive_ratio >= 0.5
    if positive_signal and stable_enough and mean_rank_ic >= 0.02:
        return WatchlistReviewAction.EXTEND_EVIDENCE
    if positive_signal and stable_enough:
        return WatchlistReviewAction.REDESIGN_CANDIDATE
    return WatchlistReviewAction.RETIRE_IF_UNCHANGED


def _watchlist_priority(action: WatchlistReviewAction) -> int:
    mapping = {
        WatchlistReviewAction.EXTEND_EVIDENCE: 1,
        WatchlistReviewAction.REDESIGN_CANDIDATE: 2,
        WatchlistReviewAction.RETIRE_IF_UNCHANGED: 3,
        WatchlistReviewAction.BLOCKED: 4,
    }
    return mapping[action]


def _watchlist_rationale(
    disposition: CandidateDisposition,
    action: WatchlistReviewAction,
) -> str:
    mean_rank_ic = _format_metric(disposition.metrics.get("mean_rank_ic"))
    top_minus_bottom = _format_metric(disposition.metrics.get("top_minus_bottom"))
    if action == WatchlistReviewAction.EXTEND_EVIDENCE:
        return (
            "基础验证有相对更清晰的正向弱信号，"
            f"mean_rank_ic={mean_rank_ic}，top_minus_bottom={top_minus_bottom}；"
            "优先补更长历史和更多币种证据。"
        )
    if action == WatchlistReviewAction.REDESIGN_CANDIDATE:
        return (
            "基础验证方向为正但强度偏弱，"
            f"mean_rank_ic={mean_rank_ic}，top_minus_bottom={top_minus_bottom}；"
            "先做因子表达和市场状态分层改造评估。"
        )
    if action == WatchlistReviewAction.BLOCKED:
        return "观察名单证据存在实现、数据或泄漏审计阻塞，必须先补证据再判断。"
    return "观察名单证据仍偏弱；如果二次复盘不能改善，应确认退休。"


def _watchlist_next_evidence(action: WatchlistReviewAction) -> list[str]:
    common = [
        "扩展到更长历史窗口，确认不是 30 天样本偶然性。",
        "按 BTC、ETH、SOL 分币种拆分，确认信号不是单一币种贡献。",
        "按趋势、震荡、高波动、低波动状态分层复盘。",
    ]
    if action == WatchlistReviewAction.EXTEND_EVIDENCE:
        return [
            *common,
            "若长历史和分币种仍稳定，再进入候选参数邻域稳定性评估。",
        ]
    if action == WatchlistReviewAction.REDESIGN_CANDIDATE:
        return [
            *common,
            "检查因子原始表达是否需要 crypto 化改造，例如归一化、阈值或状态过滤。",
        ]
    if action == WatchlistReviewAction.BLOCKED:
        return [
            "先补齐数据、实现映射或泄漏审计证据。",
            "阻塞解除后重新运行研究工作台。",
        ]
    return [
        *common,
        "如果二次复盘后指标仍无改善，确认进入退休候选。",
    ]


def _watchlist_risks(action: WatchlistReviewAction) -> list[str]:
    common = [
        "当前仍不是可交易结论，不能进入组合层。",
        "弱信号可能来自短窗口或单一市场状态。",
    ]
    if action == WatchlistReviewAction.EXTEND_EVIDENCE:
        return [*common, "补证据后仍可能因为样本外衰减而退休。"]
    if action == WatchlistReviewAction.REDESIGN_CANDIDATE:
        return [*common, "改造过程容易过拟合，必须保留 walk-forward 验证。"]
    if action == WatchlistReviewAction.BLOCKED:
        return ["证据未补齐前不应做有效性判断。"]
    return [*common, "如果继续投入研究，机会成本高于明确退休候选。"]


def _decision_product_explanation(decision: PromotionDecision) -> str:
    if decision.promoted:
        return "验证和 walk-forward 都通过，可以进入下一轮更深研究。"
    if _validation_outcome(decision) == "review":
        if not decision.walkforward_passed:
            return "有初步信号但跨窗口稳定性不足，只适合保留观察和二次复盘。"
        return "有初步信号但未达到晋升门槛，只适合保留观察，不能进入组合层。"
    if not decision.validation_passed:
        return "基础预测力没有达标，旧策略假设迁移到 crypto 后暂未成立。"
    if not decision.walkforward_passed:
        return "基础验证尚可，但跨窗口稳定性不够，暂不适合进入组合层。"
    return "证据不完整，需要补齐后再判断。"


def _skipped_product_explanation(reason: str) -> str:
    mapping = {
        "missing_implementation": "还没有可运行实现，不能判断策略价值。",
        "missing_validation_result": "缺少基础验证结果，多数情况下是数据或输入证据不足。",
        "missing_walkforward_result": "缺少滚动验证结果，不能判断稳定性。",
        "unregistered_factor": "因子没有注册到当前系统，需要补实现映射。",
    }
    return mapping.get(reason, f"未形成判断：{reason}")


def _readiness(batch: CandidatePromotionBatchResult) -> str:
    summary = batch.summary()
    if summary["promoted"] > 0:
        return "ready_for_deeper_research"
    if summary["evaluated"] > 0:
        return "no_candidate_ready"
    if summary["skipped"] > 0:
        return "blocked_by_data_or_setup"
    return "no_result"


def _next_step_text(readiness: str) -> str:
    if readiness == "ready_for_deeper_research":
        return "- 对晋升候选做更长历史窗口、更多币种和组合风控验证。"
    if readiness == "no_candidate_ready":
        return "- 优先复盘观察名单和失败原因；确认失效的候选进入知识库，有弱信号的候选再决定是否改造。"
    if readiness == "blocked_by_data_or_setup":
        return "- 先补齐数据覆盖、候选实现或验证证据，再重新运行 workbench。"
    return "- 先确认输入币种、时间范围和候选列表是否正确。"


def _coverage_snapshot(symbols: list[str], base_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        for info in coverage(symbol, base_path=base_path, datasets=["klines_1m", "funding", "oi"]):
            rows.append({
                "symbol": info.symbol,
                "dataset": info.dataset,
                "from": _format_epoch_ms(info.min_event_time),
                "to": _format_epoch_ms(info.max_event_time),
                "bars": info.bar_count,
                "gaps": len(info.gaps),
            })
    return rows


def _validation_outcome(decision: PromotionDecision) -> str:
    return str(decision.metrics.get("validation_outcome", "")).lower()


def _format_metric(value: Any) -> str:
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return f"{float(value):.6g}"
    return "-"


def _format_epoch_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")


def _finite_number(value: Any) -> float:
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return 0.0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
