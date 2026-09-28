"""Freqtrade strategy template for the frozen Kronos threshold variant (P08).

Renders one self-contained freqtrade strategy file (no kronos imports) that
encodes ``kronos_threshold_v1`` exactly as validated in the M0 semantic
comparison (``openspec/changes/p5-strategy-verdict-loop/m0/
kernel_evidence_semantics.md``):

- signals on completed 15m candles; freqtrade shifts signal columns by one
  candle and fills at the next candle open == the Kronos "next 1m open" fill;
- entry long ``q >= +1`` / short ``q <= -1`` (inclusive), flat only, never on
  the day-end bar; exit long ``q <= 0`` / short ``q >= 0``; day-end bar always
  exits a held position (tag ``day_end`` vs ``q_exit`` for score exits — the
  adapter maps these to ``day_end_flat`` / ``signal_exit``);
- no-reversal rule enforced with the confirm_trade_entry/exit same-candle
  guard (native freqtrade would close and reverse within one candle);
- warmup gate ``startup_candle_count = 96 + atr_period - 1``;
- ROI/stoploss/trailing disabled; futures CAN_SHORT; leverage fixed at 1.0;
- q/ATR arithmetic replicates the reference engine bit-for-bit (same true
  range formula, same sequential rolling sum).

The GPL-licensed freqtrade dependency stays inside the rendered file, which
only ever runs inside the pinned freqtrade venv subprocess (never imported by
kronos code).
"""

from __future__ import annotations

from typing import Final

STRATEGY_NAME: Final[str] = "KronosThresholdVariant"
"""Class name of the rendered strategy (must stay in sync with the runner)."""

TEMPLATE_VERSION: Final[str] = "kronos_threshold_v1-ft1"
"""Version of this template; bump when the rendered strategy changes."""

