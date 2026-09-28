# ruff: noqa: RUF001 -- asserts match Chinese budget messages with full-width punctuation.
"""Unit tests for the budget executor (P13, kronos.runtime.budget).

All time is injected: every ledger call takes ``now`` (epoch ms) from a
deterministic :class:`_Clock`, so rolling 24h/7d windows, wall-clock math,
and restart persistence are exact with no sleeps.
"""

from __future__ import annotations

from typing import Any

import pytest

from kronos.research.verdict.contracts import BudgetBlock
from kronos.runtime.budget import (
    BudgetExhausted,
    BudgetLedger,
    BudgetLimits,
    BudgetPlan,
    budget_guard,
    render_budget_report,
)
from kronos.runtime.tasks import TaskStore, canonical_payload_sha256

_DAY_MS = 86_400_000


class _Clock:
    """Deterministic injectable millisecond clock."""

    def __init__(self, start_ms: int = 1_700_000_000_000) -> None:
        self.ms = start_ms

    def now(self) -> int:
        return self.ms

    def advance(self, ms: int) -> int:
        self.ms += ms
        return self.ms


def _task_budget() -> BudgetBlock:
    return BudgetBlock(
        llm_calls_reserved=3,
        llm_calls_used=0,
        tokens_reserved=16_000,
        tokens_used=0,
        backtests_reserved=40,
        backtests_used=0,
        wall_clock_limit_s=1800.0,
    )


def _submit(store: TaskStore, payload: dict[str, Any]) -> str:
    record = store.submit(
        "evaluate_strategy", payload, _task_budget(), canonical_payload_sha256(payload)
    )
    return record.task_id


# --------------------------------------------------------------------- reserve


def test_reserve_happy_path_tracks_reserved_and_used(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        res = ledger.reserve(
            "r1",
            BudgetPlan(llm_calls=2, tokens=4_000, backtests=10),
            now=clock.now(),
        )
        assert res.round_id == "r1"
        assert (res.llm_calls, res.tokens, res.backtests) == (2, 4_000, 10)
        assert res.created_at_ms == clock.now()

        usage = ledger.round_usage("r1", now=clock.now())
        assert usage.llm_calls.reserved == 2
        assert usage.llm_calls.used == 0
        assert usage.llm_calls.remaining == 1  # default cap 3
        assert usage.tokens_round.reserved == 4_000
        assert usage.backtests.reserved == 10

        receipt = ledger.spend(
            "r1", "llm_call", 1, reservation_id=res.reservation_id, now=clock.advance(1)
        )
        assert receipt.over_limit is False
        assert receipt.kind == "llm_call"

        # One of the two reserved calls is spent: used=1, open reservation=1.
        assert ledger.round_usage("r1", now=clock.now()).llm_calls.used == 1
        assert ledger.reserve("r1", BudgetPlan(llm_calls=1), now=clock.now()).tokens == 0
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(llm_calls=1), now=clock.now())
        assert exc.value.kind == "llm_calls"
        assert exc.value.remaining == 0
        assert "预算不足" in str(exc.value)
        assert "本轮 LLM 调用次数" in str(exc.value)


