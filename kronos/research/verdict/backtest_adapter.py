"""StrategyBacktestAdapter — Freqtrade kernel integration (P08, ruling D-20260928-003).

Produces the unified :class:`~kronos.research.verdict.contracts.ExecutionLedger`
by running the pinned freqtrade 2026.8 kernel in an isolated subprocess
(:mod:`kronos.research.verdict.kernel.freqtrade_runner`).  No kronos module
imports freqtrade; interaction is subprocess + JSON only (GPL isolation).

Canonical semantics (M0 evidence + owner ruling):

- quantity follows exchange lot rounding (canonical; the P04 reference ledger
  is the independent checker with lot-aware tolerances);
- missing/empty funding inputs fail closed (never a silent zero);
- fills happen at the next tradable price event after a completed signal bar
  (freqtrade's shifted-signal, next-candle-open semantics on 15m);
- exit reasons map ``q_exit -> signal_exit``, ``day_end -> day_end_flat``,
  ``force_exit -> end_of_data_open``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from kronos.research.verdict.contracts import (
    ClosedTrade,
    ExecutionLedger,
    ExecutionRecord,
)
from kronos.research.verdict.kernel import freqtrade_runner as runner
from kronos.research.verdict.kernel.strategy_template import render_strategy_source

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from kronos.research.verdict.contracts import TradeDirection, TradeSide
    from kronos.research.verdict.golden.loader import GoldenCaseBundle

__all__ = [
    "STRATEGY_NAME",
    "BacktestCaseInput",
    "StrategyBacktestAdapter",
    "run_backtest",
]

from kronos.research.verdict.kernel.strategy_template import STRATEGY_NAME

TF15_MS: Final[int] = 900_000

_EXIT_REASON_MAP: Final[Mapping[str, str]] = {
    "q_exit": "signal_exit",
    "day_end": "day_end_flat",
    "force_exit": "end_of_data_open",
}

_NET_CHECK_TOL_REL: Final[float] = 1e-6
_FUNDING_SUM_TOL: Final[float] = 1e-6


class BacktestCaseInput(BaseModel):
    """One backtest request: bars, funding, params, cost, start equity.

    Field shapes mirror the golden loader (P02): 15m signal bars and 1m
    execution bars as ``(ts_ms, open, high, low, close)`` plus funding events
    as ``(ts_ms, rate)``.  ``funding_declared_absent`` must be set explicitly
    for windows that truly contain no funding settlements.
    """

    model_config = ConfigDict(extra="forbid")

    bars_15m: list[tuple[int, float, float, float, float]] = Field(min_length=1)
    bars_1m: list[tuple[int, float, float, float, float]] = Field(default_factory=list)
    funding_events: list[tuple[int, float]] = Field(default_factory=list)
    atr_period: int = Field(default=2, ge=2, le=1000)
    volatility_multiplier: float = Field(default=1.0, gt=0.0, le=20.0)
    fee_bps: float = Field(default=4.0, ge=0.0)
    slippage_bps: float = Field(
        default=0.0,
        description=(
            "Must stay 0: the freqtrade kernel has no per-order slippage; cost stress "
            "scenarios are a P10 concern."
        ),
    )
    start_equity: float = Field(default=10_000.0, gt=0.0)
    equity_fraction: float = Field(default=1.0, gt=0.0, le=1.0)
    symbol: str = "BTCUSDT"
    strategy_revision_id: str = "kronos_threshold_v1"
    funding_declared_absent: bool = False

    @classmethod
    def from_golden_bundle(cls, bundle: GoldenCaseBundle) -> BacktestCaseInput:
        """Build the input from a P02 golden bundle (contiguous 1m expected).

        The golden ``bars_1m`` are deliberately sparse; callers must pass the
        contiguous series (see
        :func:`kronos.research.verdict.kernel.freqtrade_runner.expand_15m_to_1m`).
        """
        return cls(
            bars_15m=bundle.bars_15m,
            bars_1m=bundle.bars_1m,
            funding_events=bundle.funding_events,
            atr_period=bundle.params.atr_period,
            volatility_multiplier=bundle.params.volatility_multiplier,
            fee_bps=bundle.cost.fee_bps,
            slippage_bps=0.0,
            start_equity=bundle.start_equity,
            symbol="BTCUSDT",
            # a hand-computed golden case with no events IS the explicit
            # declaration that the window has no settlements
            funding_declared_absent=not bundle.funding_events,
        )


class StrategyBacktestAdapter:
    """Run one backtest case through the pinned freqtrade kernel subprocess."""

    def __init__(
        self,
        *,
        venv_dir: str | Path | None = None,
        timeout_s: float = runner.DEFAULT_TIMEOUT_S,
        ccxt_proxy: str | None = None,
    ) -> None:
        self._venv_dir = venv_dir
        self._timeout_s = timeout_s
        self._ccxt_proxy = ccxt_proxy

    def run_backtest(
        self,
        case_input: BacktestCaseInput,
        *,
        workdir: Path | None = None,
    ) -> ExecutionLedger:
        """Run one case and return its normalized execution ledger.

        Stages a workdir (freqtrade-format data, config, rendered strategy),
        executes the pinned kernel as a subprocess, parses the result zip and
        normalizes to ledger records plus closed trades.  A caller-supplied
        ``workdir`` is kept (debugging); otherwise the staged workdir is
        removed after the run.
        """
        if case_input.slippage_bps != 0.0:
            raise ValueError(
                "the freqtrade kernel executes slippage-free; nonzero slippage_bps is "
                "rejected (fail closed) — cost stress scenarios belong to package P10"
            )
        venv = runner.resolve_venv(self._venv_dir)
        if not (venv / "bin" / "freqtrade").is_file():
            raise runner.FreqtradeEnvMissingError(
                f"freqtrade venv not found at {venv}; call ensure_freqtrade_env() first"
            )
        spec = runner.RunSpec(
            bars_15m=_typed_bars(case_input.bars_15m),
            bars_1m=_typed_bars(case_input.bars_1m),
            funding_events=[(int(ts), float(rate)) for ts, rate in case_input.funding_events],
            atr_period=case_input.atr_period,
            volatility_multiplier=case_input.volatility_multiplier,
            fee_bps=case_input.fee_bps,
            start_equity=case_input.start_equity,
            equity_fraction=case_input.equity_fraction,
            symbol=case_input.symbol,
            strategy_revision_id=case_input.strategy_revision_id,
            funding_declared_absent=case_input.funding_declared_absent,
            ccxt_proxy=self._ccxt_proxy,
        )
        strategy_source = render_strategy_source(
            atr_period=spec.atr_period,
            volatility_multiplier=spec.volatility_multiplier,
        )
        if workdir is not None:
            workdir.mkdir(parents=True, exist_ok=True)
            staged = runner.stage_case(spec, workdir, strategy_source=strategy_source)
            result = runner.run_backtesting(staged, venv_dir=venv, timeout_s=self._timeout_s)
            return _normalize(spec, result)
        with tempfile.TemporaryDirectory(prefix="kronos-ft-kernel-") as tmp:
            staged = runner.stage_case(spec, Path(tmp), strategy_source=strategy_source)
            result = runner.run_backtesting(staged, venv_dir=venv, timeout_s=self._timeout_s)
            return _normalize(spec, result)


def run_backtest(
    case_input: BacktestCaseInput,
    *,
    venv_dir: str | Path | None = None,
    timeout_s: float = runner.DEFAULT_TIMEOUT_S,
    workdir: Path | None = None,
) -> ExecutionLedger:
    """Module-level convenience wrapper around :class:`StrategyBacktestAdapter`."""
    return StrategyBacktestAdapter(
        venv_dir=venv_dir, timeout_s=timeout_s
    ).run_backtest(case_input, workdir=workdir)


# --- normalization -------------------------------------------------------------


def _typed_bars(
    bars: list[tuple[int, float, float, float, float]],
) -> list[tuple[int, float, float, float, float]]:
    """Coerce pydantic's widened tuples back to the exact ledger bar shape."""
    return [
        (int(bar[0]), float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4]))
        for bar in bars
    ]


