"""Isolated freqtrade 2026.8 kernel runner (P08).

Owns everything that touches freqtrade so no other kronos module imports it
(GPL isolation, ruling D-20260928-003): environment bootstrap, pair mapping,
freqtrade-format data staging, config generation, the backtesting subprocess,
and result-zip parsing.  Strategy semantics come from
:mod:`kronos.research.verdict.kernel.strategy_template`.

Semantic contract implemented here (M0 evidence, ruling D-20260928-003):

- exchange lot rounding of quantity is CANONICAL (the reference ledger is the
  checker, not the other way round);
- a missing/unreadable funding file for a funding-covered window is a hard
  error, never a silent zero;
- the pinned kernel is freqtrade 2026.8, run as a subprocess with a
  parameterized timeout (default 120 s).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    Bar = tuple[int, float, float, float, float]
    FundingEvent = tuple[int, float]
else:
    Bar = tuple[int, float, float, float, float]
    FundingEvent = tuple[int, float]

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "FREQTRADE_PIN",
    "FREQTRADE_VERSION",
    "DataStagingError",
    "FreqtradeBacktestResult",
    "FreqtradeEnvBootstrapError",
    "FreqtradeEnvMissingError",
    "FreqtradeKernelError",
    "FreqtradeRunError",
    "FreqtradeTimeoutError",
    "FundingDataError",
    "ResultParseError",
    "RunSpec",
    "StagedRun",
    "build_mark_1h",
    "ensure_freqtrade_env",
    "expand_15m_to_1m",
    "ft_file_stem",
    "resolve_venv",
    "run_backtesting",
    "stage_case",
    "to_ft_pair",
]

FREQTRADE_VERSION: Final[str] = "2026.8"
FREQTRADE_PIN: Final[str] = f"freqtrade=={FREQTRADE_VERSION}"
DEFAULT_TIMEOUT_S: Final[float] = 120.0
TF15_MS: Final[int] = 900_000
HOUR_MS: Final[int] = 3_600_000
STDERR_TAIL_CHARS: Final[int] = 4000
_PROBE_TIMEOUT_S: Final[float] = 60.0

_ENV_VENV_VAR: Final[str] = "KRONOS_FREQTRADE_VENV"
_ENV_PROXY_VAR: Final[str] = "KRONOS_FREQTRADE_PROXY"
_MISSING_FUNDING_WARNING: Final[str] = r"No history for \S+, funding_rate"


class FreqtradeKernelError(Exception):
    """Base class for every freqtrade-kernel failure (fail closed)."""


class FreqtradeEnvMissingError(FreqtradeKernelError):
    """The pinned freqtrade venv does not exist (bootstrap it explicitly)."""


class FreqtradeEnvBootstrapError(FreqtradeKernelError):
    """Bootstrapping the pinned freqtrade venv failed."""


class FreqtradeRunError(FreqtradeKernelError):
    """The freqtrade backtesting subprocess exited nonzero."""

    def __init__(self, returncode: int, stderr_tail: str, stdout_tail: str) -> None:
        self.returncode = returncode
        self.stderr_tail = stderr_tail
        self.stdout_tail = stdout_tail
        super().__init__(
            f"freqtrade backtesting exited with code {returncode}; "
            f"stderr tail:\n{stderr_tail}"
        )


class FreqtradeTimeoutError(FreqtradeKernelError):
    """The freqtrade backtesting subprocess exceeded the timeout."""


class FundingDataError(FreqtradeKernelError):
    """Funding inputs are missing, empty, or unreadable (never silently zero)."""


class DataStagingError(FreqtradeKernelError):
    """Caller-supplied bars are unusable (non-monotonic, malformed, gapped)."""


class ResultParseError(FreqtradeKernelError):
    """The freqtrade result zip is missing or does not parse."""


def to_ft_pair(symbol: str) -> str:
    """Map a Kronos USDT-margined symbol (``BTCUSDT``) to ``BTC/USDT:USDT``."""
    if not symbol.endswith("USDT") or len(symbol) <= 4:
        raise DataStagingError(
            f"only USDT-margined symbols are supported, got {symbol!r}"
        )
    return f"{symbol[:-4]}/USDT:USDT"


def ft_file_stem(pair: str) -> str:
    """Freqtrade data file stem for a pair (``BTC/USDT:USDT`` -> ``BTC_USDT_USDT``)."""
    return pair.replace("/", "_").replace(":", "_")


def _validate_bars(bars: Sequence[Bar], name: str) -> None:
    """Reject non-monotonic timestamps and malformed OHLC up front."""
    prev_ts: int | None = None
    for index, bar in enumerate(bars):
        ts, open_, high, low, close = bar
        if ts < 0:
            raise DataStagingError(f"{name}[{index}]: ts_ms must be >= 0, got {ts}")
        if not (high >= low and high >= open_ and high >= close and low <= open_ and low <= close):
            raise DataStagingError(
                f"{name}[{index}]: malformed OHLC (o={open_}, h={high}, l={low}, c={close})"
            )
        if prev_ts is not None and ts <= prev_ts:
            raise DataStagingError(f"{name}[{index}]: timestamps must be strictly increasing")
        prev_ts = ts


def expand_15m_to_1m(bars_15m: Sequence[Bar]) -> list[list[float]]:
    """Expand 15m bars into a contiguous 1m series (M0 protocol rule).

    Within each 15m bar the first fourteen 1m bars sit flat at the 15m open;
    the fifteenth carries the 15m close.  The fill moment "first 1m bar at or
    after the signal-bar close" is therefore the first 1m bar of the next 15m
    window, whose open equals the next 15m open by construction.
    """
    _validate_bars(bars_15m, "bars_15m")
    out: list[list[float]] = []
    for ts, open_, _high, _low, close in bars_15m:
        for i in range(15):
            minute_ts = ts + i * 60_000
            if i < 14:
                out.append([float(minute_ts), open_, open_, open_, open_, 1.0])
            else:
                out.append(
                    [
                        float(minute_ts),
                        open_,
                        max(open_, close),
                        min(open_, close),
                        close,
                        1.0,
                    ]
                )
    return out


def build_mark_1h(bars_15m: Sequence[Bar]) -> list[list[float]]:
    """Flat 1h mark candles whose OPEN at hour H is the last completed 15m close.

    freqtrade reads ``open_mark`` at the exact funding date, so this makes the
    funding mark identical to the reference engine's mark by construction.
    """
    first_ts = bars_15m[0][0]
    last_close_ts = bars_15m[-1][0] + TF15_MS
    out: list[list[float]] = []
    idx = 0  # bars_15m[idx] is the last bar with close_ts <= H
    hour = first_ts
    while hour <= last_close_ts:
        while idx + 1 < len(bars_15m) and bars_15m[idx + 1][0] + TF15_MS <= hour:
            idx += 1
        mark = bars_15m[idx][4] if bars_15m[idx][0] + TF15_MS <= hour else bars_15m[0][1]
        out.append([float(hour), mark, mark, mark, mark, 0.0])
        hour += HOUR_MS
    return out


# --- environment bootstrap -----------------------------------------------------


def resolve_venv(venv_dir: str | Path | None = None) -> Path:
    """Resolve the pinned venv location: argument > env var > ``.tools`` default."""
    if venv_dir is not None:
        return Path(venv_dir).expanduser().resolve()
    from_env = os.environ.get(_ENV_VENV_VAR)
    if from_env:
        return Path(from_env).expanduser().resolve()
    return (Path.cwd() / ".tools" / "freqtrade-venv").resolve()


def freqtrade_binary(venv_dir: str | Path | None = None) -> Path:
    """Path of the freqtrade CLI inside the pinned venv (POSIX layout)."""
    return resolve_venv(venv_dir) / "bin" / "freqtrade"


def _probe_version(ft_bin: Path) -> str | None:
    """Return the reported freqtrade version, or None if unusable."""
    try:
        proc = subprocess.run(
            [str(ft_bin), "--version"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    match = re.search(r"freqtrade\s+(\d+\.\d+)", proc.stdout)
    return match.group(1) if match else None


def ensure_freqtrade_env(
    venv_dir: str | Path | None = None,
    *,
    skip_if_missing: bool = False,
    python_version: str = "3.12",
    uv_bin: str = "uv",
) -> Path:
    """Ensure the pinned freqtrade venv exists at ``venv_dir`` and return it.

    Installs :data:`FREQTRADE_PIN` via ``uv`` when missing.  With
    ``skip_if_missing=True`` a missing environment raises
    :class:`FreqtradeEnvMissingError` instead of installing (integration tests use
    this to skip cleanly when the venv has not been bootstrapped).
    """
    directory = resolve_venv(venv_dir)
    ft_bin = directory / "bin" / "freqtrade"
    if _probe_version(ft_bin) == FREQTRADE_VERSION:
        return directory
    if skip_if_missing:
        raise FreqtradeEnvMissingError(
            f"freqtrade venv not usable at {directory} "
            f"(expected {FREQTRADE_PIN}); call ensure_freqtrade_env() to bootstrap it "
            f"or set {_ENV_VENV_VAR}"
        )
    if shutil.which(uv_bin) is None:
        raise FreqtradeEnvBootstrapError(
            f"uv binary {uv_bin!r} not found on PATH; cannot bootstrap {directory}"
        )
    directory.parent.mkdir(parents=True, exist_ok=True)
    for argv in (
        [uv_bin, "venv", "--python", python_version, str(directory)],
        [uv_bin, "pip", "install", "--python", str(directory / "bin" / "python"), FREQTRADE_PIN],
    ):
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=600, check=False)
        if proc.returncode != 0:
            raise FreqtradeEnvBootstrapError(
                f"command {argv} failed (rc={proc.returncode}):\n{proc.stderr[-STDERR_TAIL_CHARS:]}"
            )
    if _probe_version(ft_bin) != FREQTRADE_VERSION:
        raise FreqtradeEnvBootstrapError(
            f"venv at {directory} did not report freqtrade {FREQTRADE_VERSION} after bootstrap"
        )
    return directory


# --- workdir staging -----------------------------------------------------------


@dataclass(frozen=True)
class RunSpec:
    """Primitive, validated inputs for one staged freqtrade backtest.

    Same shapes as the golden loader: 15m signal bars + 1m execution bars as
    ``(ts_ms, open, high, low, close)`` tuples and funding events as
    ``(ts_ms, rate)``.  ``funding_declared_absent`` is the explicit
    acknowledgment required when a window carries no funding events; without
    it an empty event list is a hard error (fail closed, D-20260928-003).
    """

    bars_15m: list[Bar]
    bars_1m: list[Bar]
    funding_events: list[FundingEvent]
    atr_period: int
    volatility_multiplier: float
    fee_bps: float = 4.0
    start_equity: float = 10_000.0
    equity_fraction: float = 1.0
    symbol: str = "BTCUSDT"
    strategy_revision_id: str = "kronos_threshold_v1"
    funding_declared_absent: bool = False
    ccxt_proxy: str | None = None

    @property
    def ft_pair(self) -> str:
        return to_ft_pair(self.symbol)

    @property
    def file_stem(self) -> str:
        return ft_file_stem(self.ft_pair)


@dataclass(frozen=True)
class StagedRun:
    """Everything freqtrade needs, materialized inside one workdir."""

    workdir: Path
    config_path: Path
    datadir: Path
    strategy_path: Path
    strategy_name: str
    funding_path: Path
    funding_expected: bool
    funding_declared_absent: bool


def _default_proxy() -> str | None:
    explicit = os.environ.get(_ENV_PROXY_VAR)
    if explicit:
        return explicit
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(name)
        if value:
            return value
    return None


def stage_case(spec: RunSpec, workdir: Path, *, strategy_source: str) -> StagedRun:
    """Materialize data files, config and strategy for one run (fail closed).

    Raises :class:`FundingDataError` when the window has no funding events and
    the caller has not set ``funding_declared_absent``, when any funding
    timestamp is not on an hour boundary (freqtrade would silently drop it in
    the mark/funding inner join), or when an event falls outside the data span.
    """
    _validate_bars(spec.bars_15m, "bars_15m")
    _validate_bars(spec.bars_1m, "bars_1m")
    if not spec.bars_15m:
        raise DataStagingError("bars_15m must not be empty")
    span_start = spec.bars_15m[0][0]
    span_end = spec.bars_15m[-1][0] + TF15_MS

    futures_dir = workdir / "data" / "binance" / "futures"
    (workdir / "user_data").mkdir(parents=True, exist_ok=True)
    futures_dir.mkdir(parents=True, exist_ok=True)
    stem = spec.file_stem

    (futures_dir / f"{stem}-1m-futures.json").write_text(
        json.dumps(spec.bars_1m, separators=(",", ":")), encoding="utf-8"
    )
    (futures_dir / f"{stem}-15m-futures.json").write_text(
        json.dumps([[ts, o, h, low, c, 1.0] for ts, o, h, low, c in spec.bars_15m],
                   separators=(",", ":")),
        encoding="utf-8",
    )
    (futures_dir / f"{stem}-1h-mark.json").write_text(
        json.dumps(build_mark_1h(spec.bars_15m), separators=(",", ":")), encoding="utf-8"
    )

    funding_path = futures_dir / f"{stem}-1h-funding_rate.json"
    events = sorted(spec.funding_events)
    if not events:
        # Declared-absent window: stage NO funding file.  freqtrade then books
        # zero funding, which is the acknowledged correct answer; the adapter's
        # per-event reconciliation would reject any nonzero booking anyway.
        if not spec.funding_declared_absent:
            raise FundingDataError(
                "no funding events supplied for a funding-covered window; pass "
                "funding_declared_absent=True only if the window truly has no settlements "
                "(fail-closed rule D-20260928-003)"
            )
    else:
        for ts, _rate in events:
            if ts % HOUR_MS != 0:
                raise FundingDataError(
                    f"funding event at {ts} is not on an hour boundary; freqtrade would "
                    "silently drop it in the funding/mark join"
                )
            if not span_start <= ts <= span_end:
                raise FundingDataError(f"funding event at {ts} falls outside the data span")
        payload = [[float(ts), rate] for ts, rate in events]
        funding_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        if not funding_path.is_file() or funding_path.stat().st_size == 0:
            raise FundingDataError(f"staged funding file is missing or empty: {funding_path}")

    config = _build_config(spec, workdir)
    config_path = workdir / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    strategy_path = workdir / "strategy.py"
    strategy_path.write_text(strategy_source, encoding="utf-8")

    return StagedRun(
        workdir=workdir,
        config_path=config_path,
        datadir=futures_dir.parent,
        strategy_path=strategy_path,
        strategy_name=_strategy_name_from_source(strategy_source),
        funding_path=funding_path,
        funding_expected=bool(events),
        funding_declared_absent=spec.funding_declared_absent or not events,
    )


def _strategy_name_from_source(source: str) -> str:
    match = re.search(r"^class (\w+)\(IStrategy\):", source, flags=re.MULTILINE)
    if match is None:
        raise DataStagingError("strategy source does not define a class Name(IStrategy)")
    return match.group(1)


def _build_config(spec: RunSpec, workdir: Path) -> dict[str, object]:
    """Config for one staged run (futures, isolated, explicit fee, no ROI/SL)."""
    proxy = spec.ccxt_proxy if spec.ccxt_proxy is not None else _default_proxy()
    ccxt_config: dict[str, object] = {"timeout": 30000}
    ccxt_async_config: dict[str, object] = {"timeout": 30000, "aiohttp_trust_env": True}
    if proxy:
        ccxt_config["proxies"] = {"http": proxy, "https": proxy}
    user_data = workdir / "user_data"
    return {
        "bot_name": "kronos-verdict-kernel",
        "dry_run": True,
        "dry_run_wallet": spec.start_equity,
        "max_open_trades": 1,
        "stake_currency": "USDT",
        "stake_amount": "unlimited",
        "tradable_balance_ratio": spec.equity_fraction,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "fee": spec.fee_bps / 10_000.0,
        "exchange": {
            "name": "binance",
            "key": "",
            "secret": "",
            "ccxt_config": ccxt_config,
            "ccxt_async_config": ccxt_async_config,
            "pair_whitelist": [spec.ft_pair],
            "pair_blacklist": [],
        },
        "entry_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "exit_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "pairlists": [{"method": "StaticPairList"}],
        "unfilledtimeout": {"entry": 10, "exit": 10, "exit_timeout_count": 0, "unit": "minutes"},
        "user_data_dir": str(user_data),
        "db_url": f"sqlite:///{user_data / 'kernel.sqlite'}",
        "dataformat_ohlcv": "json",
        "initial_state": "running",
        "internals": {"process_throttle_secs": 5},
    }


# --- subprocess execution and result parsing -----------------------------------


@dataclass(frozen=True)
class FreqtradeTrade:
    """Normalized subset of one trade record from the result zip."""

    direction: str  # "long" | "short"
    open_ts_ms: int
    close_ts_ms: int
    open_rate: float
    close_rate: float
    amount: float
    fee_open_cost: float
    fee_close_cost: float
    funding_fees: float  # freqtrade sign: cash impact (negative when a long pays)
    profit_abs: float
    exit_reason: str
    enter_tag: str
    stake_amount: float
    leverage: float


@dataclass(frozen=True)
class FreqtradeBacktestResult:
    """Parsed backtest output: final wallet plus normalized trades."""

    final_balance: float
    backtest_start: str
    backtest_end: str
    trades: list[FreqtradeTrade] = field(default_factory=list)


def run_backtesting(
    staged: StagedRun,
    *,
    venv_dir: str | Path | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> FreqtradeBacktestResult:
    """Run the pinned freqtrade backtesting subprocess and parse its result zip.

    Fail closed on: nonzero exit (with stderr tail), timeout, a freqtrade
    warning indicating missing funding-rate history, or an unparseable result.
    """
    ft_bin = freqtrade_binary(venv_dir)
    if not ft_bin.is_file():
        raise FreqtradeEnvMissingError(
            f"freqtrade binary not found at {ft_bin}; call ensure_freqtrade_env() first"
        )
    cmd = [
        str(ft_bin),
        "backtesting",
        "-c",
        str(staged.config_path),
        "--datadir",
        str(staged.datadir),
        "--strategy",
        staged.strategy_name,
        "--strategy-path",
        str(staged.strategy_path.parent),
        "--export",
        "trades",
        "--cache",
        "none",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        stderr_tail = (exc.stderr or b"").decode("utf-8", errors="replace")[-STDERR_TAIL_CHARS:] \
            if isinstance(exc.stderr, bytes) else (exc.stderr or "")[-STDERR_TAIL_CHARS:]
        raise FreqtradeTimeoutError(
            f"freqtrade backtesting exceeded timeout of {timeout_s}s; stderr tail:\n{stderr_tail}"
        ) from exc
    if proc.returncode != 0:
        raise FreqtradeRunError(
            proc.returncode, proc.stderr[-STDERR_TAIL_CHARS:], proc.stdout[-STDERR_TAIL_CHARS:]
        )
    output = proc.stdout + proc.stderr
    if staged.funding_expected and re.search(_MISSING_FUNDING_WARNING, output):
        raise FundingDataError(
            "freqtrade reported missing funding-rate history; refusing to return a ledger "
            "with silent zero funding (fail-closed rule D-20260928-003)"
        )
    results_dir = staged.workdir / "user_data" / "backtest_results"
    return parse_result_dir(results_dir, strategy_name=staged.strategy_name)


def parse_result_dir(results_dir: Path, *, strategy_name: str) -> FreqtradeBacktestResult:
    """Parse ``.last_result.json`` -> result zip -> normalized trades."""
    last_path = results_dir / ".last_result.json"
    if not last_path.is_file():
        raise ResultParseError(f"missing {last_path}; freqtrade did not export results")
    try:
        last = json.loads(last_path.read_text(encoding="utf-8"))
        zip_name = last["latest_backtest"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ResultParseError(f"unreadable {last_path}: {exc}") from exc
    return parse_result_zip(results_dir / zip_name, strategy_name=strategy_name)


def _main_result_name(names: Sequence[str]) -> str:
    """Find the main result json inside a result zip (not the config snapshot)."""
    candidates = [
        name
        for name in names
        if name.endswith(".json") and "backtest-result-" in name and not name.endswith("_config.json")
    ]
    if len(candidates) != 1:
        raise ResultParseError(f"expected exactly one main result json, got {candidates!r}")
    return candidates[0]


def parse_result_zip(zip_path: Path, *, strategy_name: str) -> FreqtradeBacktestResult:
    """Extract final balance and normalized trades from one result zip."""
    if not zip_path.is_file():
        raise ResultParseError(f"result zip not found: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            main_name = _main_result_name(archive.namelist())
            payload = json.loads(archive.read(main_name).decode("utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise ResultParseError(f"unreadable result zip {zip_path}: {exc}") from exc
    try:
        strategy_block = payload["strategy"][strategy_name]
        raw_trades = strategy_block["trades"]
        final_balance = float(strategy_block["final_balance"])
        backtest_start = str(strategy_block["backtest_start"])
        backtest_end = str(strategy_block["backtest_end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultParseError(
            f"result zip {zip_path} lacks strategy block {strategy_name!r}: {exc}"
        ) from exc
    trades = [_normalize_trade(raw) for raw in raw_trades]
    return FreqtradeBacktestResult(
        final_balance=final_balance,
        backtest_start=backtest_start,
        backtest_end=backtest_end,
        trades=trades,
    )


def _normalize_trade(raw: dict[str, Any]) -> FreqtradeTrade:
    """Pull the typed subset the adapter needs out of one raw trade dict."""
    try:
        amount = float(raw["amount"])
        open_rate = float(raw["open_rate"])
        close_rate = float(raw["close_rate"])
        fee_open = float(raw["fee_open"])
        fee_close = float(raw["fee_close"])
        return FreqtradeTrade(
            direction="short" if raw["is_short"] else "long",
            open_ts_ms=int(raw["open_timestamp"]),
            close_ts_ms=int(raw["close_timestamp"]),
            open_rate=open_rate,
            close_rate=close_rate,
            amount=amount,
            fee_open_cost=amount * open_rate * fee_open,
            fee_close_cost=amount * close_rate * fee_close,
            funding_fees=float(raw["funding_fees"]),
            profit_abs=float(raw["profit_abs"]),
            exit_reason=str(raw["exit_reason"]),
            enter_tag=str(raw.get("enter_tag") or ""),
            stake_amount=float(raw.get("stake_amount") or 0.0),
            leverage=float(raw.get("leverage") or 1.0),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultParseError(f"malformed trade record {raw!r}: {exc}") from exc