def test_reserve_is_idempotent_by_reservation_id(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        first = ledger.reserve(
            "r1",
            BudgetPlan(llm_calls=1, tokens=100),
            reservation_id="fixed-id",
            now=clock.now(),
        )
        second = ledger.reserve(
            "r1",
            BudgetPlan(llm_calls=1, tokens=100),
            reservation_id="fixed-id",
            now=clock.advance(1_000),
        )
        assert second == first  # same result, no double charge

        usage = ledger.round_usage("r1", now=clock.now())
        assert usage.llm_calls.reserved == 1

        # Even after the reservation is consumed, re-reserving the same id
        # returns the stored reservation instead of re-running the check.
        ledger.spend("r1", "llm_call", 1, reservation_id="fixed-id", now=clock.advance(1))
        again = ledger.reserve(
            "r1", BudgetPlan(llm_calls=1), reservation_id="fixed-id", now=clock.now()
        )
        assert again == first


# ----------------------------------------------------------- per-round caps


def test_llm_call_exhaustion_raises_budget_exhausted(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        ledger.reserve("r1", BudgetPlan(llm_calls=3), now=clock.now())
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(llm_calls=1), now=clock.now())
        assert exc.value.kind == "llm_calls"
        assert "预算不足" in exc.value.human_message
        assert "剩余 0" in exc.value.human_message


def test_tokens_round_exhaustion_raises_budget_exhausted(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        ledger.reserve("r1", BudgetPlan(tokens=16_000), now=clock.now())
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(tokens=1), now=clock.now())
        assert exc.value.kind == "tokens_round"
        assert "本轮 token 预算" in str(exc.value)


def test_backtest_exhaustion_raises_budget_exhausted(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        ledger.reserve("r1", BudgetPlan(backtests=40), now=clock.now())
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(backtests=1), now=clock.now())
        assert exc.value.kind == "backtests"
        assert "本轮回测次数" in str(exc.value)


# ------------------------------------------------------- rolling windows


def test_daily_rolling_window_excludes_stale_spend(tmp_path) -> None:
    clock = _Clock()
    limits = BudgetLimits(tokens_per_day=100)
    with BudgetLedger(tmp_path / "budget.sqlite3", limits=limits) as ledger:
        # "Yesterday" (>24h ago) is outside the rolling window; an hour ago is inside.
        ledger.spend("r1", "token", 60, now=clock.now() - 25 * _DAY_MS)
        ledger.spend("r2", "token", 50, now=clock.now() - 3_600_000)

        # Rolling windows are ledger-global: query via either existing round.
        usage = ledger.round_usage("r2", now=clock.now())
        assert usage.tokens_day.used == 50
        assert usage.tokens_day.remaining == 50

        # 50 + 40 fits the 100/day cap.
        assert ledger.reserve("r3", BudgetPlan(tokens=40), now=clock.now()).tokens == 40
        # 50 + 60 does not.
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r4", BudgetPlan(tokens=60), now=clock.now())
        assert exc.value.kind == "tokens_day"
        assert "当日 token 预算" in str(exc.value)


def test_weekly_rolling_window_cap(tmp_path) -> None:
    clock = _Clock()
    limits = BudgetLimits(tokens_per_week=1_000, tokens_per_day=10_000)
    with BudgetLedger(tmp_path / "budget.sqlite3", limits=limits) as ledger:
        ledger.spend("r1", "token", 600, now=clock.now() - 8 * _DAY_MS)  # outside window
        ledger.spend("r2", "token", 500, now=clock.now() - 2 * _DAY_MS)  # inside

        usage = ledger.round_usage("r2", now=clock.now())
        assert usage.tokens_week.used == 500

        assert ledger.reserve("r3", BudgetPlan(tokens=400), now=clock.now()).tokens == 400
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r4", BudgetPlan(tokens=600), now=clock.now())
        assert exc.value.kind == "tokens_week"
        assert "每周 token 预算" in str(exc.value)


def test_daily_window_blocks_when_per_round_has_headroom(tmp_path) -> None:
    """Per-round OK is not enough: the rolling day cap bites (anti-bypass)."""
    clock = _Clock()
    limits = BudgetLimits(tokens_per_day=10_000)  # per-round default stays 16_000
    with BudgetLedger(tmp_path / "budget.sqlite3", limits=limits) as ledger:
        ledger.spend("r1", "token", 10_000, now=clock.now())

        # The round itself still has 6_000 token headroom, but the day is full.
        assert ledger.round_usage("r1", now=clock.now()).tokens_round.remaining == 6_000
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(tokens=1), now=clock.now())
        assert exc.value.kind == "tokens_day"


# ------------------------------------------------- overspend and persistence


def test_overspend_records_over_limit_and_blocks_next_reserve(tmp_path) -> None:
    clock = _Clock()
    limits = BudgetLimits(backtests_per_round=5)
    with BudgetLedger(tmp_path / "budget.sqlite3", limits=limits) as ledger:
        res = ledger.reserve("r1", BudgetPlan(backtests=4), now=clock.now())
        receipt = ledger.spend(
            "r1", "backtest", 7, reservation_id=res.reservation_id, now=clock.advance(1)
        )
        assert receipt.over_limit is True  # real usage recorded, never truncated

        events = ledger.events("r1")
        assert [e.kind for e in events] == ["over_limit"]
        assert "backtest" in (events[0].detail or "")

        # The fully-consumed reservation frees nothing: used 7 + want 1 > 5.
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(backtests=1), now=clock.now())
        assert exc.value.kind == "backtests"