def _last_completed_15m_close(
    bars_15m: Sequence[tuple[int, float, float, float, float]], event_ts: int
) -> float:
    """Close of the last 15m bar completed at ``event_ts`` (reference mark rule)."""
    mark = bars_15m[0][1]
    for ts, _open, _high, _low, close in bars_15m:
        if ts + TF15_MS <= event_ts:
            mark = close
        else:
            break
    return mark


def _normalize(spec: runner.RunSpec, result: runner.FreqtradeBacktestResult) -> ExecutionLedger:
    """Normalize the parsed freqtrade result into an ExecutionLedger (fail closed)."""
    bars_15m = spec.bars_15m
    symbol = spec.symbol
    records: list[ExecutionRecord] = []
    trades: list[ClosedTrade] = []
    last_close_ts = bars_15m[-1][0] + TF15_MS

    def mark(eq: float, ts_ms: int, price: float, unrealized: float = 0.0) -> None:
        records.append(
            ExecutionRecord(
                ts_ms=ts_ms,
                event="equity_mark",
                symbol=symbol,
                price=price,
                unrealized_pnl=unrealized,
                equity=eq,
            )
        )

    mark(spec.start_equity, bars_15m[0][0], bars_15m[0][1])
    closed_net = 0.0
    for index, trade in enumerate(result.trades):
        trade_id = f"{symbol}-{index + 1:04d}"
        direction: TradeDirection = "long" if trade.direction == "long" else "short"
        if trade.exit_reason not in _EXIT_REASON_MAP:
            raise runner.ResultParseError(
                f"trade {trade_id}: unmapped exit_reason {trade.exit_reason!r}"
            )
        exit_reason = _EXIT_REASON_MAP[trade.exit_reason]

        gross = (
            (trade.close_rate - trade.open_rate) * trade.amount
            if direction == "long"
            else (trade.open_rate - trade.close_rate) * trade.amount
        )
        total_fees = trade.fee_open_cost + trade.fee_close_cost - trade.funding_fees
        net = gross - total_fees
        if abs(net - trade.profit_abs) > _NET_CHECK_TOL_REL * max(1.0, abs(trade.profit_abs)):
            raise runner.ResultParseError(
                f"trade {trade_id}: recomputed net {net!r} != freqtrade profit_abs "
                f"{trade.profit_abs!r}"
            )
        duration = trade.close_ts_ms - trade.open_ts_ms
        if duration <= 0 or duration % TF15_MS != 0:
            raise runner.ResultParseError(
                f"trade {trade_id}: open->close span {duration}ms is not a positive "
                "multiple of the 15m timeframe"
            )

        # Funding events booked while this position was open, inclusive bounds
        # (matches freqtrade's calculate_funding_fees interval).
        funding_impacts: list[tuple[int, float, float]] = []
        for event_ts, rate in sorted(spec.funding_events):
            if trade.open_ts_ms <= event_ts <= trade.close_ts_ms:
                mark_price = _last_completed_15m_close(bars_15m, event_ts)
                impact = -rate * trade.amount * mark_price
                if direction == "short":
                    impact = rate * trade.amount * mark_price
                funding_impacts.append((event_ts, rate, impact))
        funding_sum = sum(impact for _ts, _rate, impact in funding_impacts)
        if abs(funding_sum - trade.funding_fees) > _FUNDING_SUM_TOL:
            raise runner.FundingDataError(
                f"trade {trade_id}: per-event funding impacts sum to {funding_sum!r} but "
                f"freqtrade booked {trade.funding_fees!r} (missing funding data is never "
                "accepted as silent zero)"
            )

        # entry leg
        entry_side: TradeSide = "buy" if direction == "long" else "sell"
        records.append(
            ExecutionRecord(
                ts_ms=trade.open_ts_ms - TF15_MS,
                event="order",
                symbol=symbol,
                side=entry_side,
                note=f"entry_{direction}",
            )
        )
        records.append(
            ExecutionRecord(
                ts_ms=trade.open_ts_ms,
                event="fill",
                symbol=symbol,
                side=entry_side,
                qty=trade.amount,
                price=trade.open_rate,
                note=f"entry_{direction}",
            )
        )
        records.append(
            ExecutionRecord(
                ts_ms=trade.open_ts_ms,
                event="fee",
                symbol=symbol,
                fee=trade.fee_open_cost,
                fee_asset="USDT",
                note=f"entry_fee|{trade_id}",
            )
        )
        records.append(
            ExecutionRecord(
                ts_ms=trade.open_ts_ms,
                event="position_open",
                symbol=symbol,
                side=entry_side,
                qty=trade.amount,
                price=trade.open_rate,
                note=trade_id,
            )
        )
        equity = spec.start_equity + closed_net - trade.fee_open_cost
        mark(equity, trade.open_ts_ms, trade.open_rate, unrealized=-trade.fee_open_cost)

        # funding legs
        for event_ts, rate, impact in funding_impacts:
            records.append(
                ExecutionRecord(
                    ts_ms=event_ts,
                    event="funding",
                    symbol=symbol,
                    price=_last_completed_15m_close(bars_15m, event_ts),
                    fee=impact,
                    funding_rate=rate,
                    note=f"funding_{direction}|{trade_id}",
                )
            )
        if funding_impacts:
            last_event_ts = funding_impacts[-1][0]
            last_mark = _last_completed_15m_close(bars_15m, last_event_ts)
            unrealized = (
                (last_mark - trade.open_rate) * trade.amount
                if direction == "long"
                else (trade.open_rate - last_mark) * trade.amount
            )
            equity = spec.start_equity + closed_net + funding_sum + unrealized
            mark(equity, last_event_ts, last_mark, unrealized=unrealized)

        # exit leg
        exit_side: TradeSide = "sell" if direction == "long" else "buy"
        records.append(
            ExecutionRecord(
                ts_ms=trade.close_ts_ms - TF15_MS,
                event="order",
                symbol=symbol,
                side=exit_side,
                note=f"exit_{direction}|{exit_reason}",
            )
        )
        records.append(
            ExecutionRecord(
                ts_ms=trade.close_ts_ms,
                event="fill",
                symbol=symbol,
                side=exit_side,
                qty=trade.amount,
                price=trade.close_rate,
                note=f"exit_{direction}",
            )
        )
        records.append(
            ExecutionRecord(
                ts_ms=trade.close_ts_ms,
                event="fee",
                symbol=symbol,
                fee=trade.fee_close_cost,
                fee_asset="USDT",
                note=f"exit_fee|{trade_id}",
            )
        )
        records.append(
            ExecutionRecord(
                ts_ms=trade.close_ts_ms,
                event="position_close",
                symbol=symbol,
                realized_pnl=net,
                note=f"{exit_reason}|{trade_id}",
            )
        )
        closed_net += net
        mark(spec.start_equity + closed_net, trade.close_ts_ms, trade.close_rate)

        trades.append(
            ClosedTrade(
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                entry_ts_ms=trade.open_ts_ms,
                exit_ts_ms=trade.close_ts_ms,
                entry_price=trade.open_rate,
                exit_price=trade.close_rate,
                qty=trade.amount,
                gross_pnl=gross,
                total_fees=total_fees,
                net_pnl=net,
                holding_bars=duration // TF15_MS,
                exit_reason=exit_reason,  # type: ignore[arg-type]
            )
        )

    mark(spec.start_equity + closed_net, last_close_ts, bars_15m[-1][4])
    if abs(closed_net - (result.final_balance - spec.start_equity)) > _NET_CHECK_TOL_REL * max(
        1.0, abs(result.final_balance)
    ):
        raise runner.ResultParseError(
            f"conservation broken: sum(net_pnl)={closed_net!r} but wallet moved "
            f"{result.final_balance - spec.start_equity!r}"
        )
    records.sort(key=lambda record: record.ts_ms)
    return ExecutionLedger(
        symbol=symbol,
        strategy_revision_id=spec.strategy_revision_id,
        records=records,
        final_equity=result.final_balance,
        closed_trades=trades,
    )
