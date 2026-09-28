"""Unit tests for the P07 snapshot manifest and quality gates (tmp parquet stores)."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pyarrow as pa
import pytest

from kronos.data.schemas.candle import CANDLE_DEDUP_KEY
from kronos.data.schemas.funding import FUNDING_DEDUP_KEY
from kronos.data.storage.parquet_store import write_partition, write_records_partitioned
from kronos.research.verdict.contracts import DatasetManifest, DataSnapshotManifest
from kronos.research.verdict.readiness import (
    DAY_MS,
    DataReadinessPlan,
    build_readiness_plan,
)
from kronos.research.verdict.snapshot import (
    build_snapshot,
    freeze_snapshot,
    load_snapshot,
    render_snapshot_report,
    verify_snapshot_frozen,
)

if TYPE_CHECKING:
    from pathlib import Path

# 2026-06-01 00:00:00 UTC — a midnight-aligned window start (June 2026).
W0 = 1_780_272_000_000
W1 = W0 + 2 * DAY_MS
SYMBOL = "BTCUSDT"
SYMBOLS = [SYMBOL, "ETHUSDT"]
MIN_MS = 60_000
FUNDING_MS = 28_800_000
WINDOW_BARS = 2 * 1440  # 2 days of 1m bars
FUNDING_EVENTS = 6  # 3 settlements/day x 2 days


def _kline_table(
    symbol: str,
    times: list[int],
    *,
    available_at: list[int] | None = None,
    venues: list[str] | None = None,
    closes: list[float] | None = None,
) -> pa.Table:
    """Build a kline table (test_sync.py style) with optional PIT/venue overrides."""
    n = len(times)
    now = int(time.time() * 1000)
    avail = available_at if available_at is not None else [t + MIN_MS for t in times]
    venue_values = venues if venues is not None else ["binance"] * n
    close_values = closes if closes is not None else [67200.0] * n
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array(avail, type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "open": pa.array([67000.0] * n, type=pa.float64()),
            "high": pa.array([67500.0] * n, type=pa.float64()),
            "low": pa.array([66800.0] * n, type=pa.float64()),
            "close": pa.array(close_values, type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
            "quote_volume": pa.array([6720000.0] * n, type=pa.float64()),
            "trade_count": pa.array([100] * n, type=pa.int64()),
            "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
            "venue": venue_values,
        }
    )


def _funding_table(symbol: str, times: list[int], *, rates: list[float] | None = None) -> pa.Table:
    """Build a funding table for the given settlement times."""
    n = len(times)
    now = int(time.time() * 1000)
    rate_values = rates if rates is not None else [0.0001] * n
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array(times, type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "funding_rate": pa.array(rate_values, type=pa.float64()),
            "mark_price": pa.array([67000.0] * n, type=pa.float64()),
        }
    )


def _write_klines(
    base_path: Path,
    symbol: str,
    times: list[int],
    *,
    available_at: list[int] | None = None,
    venues: list[str] | None = None,
    closes: list[float] | None = None,
) -> None:
    write_records_partitioned(
        _kline_table(symbol, times, available_at=available_at, venues=venues, closes=closes),
        base_path,
        symbol,
        "klines_1m",
        CANDLE_DEDUP_KEY,
    )


def _write_funding(
    base_path: Path, symbol: str, times: list[int], *, rates: list[float] | None = None
) -> None:
    write_records_partitioned(
        _funding_table(symbol, times, rates=rates), base_path, symbol, "funding", FUNDING_DEDUP_KEY
    )


def _kline_times(start: int, n: int) -> list[int]:
    """Minute-grid open times covering [start, start + n minutes)."""
    return [start + i * MIN_MS for i in range(n)]


def _funding_times(start: int, n_events: int) -> list[int]:
    """8h-grid settlement times starting at ``start``."""
    return [start + i * FUNDING_MS for i in range(n_events)]


def _write_full_store(
    base_path: Path,
    symbols: tuple[str, ...] = (SYMBOL,),
    *,
    start: int = W0,
    days: int = 2,
    head_days: int = 0,
) -> None:
    """Write complete 1m + funding coverage for [start - head_days, start + days)."""
    span_start = start - head_days * DAY_MS
    n_days = days + head_days
    for symbol in symbols:
        _write_klines(base_path, symbol, _kline_times(span_start, n_days * 1440))
        _write_funding(base_path, symbol, _funding_times(span_start, n_days * 3))


def _write_store_with_duplicate_row(base_path: Path, dup_time: int) -> None:
    """Write the kline partition directly so one event_time appears twice.

    ``write_records_partitioned`` dedups by (symbol, event_time); writing the
    combined table via ``write_partition`` bypasses that to create a real dupe.
    All fixture rows live in one month partition, so the rewrite replaces it.
    """
    dt = datetime.fromtimestamp(dup_time / 1000, tz=UTC)
    write_partition(
        _kline_table(SYMBOL, [*_kline_times(W0, WINDOW_BARS), dup_time]),
        base_path,
        SYMBOL,
        "klines_1m",
        dt.year,
        dt.month,
    )


def _plan(
    base_path: Path,
    *,
    symbols: list[str] | None = None,
    window_start: int = W0,
    window_end: int = W1,
    warmup_bars: int = 0,
    timeframe: str = "15m",
) -> DataReadinessPlan:
    return build_readiness_plan(
        symbols if symbols is not None else [SYMBOL],
        base_path=base_path,
        window_start_ms=window_start,
        window_end_ms=window_end,
        warmup_bars=warmup_bars,
        signal_timeframe=timeframe,
    )


def _build(
    base_path: Path,
    plan: DataReadinessPlan | None = None,
    **kwargs: object,
) -> DataSnapshotManifest:
    resolved = plan if plan is not None else _plan(base_path)
    return build_snapshot(resolved, base_path=base_path, **kwargs)  # type: ignore[arg-type]


def _dataset(manifest: DataSnapshotManifest, name: str) -> DatasetManifest:
    return next(d for d in manifest.datasets if d.name == name)


def _flip_first_hash_char(text: str) -> str:
    """Tamper with the first content_sha256 byte in the frozen JSON text."""
    match = re.search(r'"content_sha256": "([0-9a-f]{64})"', text)
    assert match is not None
    first = match.group(1)[0]
    flipped = "0" if first != "0" else "1"
    return text.replace(f'"content_sha256": "{first}', f'"content_sha256": "{flipped}', 1)


class TestValidSnapshot:
    def test_all_gates_pass_produces_valid_manifest(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path, tuple(SYMBOLS))
        manifest = _build(tmp_path, plan=_plan(tmp_path, symbols=SYMBOLS))

        assert isinstance(manifest, DataSnapshotManifest)
        assert manifest.overall_status == "valid"
        assert manifest.snapshot_id.startswith("snap-")
        assert manifest.interval == "1m"
        assert manifest.symbols == SYMBOLS
        assert manifest.window_start_ms == W0
        assert manifest.window_end_ms == W1
        assert manifest.mock_available_at is True
        assert set(manifest.quality_checks) == {
            "closed_bars_only",
            "no_interior_gaps",
            "no_duplicates",
            "no_synthetic_mix",
            "resample_buckets_complete",
            "funding_coverage",
        }
        assert all(manifest.quality_checks.values())
        assert manifest.funding_coverage is True

        klines = _dataset(manifest, "klines_1m")
        funding = _dataset(manifest, "funding")
        assert klines.row_count == 2 * WINDOW_BARS  # both symbols
        assert funding.row_count == 2 * FUNDING_EVENTS
        assert klines.venue == "binance"
        assert funding.venue == "binance"
        assert klines.source == "binance_usdm_public"
        assert klines.coverage_ok and funding.coverage_ok
        assert re.fullmatch(r"[0-9a-f]{64}", klines.content_sha256) is not None

    def test_same_inputs_reuse_same_snapshot_id(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        manifest_a = _build(tmp_path)
        manifest_b = _build(tmp_path)
        assert manifest_a.snapshot_id == manifest_b.snapshot_id

        out = tmp_path / "snapshots"
        assert freeze_snapshot(manifest_a, snapshots_dir=out) == freeze_snapshot(
            manifest_b, snapshots_dir=out
        )

    def test_different_symbols_change_snapshot_id(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path, tuple(SYMBOLS))
        id_btc = _build(tmp_path, plan=_plan(tmp_path, symbols=[SYMBOL])).snapshot_id
        id_both = _build(tmp_path, plan=_plan(tmp_path, symbols=SYMBOLS)).snapshot_id
        assert id_btc != id_both

    def test_mock_available_at_parameterizable(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        assert _build(tmp_path).mock_available_at is True
        assert _build(tmp_path, mock_available_at=False).mock_available_at is False


class TestGateFailures:
    def test_synthetic_mix_invalid_and_named(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        # Dedup (keep last) flips one existing bar into the synthetic namespace.
        _write_klines(tmp_path, SYMBOL, [W0 + 600 * MIN_MS], venues=["synthetic"])

        manifest = _build(tmp_path)
        assert manifest.overall_status == "invalid"
        assert manifest.quality_checks["no_synthetic_mix"] is False
        assert _dataset(manifest, "klines_1m").venue == "synthetic"
        assert "synthetic" in render_snapshot_report(manifest)

    def test_interior_gap_invalid_with_reason(self, tmp_path: Path) -> None:
        times = [
            t for i, t in enumerate(_kline_times(W0, WINDOW_BARS)) if i not in set(range(600, 605))
        ]
        _write_klines(tmp_path, SYMBOL, times)
        _write_funding(tmp_path, SYMBOL, _funding_times(W0, FUNDING_EVENTS))

        manifest = _build(tmp_path)
        assert manifest.overall_status == "invalid"
        assert manifest.quality_checks["no_interior_gaps"] is False
        assert "内部缺口" in render_snapshot_report(manifest)

    def test_duplicate_event_time_invalid(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        _write_store_with_duplicate_row(tmp_path, W0 + 600 * MIN_MS)

        manifest = _build(tmp_path)
        assert manifest.overall_status == "invalid"
        assert manifest.quality_checks["no_duplicates"] is False

    def test_incomplete_resample_bucket_invalid(self, tmp_path: Path) -> None:
        times = [t for i, t in enumerate(_kline_times(W0, WINDOW_BARS)) if i != 600]
        _write_klines(tmp_path, SYMBOL, times)
        _write_funding(tmp_path, SYMBOL, _funding_times(W0, FUNDING_EVENTS))

        manifest = _build(tmp_path)
        assert manifest.overall_status == "invalid"
        assert manifest.quality_checks["resample_buckets_complete"] is False

    def test_missing_funding_tail_invalid(self, tmp_path: Path) -> None:
        _write_klines(tmp_path, SYMBOL, _kline_times(W0, WINDOW_BARS))
        _write_funding(tmp_path, SYMBOL, _funding_times(W0, FUNDING_EVENTS)[:-1])

        manifest = _build(tmp_path)
        assert manifest.overall_status == "invalid"
        assert manifest.funding_coverage is False
        assert manifest.quality_checks["funding_coverage"] is False
        assert _dataset(manifest, "funding").coverage_ok is False

    def test_unclosed_bar_invalid(self, tmp_path: Path) -> None:
        times = _kline_times(W0, WINDOW_BARS)
        available_at = [t + MIN_MS for t in times]
        available_at[600] = times[600] + 61 * MIN_MS  # knowable 61 min late: future leak
        _write_klines(tmp_path, SYMBOL, times, available_at=available_at)
        _write_funding(tmp_path, SYMBOL, _funding_times(W0, FUNDING_EVENTS))

        manifest = _build(tmp_path)
        assert manifest.overall_status == "invalid"
        assert manifest.quality_checks["closed_bars_only"] is False

    def test_empty_store_produces_invalid_snapshot(self, tmp_path: Path) -> None:
        manifest = _build(tmp_path)

        assert manifest.overall_status == "invalid"
        klines = _dataset(manifest, "klines_1m")
        funding = _dataset(manifest, "funding")
        assert klines.row_count == 0
        assert funding.row_count == 0
        assert not klines.coverage_ok
        assert not funding.coverage_ok
        assert manifest.quality_checks["no_interior_gaps"] is False
        assert manifest.funding_coverage is False


class TestFreezeAndVerify:
    def test_freeze_load_roundtrip_and_reuse(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        manifest = _build(tmp_path)

        out = tmp_path / "snapshots"
        path = freeze_snapshot(manifest, snapshots_dir=out)
        assert path == out / f"{manifest.snapshot_id}.json"
        assert path.exists()
        assert load_snapshot(path) == manifest

        # Re-freezing the identical snapshot reuses the same file atomically.
        assert freeze_snapshot(manifest, snapshots_dir=out) == path
        assert load_snapshot(path) == manifest

    def test_verify_true_for_untampered(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        path = freeze_snapshot(_build(tmp_path), snapshots_dir=tmp_path / "snapshots")
        assert verify_snapshot_frozen(path, base_path=tmp_path) is True

    def test_verify_false_when_content_hash_byte_tampered(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        path = freeze_snapshot(_build(tmp_path), snapshots_dir=tmp_path / "snapshots")
        path.write_text(_flip_first_hash_char(path.read_text(encoding="utf-8")), encoding="utf-8")
        assert verify_snapshot_frozen(path, base_path=tmp_path) is False

    def test_verify_false_when_row_count_tampered(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        path = freeze_snapshot(_build(tmp_path), snapshots_dir=tmp_path / "snapshots")
        text = path.read_text(encoding="utf-8")
        tampered = text.replace('"row_count": 2880', '"row_count": 2879', 1)
        assert tampered != text
        path.write_text(tampered, encoding="utf-8")
        assert verify_snapshot_frozen(path, base_path=tmp_path) is False

    def test_verify_false_when_store_drifts_after_freeze(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        path = freeze_snapshot(_build(tmp_path), snapshots_dir=tmp_path / "snapshots")
        assert verify_snapshot_frozen(path, base_path=tmp_path) is True

        # Store drift: an extra in-window row appears after freezing.
        _write_store_with_duplicate_row(tmp_path, W0 + 600 * MIN_MS)
        assert verify_snapshot_frozen(path, base_path=tmp_path) is False


class TestHashStability:
    def test_partition_regrouping_preserves_hash_and_id(self, tmp_path: Path) -> None:
        base_a = tmp_path / "a"
        base_b = tmp_path / "b"
        base_a.mkdir()
        base_b.mkdir()
        times = _kline_times(W0, WINDOW_BARS)

        _write_full_store(base_a)  # canonical month partitioning
        # Same rows, regrouped across two arbitrary partitions (layout differs).
        dt = datetime.fromtimestamp(W0 / 1000, tz=UTC)
        write_partition(
            _kline_table(SYMBOL, times[:1000]),
            base_b,
            SYMBOL,
            "klines_1m",
            dt.year,
            dt.month - 1,
        )
        write_partition(
            _kline_table(SYMBOL, times[1000:]),
            base_b,
            SYMBOL,
            "klines_1m",
            dt.year,
            dt.month,
        )
        _write_funding(base_b, SYMBOL, _funding_times(W0, FUNDING_EVENTS))

        manifest_a = _build(base_a)
        manifest_b = _build(base_b)
        klines_a = _dataset(manifest_a, "klines_1m")
        klines_b = _dataset(manifest_b, "klines_1m")
        assert klines_a.content_sha256 == klines_b.content_sha256
        assert klines_b.row_count == WINDOW_BARS
        assert manifest_a.snapshot_id == manifest_b.snapshot_id
        assert manifest_b.overall_status == "valid"


class TestValueBoundHash:
    """Lead ruling: the hash binds VALUES (同快照 ID = 同结果), not just identity."""

    def test_verify_false_when_close_value_edited_in_window(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        path = freeze_snapshot(_build(tmp_path), snapshots_dir=tmp_path / "snapshots")
        assert verify_snapshot_frozen(path, base_path=tmp_path) is True

        # Same (symbol, event_time), different close: dedup keep-last flips the
        # value in place — row identity and row_count are completely unchanged.
        _write_klines(tmp_path, SYMBOL, [W0 + 600 * MIN_MS], closes=[67321.5])
        assert verify_snapshot_frozen(path, base_path=tmp_path) is False

        # The value edit also changes the content hash, hence the snapshot id.
        rebuilt = _build(tmp_path)
        assert rebuilt.overall_status == "valid"
        assert rebuilt.snapshot_id != load_snapshot(path).snapshot_id

    def test_verify_false_when_funding_rate_edited_in_window(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        path = freeze_snapshot(_build(tmp_path), snapshots_dir=tmp_path / "snapshots")
        assert verify_snapshot_frozen(path, base_path=tmp_path) is True

        # Same settlement time, different funding_rate: identity unchanged.
        _write_funding(tmp_path, SYMBOL, [W0], rates=[-0.00075])
        assert verify_snapshot_frozen(path, base_path=tmp_path) is False

        rebuilt = _build(tmp_path)
        assert rebuilt.overall_status == "valid"
        assert rebuilt.snapshot_id != load_snapshot(path).snapshot_id

    def test_value_edit_changes_content_hash_but_not_row_count(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        before = _build(tmp_path)

        _write_klines(tmp_path, SYMBOL, [W0 + 600 * MIN_MS], closes=[67321.5])
        after = _build(tmp_path)

        klines_before = _dataset(before, "klines_1m")
        klines_after = _dataset(after, "klines_1m")
        assert klines_before.row_count == klines_after.row_count == WINDOW_BARS
        assert klines_before.content_sha256 != klines_after.content_sha256


class TestWarmupSpan:
    def test_warmup_span_included_in_gates_and_hash(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path, head_days=1)  # data from W0 - 1 day
        plan = _plan(tmp_path, warmup_bars=96)  # 96 x 15m = 1 day of warmup
        assert plan.warmup_start_ms == W0 - DAY_MS

        manifest = _build(tmp_path, plan=plan)
        assert manifest.overall_status == "valid"
        assert manifest.warmup_start_ms == W0 - DAY_MS
        assert manifest.window_start_ms == W0
        assert manifest.window_end_ms == W1
        assert _dataset(manifest, "klines_1m").row_count == 3 * 1440
        assert _dataset(manifest, "funding").row_count == 9

    def test_missing_warmup_data_invalid(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)  # data only from W0; warmup needs W0 - 1 day
        plan = _plan(tmp_path, warmup_bars=96)

        manifest = _build(tmp_path, plan=plan)
        assert manifest.overall_status == "invalid"
        assert manifest.quality_checks["no_interior_gaps"] is False


class TestValidation:
    def test_rejects_invalid_bucket_timeframe(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        with pytest.raises(ValueError, match="bucket_timeframe"):
            _build(tmp_path, bucket_timeframe="2m")

    def test_rejects_inverted_window_override(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        with pytest.raises(ValueError, match="window_end_ms"):
            build_snapshot(
                _plan(tmp_path),
                base_path=tmp_path,
                window_start_ms=W0,
                window_end_ms=W0 - DAY_MS,
            )

    def test_rejects_warmup_after_window_start(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        with pytest.raises(ValueError, match="warmup_start_ms"):
            build_snapshot(_plan(tmp_path), base_path=tmp_path, warmup_start_ms=W0 + MIN_MS)


class TestReport:
    def test_report_renders_valid_snapshot(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path, tuple(SYMBOLS))
        manifest = _build(tmp_path, plan=_plan(tmp_path, symbols=SYMBOLS))

        report = render_snapshot_report(manifest)
        assert "数据快照清单" in report
        assert f"快照ID: {manifest.snapshot_id}" in report
        assert "总体状态: 有效" in report
        assert "1m K线[klines_1m]" in report
        assert "资金费率[funding]" in report
        assert "venue=binance" in report
        assert "历史模拟(mock)" in report
        assert "质量门: 全部通过" in report
        dataset_lines = [line for line in report.splitlines() if line.startswith("  ")]
        assert len(dataset_lines) == 2  # one line per dataset

    def test_report_renders_invalid_reasons(self, tmp_path: Path) -> None:
        _write_full_store(tmp_path)
        _write_klines(tmp_path, SYMBOL, [W0 + 600 * MIN_MS], venues=["synthetic"])

        report = render_snapshot_report(_build(tmp_path))
        assert "总体状态: 无效" in report
        assert "synthetic" in report
        assert "质量门未通过" in report
        assert "no_synthetic_mix" in report
