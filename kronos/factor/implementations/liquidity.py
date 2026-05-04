"""Volume/liquidity factor implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from kronos.factor.base import BaseFactor

if TYPE_CHECKING:
    import pandas as pd


class TakerBuyRatioFactor(BaseFactor):
    """Crypto-native taker buy ratio factor.

    Higher values mean aggressive buy flow dominates total traded volume.
    """

    name = "taker_buy_ratio"
    family = "volume_liquidity"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["volume", "taker_buy_volume"]
    description = (
        "Rolling taker-buy participation ratio. Captures persistent aggressive "
        "buying relative to total traded volume."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        total = df["volume"].clip(lower=1e-12)
        ratio = df["taker_buy_volume"] / total
        return ratio.rolling(self.lookback, min_periods=self.lookback).mean()


class VolumeDroughtFactor(BaseFactor):
    """Low-participation trend filter.

    Higher values mean current volume is lower than its recent baseline,
    which is treated as a cleaner trend regime candidate.
    """

    name = "volume_drought"
    family = "volume_liquidity"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["volume"]
    description = (
        "Inverse rolling participation score. Highlights bars where realised "
        "volume is unusually low versus recent average activity."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        avg_volume = df["volume"].rolling(self.lookback, min_periods=self.lookback).mean()
        drought = 1.0 - (df["volume"] / avg_volume.clip(lower=1e-12))
        return drought


class MoveDensityFactor(BaseFactor):
    """Volume per unit of absolute close move.

    Higher values mean more traded volume is required per unit of realised move.
    """

    name = "move_density"
    family = "volume_liquidity"
    version = "1.0.0"
    lookback = 20
    warmup_bars = 20
    universe = "crypto_perp"
    required_columns: ClassVar[list[str]] = ["volume", "close"]
    description = (
        "Rolling volume-to-move density. Measures how much participation is "
        "needed to generate each unit of realised close-to-close movement."
    )

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.warmup_bars = lookback

    def metadata(self) -> dict[str, Any]:
        return {"lookback": self.lookback}

    def _compute(self, df: pd.DataFrame) -> pd.Series:
        move = df["close"].diff().abs().clip(lower=1e-12)
        density = df["volume"] / move
        return density.rolling(self.lookback, min_periods=self.lookback).mean()
