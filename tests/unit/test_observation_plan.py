import json
from pathlib import Path

from kronos.reporting.observation_plan import generate_observation_plan


def _write_auto_report(
    run_dir: Path,
    *,
    data_kind: str,
    span_days: float | None,
    promoted: int,
    evaluated: int = 1,
) -> Path:
    run_dir.mkdir(parents=True)
    report = run_dir / "auto_run_report.md"
    report.write_text("# Kronos 自动研究日报\n", encoding="utf-8")
    (run_dir / "auto_run_summary.json").write_text(
        json.dumps({
            "summary": {
                "evaluated": evaluated,
                "promoted": promoted,
                "not_promoted": max(evaluated - promoted, 0),
                "skipped": 0,
            },
            "run_id": run_dir.name,
            "symbols": ["BTCUSDT"],
            "timeframe": "15m",
            "data_coverage": [] if span_days is None else [{
                "symbol": "BTCUSDT",
                "dataset": "klines_15m",
                "span_days": span_days,
            }],
            "config_snapshot": {"data_kind": data_kind},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def test_observation_plan_blocks_sample_data(tmp_path: Path) -> None:
    report = _write_auto_report(
        tmp_path / "reports" / "research" / "experiments" / "sample-run",
        data_kind="synthetic",
        span_days=7.0,
        promoted=0,
    )

    plan = generate_observation_plan(report)
    text = plan.path.read_text(encoding="utf-8")

    assert plan.status == "不建议观察"
    assert "sample 流程试跑" in text
    assert "先同步真实行情" in text
    assert "不会发送真实订单" in text


def test_observation_plan_marks_long_real_promoted_report_as_candidate(tmp_path: Path) -> None:
    report = _write_auto_report(
        tmp_path / "reports" / "research" / "experiments" / "real-run",
        data_kind="local",
        span_days=120.0,
        promoted=1,
    )

    plan = generate_observation_plan(report, latency_bars=2, slippage_bps=7.5)
    text = plan.path.read_text(encoding="utf-8")

    assert plan.status == "只读观察候选"
    assert "这仍不是模拟盘运行或实盘建议" in plan.verdict
    assert "等待 2 根 bar" in text
    assert "7.5 bps" in text
    assert "不能自动升级到实盘" in text
    metadata = json.loads(plan.path.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["artifact_type"] == "kronos.paper_observation_plan"
    assert metadata["eligible_for_testnet_paper"] is True
    assert metadata["promoted"] == 1


def test_observation_plan_blocks_short_real_sample(tmp_path: Path) -> None:
    report = _write_auto_report(
        tmp_path / "reports" / "research" / "experiments" / "short-run",
        data_kind="local",
        span_days=30.0,
        promoted=1,
    )

    plan = generate_observation_plan(report)

    assert plan.status == "先补数据"
    assert "不足 90 天" in plan.verdict


def test_observation_plan_blocks_missing_coverage(tmp_path: Path) -> None:
    report = _write_auto_report(
        tmp_path / "reports" / "research" / "experiments" / "missing-coverage-run",
        data_kind="local",
        span_days=None,
        promoted=1,
    )

    plan = generate_observation_plan(report)

    assert plan.status == "证据不足"
    assert "没有记录有效样本范围" in plan.verdict


def test_observation_plan_blocks_unpromoted_report(tmp_path: Path) -> None:
    report = _write_auto_report(
        tmp_path / "reports" / "research" / "experiments" / "unpromoted-run",
        data_kind="local",
        span_days=120.0,
        promoted=0,
    )

    plan = generate_observation_plan(report)

    assert plan.status == "暂不观察"
    assert "没有策略通过验证" in plan.verdict


def test_observation_plan_requires_existing_report(tmp_path: Path) -> None:
    missing_report = tmp_path / "reports" / "research" / "experiments" / "missing.md"

    try:
        generate_observation_plan(missing_report)
    except FileNotFoundError as exc:
        assert "Research report does not exist" in str(exc)
    else:
        raise AssertionError("missing report should not generate an observation plan")
