"""Binance USDM Futures data adapter."""

from __future__ import annotations

import time
from typing import Any

import httpx
import pyarrow as pa

from kronos.common.errors import DataError, IngestionError
from kronos.common.log import get_logger

log = get_logger("kronos.data.loaders.binance_usdm")

BASE_URL = "https://fapi.binance.com"
KLINE_LIMIT = 1500
FUNDING_LIMIT = 1000
OI_LIMIT = 500

# DataError is part of the public error surface exported alongside IngestionError.
__all__ = ["DataError", "fetch_funding_rates", "fetch_klines", "fetch_open_interest"]


def _now_ms() -> int:
    """Current UTC time in epoch-ms."""
    return int(time.time() * 1000)


def _request_with_retry(
    url: str,
    params: dict[str, Any],
    *,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> list[Any]:
    """Make an HTTP GET request with retry and exponential backoff.

    Args:
        url: Request URL.
        params: Query parameters.
        max_retries: Maximum retry attempts.
        request_interval_ms: Minimum interval between requests in ms.

    Returns:
        Parsed JSON response (expected to be a list).

    Raises:
        IngestionError: If all retries fail.
    """
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(request_interval_ms / 1000)
        try:
            resp = httpx.get(url, params=params, timeout=30.0)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 0))
                wait = max(retry_after, 2**attempt)
                log.warning(
                    "api.rate_limited",
                    attempt=attempt,
                    wait_s=wait,
                    url=url,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            result: list[Any] = resp.json()
            return result

        except httpx.HTTPStatusError as e:
            if attempt < max_retries:
                wait = 2**attempt
                log.warning("api.error", status=e.response.status_code, attempt=attempt, wait_s=wait)
                time.sleep(wait)
            else:
                raise IngestionError(f"API request failed after {max_retries} retries: {e}") from e

        except httpx.HTTPError as e:
            if attempt < max_retries:
                wait = 2**attempt
                log.warning("api.connection_error", error=str(e), attempt=attempt, wait_s=wait)
                time.sleep(wait)
            else:
                raise IngestionError(f"Connection failed after {max_retries} retries: {e}") from e

    raise IngestionError(f"Request failed after {max_retries} retries")


def fetch_klines(
    symbol: str,
    *,
    start_time: int | None = None,
    end_time: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> pa.Table:
    """Fetch 1m kline data from Binance USDM.

    Paginates through all available data from start_time to end_time.
    Excludes unclosed bars (close_time > current time).

    Args:
        symbol: Trading pair (e.g. "BTCUSDT").
        start_time: Start time in epoch-ms. If None, fetches from earliest.
        end_time: End time in epoch-ms. If None, fetches up to now.
        max_retries: Max retry attempts per request.
        request_interval_ms: Min interval between requests.

    Returns:
        PyArrow Table with kline data.
    """
    url = f"{BASE_URL}/fapi/v1/klines"
    now = _now_ms()
    all_rows: list[dict[str, Any]] = []

    current_start = start_time or 0

    while True:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": "1m",
            "limit": KLINE_LIMIT,
            "startTime": current_start,
        }
        if end_time is not None:
            params["endTime"] = end_time

        data = _request_with_retry(
            url,
            params,
            max_retries=max_retries,
            request_interval_ms=request_interval_ms,
        )

        if not data:
            break

        for bar in data:
            open_time = int(bar[0])
            close_time = int(bar[6])

            # Skip unclosed bars
            if close_time > now:
                continue

            all_rows.append(
                {
                    "event_time": open_time,
                    "available_at": close_time,
                    "ingested_at": now,
                    "symbol": symbol,
                    "open": float(bar[1]),
                    "high": float(bar[2]),
                    "low": float(bar[3]),
                    "close": float(bar[4]),
                    "volume": float(bar[5]),
                    "quote_volume": float(bar[7]),
                    "trade_count": int(bar[8]),
                    "taker_buy_volume": float(bar[9]),
                    "venue": "binance",
                }
            )

        # Check if we got a full page — if not, we're done
        if len(data) < KLINE_LIMIT:
            break

        # Move start to after the last bar
        last_close_time = int(data[-1][6])
        current_start = last_close_time + 1

        log.info(
            "klines.page_fetched",
            symbol=symbol,
            bars=len(data),
            total=len(all_rows),
        )

    if not all_rows:
        return pa.table(
            {
                "event_time": pa.array([], type=pa.int64()),
                "available_at": pa.array([], type=pa.int64()),
                "ingested_at": pa.array([], type=pa.int64()),
                "symbol": pa.array([], type=pa.string()),
                "open": pa.array([], type=pa.float64()),
                "high": pa.array([], type=pa.float64()),
                "low": pa.array([], type=pa.float64()),
                "close": pa.array([], type=pa.float64()),
                "volume": pa.array([], type=pa.float64()),
                "quote_volume": pa.array([], type=pa.float64()),
                "trade_count": pa.array([], type=pa.int64()),
                "taker_buy_volume": pa.array([], type=pa.float64()),
                "venue": pa.array([], type=pa.string()),
            }
        )

    log.info("klines.fetched", symbol=symbol, total_bars=len(all_rows))
    return pa.Table.from_pylist(all_rows)


def fetch_funding_rates(
    symbol: str,
    *,
    start_time: int | None = None,
    end_time: int | None = None,
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> pa.Table:
    """Fetch funding rate history from Binance USDM.

    Args:
        symbol: Trading pair.
        start_time: Start time in epoch-ms.
        end_time: End time in epoch-ms.
        max_retries: Max retries per request.
        request_interval_ms: Min interval between requests.

    Returns:
        PyArrow Table with funding rate data.
    """
    url = f"{BASE_URL}/fapi/v1/fundingRate"
    now = _now_ms()
    all_rows: list[dict[str, Any]] = []

    current_start = start_time or 0

    while True:
        params: dict[str, Any] = {
            "symbol": symbol,
            "limit": FUNDING_LIMIT,
            "startTime": current_start,
        }
        if end_time is not None:
            params["endTime"] = end_time

        data = _request_with_retry(
            url,
            params,
            max_retries=max_retries,
            request_interval_ms=request_interval_ms,
        )

        if not data:
            break

        for record in data:
            funding_time = int(record["fundingTime"])
            all_rows.append(
                {
                    "event_time": funding_time,
                    "available_at": funding_time,  # settlement = publication
                    "ingested_at": now,
                    "symbol": symbol,
                    "funding_rate": float(record["fundingRate"]),
                    "mark_price": float(record.get("markPrice", 0)),
                }
            )

        if len(data) < FUNDING_LIMIT:
            break

        last_time = int(data[-1]["fundingTime"])
        current_start = last_time + 1

        log.info(
            "funding.page_fetched",
            symbol=symbol,
            records=len(data),
            total=len(all_rows),
        )

    if not all_rows:
        return pa.table(
            {
                "event_time": pa.array([], type=pa.int64()),
                "available_at": pa.array([], type=pa.int64()),
                "ingested_at": pa.array([], type=pa.int64()),
                "symbol": pa.array([], type=pa.string()),
                "funding_rate": pa.array([], type=pa.float64()),
                "mark_price": pa.array([], type=pa.float64()),
            }
        )

    log.info("funding.fetched", symbol=symbol, total_records=len(all_rows))
    return pa.Table.from_pylist(all_rows)


def fetch_open_interest(
    symbol: str,
    *,
    start_time: int | None = None,
    end_time: int | None = None,
    period: str = "5m",
    max_retries: int = 5,
    request_interval_ms: int = 200,
) -> pa.Table:
    """Fetch open interest history from Binance USDM.

    Note: Binance OI history endpoint only provides ~30 days of data.

    Args:
        symbol: Trading pair.
        start_time: Start time in epoch-ms.
        end_time: End time in epoch-ms.
        period: Sampling period (default "5m").
        max_retries: Max retries per request.
        request_interval_ms: Min interval between requests.

    Returns:
        PyArrow Table with OI data.
    """
    url = f"{BASE_URL}/futures/data/openInterestHist"
    now = _now_ms()
    # OI available_at offset: 5m = 300_000ms
    period_minutes: dict[str, int] = {
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "1d": 1440,
    }
    offset_ms = period_minutes.get(period, 5) * 60 * 1000

    all_rows: list[dict[str, Any]] = []
    current_start = start_time

    while True:
        params: dict[str, Any] = {
            "symbol": symbol,
            "period": period,
            "limit": OI_LIMIT,
        }
        if current_start is not None:
            params["startTime"] = current_start
        if end_time is not None:
            params["endTime"] = end_time

        data: list[dict[str, Any]] = []
        try:
            data = _request_with_retry(
                url,
                params,
                max_retries=max_retries,
                request_interval_ms=request_interval_ms,
            )
        except IngestionError:
            if not all_rows:
                log.warning("oi.history_limited", symbol=symbol)
            break

        if not data:
            if not all_rows:
                log.warning("oi.history_limited", symbol=symbol)
            break

        for record in data:
            ts = int(record["timestamp"])
            all_rows.append(
                {
                    "event_time": ts,
                    "available_at": ts + offset_ms,
                    "ingested_at": now,
                    "symbol": symbol,
                    "sum_open_interest": float(record["sumOpenInterest"]),
                    "sum_open_interest_value": float(record["sumOpenInterestValue"]),
                }
            )

        if len(data) < OI_LIMIT:
            break

        last_time = int(data[-1]["timestamp"])
        current_start = last_time + 1

        log.info(
            "oi.page_fetched",
            symbol=symbol,
            records=len(data),
            total=len(all_rows),
        )

    if not all_rows:
        return pa.table(
            {
                "event_time": pa.array([], type=pa.int64()),
                "available_at": pa.array([], type=pa.int64()),
                "ingested_at": pa.array([], type=pa.int64()),
                "symbol": pa.array([], type=pa.string()),
                "sum_open_interest": pa.array([], type=pa.float64()),
                "sum_open_interest_value": pa.array([], type=pa.float64()),
            }
        )

    log.info("oi.fetched", symbol=symbol, total_records=len(all_rows))
    return pa.Table.from_pylist(all_rows)
