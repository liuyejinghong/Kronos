"""Unit tests for the Kronos threshold variant pure decision rules (P01)."""

from __future__ import annotations

from typing import Literal

import pytest

from kronos.strategy.variant_rules import (
    compute_q,
    evaluate_entry,
    evaluate_exit,
    required_warmup_bars,
    true_range,
)

Holding = Literal["flat", "long", "short"]


class TestEvaluateEntry:
    @pytest.mark.parametrize(
        ("q", "expected"),
        [
            (1.0, "open_long"),
            (2.5, "open_long"),
            (0.999, "hold"),
            (0.0, "hold"),
            (-0.999, "hold"),
            (-1.0, "open_short"),
            (-2.5, "open_short"),
        ],
    )
    def test_flat_truth_table(self, q: float, expected: str) -> None:
        assert evaluate_entry(q, "flat") == expected

    @pytest.mark.parametrize("q", [5.0, 1.0, 0.0, -1.0, -5.0])
    @pytest.mark.parametrize("holding", ["long", "short"])
    def test_no_reversal_or_add_while_holding(self, q: float, holding: Holding) -> None:
        assert evaluate_entry(q, holding) == "hold"


class TestEvaluateExit:
    @pytest.mark.parametrize(
        ("q", "holding", "is_day_end", "expected"),
        [
            # flat: nothing to close, even at day end
            (0.0, "flat", False, False),
            (5.0, "flat", True, False),
            # long exits at or below zero
            (0.0, "long", False, True),
            (-0.4, "long", False, True),
            (0.4, "long", False, False),
            # short exits at or above zero
            (0.0, "short", False, True),
            (0.4, "short", False, True),
            (-0.4, "short", False, False),
            # warmup / unknown score: never exits except day end
            (None, "long", False, False),
            (None, "short", False, False),
            # day-end force close wins over everything (incl. warmup)
            (None, "long", True, True),
            (None, "short", True, True),
            (0.4, "long", True, True),
            (-0.4, "short", True, True),
        ],
    )
    def test_truth_table(
        self, q: float | None, holding: Holding, is_day_end: bool, expected: bool
    ) -> None:
        assert evaluate_exit(q, holding, is_day_end) is expected


class TestExitBeforeEntry:
    def test_long_closing_threshold_does_not_reverse(self) -> None:
        q = -2.0  # would open_short if flat, but holding long: exit only
        assert evaluate_exit(q, "long", is_day_end=False) is True
        assert evaluate_entry(q, "long") == "hold"

    def test_short_closing_threshold_does_not_reverse(self) -> None:
        q = 2.0  # would open_long if flat, but holding short: exit only
        assert evaluate_exit(q, "short", is_day_end=False) is True
        assert evaluate_entry(q, "short") == "hold"

    def test_zero_score_closes_both_directions(self) -> None:
        assert evaluate_exit(0.0, "long", is_day_end=False) is True
        assert evaluate_exit(0.0, "short", is_day_end=False) is True


class TestRequiredWarmupBars:
    def test_15m_day_is_96_bars(self) -> None:
        assert required_warmup_bars(14, "15m") == 110
        assert required_warmup_bars(1, "15m") == 97

    def test_1h_day_is_24_bars(self) -> None:
        assert required_warmup_bars(14, "1h") == 38
        assert required_warmup_bars(2, "1h") == 26

    @pytest.mark.parametrize("timeframe", ["5m", "4h", "1d", ""])
    def test_unsupported_timeframe_rejected(self, timeframe: str) -> None:
        with pytest.raises(ValueError, match="signal_timeframe"):
            required_warmup_bars(14, timeframe)

    def test_non_positive_atr_period_rejected(self) -> None:
        with pytest.raises(ValueError, match="atr_period"):
            required_warmup_bars(0, "15m")


class TestTrueRange:
    def test_plain_range_dominates(self) -> None:
        assert true_range(110.0, 100.0, 105.0) == pytest.approx(10.0)

    def test_gap_up_dominates(self) -> None:
        assert true_range(120.0, 101.0, 100.0) == pytest.approx(20.0)

    def test_gap_down_dominates(self) -> None:
        assert true_range(104.0, 90.0, 105.0) == pytest.approx(15.0)


class TestComputeQ:
    def test_q_formula_uses_pivot_of_previous_day(self) -> None:
        # pivot = (110 + 100 + 105) / 3 = 105; close one ATR*m above pivot -> q = 1
        q = compute_q(
            close=107.0,
            prev_high=110.0,
            prev_low=100.0,
            prev_close=105.0,
            atr=2.0,
            volatility_multiplier=1.0,
        )
        assert q == pytest.approx(1.0)

    def test_q_at_pivot_is_zero(self) -> None:
        q = compute_q(
            close=105.0,
            prev_high=110.0,
            prev_low=100.0,
            prev_close=105.0,
            atr=2.0,
            volatility_multiplier=1.5,
        )
        assert q == pytest.approx(0.0)

    def test_multiplier_scales_q(self) -> None:
        kwargs = {
            "close": 108.0,
            "prev_high": 110.0,
            "prev_low": 100.0,
            "prev_close": 105.0,
            "atr": 3.0,
        }
        assert compute_q(**kwargs, volatility_multiplier=1.0) == pytest.approx(1.0)
        assert compute_q(**kwargs, volatility_multiplier=2.0) == pytest.approx(0.5)

    @pytest.mark.parametrize("atr", [0.0, -1.0])
    def test_non_positive_atr_rejected(self, atr: float) -> None:
        with pytest.raises(ValueError, match="atr"):
            compute_q(
                close=105.0,
                prev_high=110.0,
                prev_low=100.0,
                prev_close=105.0,
                atr=atr,
                volatility_multiplier=1.0,
            )

    @pytest.mark.parametrize("multiplier", [0.0, -0.5])
    def test_non_positive_multiplier_rejected(self, multiplier: float) -> None:
        with pytest.raises(ValueError, match="volatility_multiplier"):
            compute_q(
                close=105.0,
                prev_high=110.0,
                prev_low=100.0,
                prev_close=105.0,
                atr=2.0,
                volatility_multiplier=multiplier,
            )


class TestThresholdBoundariesFeedDecisions:
    def test_entry_boundary_is_inclusive(self) -> None:
        # q exactly +1/-1 must trigger, computed through the real formula.
        kwargs = {
            "prev_high": 110.0,
            "prev_low": 100.0,
            "prev_close": 105.0,  # pivot = 105
            "atr": 2.0,
            "volatility_multiplier": 1.0,
        }
        assert evaluate_entry(compute_q(close=107.0, **kwargs), "flat") == "open_long"
        assert evaluate_entry(compute_q(close=103.0, **kwargs), "flat") == "open_short"
        assert evaluate_entry(compute_q(close=106.9, **kwargs), "flat") == "hold"
