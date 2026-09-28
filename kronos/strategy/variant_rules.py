"""Pure decision rules for the Kronos threshold variant (``kronos_threshold_v1``).

Single source of truth for the *decision math* of the variant labelled
"Kronos 变体".  No I/O and no pandas: inputs and outputs are plain floats and
literals, so the backtest kernel (P08), the reference ledger (P04) and the
golden cases (P02) share identical semantics.  Identity/serialization lives in
:mod:`kronos.strategy.spec`.

Score
-----
On each COMPLETED signal-timeframe bar (15m or 1h, UTC)::

    pivot = (prev_high + prev_low + prev_close) / 3   # of the previous COMPLETE UTC day
    q     = (close - pivot) / (ATR * volatility_multiplier)

``ATR`` is the simple rolling mean of the true range over ``atr_period`` signal
bars, where ``TR = max(H - L, |H - prev_close|, |L - prev_close|)``.

Per-bar orchestration (enforced by the caller, normative here)
---------------------------------------------------------------
1. Day-end bar (last completed signal bar of a UTC day): force-close everything
   (day-flat) and take NO new entries, even if an entry threshold fires.
2. Any other bar, while holding: only exit rules apply (exit first).  No
   same-bar reversal: a bar that closes a position cannot open the opposite
   one.
3. Entry rules are evaluated only while flat at bar start.  Entry decisions on
   the bar that an exit fired are therefore impossible by construction
   (:func:`evaluate_entry` returns ``"hold"`` for any non-flat holding).
4. Fills simulate at the NEXT available 1m bar open; costs come from a separate
   cost policy and are not part of these rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

Holding = Literal["flat", "long", "short"]
EntryAction = Literal["open_long", "open_short", "hold"]

ENTRY_LONG_THRESHOLD: Final[float] = 1.0
ENTRY_SHORT_THRESHOLD: Final[float] = -1.0
BARS_PER_UTC_DAY: Final[Mapping[str, int]] = {"15m": 96, "1h": 24}


def true_range(high: float, low: float, prev_close: float) -> float:
    """True range of one bar: ``max(H - L, |H - prev_close|, |L - prev_close|)``.

    Examples:
        high=110, low=100, prev_close=105 -> 10.0 (plain range dominates)
        high=120, low=101, prev_close=100 -> 20.0 (gap up dominates)
        high=104, low=90,  prev_close=105 -> 15.0 (gap down dominates)
    """
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def compute_q(
    *,
    close: float,
    prev_high: float,
    prev_low: float,
    prev_close: float,
    atr: float,
    volatility_multiplier: float,
) -> float:
    """Normalized breakout score ``q = (close - pivot) / (atr * multiplier)``.

    ``pivot = (prev_high + prev_low + prev_close) / 3`` from the previous
    COMPLETE UTC day; ``atr`` is the rolling mean of true ranges over the
    trailing ``atr_period`` completed signal bars (caller-computed).

    Raises:
        ValueError: if ``atr`` or ``volatility_multiplier`` is not strictly
            positive (NaN included).

    Examples:
        prev=(110, 100, 105) -> pivot=105.0; close=105 + atr*m -> q=1.0
        close=105.0 with prev=(110, 100, 105) -> q=0.0
        close=103.0, atr=2.0, m=1.0, pivot=105.0 -> q=-1.0
    """
    if not atr > 0.0:
        raise ValueError(f"atr must be strictly positive, got {atr}")
    if not volatility_multiplier > 0.0:
        raise ValueError(
            f"volatility_multiplier must be strictly positive, got {volatility_multiplier}"
        )
    pivot = (prev_high + prev_low + prev_close) / 3.0
    return (close - pivot) / (atr * volatility_multiplier)


def evaluate_entry(q: float, holding: Holding) -> EntryAction:
    """Entry decision from the score ``q``, only while flat.

    Behavior table (thresholds inclusive; "hold" also covers the no-reversal
    rule: while holding, only exit rules apply):

    =========================================  ============  ==============================================
    holding / q                                result        example
    =========================================  ============  ==============================================
    flat, q >= 1.0                             open_long     q=1.0 -> open_long; q=2.5 -> open_long
    flat, -1.0 < q < 1.0                       hold          q=0.999 -> hold; q=0.0 -> hold
    flat, q <= -1.0                            open_short    q=-1.0 -> open_short; q=-2.5 -> open_short
    long, any q                                hold          no reversal/add: q=-5.0 -> hold (use evaluate_exit)
    short, any q                               hold          no reversal/add: q=5.0 -> hold (use evaluate_exit)
    =========================================  ============  ==============================================

    Examples:
        >>> evaluate_entry(1.0, "flat")
        'open_long'
        >>> evaluate_entry(0.999, "flat")
        'hold'
        >>> evaluate_entry(-2.5, "flat")
        'open_short'
        >>> evaluate_entry(-2.5, "long")   # no same-bar reversal
        'hold'
    """
    if holding != "flat":
        return "hold"
    if q >= ENTRY_LONG_THRESHOLD:
        return "open_long"
    if q <= ENTRY_SHORT_THRESHOLD:
        return "open_short"
    return "hold"


def evaluate_exit(q: float | None, holding: Holding, is_day_end: bool) -> bool:
    """Exit decision; day-end force-close always wins, warmup (q None) never exits.

    Behavior table:

    =====================================  ===========  ======  ================================================
    holding / q                            is_day_end   result  example
    =====================================  ===========  ======  ================================================
    flat, any q                            any          False   nothing to close: q=5.0 -> False
    long, q is None                        False        False   warmup/unknown score -> wait
    long, q <= 0.0                         False        True    q=0.0 or q=-0.4 -> exit
    long, q > 0.0                          False        False   q=0.4 -> stay
    short, q is None                       False        False   warmup/unknown score -> wait
    short, q >= 0.0                        False        True    q=0.0 or q=0.4 -> exit
    short, q < 0.0                         False        False   q=-0.4 -> stay
    long/short, any q (incl. None)         True         True    day-end force close even during warmup
    =====================================  ===========  ======  ================================================

    Examples:
        >>> evaluate_exit(0.0, "long", is_day_end=False)
        True
        >>> evaluate_exit(0.4, "long", is_day_end=False)
        False
        >>> evaluate_exit(None, "short", is_day_end=False)
        False
        >>> evaluate_exit(None, "short", is_day_end=True)
        True
        >>> evaluate_exit(5.0, "flat", is_day_end=True)
        False
    """
    if holding == "flat":
        return False
    if is_day_end:
        return True
    if q is None:
        return False
    if holding == "long":
        return q <= 0.0
    return q >= 0.0


def required_warmup_bars(atr_period: int, signal_timeframe: str) -> int:
    """Minimum completed signal bars before the first decision: one full UTC day
    of signal bars plus ``atr_period`` bars of true-range history.

    Behavior table:

    ==========================  =============================================
    inputs                      result
    ==========================  =============================================
    atr_period=14, "15m"        96 + 14 = 110 (a 15m UTC day is 96 bars)
    atr_period=14, "1h"         24 + 14 = 38 (a 1h UTC day is 24 bars)
    atr_period=1, "15m"         96 + 1 = 97
    any, "5m" (or other)        ValueError: unsupported signal timeframe
    atr_period=0 (or less)      ValueError: atr_period must be >= 1
    ==========================  =============================================

    Notes:
        - ``StrategySpec`` already bounds ``atr_period`` to 2..1000; this
          function only enforces the mathematical minimum (>= 1).
        - The ATR window is a bar count, not a fixed duration: the same
          ``atr_period`` on 1h spans 4x the wall-clock time of 15m.

    Examples:
        >>> required_warmup_bars(14, "15m")
        110
        >>> required_warmup_bars(14, "1h")
        38
    """
    if atr_period < 1:
        raise ValueError(f"atr_period must be >= 1, got {atr_period}")
    bars_per_day = BARS_PER_UTC_DAY.get(signal_timeframe)
    if bars_per_day is None:
        supported = ", ".join(sorted(BARS_PER_UTC_DAY))
        raise ValueError(f"signal_timeframe must be one of: {supported}, got {signal_timeframe!r}")
    return bars_per_day + atr_period
