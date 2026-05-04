# ruff: noqa: RUF001
"""Focused evidence review for watchlist candidates."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from kronos.common.errors import DataError, FactorInputError, FactorVersionError
from kronos.data import load_universe
from kronos.research.experiments.artifacts import experiment_root
from kronos.research.knowledge_base import add_watchlist_evidence_entry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from kronos.factor.base import BaseFactor
    from kronos.factor.candidates import CandidateFactorSpec
    from kronos.factor.registry import FactorRegistry
    from kronos.factor.validation.thresholds import ValidationConfig


DAY_MS = 86_400_000


class EvidenceSliceType(StrEnum):
    """Evidence slice dimensions."""

    SYMBOL = "symbol"
    REGIME = "regime"


@dataclass(frozen=True)
class EvidenceSlice:
    """One evidence slice for a focused watchlist review."""

    slice_type: EvidenceSliceType
    slice_id: str
    label_zh: str
    n_obs: int
    outcome: str
    mean_rank_ic: float | None
    top_minus_bottom: float | None
    median_turnover: float | None
    skipped_pct: float | None
    interpretation_zh: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slice_type": str(self.slice_type),
            "slice_id": self.slice_id,
            "label_zh": self.label_zh,
            "n_obs": self.n_obs,
            "outcome": self.outcome,
            "mean_rank_ic": self.mean_rank_ic,
            "top_minus_bottom": self.top_minus_bottom,
            "median_turnover": self.median_turnover,
            "skipped_pct": self.skipped_pct,
            "interpretation_zh": self.interpretation_zh,
        }


@dataclass(frozen=True)
class WatchlistEvidenceReviewResult:
    """Focused watchlist evidence review result."""

    batch_id: str
    candidate_id: str
    candidate_title: str
    factor_name: str
    symbols: list[str]
    timeframe: str
    coverage: list[dict[str, Any]]
    history_requirement_days: int
    history_status: str
    recommendation_zh: str
    redesign_suggestions_zh: list[str]
    symbol_slices: list[EvidenceSlice]
    regime_slices: list[EvidenceSlice]
    artifact_paths: dict[str, str]

    def summary(self) -> dict[str, Any]:
        supportive_slices = sum(
            slice_.outcome == "supportive"
            for slice_ in [*self.symbol_slices, *self.regime_slices]
        )
        weak_positive_slices = sum(
            slice_.outcome == "weak_positive"
            for slice_ in [*self.symbol_slices, *self.regime_slices]
        )
        return {
            "batch_id": self.batch_id,
            "candidate_id": self.candidate_id,
            "factor_name": self.factor_name,
            "history_status": self.history_status,
            "symbol_slices": len(self.symbol_slices),
            "regime_slices": len(self.regime_slices),
            "supportive_slices": supportive_slices,
            "weak_positive_slices": weak_positive_slices,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "batch_id": self.batch_id,
            "candidate_id": self.candidate_id,
            "candidate_title": self.candidate_title,
            "factor_name": self.factor_name,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "coverage": self.coverage,
            "history_requirement_days": self.history_requirement_days,
            "history_status": self.history_status,
            "recommendation_zh": self.recommendation_zh,
            "redesign_suggestions_zh": self.redesign_suggestions_zh,
            "symbol_slices": [slice_.to_dict() for slice_ in self.symbol_slices],
            "regime_slices": [slice_.to_dict() for slice_ in self.regime_slices],
            "artifact_paths": self.artifact_paths,
        }


def run_watchlist_evidence_review(
    *,
    registry: FactorRegistry,
    symbols: list[str],
    data_base_path: str | Path,
    output_base_path: str | Path,
    batch_id: str,
    candidate_spec: CandidateFactorSpec,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
    factor_versions: Mapping[str, str] | None = None,
    timeframe: str = "1m",
    since: str | int | None = None,
    until: str | int | None = None,
    validation_config: ValidationConfig | None = None,
    min_history_days: int = 90,
) -> WatchlistEvidenceReviewResult:
    """Run a focused evidence review for one watchlist candidate."""
    if not symbols:
        raise DataError("watchlist evidence review requires at least one symbol")
    if candidate_spec.implementation_name is None:
        raise DataError(f"candidate has no implementation: {candidate_spec.candidate_id}")

    data = load_universe(
        symbols,
        base_path=Path(data_base_path),
        timeframe=timeframe,
        since=since,
        until=until,
    )
    if data.empty:
        raise DataError("watchlist evidence review found no market data")

    factor = _resolve_factor(registry, candidate_spec.implementation_name, factor_versions or {})
    missing_columns = [column for column in factor.required_columns if column not in data.columns]
    if missing_columns:
        raise DataError(f"market data missing required columns: {', '.join(missing_columns)}")

    try:
        factor_scores = registry.compute_all(
            data,
            factor_names=[factor.name],
            version_map={factor.name: factor.version},
        )
    except FactorInputError as exc:
        raise DataError(f"cannot compute watchlist factor: {exc}") from exc

    aligned_by_symbol = {
        symbol: _align_factor_scores_for_symbol(factor_scores, data, symbol)
        for symbol in symbols
    }
    aligned_frames = [frame for frame in aligned_by_symbol.values() if not frame.empty]
    if not aligned_frames:
        raise DataError("watchlist evidence review produced no aligned factor rows")

    resolved_config = validation_config or _default_validation_config()
    coverage_rows = _coverage_snapshot(data, symbols)
    history_status = _history_status(coverage_rows, min_history_days)
    symbol_slices = [
        _symbol_slice(symbol, frame, resolved_config)
        for symbol, frame in aligned_by_symbol.items()
        if not frame.empty
    ]
    combined = pd.concat(aligned_frames, ignore_index=True)
    regime_slices = _regime_slices(combined, primary_period=resolved_config.periods[0])
    recommendation = _recommendation(history_status, symbol_slices, regime_slices)

    run_root = experiment_root(output_base_path, batch_id)
    json_path = run_root / "watchlist_evidence_review.json"
    report_path = run_root / "watchlist_evidence_report.md"
    result = WatchlistEvidenceReviewResult(
        batch_id=batch_id,
        candidate_id=candidate_spec.candidate_id,
        candidate_title=candidate_spec.title,
        factor_name=factor.name,
        symbols=symbols,
        timeframe=timeframe,
        coverage=coverage_rows,
        history_requirement_days=min_history_days,
        history_status=history_status,
        recommendation_zh=recommendation,
        redesign_suggestions_zh=_redesign_suggestions(candidate_spec.candidate_id),
        symbol_slices=symbol_slices,
        regime_slices=regime_slices,
        artifact_paths={
            "evidence_json": str(json_path),
            "evidence_report": str(report_path),
        },
    )
    json_path.write_text(
        json.dumps(_json_safe(result.to_dict()), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _write_evidence_report(result, report_path)
    _record_watchlist_evidence(
        result,
        base_path=output_base_path,
        data_snapshot_id=data_snapshot_id,
        config_snapshot={
            **config_snapshot,
            "timeframe": timeframe,
            "since": since,
            "until": until,
            "min_history_days": min_history_days,
        },
    )
    return result


def _default_validation_config() -> ValidationConfig:
    from kronos.factor.validation.thresholds import ValidationConfig

    return ValidationConfig()


def _resolve_factor(
    registry: FactorRegistry,
    factor_name: str,
    versions: Mapping[str, str],
) -> BaseFactor:
    explicit_version = versions.get(factor_name)
    if explicit_version is not None:
        return registry.get(factor_name, explicit_version)

    summaries = [item for item in registry.list_factors() if item["name"] == factor_name]
    if len(summaries) == 1:
        return registry.get(factor_name, str(summaries[0]["version"]))

    defaults = [item for item in summaries if item["is_default"]]
    if len(defaults) == 1:
        return registry.get(factor_name, str(defaults[0]["version"]))

    try:
        return registry.get(factor_name)
    except FactorVersionError as exc:
        raise DataError(f"factor is not registered: {factor_name}") from exc


def _align_factor_scores_for_symbol(
    factor_scores: pd.DataFrame,
    market_data: pd.DataFrame,
    symbol: str,
) -> pd.DataFrame:
    score_rows = factor_scores[factor_scores["symbol"] == symbol].copy()
    price_rows = market_data[market_data["symbol"] == symbol].copy()
    if score_rows.empty or price_rows.empty:
        return pd.DataFrame()

    score_rows["factor_value"] = score_rows["score"].where(
        score_rows["score"].notna(),
        score_rows["value"],
    )
    merged = score_rows[
        ["event_time", "available_at", "symbol", "factor_value"]
    ].merge(
        price_rows[["event_time", "available_at", "symbol", "high", "low", "close"]],
        on=["event_time", "available_at", "symbol"],
        how="inner",
    )
    return merged.sort_values("event_time").reset_index(drop=True)


def _symbol_slice(
    symbol: str,
    aligned: pd.DataFrame,
    validation_config: ValidationConfig,
) -> EvidenceSlice:
    from kronos.factor.validation.pipeline import validate_factor

    result = validate_factor(
        aligned["factor_value"].reset_index(drop=True),
        aligned["close"].reset_index(drop=True),
        aligned["available_at"].reset_index(drop=True),
        config=validation_config,
    )
    outcome = _slice_outcome(
        n_obs=result.n_obs,
        mean_rank_ic=result.mean_rank_ic,
        top_minus_bottom=result.top_minus_bottom,
    )
    return EvidenceSlice(
        slice_type=EvidenceSliceType.SYMBOL,
        slice_id=symbol,
        label_zh=symbol,
        n_obs=result.n_obs,
        outcome=outcome,
        mean_rank_ic=_finite_or_none(result.mean_rank_ic),
        top_minus_bottom=_finite_or_none(result.top_minus_bottom),
        median_turnover=_finite_or_none(result.median_turnover),
        skipped_pct=_finite_or_none(result.skipped_pct),
        interpretation_zh=_slice_interpretation(outcome),
    )


def _regime_slices(aligned: pd.DataFrame, *, primary_period: int) -> list[EvidenceSlice]:
    prepared = _prepare_regime_frame(aligned, primary_period=primary_period)
    if prepared.empty:
        return []

    volatility_threshold = float(prepared["volatility_score"].median())
    trend_threshold = float(prepared["trend_efficiency"].median())
    regimes = [
        ("high_volatility", "高波动", prepared["volatility_score"] >= volatility_threshold),
        ("low_volatility", "低波动", prepared["volatility_score"] < volatility_threshold),
        ("trend", "趋势状态", prepared["trend_efficiency"] >= trend_threshold),
        ("chop", "震荡状态", prepared["trend_efficiency"] < trend_threshold),
    ]
    return [
        _regime_slice(slice_id, label, prepared[mask].copy())
        for slice_id, label, mask in regimes
    ]


def _prepare_regime_frame(aligned: pd.DataFrame, *, primary_period: int) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, frame in aligned.groupby("symbol"):
        ordered = frame.sort_values("event_time").copy()
        ordered["bar_return"] = ordered["close"].pct_change()
        ordered["forward_return"] = ordered["close"].shift(-primary_period) / ordered["close"] - 1.0
        ordered["volatility_score"] = (
            ordered["bar_return"].abs().rolling(20, min_periods=5).mean()
        )
        path_distance = ordered["close"].diff().abs().rolling(20, min_periods=5).sum()
        net_distance = (ordered["close"] - ordered["close"].shift(19)).abs()
        ordered["trend_efficiency"] = net_distance / path_distance.replace(0.0, math.nan)
        parts.append(ordered)

    prepared = pd.concat(parts, ignore_index=True)
    prepared = prepared.dropna(
        subset=["factor_value", "forward_return", "volatility_score", "trend_efficiency"]
    )
    return prepared.reset_index(drop=True)


def _regime_slice(slice_id: str, label: str, subset: pd.DataFrame) -> EvidenceSlice:
    metrics = _simple_slice_metrics(subset)
    outcome = _slice_outcome(
        n_obs=metrics["n_obs"],
        mean_rank_ic=metrics["mean_rank_ic"],
        top_minus_bottom=metrics["top_minus_bottom"],
    )
    return EvidenceSlice(
        slice_type=EvidenceSliceType.REGIME,
        slice_id=slice_id,
        label_zh=label,
        n_obs=metrics["n_obs"],
        outcome=outcome,
        mean_rank_ic=_finite_or_none(metrics["mean_rank_ic"]),
        top_minus_bottom=_finite_or_none(metrics["top_minus_bottom"]),
        median_turnover=None,
        skipped_pct=None,
        interpretation_zh=_slice_interpretation(outcome),
    )


def _simple_slice_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    clean = frame[["factor_value", "forward_return"]].dropna()
    if len(clean) < 3:
        return {"n_obs": len(clean), "mean_rank_ic": None, "top_minus_bottom": None}

    rank_ic = clean["factor_value"].corr(clean["forward_return"], method="spearman")
    top_minus_bottom: float | None
    try:
        quantiles = pd.qcut(clean["factor_value"], q=5, labels=False, duplicates="drop")
        grouped = clean.assign(_quantile=quantiles).groupby("_quantile")["forward_return"].mean()
        top_minus_bottom = (
            float(grouped.iloc[-1] - grouped.iloc[0])
            if len(grouped) >= 2
            else None
        )
    except ValueError:
        top_minus_bottom = None

    return {
        "n_obs": len(clean),
        "mean_rank_ic": _finite_or_none(rank_ic),
        "top_minus_bottom": _finite_or_none(top_minus_bottom),
    }


def _slice_outcome(
    *,
    n_obs: int,
    mean_rank_ic: float | None,
    top_minus_bottom: float | None,
) -> str:
    if n_obs < 30:
        return "insufficient"
    if mean_rank_ic is None or top_minus_bottom is None:
        return "insufficient"
    if mean_rank_ic >= 0.02 and top_minus_bottom > 0:
        return "supportive"
    if mean_rank_ic > 0 and top_minus_bottom > 0:
        return "weak_positive"
    return "not_supportive"


def _slice_interpretation(outcome: str) -> str:
    mapping = {
        "supportive": "该切片支持继续补证据，但还不能直接进入组合层。",
        "weak_positive": "该切片有弱正向信号，优先看后续复验是否能保持稳定。",
        "not_supportive": "该切片暂不支持继续加码研究。",
        "insufficient": "该切片样本或有效分组不足，不能形成判断。",
    }
    return mapping[outcome]


def _coverage_snapshot(data: pd.DataFrame, symbols: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        frame = data[data["symbol"] == symbol]
        if frame.empty:
            rows.append({
                "symbol": symbol,
                "bars": 0,
                "from": None,
                "to": None,
                "span_days": 0.0,
            })
            continue
        min_time = int(frame["event_time"].min())
        max_time = int(frame["event_time"].max())
        rows.append({
            "symbol": symbol,
            "bars": len(frame),
            "from": _format_epoch_ms(min_time),
            "to": _format_epoch_ms(max_time),
            "span_days": round((max_time - min_time) / DAY_MS, 2),
        })
    return rows


def _history_status(coverage_rows: list[dict[str, Any]], min_history_days: int) -> str:
    spans = [float(row["span_days"]) for row in coverage_rows if row["bars"]]
    if not spans:
        return "blocked"
    if min(spans) >= min_history_days:
        return "enough_history"
    return "needs_longer_history"


def _recommendation(
    history_status: str,
    symbol_slices: list[EvidenceSlice],
    regime_slices: list[EvidenceSlice],
) -> str:
    positive_symbol_count = sum(
        slice_.outcome in {"supportive", "weak_positive"} for slice_ in symbol_slices
    )
    supportive_regime_count = sum(slice_.outcome == "supportive" for slice_ in regime_slices)
    if history_status != "enough_history":
        return "当前证据仍偏短，建议先补更长历史，再判断是否进入深度研究。"
    if positive_symbol_count >= 2 and supportive_regime_count >= 1:
        return "证据面较健康，可以进入下一轮参数邻域稳定性评估。"
    if positive_symbol_count >= 1:
        return "存在局部弱信号，建议先做分币种和分状态复验，不进入组合层。"
    return "补证据后仍未看到稳定支持，建议转入退休评审。"


def _write_evidence_report(result: WatchlistEvidenceReviewResult, path: Path) -> None:
    lines = [
        f"# 观察名单补证据专项报告：{result.candidate_title}",
        "",
        "## 一句话结论",
        "",
        result.recommendation_zh,
        "",
        "## 研究范围",
        "",
        f"- 候选：{result.candidate_title}",
        f"- 因子：{result.factor_name}",
        f"- 币种：{', '.join(result.symbols)}",
        f"- 周期：{result.timeframe}",
        f"- 历史要求：至少 {result.history_requirement_days} 天",
        f"- 历史状态：{_history_status_zh(result.history_status)}",
        "",
        "## 数据覆盖",
        "",
    ]
    for row in result.coverage:
        lines.append(
            f"- {row['symbol']}：{row['bars']} 条，{row['from'] or '-'} -> "
            f"{row['to'] or '-'}，覆盖约 {row['span_days']} 天"
        )

    lines.extend(["", "## 分币种证据", ""])
    lines.extend(_slice_table(result.symbol_slices))
    lines.extend(["", "## 分市场状态证据", ""])
    lines.extend(_slice_table(result.regime_slices))
    lines.extend(["", "## 候选改造评估", ""])
    if result.redesign_suggestions_zh:
        lines.extend([f"- {item}" for item in result.redesign_suggestions_zh])
    else:
        lines.append("- 当前优先看长历史证据稳定性；暂不建议改写因子表达。")
    lines.extend([
        "",
        "## 产品判断",
        "",
    ])
    lines.extend(_product_judgement_lines(result))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _product_judgement_lines(result: WatchlistEvidenceReviewResult) -> list[str]:
    lines = ["- 本报告仍属于研究证据补强，不是交易结论。"]
    if result.history_status != "enough_history":
        lines.extend([
            "- 当前历史长度还不达标，先补齐长窗口数据再做处置判断。",
            "- 数据补齐前不能进入参数稳定性、组合或实盘评估。",
        ])
        return lines

    supportive_count = sum(
        slice_.outcome == "supportive"
        for slice_ in [*result.symbol_slices, *result.regime_slices]
    )
    weak_count = sum(
        slice_.outcome == "weak_positive"
        for slice_ in [*result.symbol_slices, *result.regime_slices]
    )
    if supportive_count:
        lines.append("- 90 天证据中已有支持切片，但仍需通过参数邻域稳定性评估后才可升级。")
    elif weak_count:
        lines.append("- 90 天证据中只有局部弱信号，当前只能保留观察或状态过滤评估。")
    else:
        lines.append("- 90 天证据中没有支持切片，建议进入退休评审。")
    lines.append("- 未通过更严格验证前，不能进入组合层或实盘层。")
    return lines


def _slice_table(slices: list[EvidenceSlice]) -> list[str]:
    if not slices:
        return ["- 没有可用切片。"]
    lines = [
        "| 切片 | 样本 | 结论 | mean_rank_ic | top_minus_bottom | 解释 |",
        "|---|---:|---|---:|---:|---|",
    ]
    for slice_ in slices:
        lines.append(
            "| "
            f"{slice_.label_zh} | "
            f"{slice_.n_obs} | "
            f"{_outcome_zh(slice_.outcome)} | "
            f"{_format_metric(slice_.mean_rank_ic)} | "
            f"{_format_metric(slice_.top_minus_bottom)} | "
            f"{slice_.interpretation_zh} |"
        )
    return lines


def _record_watchlist_evidence(
    result: WatchlistEvidenceReviewResult,
    *,
    base_path: str | Path,
    data_snapshot_id: str,
    config_snapshot: dict[str, Any],
) -> None:
    add_watchlist_evidence_entry(
        title=f"Watchlist evidence: {result.candidate_title}",
        summary=result.recommendation_zh,
        factor_name=result.factor_name,
        tags=[
            "watchlist_evidence",
            result.candidate_id,
            result.factor_name,
            result.history_status,
        ],
        metadata=_json_safe({
            "run_id": result.batch_id,
            "batch_id": result.batch_id,
            "candidate_id": result.candidate_id,
            "candidate_title": result.candidate_title,
            "factor_name": result.factor_name,
            "symbols": result.symbols,
            "timeframe": result.timeframe,
            "data_snapshot_id": data_snapshot_id,
            "config_snapshot": config_snapshot,
            "summary": result.summary(),
            "coverage": result.coverage,
            "recommendation_zh": result.recommendation_zh,
            "redesign_suggestions_zh": result.redesign_suggestions_zh,
            "artifact_paths": result.artifact_paths,
        }),
        base_path=base_path,
    )


def _history_status_zh(status: str) -> str:
    mapping = {
        "enough_history": "历史长度达标",
        "needs_longer_history": "需要更长历史",
        "blocked": "缺少可用数据",
    }
    return mapping.get(status, status)


def _outcome_zh(outcome: str) -> str:
    mapping = {
        "supportive": "支持",
        "weak_positive": "弱正向",
        "not_supportive": "不支持",
        "insufficient": "证据不足",
    }
    return mapping.get(outcome, outcome)


def _redesign_suggestions(candidate_id: str) -> list[str]:
    if candidate_id == "body_energy":
        return [
            "优先把原始 body-energy 改成相对波动归一化表达，避免不同币种价格尺度和波动率直接污染信号。",
            "增加趋势 / 震荡状态过滤，只在方向延续或波动收敛状态下评估 body pressure。",
            "增加成交量或 taker-buy 确认，避免 24/7 噪声市场里单根 K 线实体被过度解释。",
            "如果 90 天以上历史和分状态复验后仍无稳定切片，建议确认退休，不继续做参数微调。",
        ]
    if candidate_id == "range_chop_filter":
        return [
            "优先确认弱信号是否跨 90 天以上历史和多币种保持稳定，再考虑参数邻域稳定性。",
            "如果只有单一币种或单一状态支持，不进入组合层，只保留为市场状态过滤候选。",
        ]
    return []


def _format_metric(value: Any) -> str:
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return f"{float(value):.6g}"
    return "-"


def _format_epoch_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")


def _finite_or_none(value: Any) -> float | None:
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