_TEMPLATE: Final[str] = '''
"""Kronos threshold variant (kronos_threshold_v1) for freqtrade __FT_VERSION__.

Rendered by kronos.research.verdict.kernel.strategy_template (P08).
Parameters: atr_period=__ATR_PERIOD__, volatility_multiplier=__MULT__.
Do not edit by hand: regenerate via the template instead.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy

TF_MS = 900_000
DAY_MS = 86_400_000
BARS_PER_UTC_DAY = 96
ENTRY_LONG_THRESHOLD = 1.0
ENTRY_SHORT_THRESHOLD = -1.0


class __NAME__(IStrategy):
    """Threshold variant on 15m futures: full-equity single position, 1x."""

    timeframe = "15m"
    can_short = True
    minimal_roi: dict = {}
    stoploss = -1.0
    trailing_stop = False
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    position_adjustment_enable = False

    # Warmup gate: first actionable signal bar == required_warmup_bars - 1
    # (96 + atr_period - 1), matching reference_ledger's
    # `index + 1 >= required_warmup_bars` (M0 evidence, case G05).
    atr_period = __ATR_PERIOD__
    volatility_multiplier = __MULT__
    startup_candle_count = __STARTUP__

    def leverage(
        self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side,
        **kwargs,
    ) -> float:
        return 1.0

    # --- no-same-candle reversal guard (frozen rule 2) ----------------------
    # Native freqtrade (CAN_SHORT) closes and re-enters the opposite side
    # within the same candle row when the shifted signals contain both the
    # exit and the opposite entry.  The frozen rules forbid this: the earliest
    # re-entry is off the NEXT bar's close.  Guard: reject any entry whose
    # current_time equals the last exit's current_time (both callbacks are
    # invoked by the backtester with the candle-open time).

    _last_exit_candle: datetime | None = None

    def confirm_trade_exit(
        self, pair, trade, order_type, amount, rate, time_in_force, exit_reason,
        current_time, **kwargs,
    ) -> bool:
        self._last_exit_candle = current_time
        return True

    def confirm_trade_entry(
        self, pair, order_type, amount, rate, time_in_force, current_time,
        entry_tag, side, **kwargs,
    ) -> bool:
        if self._last_exit_candle is not None and current_time == self._last_exit_candle:
            return False
        return True

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = dataframe
        # --- previous COMPLETE UTC day H/L/C (exactly 96 bars required) -----
        day_key = df["date"].dt.floor("1D")
        agg = (
            df.assign(_day=day_key)
            .groupby("_day", sort=True)
            .agg(dh=("high", "max"), dl=("low", "min"), dc=("close", "last"), dn=("close", "size"))
        )
        agg["ph"] = agg["dh"].shift(1)
        agg["pl"] = agg["dl"].shift(1)
        agg["pc"] = agg["dc"].shift(1)
        agg["pn"] = agg["dn"].shift(1)
        df = df.merge(agg[["ph", "pl", "pc", "pn"]], left_on=day_key, right_index=True, how="left")
        prev_complete = df["pn"] == BARS_PER_UTC_DAY

        # --- true range + ATR: sequential, bit-identical to the reference ---
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)
        n = len(df)
        tr = np.empty(n, dtype=float)
        prev_close = None
        for i in range(n):
            tr[i] = (
                high[i] - low[i]
                if prev_close is None
                else max(high[i] - low[i], abs(high[i] - prev_close), abs(low[i] - prev_close))
            )
            prev_close = close[i]

        k = int(self.atr_period)
        window: list[float] = []
        tr_sum = 0.0
        atr = np.full(n, np.nan)
        for i in range(n):
            window.append(tr[i])
            tr_sum += tr[i]
            if len(window) > k:
                tr_sum -= window.pop(0)
            if len(window) == k and tr_sum > 0.0:
                atr[i] = tr_sum / k

        pivot = (df["ph"] + df["pl"] + df["pc"]) / 3.0
        q = np.full(n, np.nan)
        for i in range(n):
            if prev_complete.iat[i] and not np.isnan(atr[i]):
                q[i] = (close[i] - pivot.iat[i]) / (atr[i] * float(self.volatility_multiplier))
        df["q"] = q

        # day-end bar: close crosses the UTC day boundary (bar opening 23:45).
        # pandas 3.x stores datetimes at non-ns resolution -> normalize to ms.
        ts_ms = df["date"].astype("datetime64[ms, UTC]").astype("int64")
        df["day_end"] = (ts_ms + TF_MS) // DAY_MS != ts_ms // DAY_MS
        return df

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        q = dataframe["q"]
        ok = q.notna() & ~dataframe["day_end"]
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe.loc[ok & (q >= ENTRY_LONG_THRESHOLD), ["enter_long", "enter_tag"]] = (1, "q_long")
        dataframe.loc[ok & (q <= ENTRY_SHORT_THRESHOLD), ["enter_short", "enter_tag"]] = (
            1,
            "q_short",
        )
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        q = dataframe["q"]
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        # Day-end exits carry a distinct tag so the adapter can map them to
        # exit_reason='day_end_flat'; score exits map to 'signal_exit'.
        day_end = dataframe["day_end"].fillna(False)
        dataframe.loc[day_end | (q <= 0.0), ["exit_long", "exit_tag"]] = (1, "__Q_EXIT_TAG__")
        dataframe.loc[day_end, ["exit_long", "exit_tag"]] = (1, "__DAY_END_TAG__")
        dataframe.loc[day_end | (q >= 0.0), ["exit_short", "exit_tag"]] = (1, "__Q_EXIT_TAG__")
        dataframe.loc[day_end, ["exit_short", "exit_tag"]] = (1, "__DAY_END_TAG__")
        return dataframe
'''

Q_EXIT_TAG: Final[str] = "q_exit"
DAY_END_TAG: Final[str] = "day_end"


def render_strategy_source(
    *,
    atr_period: int,
    volatility_multiplier: float,
    strategy_name: str = STRATEGY_NAME,
    freqtrade_version: str = "2026.8",
) -> str:
    """Render the self-contained strategy source for one parameter set.

    The class name must appear literally (``class <name>(``) because the
    freqtrade strategy resolver text-searches candidate files for that pattern.
    ``startup_candle_count`` is baked in as ``96 + atr_period - 1``.
    """
    if atr_period < 2:
        raise ValueError(f"atr_period must be >= 2, got {atr_period}")
    if not volatility_multiplier > 0.0:
        raise ValueError(f"volatility_multiplier must be > 0, got {volatility_multiplier}")
    startup = 96 + atr_period - 1
    source = _TEMPLATE
    for token, value in (
        ("__NAME__", strategy_name),
        ("__ATR_PERIOD__", str(atr_period)),
        ("__MULT__", repr(float(volatility_multiplier))),
        ("__STARTUP__", str(startup)),
        ("__FT_VERSION__", freqtrade_version),
        ("__Q_EXIT_TAG__", Q_EXIT_TAG),
        ("__DAY_END_TAG__", DAY_END_TAG),
    ):
        source = source.replace(token, value)
    if f"class {strategy_name}(" not in source:
        raise ValueError(f"rendered source is missing the literal class line for {strategy_name!r}")
    return source.lstrip("\n")
