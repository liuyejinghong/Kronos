# ruff: noqa: RUF001
"""System-level Run MVP orchestration for Kronos."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kronos.data.storage.query import coverage
from kronos.research.auto_runner import AutoRunCycleResult, run_auto_research_cycle
from kronos.research.experiments.artifacts import experiment_root

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from kronos.factor.candidates import CandidateFactorSpec
    from kronos.factor.registry import FactorRegistry
    from kronos.factor.validation.thresholds import ValidationConfig
    from kronos.research.promotion import PromotionCriteria


@dataclass(frozen=True)
class KronosRunResult:
    """Top-level product-facing result for one Kronos run."""

    run_id: str
    status: str
    started_at: str
    finished_at: str
    profile: dict[str, Any]
    data_readiness: dict[str, Any]
    failure_reason: str | None
    auto_run: AutoRunCycleResult | None
    artifact_paths: dict[str, str]

    def summary(self) -> dict[str, Any]:
        auto_summary = self.auto_run.summary() if self.auto_run is not None else {}
        return {
            "run_id": self.run_id,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "blockers": len(self.data_readiness.get("blockers", [])),
            "warnings": len(self.data_readiness.get("warnings", [])),
            "research_status": auto_summary.get("readiness"),
            "evaluated": auto_summary.get("evaluated", 0),
            "promoted": auto_summary.get("promoted", 0),
            "skipped": auto_summary.get("skipped", 0),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "profile": self.profile,
            "data_readiness": self.data_readiness,
            "failure_reason": self.failure_reason,
            "auto_run": self.auto_run.to_dict() if self.auto_run is not None else None,
            "artifact_paths": self.artifact_paths,
        }


def run_kronos_today(
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
    max_data_age_hours: int = 72,
    require_fresh_data: bool = False,
) -> KronosRunResult:
    """Run the default product-facing Kronos MVP flow.

    This wraps the research auto-run with product-level checks and a system
    status artifact. It is intentionally still research-only and never trades.
    """
    started_at = _now_iso()
    output_path = Path(output_base_path)
    data_path = Path(data_base_path)
    run_root = experiment_root(output_path, run_id)
    status_report_path = run_root / "kronos_run_status.md"
    status_json_path = run_root / "kronos_run_status.json"
    profile = {
        "entrypoint": "kronos run today",
        "symbols": symbols,
        "timeframe": timeframe,
        "sync_policy": "sync-before-run" if sync_data else "local-data-only",
        "min_history_days": min_history_days,
        "max_data_age_hours": max_data_age_hours,
        "require_fresh_data": require_fresh_data,
        "research_step": "research auto-run",
        "trading_enabled": False,
        "output_base_path": str(output_path),
    }
    artifact_paths = {
        "run_status_report": str(status_report_path),
        "run_status_json": str(status_json_path),
    }
    readiness = _assess_data_readiness(
        symbols=symbols,
        base_path=data_path,
        timeframe=timeframe,
        min_history_days=min_history_days,
        max_data_age_hours=max_data_age_hours,
        require_fresh_data=require_fresh_data,
        sync_data=sync_data,
    )
    if readiness["blockers"] and not sync_data:
        return _finish_run(
            run_id=run_id,
            status="failed",
            started_at=started_at,
            profile=profile,
            data_readiness=readiness,
            failure_reason="数据检查未通过，未启动研究任务。",
            auto_run=None,
            artifact_paths=artifact_paths,
            status_report_path=status_report_path,
            status_json_path=status_json_path,
        )

    try:
        auto_run = run_auto_research_cycle(
            registry=registry,
            symbols=symbols,
            data_base_path=data_path,
            output_base_path=output_path,
            run_id=f"{run_id}-research",
            git_commit=git_commit,
            data_snapshot_id=data_snapshot_id,
            config_snapshot={
                **config_snapshot,
                "command": "kronos run today",
                "kronos_run_id": run_id,
                "run_profile": profile,
            },
            candidate_specs=candidate_specs,
            watchlist_candidate_specs=watchlist_candidate_specs,
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
            sync_data=sync_data,
            sync_since=sync_since,
            max_retries=max_retries,
            request_interval_ms=request_interval_ms,
            min_history_days=min_history_days,
        )
    except Exception as exc:
        return _finish_run(
            run_id=run_id,
            status="failed",
            started_at=started_at,
            profile=profile,
            data_readiness=readiness,
            failure_reason=f"研究任务运行失败：{exc}",
            auto_run=None,
            artifact_paths=artifact_paths,
            status_report_path=status_report_path,
            status_json_path=status_json_path,
        )

    artifact_paths.update({
        "auto_run_report": auto_run.artifact_paths["auto_run_report"],
        "auto_run_summary": auto_run.artifact_paths["auto_run_summary"],
        "workbench_report": auto_run.artifact_paths["workbench_report"],
    })
    if "first_evidence_report" in auto_run.artifact_paths:
        artifact_paths["first_evidence_report"] = auto_run.artifact_paths["first_evidence_report"]

    refreshed_readiness = _assess_data_readiness(
        symbols=symbols,
        base_path=data_path,
        timeframe=timeframe,
        min_history_days=min_history_days,
        max_data_age_hours=max_data_age_hours,
        require_fresh_data=require_fresh_data,
        sync_data=False,
    )
    return _finish_run(
        run_id=run_id,
        status="success",
        started_at=started_at,
        profile=profile,
        data_readiness=refreshed_readiness,
        failure_reason=None,
        auto_run=auto_run,
        artifact_paths=artifact_paths,
        status_report_path=status_report_path,
        status_json_path=status_json_path,
    )


def _finish_run(
    *,
    run_id: str,
    status: str,
    started_at: str,
    profile: dict[str, Any],
    data_readiness: dict[str, Any],
    failure_reason: str | None,
    auto_run: AutoRunCycleResult | None,
    artifact_paths: dict[str, str],
    status_report_path: Path,
    status_json_path: Path,
) -> KronosRunResult:
    result = KronosRunResult(
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=_now_iso(),
        profile=profile,
        data_readiness=data_readiness,
        failure_reason=failure_reason,
        auto_run=auto_run,
        artifact_paths=artifact_paths,
    )
    status_json_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _write_status_report(result, status_report_path)
    return result


def _write_status_report(result: KronosRunResult, path: Path) -> None:
    lines = [
        f"# Kronos 运行状态：{result.run_id}",
        "",
        "## 第一屏结论",
        "",
        f"- 整体状态：{'成功' if result.status == 'success' else '失败'}",
        f"- 运行开始：{result.started_at}",
        f"- 运行完成：{result.finished_at}",
        f"- 程序耗时：{_duration_text(result.started_at, result.finished_at)}",
        f"- 默认入口：{result.profile['entrypoint']}",
        f"- 默认币种：{', '.join(result.profile['symbols'])}",
        f"- 数据粒度：{result.profile['timeframe']} K线",
        f"- 同步策略：{_sync_policy_text(str(result.profile['sync_policy']))}",
        "- 自动交易：关闭，本轮只产出研究证据和报告。",
        "",
        "## 产品结论",
        "",
        _product_conclusion(result),
        "",
        "## 数据检查",
        "",
    ]
    rows = result.data_readiness.get("rows", [])
    if rows:
        for row in rows:
            lines.append(
                f"- {row['symbol']} / {row['dataset_label']}：{row['status']}，"
                f"{row['from']} -> {row['to']}，{row['bars']} 条，约 {row['span_days']} 天"
            )
    else:
        lines.append("- 没有读取到数据覆盖信息。")

    blockers = result.data_readiness.get("blockers", [])
    if blockers:
        lines.extend(["", "## 阻塞原因", ""])
        lines.extend(f"- {blocker}" for blocker in blockers)

    warnings = result.data_readiness.get("warnings", [])
    if warnings:
        lines.extend(["", "## 提醒", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    if result.failure_reason is not None:
        lines.extend(["", "## 失败说明", "", f"- {result.failure_reason}"])

    if result.auto_run is not None:
        auto_summary = result.auto_run.summary()
        lines.extend([
            "",
            "## 默认研究任务",
            "",
            "- 内部步骤：research auto-run",
            f"- 研究状态：{auto_summary['readiness']}",
            f"- 评估完成：{auto_summary['evaluated']}",
            f"- 通过晋升：{auto_summary['promoted']}",
            f"- 跳过：{auto_summary['skipped']}",
            f"- 观察名单补证据：{auto_summary['evidence_reviews']}",
            f"- 自动研究日报：{result.artifact_paths['auto_run_report']}",
            f"- 工作台报告：{result.artifact_paths['workbench_report']}",
        ])

    lines.extend([
        "",
        "## 下一步",
        "",
        _next_action(result),
        "",
        "## 产物位置",
        "",
        f"- 系统状态报告：{result.artifact_paths['run_status_report']}",
        f"- 系统状态 JSON：{result.artifact_paths['run_status_json']}",
    ])
    if "auto_run_report" in result.artifact_paths:
        lines.append(f"- 自动研究日报：{result.artifact_paths['auto_run_report']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _product_conclusion(result: KronosRunResult) -> str:
    if result.status != "success":
        return "本轮 Kronos 没有完成默认运行。先处理阻塞原因，再重新运行。"
    if result.auto_run is None:
        return "本轮系统运行成功，但没有执行默认研究任务。"
    summary = result.auto_run.summary()
    if summary["promoted"] > 0:
        return "本轮发现候选可以进入深度研究，但仍不是交易结论。"
    if summary["skipped"] > 0:
        return "本轮有候选被跳过，需要先看 skipped 原因；当前不能进入组合或实盘。"
    return "本轮 Kronos 已完成默认研究运行，当前没有候选进入组合或实盘。"


def _next_action(result: KronosRunResult) -> str:
    if result.status != "success":
        return "- 先按阻塞原因修复数据或运行配置，再重新运行 `kronos run today`。"
    if result.auto_run is None:
        return "- 检查为什么默认研究任务没有执行。"
    summary = result.auto_run.summary()
    if summary["promoted"] > 0:
        return "- 对晋升候选做更长历史、多币种、组合和风控验证。"
    if summary["skipped"] > 0:
        return "- 先处理 skipped 候选的失败原因，再决定是否保留或退休。"
    return "- 产品评审未通过候选；确认退休、观察或重新设计，不进入实盘。"


def _assess_data_readiness(
    *,
    symbols: list[str],
    base_path: Path,
    timeframe: str,
    min_history_days: int,
    max_data_age_hours: int,
    require_fresh_data: bool,
    sync_data: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    kline_dataset = f"klines_{timeframe}"
    if not symbols:
        blockers.append("没有配置默认币种。")
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    for symbol in symbols:
        infos = coverage(symbol, base_path=base_path, datasets=[kline_dataset])
        if not infos:
            message = f"缺少 {symbol} / {timeframe} K线数据。"
            if sync_data:
                warnings.append(f"{message} 本轮会先尝试同步数据。")
            else:
                blockers.append(message)
            continue
        info = infos[0]
        span_days = round((info.max_event_time - info.min_event_time) / 86_400_000, 2)
        age_hours = round(max(0, now_ms - info.max_event_time) / 3_600_000, 2)
        status = "可用"
        if span_days < min_history_days:
            status = "历史不足"
            message = (
                f"{symbol} / {timeframe} K线只有约 {span_days} 天，"
                f"低于默认要求 {min_history_days} 天。"
            )
            if sync_data:
                warnings.append(f"{message} 本轮会先尝试同步数据。")
            else:
                blockers.append(message)
        if max_data_age_hours > 0 and age_hours > max_data_age_hours:
            status = "数据较旧" if status == "可用" else status
            message = (
                f"{symbol} / {timeframe} K线最新时间距现在约 {age_hours} 小时，"
                f"超过 {max_data_age_hours} 小时。"
            )
            if require_fresh_data:
                blockers.append(message)
            else:
                warnings.append(message)
        rows.append({
            "symbol": symbol,
            "dataset": kline_dataset,
            "dataset_label": f"{timeframe} K线",
            "status": status,
            "from": _format_epoch_ms(info.min_event_time),
            "to": _format_epoch_ms(info.max_event_time),
            "bars": info.bar_count,
            "span_days": span_days,
            "age_hours": age_hours,
            "gaps": len(info.gaps),
        })
    return {
        "status": "blocked" if blockers else "ready",
        "rows": rows,
        "blockers": blockers,
        "warnings": warnings,
    }


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


def _sync_policy_text(value: str) -> str:
    if value == "sync-before-run":
        return "运行前先同步数据"
    return "默认使用本地数据，不隐式联网"


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
