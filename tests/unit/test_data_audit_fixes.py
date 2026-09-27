"""Regression tests for the 2026-09-27 audit data-layer fixes (FSR-007/008/009/030)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from kronos.common.errors import IngestionError
from kronos.data.loaders.binance_usdm import (
    _request_with_retry,
    fetch_open_interest,
)
from kronos.data.storage.query import _parse_datetime_to_ms
from kronos.data.sync import sync_klines


def _ok_response(payload: list[Any]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


class TestParseDatetimeTimezone:
    def test_offset_aware_iso_converts_not_discards(self) -> None:
        # +08:00 midnight is 8h before UTC midnight (FSR-007).
        assert _parse_datetime_to_ms("2024-03-01T00:00:00+08:00") == 1709222400000

    def test_naive_and_zulu_stay_utc(self) -> None:
        assert _parse_datetime_to_ms("2024-03-01T00:00:00") == 1709251200000
        assert _parse_datetime_to_ms("2024-03-01T00:00:00Z") == 1709251200000
        assert _parse_datetime_to_ms("2024-03-01T00:00:00+00:00") == 1709251200000


class TestRequestThrottle:
    @patch("kronos.data.loaders.binance_usdm.httpx.get")
    def test_interval_enforced_between_pagination_requests(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _ok_response([])
        interval_ms = 120
        start = time.monotonic()
        for _ in range(3):
            _request_with_retry("https://x", {}, max_retries=0, request_interval_ms=interval_ms)
        elapsed = time.monotonic() - start
        assert mock_get.call_count == 3
        # 3 requests must span at least 2 intervals.
        assert elapsed >= 2 * interval_ms / 1000

    @patch("kronos.data.loaders.binance_usdm.httpx.get")
    @patch("kronos.data.loaders.binance_usdm.time.sleep")
    def test_permanent_4xx_fails_fast(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        resp = MagicMock()
        resp.status_code = 400
        resp.text = '{"code":-1130,"msg":"invalid"}'
        error = __import__("httpx").HTTPStatusError("400", request=MagicMock(), response=resp)
        resp.raise_for_status.side_effect = error
        mock_get.return_value = resp
        with pytest.raises(IngestionError, match="rejected request \\(400\\)"):
            _request_with_retry("https://x", {}, max_retries=5, request_interval_ms=0)
        assert mock_get.call_count == 1

    @patch("kronos.data.loaders.binance_usdm.httpx.get")
    @patch("kronos.data.loaders.binance_usdm.time.sleep")
    def test_non_numeric_retry_after_does_not_crash(
        self, mock_sleep: MagicMock, mock_get: MagicMock
    ) -> None:
        limited = MagicMock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "soon-ish"}
        ok = _ok_response([{"a": 1}])
        mock_get.side_effect = [limited, ok]
        result = _request_with_retry("https://x", {}, max_retries=2, request_interval_ms=0)
        assert result == [{"a": 1}]


class TestOiWindowClamp:
    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    def test_old_start_clamped_to_30d_window(self, mock_retry: MagicMock) -> None:
        captured: dict[str, Any] = {}

        def capture(url: str, params: dict[str, Any], **_kw: Any) -> list[Any]:
            captured.update(params)
            return []

        mock_retry.side_effect = capture
        very_old = int(time.time() * 1000) - 200 * 24 * 3600 * 1000
        fetch_open_interest("BTCUSDT", start_time=very_old, request_interval_ms=0)
        assert captured["startTime"] > int(time.time() * 1000) - 31 * 24 * 3600 * 1000


class TestSyncSchemaValidation:
    def test_malformed_row_rejected_before_store(self, tmp_path: Any) -> None:
        base = 1709251200000
        now = int(time.time() * 1000)
        bad = pa.table({
            "event_time": pa.array([base], type=pa.int64()),
            "available_at": pa.array([base + 60_000], type=pa.int64()),
            "ingested_at": pa.array([now], type=pa.int64()),
            "symbol": ["BTCUSDT"],
            "open": pa.array([67000.0], type=pa.float64()),
            "high": pa.array([66800.0], type=pa.float64()),  # high < open → invalid
            "low": pa.array([66900.0], type=pa.float64()),
            "close": pa.array([67200.0], type=pa.float64()),
            "volume": pa.array([100.0], type=pa.float64()),
            "quote_volume": pa.array([6720000.0], type=pa.float64()),
            "trade_count": pa.array([100], type=pa.int64()),
            "taker_buy_volume": pa.array([50.0], type=pa.float64()),
            "venue": ["binance"],
        })
        with (
            patch("kronos.data.sync.fetch_klines", return_value=bad),
            pytest.raises(IngestionError, match="Schema validation failed"),
        ):
            sync_klines("BTCUSDT", base_path=tmp_path)
