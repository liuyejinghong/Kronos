"""Unit tests for data schemas."""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from kronos.data.schemas.candle import CANDLE_DEDUP_KEY, CandleRecord
from kronos.data.schemas.funding import FUNDING_DEDUP_KEY, FundingRecord
from kronos.data.schemas.oi import OI_DEDUP_KEY, OIRecord

# === Fixtures ===

NOW_MS = int(time.time() * 1000)
BAR_DURATION_MS = 60_000  # 1 minute


def _valid_candle(**overrides: object) -> dict:  # type: ignore[type-arg]
    """Build a valid candle record dict."""
    base = {
        "event_time": NOW_MS,
        "available_at": NOW_MS + BAR_DURATION_MS,
        "ingested_at": NOW_MS + BAR_DURATION_MS + 1000,
        "symbol": "BTCUSDT",
        "open": 67000.0,
        "high": 67500.0,
        "low": 66800.0,
        "close": 67200.0,
        "volume": 123.45,
        "quote_volume": 8_300_000.0,
        "trade_count": 5432,
        "taker_buy_volume": 61.23,
        "venue": "binance",
    }
    base.update(overrides)
    return base


def _valid_funding(**overrides: object) -> dict:  # type: ignore[type-arg]
    """Build a valid funding record dict."""
    base = {
        "event_time": NOW_MS,
        "available_at": NOW_MS,
        "ingested_at": NOW_MS + 1000,
        "symbol": "BTCUSDT",
        "funding_rate": 0.0001,
        "mark_price": 67000.0,
    }
    base.update(overrides)
    return base


def _valid_oi(**overrides: object) -> dict:  # type: ignore[type-arg]
    """Build a valid OI record dict."""
    base = {
        "event_time": NOW_MS,
        "available_at": NOW_MS,
        "ingested_at": NOW_MS + 1000,
        "symbol": "BTCUSDT",
        "sum_open_interest": 50000.0,
        "sum_open_interest_value": 3_350_000_000.0,
    }
    base.update(overrides)
    return base


# === Candle Tests ===

class TestCandleRecord:
    """Tests for CandleRecord schema."""

    def test_valid_candle(self) -> None:
        record = CandleRecord(**_valid_candle())
        assert record.symbol == "BTCUSDT"
        assert record.open == 67000.0

    def test_ohlc_low_above_open(self) -> None:
        with pytest.raises(ValidationError, match=r"low.*must be.*open"):
            CandleRecord(**_valid_candle(low=68000.0))

    def test_ohlc_high_below_close(self) -> None:
        with pytest.raises(ValidationError, match=r"high.*must be.*close"):
            CandleRecord(**_valid_candle(high=66000.0))

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CandleRecord(**_valid_candle(volume=-1.0))

    def test_available_at_must_be_after_event_time(self) -> None:
        with pytest.raises(ValidationError, match=r"available_at.*must be.*event_time"):
            CandleRecord(**_valid_candle(available_at=NOW_MS))

    def test_missing_required_field(self) -> None:
        data = _valid_candle()
        del data["symbol"]
        with pytest.raises(ValidationError):
            CandleRecord(**data)

    def test_dedup_key(self) -> None:
        assert CANDLE_DEDUP_KEY == ["symbol", "event_time"]


# === Funding Tests ===

class TestFundingRecord:
    """Tests for FundingRecord schema."""

    def test_valid_funding(self) -> None:
        record = FundingRecord(**_valid_funding())
        assert record.funding_rate == 0.0001

    def test_negative_funding_rate_allowed(self) -> None:
        record = FundingRecord(**_valid_funding(funding_rate=-0.0003))
        assert record.funding_rate == -0.0003

    def test_zero_mark_price_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FundingRecord(**_valid_funding(mark_price=0.0))

    def test_dedup_key(self) -> None:
        assert FUNDING_DEDUP_KEY == ["symbol", "event_time"]


# === OI Tests ===

class TestOIRecord:
    """Tests for OIRecord schema."""

    def test_valid_oi(self) -> None:
        record = OIRecord(**_valid_oi())
        assert record.sum_open_interest == 50000.0

    def test_negative_oi_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OIRecord(**_valid_oi(sum_open_interest=-1.0))

    def test_negative_oi_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OIRecord(**_valid_oi(sum_open_interest_value=-1.0))

    def test_dedup_key(self) -> None:
        assert OI_DEDUP_KEY == ["symbol", "event_time"]
