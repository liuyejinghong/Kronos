"""Open interest data schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OIRecord(BaseModel):
    """Single open interest record.

    Note: Binance OI history endpoint only provides ~30 days of data.
    """

    # Three-timestamp PIT model
    event_time: int = Field(description="OI snapshot time, epoch-ms")
    available_at: int = Field(description="When OI data became observable, epoch-ms")
    ingested_at: int = Field(description="Ingestion time, epoch-ms. Audit only.")

    # Identity
    symbol: str = Field(description="Trading pair, e.g. BTCUSDT")

    # Data
    sum_open_interest: float = Field(ge=0, description="Total open interest in contracts")
    sum_open_interest_value: float = Field(ge=0, description="Total OI value in USDT")


# Dedup key for OI data
OI_DEDUP_KEY: list[str] = ["symbol", "event_time"]
