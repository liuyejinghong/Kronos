"""Unit tests for the P06 data readiness plan (tmp parquet stores, no API)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import patch

import pyarrow as pa
import pytest

from kronos.common.errors import DataError
from kronos.data.schemas.candle import CANDLE_DEDUP_KEY
from kronos.data.schemas.funding import FUNDING_DEDUP_KEY
from kronos.data.schemas.oi import OI_DEDUP_KEY
from kronos.data.storage.parquet_store import write_records_partitioned
from kronos.research.verdict.readiness import (
    DAY_MS,
    DEFAULT_MAX_FETCH_SPAN_DAYS,
    FUNDING_MAX_FETCH_SPAN_MS,
    DataReadinessPlan,
    apply_repair_actions,
    build_readiness_plan,
    render_readiness_report,
)

if TYPE_CHECKING:
    from pathlib import Path

# 2026-06-01 00:00:00 UTC — a midnight-aligned window start.
W0 = 1_780_272_000_000
W1 = W0 + 2 * DAY_MS
SYMBOL = "BTCUSDT"
MIN_MS = 60_000
FUNDING_MS = 28_800_000


def _kline_table(symbol: str, times: list[int]) -> pa.Table:
    """Build a kline table for the given open times (test_sync.py style)."""
    n = len(times)
    now = int(time.time() * 1000)
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array([t + MIN_MS for t in times], type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "open": pa.array([67000.0] * n, type=pa.float64()),
            "high": pa.array([67500.0] * n, type=pa.float64()),
            "low": pa.array([66800.0] * n, type=pa.float64()),
            "close": pa.array([67200.0] * n, type=pa.float64()),
            "volume": pa.array([100.0] * n, type=pa.float64()),
            "quote_volume": pa.array([6720000.0] * n, type=pa.float64()),
            "trade_count": pa.array([100] * n, type=pa.int64()),
            "taker_buy_volume": pa.array([50.0] * n, type=pa.float64()),
            "venue": ["binance"] * n,
        }
    )


def _funding_table(symbol: str, times: list[int]) -> pa.Table:
    """Build a funding table for the given settlement times."""
    n = len(times)
    now = int(time.time() * 1000)
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array(times, type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "funding_rate": pa.array([0.0001] * n, type=pa.float64()),
            "mark_price": pa.array([67000.0] * n, type=pa.float64()),
        }
    )


def _oi_table(symbol: str, times: list[int]) -> pa.Table:
    """Build an OI table (only used to prove the plan ignores OI)."""
    n = len(times)
    now = int(time.time() * 1000)
    return pa.table(
        {
            "event_time": pa.array(times, type=pa.int64()),
            "available_at": pa.array([t + 300_000 for t in times], type=pa.int64()),
            "ingested_at": pa.array([now] * n, type=pa.int64()),
            "symbol": [symbol] * n,
            "sum_open_interest": pa.array([50000.0] * n, type=pa.float64()),
            "sum_open_interest_value": pa.array([3350000000.0] * n, type=pa.float64()),
        }
    )


def _kline_times(n: int) -> list[int]:
    """Minute-grid open times covering [W0, W0 + n minutes)."""
    return [W0 + i * MIN_MS for i in range(n)]


def _funding_times(n_days: int) -> list[int]:
    """8h-grid settlement times fully covering [W0, W0 + n_days days)."""
    per_day = DAY_MS // FUNDING_MS
    return [W0 + i * FUNDING_MS for i in range(n_days * per_day)]


def _write(table: pa.Table, base_path: Path, symbol: str, dataset: str, dedup: list[str]) -> None:
    write_records_partitioned(table, base_path, symbol, dataset, dedup)


def _write_full_klines(base_path: Path, symbol: str = SYMBOL, n: int = 2880) -> None:
    _write(_kline_table(symbol, _kline_times(n)), base_path, symbol, "klines_1m", CANDLE_DEDUP_KEY)


def _write_full_funding(base_path: Path, symbol: str = SYMBOL, n_days: int = 2) -> None:
    _write(
        _funding_table(symbol, _funding_times(n_days)),
        base_path,
        symbol,
        "funding",
        FUNDING_DEDUP_KEY,
    )


def _drop(times: list[int], indices: set[int]) -> list[int]:
    return [t for i, t in enumerate(times) if i not in indices]


def _build(
    base_path: Path,
    *,
    symbols: list[str] | None = None,
    window_start: int = W0,
    window_end: int = W1,
    warmup_bars: int = 0,
    timeframe: str = "1m",
) -> DataReadinessPlan:
    return build_readiness_plan(
        symbols if symbols is not None else [SYMBOL],
        base_path=base_path,
        window_start_ms=window_start,
        window_end_ms=window_end,
        warmup_bars=warmup_bars,
        signal_timeframe=timeframe,
    )


class TestInteriorGap:
    def test_interior_gap_produces_exact_repair_interval(self, tmp_path: Path) -> None:
        _write(
            _kline_table(SYMBOL, _drop(_kline_times(2880), set(range(600, 605)))),
            tmp_path,
            SYMBOL,
            "klines_1m",
            CANDLE_DEDUP_KEY,
        )
        _write_full_funding(tmp_path)
        plan = _build(tmp_path)

        entry = next(e for e in plan.entries if e.dataset == "klines_1m")
        expected_gap = (W0 + 600 * MIN_MS, W0 + 604 * MIN_MS)
        assert entry.interior_gaps == [expected_gap]
        assert entry.missing_head is None
        assert entry.missing_tail is None
        assert entry.status == "needs_repair"
        assert "interior_gap" in entry.reasons

        kline_actions = [a for a in plan.actions if a.dataset == "klines_1m"]
        assert [(a.since_ms, a.until_ms) for a in kline_actions] == [expected_gap]
        assert plan.overall_status == "needs_repair"


class TestMissingHeadTail:
    def test_missing_head_and_tail_listed_as_repair_intervals(self, tmp_path: Path) -> None:
        times = _kline_times(2880)[10:2875]
        _write(_kline_table(SYMBOL, times), tmp_path, SYMBOL, "klines_1m", CANDLE_DEDUP_KEY)
        _write_full_funding(tmp_path)
        plan = _build(tmp_path)

        entry = next(e for e in plan.entries if e.dataset == "klines_1m")
        expected_head = (W0, W0 + 9 * MIN_MS)
        expected_tail = (W0 + 2875 * MIN_MS, W0 + 2879 * MIN_MS)
        assert entry.missing_head == expected_head
        assert entry.missing_tail == expected_tail
        assert entry.interior_gaps == []
        assert "missing_head" in entry.reasons
        assert "missing_tail" in entry.reasons
        assert entry.status == "needs_repair"

        kline_actions = [a for a in plan.actions if a.dataset == "klines_1m"]
        assert [(a.since_ms, a.until_ms) for a in kline_actions] == [expected_head, expected_tail]


class TestAllReady:
    def test_full_coverage_plan_is_ready(self, tmp_path: Path) -> None:
        _write_full_klines(tmp_path)
        _write_full_funding(tmp_path)
        plan = _build(tmp_path)

        assert plan.overall_status == "ready"
        assert plan.actions == []
        assert all(e.status == "ready" for e in plan.entries)
        klines = next(e for e in plan.entries if e.dataset == "klines_1m")
        funding = next(e for e in plan.entries if e.dataset == "funding")
        assert klines.bar_count == 2880
        assert klines.reasons == []
        assert funding.bar_count == 6  # 3 funding events per UTC day

    def test_data_beyond_window_is_not_a_tail_gap(self, tmp_path: Path) -> None:
        _write_full_klines(tmp_path, n=3 * 1440)  # 3 days stored, 2-day window
        _write_full_funding(tmp_path, n_days=3)
        plan = _build(tmp_path)

        klines = next(e for e in plan.entries if e.dataset == "klines_1m")
        assert klines.status == "ready"
        assert klines.missing_tail is None


class TestBlockedOverspan:
    def test_overspan_klines_repair_blocks_the_plan(self, tmp_path: Path) -> None:
        plan = _build(tmp_path, window_start=W0, window_end=W0 + 130 * DAY_MS)

        assert plan.overall_status == "blocked"
        klines = next(e for e in plan.entries if e.dataset == "klines_1m")
        assert klines.status == "blocked"
        assert "no_local_data" in klines.reasons
        assert "missing_head" in klines.reasons
        assert "repair_span_exceeds_limit" in klines.reasons
        # The blocked (overspan) klines entry contributes no fetch actions:
        # never fill the gap. Chunkable funding actions may still be listed.
        assert [a for a in plan.actions if a.dataset == "klines_1m"] == []
        report = render_readiness_report(plan)
        assert "阻塞" in report

    def test_repair_exactly_at_limit_still_repairable(self, tmp_path: Path) -> None:
        plan = _build(tmp_path, window_start=W0, window_end=W0 + 120 * DAY_MS)

        klines = next(e for e in plan.entries if e.dataset == "klines_1m")
        assert klines.status == "needs_repair"
        kline_actions = [a for a in plan.actions if a.dataset == "klines_1m"]
        assert kline_actions[0].since_ms == plan.data_start_ms
        assert kline_actions[0].until_ms == plan.data_end_ms - MIN_MS
        assert kline_actions[0].span_ms <= DEFAULT_MAX_FETCH_SPAN_DAYS * DAY_MS


class TestFundingClamp:
    def test_long_funding_repair_chunked_to_venue_window(self, tmp_path: Path) -> None:
        plan = _build(tmp_path, window_start=W0, window_end=W0 + 70 * DAY_MS)

        funding_actions = [a for a in plan.actions if a.dataset == "funding"]
        assert len(funding_actions) == 3
        for action in funding_actions:
            assert action.span_ms <= FUNDING_MAX_FETCH_SPAN_MS
        assert funding_actions[0].since_ms == plan.data_start_ms
        assert funding_actions[-1].until_ms == plan.data_end_ms - FUNDING_MS
        for i in range(1, len(funding_actions)):
            prev, nxt = funding_actions[i - 1], funding_actions[i]
            assert nxt.since_ms == prev.until_ms + FUNDING_MS
        # 70-day klines repair is under the 120-day limit -> needs repair.
        assert plan.overall_status == "needs_repair"


class TestOIExcluded:
    def test_plan_never_contains_oi(self, tmp_path: Path) -> None:
        _write_full_klines(tmp_path)
        oi_times = [W0 + i * 300_000 for i in range(12) if i not in {4, 5, 6, 7}]
        _write(_oi_table(SYMBOL, oi_times), tmp_path, SYMBOL, "oi", OI_DEDUP_KEY)
        plan = _build(tmp_path)

        assert {e.dataset for e in plan.entries} == {"klines_1m", "funding"}
        assert all(a.dataset in {"klines_1m", "funding"} for a in plan.actions)
        # OI gaps must not leak into any entry.
        assert all(not e.interior_gaps or e.dataset != "oi" for e in plan.entries)
        assert "oi" not in render_readiness_report(plan)


class TestApplyRepairActions:
    def test_records_outcomes_per_action(self, tmp_path: Path) -> None:
        _write(
            _kline_table(SYMBOL, _drop(_kline_times(2880), set(range(600, 605)))),
            tmp_path,
            SYMBOL,
            "klines_1m",
            CANDLE_DEDUP_KEY,
        )
        plan = _build(tmp_path)
        kline_action = next(a for a in plan.actions if a.dataset == "klines_1m")

        with (
            patch("kronos.research.verdict.readiness.sync_klines") as mock_klines,
            patch(
                "kronos.research.verdict.readiness.sync_funding",
                side_effect=DataError("boom"),
            ),
        ):
            mock_klines.return_value = 300
            outcomes = apply_repair_actions(
                plan,
                base_path=tmp_path,
                max_retries=3,
                request_interval_ms=0,
            )

        assert [o.status for o in outcomes] == ["ok", "error"]
        assert outcomes[0].dataset == "klines_1m"
        assert outcomes[0].rows_fetched == 300
        assert outcomes[0].error is None
        assert outcomes[1].dataset == "funding"
        assert outcomes[1].rows_fetched == 0
        assert outcomes[1].error is not None and "boom" in outcomes[1].error
        mock_klines.assert_called_once_with(
            SYMBOL,
            base_path=tmp_path,
            since=kline_action.since_ms,
            max_retries=3,
            request_interval_ms=0,
        )

    def test_funding_only_plan_repairs_funding(self, tmp_path: Path) -> None:
        _write_full_klines(tmp_path)  # klines ready, funding absent
        plan = _build(tmp_path)

        with patch("kronos.research.verdict.readiness.sync_funding") as mock_funding:
            mock_funding.return_value = 3
            outcomes = apply_repair_actions(plan, base_path=tmp_path)

        assert [o.status for o in outcomes] == ["ok"]
        assert outcomes[0].dataset == "funding"
        assert outcomes[0].since_ms == plan.data_start_ms
        assert mock_funding.call_count == 1


class TestReport:
    def test_renders_pm_readable_chinese_report(self, tmp_path: Path) -> None:
        _write_full_klines(tmp_path, "BTCUSDT")
        _write_full_funding(tmp_path, "BTCUSDT")
        _write(
            _kline_table("ETHUSDT", _drop(_kline_times(2880), set(range(600, 605)))),
            tmp_path,
            "ETHUSDT",
            "klines_1m",
            CANDLE_DEDUP_KEY,
        )
        plan = _build(tmp_path, symbols=["BTCUSDT", "ETHUSDT"])

        report = render_readiness_report(plan)
        assert "总体状态: 需修复" in report
        assert "就绪" in report  # BTCUSDT rows
        assert "BTCUSDT" in report
        assert "ETHUSDT" in report
        assert "1m K线" in report
        assert "资金费率" in report
        assert "内部缺口" in report
        assert "修复任务" in report
        entry_lines = [
            line
            for line in report.splitlines()
            if line.startswith("  ") and "[" in line and "]" in line
        ]
        assert len(entry_lines) == 4  # one line per symbol/dataset
        assert "oi" not in report


class TestWindowDayAlignment:
    @pytest.mark.parametrize(
        ("timeframe", "warmup_bars"),
        [("1m", 1500), ("1h", 200), ("15m", 96)],
    )
    def test_90_day_window_bounds_stay_utc_day_aligned(
        self,
        tmp_path: Path,
        timeframe: str,
        warmup_bars: int,
    ) -> None:
        window_end = W0 + 90 * DAY_MS
        plan = _build(
            tmp_path,
            window_start=W0,
            window_end=window_end,
            warmup_bars=warmup_bars,
            timeframe=timeframe,
        )

        tf_minutes = {"1m": 1, "1h": 60, "15m": 15}[timeframe]
        warmup_start = W0 - warmup_bars * tf_minutes * MIN_MS
        assert plan.window_start_ms == W0
        assert plan.window_end_ms == window_end
        assert plan.warmup_start_ms == warmup_start
        # Effective data bounds are floored/ceiled to complete UTC days.
        assert plan.data_start_ms == (warmup_start // DAY_MS) * DAY_MS
        assert plan.data_start_ms % DAY_MS == 0
        assert plan.data_end_ms == window_end
        assert plan.data_end_ms % DAY_MS == 0
        assert plan.window_end_ms - plan.window_start_ms == 90 * DAY_MS


class TestValidation:
    def test_rejects_empty_symbols(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="symbols"):
            _build(tmp_path, symbols=[])

    def test_rejects_inverted_window(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="window_end_ms"):
            _build(tmp_path, window_start=W1, window_end=W0)

    def test_rejects_unknown_timeframe(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="signal_timeframe"):
            _build(tmp_path, timeframe="2m")

    def test_rejects_negative_warmup(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="warmup_bars"):
            _build(tmp_path, warmup_bars=-1)

    def test_rejects_invalid_fetch_span_limit(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="max_fetch_span_days"):
            build_readiness_plan(
                [SYMBOL],
                base_path=tmp_path,
                window_start_ms=W0,
                window_end_ms=W1,
                warmup_bars=0,
                signal_timeframe="1m",
                max_fetch_span_days=0,
            )
