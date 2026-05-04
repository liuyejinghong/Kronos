"""Unit tests for Binance USDM adapter (mocked, no real API calls)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kronos.common.errors import IngestionError
from kronos.data.loaders.binance_usdm import (
    _request_with_retry,
    fetch_funding_rates,
    fetch_klines,
    fetch_open_interest,
)


def _mock_kline_bar(open_time: int, close_time: int) -> list[Any]:
    """Create a mock kline bar in Binance API format."""
    return [
        open_time,      # 0: open time
        "67000.0",      # 1: open
        "67500.0",      # 2: high
        "66800.0",      # 3: low
        "67200.0",      # 4: close
        "100.0",        # 5: volume
        close_time,     # 6: close time
        "6720000.0",    # 7: quote volume
        100,            # 8: trade count
        "50.0",         # 9: taker buy volume
        "0",            # 10: ignore
        "0",            # 11: ignore
    ]


def _mock_funding_record(funding_time: int) -> dict[str, Any]:
    """Create a mock funding rate record."""
    return {
        "symbol": "BTCUSDT",
        "fundingTime": funding_time,
        "fundingRate": "0.0001",
        "markPrice": "67000.00",
    }


def _mock_oi_record(timestamp: int) -> dict[str, Any]:
    """Create a mock OI record."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": timestamp,
        "sumOpenInterest": "50000.0",
        "sumOpenInterestValue": "3350000000.0",
    }


class TestRequestWithRetry:
    @patch("kronos.data.loaders.binance_usdm.httpx.get")
    @patch("kronos.data.loaders.binance_usdm.time.sleep")
    def test_success(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"data": 1}]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _request_with_retry("http://test", {}, request_interval_ms=0)
        assert result == [{"data": 1}]

    @patch("kronos.data.loaders.binance_usdm.httpx.get")
    @patch("kronos.data.loaders.binance_usdm.time.sleep")
    def test_429_retries(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "1"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = []
        mock_200.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_429, mock_200]
        result = _request_with_retry("http://test", {}, max_retries=2, request_interval_ms=0)
        assert result == []

    @patch("kronos.data.loaders.binance_usdm.httpx.get")
    @patch("kronos.data.loaders.binance_usdm.time.sleep")
    def test_exhausted_retries(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        import httpx as httpx_mod
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        error = httpx_mod.HTTPStatusError("Server Error", request=MagicMock(), response=mock_resp)
        mock_resp.raise_for_status.side_effect = error
        mock_get.return_value = mock_resp

        with pytest.raises(IngestionError, match=r"retries"):
            _request_with_retry("http://test", {}, max_retries=1, request_interval_ms=0)


class TestFetchKlines:
    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_single_page(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        now = 1709300000000
        mock_now.return_value = now
        bars = [
            _mock_kline_bar(1709251200000 + i * 60000, 1709251200000 + (i + 1) * 60000 - 1)
            for i in range(5)
        ]
        mock_req.return_value = bars

        table = fetch_klines("BTCUSDT", start_time=1709251200000, request_interval_ms=0)
        assert table.num_rows == 5
        assert "event_time" in table.column_names
        assert "available_at" in table.column_names
        assert "symbol" in table.column_names

    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_excludes_unclosed_bars(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        now = 1709251200000 + 3 * 60000  # Only 3 minutes have passed
        mock_now.return_value = now
        bars = [
            _mock_kline_bar(1709251200000 + i * 60000, 1709251200000 + (i + 1) * 60000 - 1)
            for i in range(5)
        ]
        mock_req.return_value = bars

        table = fetch_klines("BTCUSDT", start_time=1709251200000, request_interval_ms=0)
        assert table.num_rows == 3  # Only first 3 bars are closed

    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_empty_response(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        mock_now.return_value = 1709300000000
        mock_req.return_value = []

        table = fetch_klines("BTCUSDT", request_interval_ms=0)
        assert table.num_rows == 0
        assert "event_time" in table.column_names  # Schema preserved


class TestFetchFunding:
    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_fetches_records(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        mock_now.return_value = 1709300000000
        records = [_mock_funding_record(1709251200000 + i * 28800000) for i in range(3)]
        mock_req.return_value = records

        table = fetch_funding_rates("BTCUSDT", start_time=1709251200000, request_interval_ms=0)
        assert table.num_rows == 3
        assert "funding_rate" in table.column_names

    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_available_at_equals_event_time(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        mock_now.return_value = 1709300000000
        mock_req.return_value = [_mock_funding_record(1709251200000)]

        table = fetch_funding_rates("BTCUSDT", request_interval_ms=0)
        assert table.column("event_time")[0].as_py() == table.column("available_at")[0].as_py()


class TestFetchOI:
    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_fetches_records(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        mock_now.return_value = 1709300000000
        records = [_mock_oi_record(1709251200000 + i * 300000) for i in range(5)]
        mock_req.return_value = records

        table = fetch_open_interest("BTCUSDT", start_time=1709251200000, request_interval_ms=0)
        assert table.num_rows == 5
        assert "sum_open_interest" in table.column_names

    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_available_at_has_offset(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        mock_now.return_value = 1709300000000
        mock_req.return_value = [_mock_oi_record(1709251200000)]

        table = fetch_open_interest("BTCUSDT", request_interval_ms=0)
        event = table.column("event_time")[0].as_py()
        available = table.column("available_at")[0].as_py()
        assert available == event + 300000  # 5m offset

    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_empty_returns_schema(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        mock_now.return_value = 1709300000000
        mock_req.return_value = []

        table = fetch_open_interest("BTCUSDT", request_interval_ms=0)
        assert table.num_rows == 0
        assert "sum_open_interest" in table.column_names

    @patch("kronos.data.loaders.binance_usdm._request_with_retry")
    @patch("kronos.data.loaders.binance_usdm._now_ms")
    def test_pagination_at_limit(self, mock_now: MagicMock, mock_req: MagicMock) -> None:
        """When first page returns exactly OI_LIMIT (500) records, must paginate."""
        mock_now.return_value = 1709300000000
        base_ts = 1709251200000
        interval = 300_000  # 5m

        # First page: 500 records (triggers pagination)
        page1 = [_mock_oi_record(base_ts + i * interval) for i in range(500)]
        # Second page: 200 records (< OI_LIMIT, stops pagination)
        page2 = [_mock_oi_record(base_ts + (500 + i) * interval) for i in range(200)]

        mock_req.side_effect = [page1, page2]

        table = fetch_open_interest("BTCUSDT", start_time=base_ts, request_interval_ms=0)
        assert table.num_rows == 700
        # Verify second call used correct startTime
        second_call_params = mock_req.call_args_list[1][0][1]
        expected_start = int(page1[-1]["timestamp"]) + 1
        assert second_call_params["startTime"] == expected_start