def test_restart_persists_spend_and_does_not_reset_budgets(tmp_path) -> None:
    clock = _Clock()
    limits = BudgetLimits(tokens_per_day=20_000)
    path = tmp_path / "budget.sqlite3"
    with BudgetLedger(path, limits=limits) as ledger:
        res = ledger.reserve("r1", BudgetPlan(tokens=2_000), now=clock.now())
        ledger.spend(
            "r1", "token", 15_000, reservation_id=res.reservation_id, now=clock.advance(1_000)
        )

    with BudgetLedger(path, limits=limits) as reopened:
        assert reopened.reservation(res.reservation_id) == res
        usage = reopened.round_usage("r1", now=clock.now())
        assert usage.tokens_round.used == 15_000
        assert usage.tokens_day.used == 15_000

        # A fresh round_id gets a fresh per-round budget, but the rolling day
        # window still counts the pre-restart spend: budgets were not reset.
        with pytest.raises(BudgetExhausted) as exc:
            reopened.reserve("r2", BudgetPlan(tokens=6_000), now=clock.advance(1_000))
        assert exc.value.kind == "tokens_day"
        assert reopened.reserve("r2", BudgetPlan(tokens=5_000), now=clock.now()).tokens == 5_000


def test_clock_and_round_limits_never_reset(tmp_path) -> None:
    clock = _Clock()
    path = tmp_path / "budget.sqlite3"
    t0 = clock.now()
    with BudgetLedger(path) as ledger:
        assert ledger.start_round_clock("r1", now=t0) == t0

        widened = BudgetLimits(
            llm_calls_per_round=999,
            tokens_per_round=999_999,
            backtests_per_round=999,
            wall_clock_per_round_s=99_999.0,
        )
        info = ledger.start_round("r1", limits=widened, now=t0 + 1)
        assert info.limits.llm_calls_per_round == 3  # frozen at creation
        assert info.limits.tokens_per_round == 16_000
        assert info.limits.wall_clock_per_round_s == 1800.0
        frozen = info.limits

        # A second clock anchor must not move the first one (no extension).
        assert ledger.start_round_clock("r1", now=t0 + 500_000) == t0
        assert ledger.remaining_ms("r1", now=t0 + 600_000) == 1_200_000

    with BudgetLedger(path) as reopened:
        assert reopened.remaining_ms("r1", now=t0 + 600_000) == 1_200_000
        assert reopened.round_info("r1").limits == frozen


# ------------------------------------------------- unreported token usage


def test_unreported_token_usage_defaults_and_validation(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "b1.sqlite3", unreported_usage_default_tokens=777) as ledger:
        receipt = ledger.spend("r1", "token", 0, meta={"estimated": True}, now=clock.now())
        assert receipt.amount == 777  # conservative default, never zero

    with BudgetLedger(tmp_path / "b2.sqlite3") as ledger:
        receipt = ledger.spend("r1", "token", 0, meta={"estimated": True}, now=clock.now())
        assert receipt.amount == 2_000

        with pytest.raises(ValueError, match="estimated"):
            ledger.spend("r1", "token", 0, now=clock.now())
        with pytest.raises(ValueError, match="non-negative"):
            ledger.spend("r1", "token", -5, now=clock.now())
        with pytest.raises(ValueError, match="unknown spend kind"):
            ledger.spend("r1", "cpu_s", 1, now=clock.now())  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="unknown reservation_id"):
            ledger.spend("r1", "token", 10, reservation_id="nope", now=clock.now())


# ------------------------------------------------------------- wall clock


def test_wall_clock_helpers_and_exhaustion(tmp_path) -> None:
    clock = _Clock()
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        t0 = clock.now()
        assert ledger.start_round_clock("r1", now=t0) == t0
        assert ledger.remaining_ms("r1", now=t0 + 600_000) == 1_200_000
        assert ledger.remaining_ms("r1", now=t0 + 1_799_999) == 1

        assert ledger.remaining_ms("r1", now=t0 + 1_800_000) == 0
        assert ledger.remaining_ms("r1", now=t0 + 1_805_000) == 0

        # An exhausted wall clock also refuses new reservations.
        with pytest.raises(BudgetExhausted) as exc:
            ledger.reserve("r1", BudgetPlan(tokens=1), now=t0 + 1_800_000)
        assert exc.value.kind == "wall_clock"
        assert "墙钟" in str(exc.value)

        # Recorded wall-clock usage over the cap is an over_limit receipt.
        receipt = ledger.spend("r1", "wall_clock_s", 1900, now=t0)
        assert receipt.over_limit is True
        assert len(ledger.events("r1")) == 1

    # Unknown rounds raise; a registered round without a clock has full budget.
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        with pytest.raises(ValueError, match="unknown round"):
            ledger.remaining_ms("r3", now=0)
        ledger.start_round("r4")
        assert ledger.remaining_ms("r4", now=0) == 1_800_000


# ----------------------------------------------------------------- report


