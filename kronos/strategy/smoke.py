"""Strategy smoke tests over local market data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kronos.common.errors import DataError, FactorInputError
from kronos.data.storage.query import load
from kronos.strategy.r_breaker import create_r_breaker

if TYPE_CHECKING:
    from kronos.strategy.config import StrategyConfig


@dataclass(frozen=True)
class StrategySmokeResult:
    """Result of a lightweight strategy logic check."""

    strategy_id: str
    symbol: str
    timeframe: str
    passed: bool
    reason_code: str
    message_zh: str
    rows: int = 0
    valid_signal_count: int = 0
    strong_signal_count: int = 0
    min_signal: float | None = None
    max_signal: float | None = None

    def summary_lines(self) -> list[str]:
        """Return product-facing summary lines for CLI output."""
        status = "通过" if self.passed else "未通过"
        lines = [
            f"status: {status}",
            f"strategy: {self.strategy_id}",
            f"symbol: {self.symbol}",
            f"timeframe: {self.timeframe}",
            f"rows: {self.rows}",
            f"valid_signals: {self.valid_signal_count}",
            f"strong_signals: {self.strong_signal_count}",
            f"reason: {self.reason_code}",
            f"message: {self.message_zh}",
        ]
        if self.min_signal is not None and self.max_signal is not None:
            lines.append(f"signal_range: {self.min_signal:.4f} -> {self.max_signal:.4f}")
        lines.append("trading_enabled: no; smoke test only checks research logic")
        return lines


@dataclass(frozen=True)
class StrategySmokeBatchResult:
    """Aggregate result for smoke-testing a strategy across its symbols."""

    strategy_id: str
    timeframe: str
    results: list[StrategySmokeResult]

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(result.passed for result in self.results)

    @property
    def failed_symbols(self) -> list[str]:
        return [result.symbol for result in self.results if not result.passed]

    def summary_lines(self) -> list[str]:
        """Return product-facing summary lines for CLI output."""
        status = "通过" if self.passed else "未通过"
        failed_symbols = ", ".join(self.failed_symbols) if self.failed_symbols else "无"
        lines = [
            f"status: {status}",
            f"strategy: {self.strategy_id}",
            f"timeframe: {self.timeframe}",
            f"symbols_checked: {len(self.results)}",
            f"failed_symbols: {failed_symbols}",
        ]
        for result in self.results:
            lines.append("")
            lines.append(f"--- symbol: {result.symbol} ---")
            lines.extend(result.summary_lines())
        lines.append("trading_enabled: no; smoke test only checks research logic")
        return lines


def run_strategy_smoke_test(
    config: StrategyConfig,
    *,
    data_base_path: str | Path,
) -> StrategySmokeBatchResult:
    """Run a local smoke test for one strategy config.

    The smoke test only verifies that the strategy can load local data and
    compute non-empty signals. It does not imply validation, simulation, or
    readiness for paper/live trading.
    """
    if config.strategy.kind != "r_breaker":
        return StrategySmokeBatchResult(
            strategy_id=config.strategy.id,
            timeframe=config.universe.timeframe,
            results=[
                StrategySmokeResult(
                    strategy_id=config.strategy.id,
                    symbol="-",
                    timeframe=config.universe.timeframe,
                    passed=False,
                    reason_code="unsupported_strategy",
                    message_zh="当前版本只支持 R-breaker 配置的烟雾测试。",
                ),
            ],
        )

    timeframe = config.universe.timeframe
    factor = create_r_breaker(**config.params.model_dump())
    min_rows = factor.warmup_bars + 2

    results: list[StrategySmokeResult] = []
    for symbol in config.universe.symbols:
        try:
            df = load(symbol, base_path=Path(data_base_path), timeframe=timeframe)
        except DataError as exc:
            results.append(
                StrategySmokeResult(
                    strategy_id=config.strategy.id,
                    symbol=symbol,
                    timeframe=timeframe,
                    passed=False,
                    reason_code="data_error",
                    message_zh=f"读取本地行情数据失败: {exc}",
                )
            )
            continue

        if df.empty:
            results.append(
                StrategySmokeResult(
                    strategy_id=config.strategy.id,
                    symbol=symbol,
                    timeframe=timeframe,
                    passed=False,
                    reason_code="missing_data",
                    message_zh="本地没有可用于试算的 K 线数据。先运行 quickstart 或 data sync。",
                )
            )
            continue

        if len(df) < min_rows:
            results.append(
                StrategySmokeResult(
                    strategy_id=config.strategy.id,
                    symbol=symbol,
                    timeframe=timeframe,
                    passed=False,
                    reason_code="insufficient_history",
                    message_zh=f"历史样本不足: 需要至少 {min_rows} 根 K 线, 当前只有 {len(df)} 根。",
                    rows=len(df),
                )
            )
            continue

        try:
            signal = factor.compute(df)
        except (FactorInputError, ValueError, TypeError) as exc:
            results.append(
                StrategySmokeResult(
                    strategy_id=config.strategy.id,
                    symbol=symbol,
                    timeframe=timeframe,
                    passed=False,
                    reason_code="signal_error",
                    message_zh=f"策略逻辑无法计算信号: {exc}",
                    rows=len(df),
                )
            )
            continue

        valid = signal.dropna()
        if valid.empty:
            results.append(
                StrategySmokeResult(
                    strategy_id=config.strategy.id,
                    symbol=symbol,
                    timeframe=timeframe,
                    passed=False,
                    reason_code="empty_signal",
                    message_zh="策略可运行, 但没有产生任何有效信号, 请检查参数或数据周期。",
                    rows=len(df),
                )
            )
            continue

        strong_signal_count = int((valid.abs() >= 1.0).sum())
        min_signal = float(valid.min())
        max_signal = float(valid.max())
        if strong_signal_count > 0:
            message = "策略能读取本地数据并产生强突破信号, 可进入研究验证。"
        else:
            message = "策略能读取本地数据并产生连续信号, 但样本内没有强突破信号; 仍可进入研究验证。"

        results.append(
            StrategySmokeResult(
                strategy_id=config.strategy.id,
                symbol=symbol,
                timeframe=timeframe,
                passed=True,
                reason_code="ok",
                message_zh=message,
                rows=len(df),
                valid_signal_count=len(valid),
                strong_signal_count=strong_signal_count,
                min_signal=min_signal,
                max_signal=max_signal,
            )
        )

    return StrategySmokeBatchResult(
        strategy_id=config.strategy.id,
        timeframe=timeframe,
        results=results,
    )
