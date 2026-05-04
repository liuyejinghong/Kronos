"""K-line (candlestick) data schema."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CandleRecord(BaseModel):
    """Single K-line bar record.

    All timestamps are epoch-ms (int64).
    All prices are float64.
    """

    # Three-timestamp PIT model
    event_time: int = Field(description="Bar open time, epoch-ms")
    available_at: int = Field(description="Bar close time, epoch-ms. PIT anchor.")
    ingested_at: int = Field(description="Ingestion time, epoch-ms. Audit only.")

    # Identity
    symbol: str = Field(description="Trading pair, e.g. BTCUSDT")

    # OHLCV
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    quote_volume: float = Field(ge=0)
    trade_count: int = Field(ge=0)
    taker_buy_volume: float = Field(ge=0)

    # Source
    venue: str = Field(default="binance")

    @model_validator(mode="after")
    def validate_ohlc_consistency(self) -> CandleRecord:
        """Validate OHLC price relationships."""
        if self.low > self.open or self.low > self.close:
            msg = f"low ({self.low}) must be <= open ({self.open}) and close ({self.close})"
            raise ValueError(msg)
        if self.high < self.open or self.high < self.close:
            msg = f"high ({self.high}) must be >= open ({self.open}) and close ({self.close})"
            raise ValueError(msg)
        if self.available_at <= self.event_time:
            msg = f"available_at ({self.available_at}) must be > event_time ({self.event_time})"
            raise ValueError(msg)
        return self


# Dedup key for K-line data
CANDLE_DEDUP_KEY: list[str] = ["symbol", "event_time"]
