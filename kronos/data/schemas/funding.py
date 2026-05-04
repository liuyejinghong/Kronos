"""Funding rate data schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FundingRecord(BaseModel):
    """Single funding rate record.

    Funding is sparse data (typically every 8 hours).
    """

    # Three-timestamp PIT model
    event_time: int = Field(description="Funding time, epoch-ms")
    available_at: int = Field(description="Settlement time, epoch-ms. PIT anchor.")
    ingested_at: int = Field(description="Ingestion time, epoch-ms. Audit only.")

    # Identity
    symbol: str = Field(description="Trading pair, e.g. BTCUSDT")

    # Data
    funding_rate: float = Field(description="Funding rate value")
    mark_price: float = Field(gt=0, description="Mark price at funding time")


# Dedup key for funding data
FUNDING_DEDUP_KEY: list[str] = ["symbol", "event_time"]