def test_render_budget_report_in_chinese(tmp_path) -> None:
    clock = _Clock()
    limits = BudgetLimits(backtests_per_round=30)
    with BudgetLedger(tmp_path / "budget.sqlite3", limits=limits) as ledger:
        t0 = clock.now()
        ledger.start_round_clock("r1", now=t0)
        ledger.reserve("r1", BudgetPlan(llm_calls=1, tokens=2_000), now=t0)
        ledger.spend("r1", "token", 2_500, now=t0 + 1)
        ledger.spend("r1", "backtest", 39, now=t0 + 2)  # over the 30 cap

        report = render_budget_report(ledger, "r1", now=t0 + 600_000)

    assert "预算报告（轮次 r1）" in report
    assert "- LLM 调用：上限 3 ｜ 预留 1 ｜ 已用 0 ｜ 剩余 2" in report
    assert "- Token（本轮）：上限 16000 ｜ 预留 2000 ｜ 已用 2500" in report
    assert "- 回测次数：上限 30 ｜ 预留 0 ｜ 已用 39 ｜ 剩余 0" in report
    assert "- 墙钟（本轮）：上限 1800s ｜ 预留 0 ｜ 已用 600s ｜ 剩余 1200s" in report
    assert "近24小时 已用 2500/100000（剩余 95500）" in report
    assert "近7天 已用 2500/500000（剩余 495500）" in report
    assert "- 超限事件：1 条（最近：backtest 已用 39 超出本轮上限 30）" in report


# ------------------------------------------------------------------ guard


def test_budget_guard_allows_valid_reservation(tmp_path) -> None:
    clock = _Clock()
    store = TaskStore(tmp_path / "runtime.sqlite3")
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        ledger.start_round_clock("round-1", now=clock.now())
        res = ledger.reserve("round-1", BudgetPlan(llm_calls=1, tokens=100), now=clock.now())
        payload = {
            "strategy_revision_id": "rev-1",
            "budget_round_id": "round-1",
            "budget_reservation_id": res.reservation_id,
        }
        task_id = _submit(store, payload)

        verdict = budget_guard(store, ledger, task_id, now=clock.now())

        assert verdict.allowed is True
        assert verdict.reason is None
        assert verdict.round_id == "round-1"
        assert verdict.reservation_id == res.reservation_id
        assert verdict.wall_clock_remaining_ms == 1_800_000
    store.close()


def test_budget_guard_rejects_unknown_reservation(tmp_path) -> None:
    clock = _Clock()
    store = TaskStore(tmp_path / "runtime.sqlite3")
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        payload = {"budget_round_id": "round-1", "budget_reservation_id": "missing"}
        task_id = _submit(store, payload)

        verdict = budget_guard(store, ledger, task_id, now=clock.now())

        assert verdict.allowed is False
        assert verdict.reason is not None
        assert "预算预留无效" in verdict.reason
        assert "missing" in verdict.reason
    store.close()


def test_budget_guard_rejects_round_mismatch(tmp_path) -> None:
    clock = _Clock()
    store = TaskStore(tmp_path / "runtime.sqlite3")
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        res = ledger.reserve("round-1", BudgetPlan(tokens=10), now=clock.now())
        payload = {"budget_round_id": "round-2", "budget_reservation_id": res.reservation_id}
        task_id = _submit(store, payload)

        verdict = budget_guard(store, ledger, task_id, now=clock.now())

        assert verdict.allowed is False
        assert verdict.reason is not None
        assert "不一致" in verdict.reason
    store.close()


def test_budget_guard_blocks_on_exhausted_wall_clock(tmp_path) -> None:
    clock = _Clock()
    store = TaskStore(tmp_path / "runtime.sqlite3")
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        ledger.start_round_clock("round-1", now=clock.now())
        res = ledger.reserve("round-1", BudgetPlan(tokens=10), now=clock.now())
        payload = {"budget_round_id": "round-1", "budget_reservation_id": res.reservation_id}
        task_id = _submit(store, payload)

        verdict = budget_guard(store, ledger, task_id, now=clock.now() + 1_800_000)

        assert verdict.allowed is False
        assert verdict.reason is not None
        assert "墙钟" in verdict.reason
        assert verdict.wall_clock_remaining_ms == 0
    store.close()


def test_budget_guard_ignores_tasks_without_budget_refs(tmp_path) -> None:
    clock = _Clock()
    store = TaskStore(tmp_path / "runtime.sqlite3")
    with BudgetLedger(tmp_path / "budget.sqlite3") as ledger:
        task_id = _submit(store, {"strategy_revision_id": "rev-1"})

        verdict = budget_guard(store, ledger, task_id, now=clock.now())

        assert verdict.allowed is True
        assert verdict.round_id is None
        assert verdict.reservation_id is None
        assert verdict.wall_clock_remaining_ms is None
    store.close()
