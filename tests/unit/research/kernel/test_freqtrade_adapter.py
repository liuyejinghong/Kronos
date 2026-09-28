"""Unit tests for the freqtrade kernel adapter (P08) — subprocess fully mocked.

These tests must pass on any machine: the pinned freqtrade venv is faked with
an empty binary and the result zip is a committed fixture from one real run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from kronos.research.verdict.backtest_adapter import (
    BacktestCaseInput,
    StrategyBacktestAdapter,
)
from kronos.research.verdict.contracts import ExecutionLedger
from kronos.research.verdict.golden.loader import load_case
from kronos.research.verdict.kernel import freqtrade_runner as runner
from kronos.research.verdict.kernel.freqtrade_runner import expand_15m_to_1m
from kronos.research.verdict.kernel.strategy_template import (
    STRATEGY_NAME,
    render_strategy_source,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# --- shared local helpers -------------------------------------------------------

FIXTURE_ZIP = Path(__file__).resolve().parents[3] / "fixtures" / "research" / "kernel" / (
    "freqtrade_result_G01.zip"
)
"""Committed result zip from one real pinned-kernel G01 run."""


def golden_case_input(case_id: str = "G01") -> BacktestCaseInput:
    """Build a contiguous-data case input from the golden fixtures."""
    case = load_case(case_id)
    bars_15m = [(b.ts_ms, b.o, b.h, b.l, b.c) for b in case.bars_15m]
    bundle = SimpleNamespace(
        bars_15m=bars_15m,
        bars_1m=[tuple(row[:5]) for row in expand_15m_to_1m(bars_15m)],
        funding_events=[(f.ts_ms, f.rate) for f in case.funding_events],
        params=case.params,
        cost=case.cost,
        start_equity=case.start_equity,
    )
    return BacktestCaseInput.from_golden_bundle(bundle)  # type: ignore[arg-type]


def fake_freqtrade_run(fixture_zip: Path) -> Callable[..., object]:
    """subprocess.run stand-in that stages a stored result zip under the workdir."""

    def _run(cmd: list[str], **_kwargs: object) -> object:
        config_path = Path(cmd[cmd.index("-c") + 1])
        results_dir = config_path.parent / "user_data" / "backtest_results"
        results_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fixture_zip, results_dir / fixture_zip.name)
        (results_dir / ".last_result.json").write_text(
            json.dumps({"latest_backtest": fixture_zip.name}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="ok", stderr="")

    return _run


# --- mapping and data conversion ------------------------------------------------


def test_to_ft_pair_mapping() -> None:
    assert runner.to_ft_pair("BTCUSDT") == "BTC/USDT:USDT"
    assert runner.ft_file_stem("BTC/USDT:USDT") == "BTC_USDT_USDT"
    with pytest.raises(runner.DataStagingError, match="USDT-margined"):
        runner.to_ft_pair("BTCUSD")


def test_expand_15m_to_1m_contiguous_and_aligned() -> None:
    case_in = golden_case_input("G01")
    rows = runner.expand_15m_to_1m(case_in.bars_15m)
    assert len(rows) == len(case_in.bars_15m) * 15
    for a, b in pairwise(rows):
        assert b[0] - a[0] == 60_000.0
    # every fill moment ("first 1m at/after signal close") opens at the next 15m open
    by_ts = {int(row[0]): row for row in rows}
    for i, (ts, _o, _h, _l, _c) in enumerate(case_in.bars_15m[:-1]):
        next_open = case_in.bars_15m[i + 1][1]
        assert by_ts[ts + 900_000][1] == next_open


def test_render_strategy_source_bakes_params_and_guard() -> None:
    source = render_strategy_source(atr_period=3, volatility_multiplier=2.5)
    assert f"class {STRATEGY_NAME}(IStrategy):" in source
    assert "startup_candle_count = 98" in source  # 96 + 3 - 1
    assert "volatility_multiplier = 2.5" in source
    assert "confirm_trade_entry" in source and "confirm_trade_exit" in source
    assert '"day_end"' in source and '"q_exit"' in source


def test_render_strategy_source_rejects_bad_params() -> None:
    with pytest.raises(ValueError, match="atr_period"):
        render_strategy_source(atr_period=1, volatility_multiplier=1.0)
    with pytest.raises(ValueError, match="volatility_multiplier"):
        render_strategy_source(atr_period=2, volatility_multiplier=0.0)


# --- environment bootstrap --------------------------------------------------------


def test_ensure_freqtrade_env_missing_raises_when_skip(tmp_path: Path) -> None:
    with pytest.raises(runner.FreqtradeEnvMissingError, match="ensure_freqtrade_env"):
        runner.ensure_freqtrade_env(tmp_path / "nope", skip_if_missing=True)


def test_adapter_run_requires_venv(tmp_path: Path) -> None:
    adapter = StrategyBacktestAdapter(venv_dir=tmp_path / "absent-venv")
    with pytest.raises(runner.FreqtradeEnvMissingError, match="ensure_freqtrade_env"):
        adapter.run_backtest(golden_case_input("G01"))


# --- staging guards (fail closed) --------------------------------------------------


def _spec(case_in: BacktestCaseInput, **overrides: object) -> runner.RunSpec:
    fields: dict[str, object] = {
        "bars_15m": case_in.bars_15m,
        "bars_1m": case_in.bars_1m,
        "funding_events": case_in.funding_events,
        "atr_period": case_in.atr_period,
        "volatility_multiplier": case_in.volatility_multiplier,
    }
    fields.update(overrides)
    return runner.RunSpec(
        bars_15m=fields["bars_15m"],  # type: ignore[arg-type]
        bars_1m=fields["bars_1m"],  # type: ignore[arg-type]
        funding_events=fields["funding_events"],  # type: ignore[arg-type]
        atr_period=fields["atr_period"],  # type: ignore[arg-type]
        volatility_multiplier=fields["volatility_multiplier"],  # type: ignore[arg-type]
        funding_declared_absent=bool(fields.get("funding_declared_absent", False)),
    )


def _source(case_in: BacktestCaseInput) -> str:
    return render_strategy_source(
        atr_period=case_in.atr_period,
        volatility_multiplier=case_in.volatility_multiplier,
    )


def test_stage_case_requires_funding_acknowledgment(tmp_path: Path) -> None:
    case_in = golden_case_input("G01")  # golden window with zero funding events
    with pytest.raises(runner.FundingDataError, match="funding_declared_absent"):
        runner.stage_case(_spec(case_in), tmp_path, strategy_source=_source(case_in))


def test_stage_case_declared_absent_writes_no_funding_file(tmp_path: Path) -> None:
    case_in = golden_case_input("G01")
    staged = runner.stage_case(
        _spec(case_in, funding_declared_absent=True),
        tmp_path,
        strategy_source=_source(case_in),
    )
    assert staged.funding_expected is False
    assert not staged.funding_path.exists()


def test_stage_case_validates_funding_events(tmp_path: Path) -> None:
    case_in = golden_case_input("G01")
    span_start = case_in.bars_15m[0][0]
    off_hour = [(span_start + 60_000, 0.0001)]
    with pytest.raises(runner.FundingDataError, match="hour boundary"):
        runner.stage_case(
            _spec(case_in, funding_events=off_hour), tmp_path, strategy_source=_source(case_in)
        )
    span_close = case_in.bars_15m[-1][0] + 900_000
    outside = [(span_close + 8 * 3_600_000, 0.0001)]
    with pytest.raises(runner.FundingDataError, match="outside the data span"):
        runner.stage_case(
            _spec(case_in, funding_events=outside), tmp_path, strategy_source=_source(case_in)
        )
    good = [(span_start + 8 * 3_600_000, 0.0001)]
    staged = runner.stage_case(
        _spec(case_in, funding_events=good), tmp_path, strategy_source=_source(case_in)
    )
    assert staged.funding_expected is True
    payload = json.loads(staged.funding_path.read_text(encoding="utf-8"))
    assert payload == [[float(good[0][0]), 0.0001]]


def test_stage_case_rejects_bad_bars(tmp_path: Path) -> None:
    case_in = golden_case_input("G01")
    unsorted = [case_in.bars_15m[1], case_in.bars_15m[0]]
    with pytest.raises(runner.DataStagingError, match="strictly increasing"):
        runner.stage_case(
            _spec(case_in, bars_15m=unsorted),
            tmp_path,
            strategy_source=_source(case_in),
        )


def test_stage_case_writes_freqtrade_files(tmp_path: Path) -> None:
    case_in = golden_case_input("G08")  # carries real funding events
    staged = runner.stage_case(_spec(case_in), tmp_path, strategy_source=_source(case_in))
    stem = staged.funding_path.name.replace("-1h-funding_rate.json", "")
    futures = staged.datadir / "futures"
    assert (futures / f"{stem}-1m-futures.json").is_file()
    assert (futures / f"{stem}-15m-futures.json").is_file()
    assert (futures / f"{stem}-1h-mark.json").is_file()
    assert staged.funding_path.read_text(encoding="utf-8").startswith("[[")
    config = json.loads(staged.config_path.read_text(encoding="utf-8"))
    assert config["trading_mode"] == "futures"
    assert config["fee"] == pytest.approx(0.0004)
    assert config["exchange"]["pair_whitelist"] == ["BTC/USDT:USDT"]


# --- subprocess behavior (mocked) ---------------------------------------------------


@pytest.fixture()
def fake_venv(tmp_path: Path) -> Path:
    venv = tmp_path / "ft-venv"
    (venv / "bin").mkdir(parents=True)
    binary = venv / "bin" / "freqtrade"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    return venv


def test_run_backtest_normalizes_fixture_result(
    fake_venv: Path, tmp_path: Path, mock_freqtrade_subprocess: None
) -> None:
    adapter = StrategyBacktestAdapter(venv_dir=fake_venv)
    ledger = adapter.run_backtest(golden_case_input("G01"), workdir=tmp_path / "wd")
    assert isinstance(ledger, ExecutionLedger)
    assert ledger.symbol == "BTCUSDT"
    assert ledger.final_equity == pytest.approx(9975.42536)
    assert len(ledger.closed_trades) == 1
    trade = ledger.closed_trades[0]
    # exchange lot rounding (0.001) is canonical per D-20260928-003
    assert trade.qty == 0.166
    assert trade.qty < 0.166389  # lot-rounded down from the 6dp reference amount
    assert trade.direction == "long"
    assert trade.entry_price == 60100.0 and trade.exit_price == 60000.0
    assert trade.exit_reason == "signal_exit"
    assert trade.holding_bars == 3
    # conservation: final - start == sum(closed net)
    residual = ledger.final_equity - 10_000.0 - sum(t.net_pnl for t in ledger.closed_trades)
    assert abs(residual) < 1e-6
    events = {record.event for record in ledger.records}
    assert events == {"order", "fill", "fee", "position_open", "position_close", "equity_mark"}
    fills = [r for r in ledger.records if r.event == "fill"]
    assert [(f.side, f.price) for f in fills] == [("buy", 60100.0), ("sell", 60000.0)]


def test_run_backtest_nonzero_exit_raises_structured(fake_venv: Path, tmp_path: Path) -> None:
    def boom(cmd: list[str], **_kw: object) -> object:
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="part done", stderr="boom: bad data"
        )

    with patch(
        "kronos.research.verdict.kernel.freqtrade_runner.subprocess.run", side_effect=boom
    ):
        adapter = StrategyBacktestAdapter(venv_dir=fake_venv)
        with pytest.raises(runner.FreqtradeRunError) as excinfo:
            adapter.run_backtest(golden_case_input("G01"), workdir=tmp_path / "wd")
    assert excinfo.value.returncode == 1
    assert "boom: bad data" in excinfo.value.stderr_tail


def test_run_backtest_timeout_raises(fake_venv: Path, tmp_path: Path) -> None:
    def slow(cmd: list[str], **_kw: object) -> object:
        raise subprocess.TimeoutExpired(cmd="freqtrade", timeout=0.01, stderr=b"timed out tail")

    with patch(
        "kronos.research.verdict.kernel.freqtrade_runner.subprocess.run", side_effect=slow
    ):
        adapter = StrategyBacktestAdapter(venv_dir=fake_venv)
        with pytest.raises(runner.FreqtradeTimeoutError, match="timed out tail"):
            adapter.run_backtest(golden_case_input("G01"), workdir=tmp_path / "wd")


def test_missing_funding_history_fails_closed(fake_venv: Path, tmp_path: Path) -> None:
    """A freqtrade warning about missing funding history must abort the run."""
    stdout = (
        "WARNING - No history for BTC/USDT:USDT, funding_rate, 1h found. "
        "Use `freqtrade download-data` to download the data\n"
    )

    def sneaky(cmd: list[str], **_kw: object) -> object:
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=stdout, stderr="")

    case_in = golden_case_input("G08")  # window with real funding events
    with patch(
        "kronos.research.verdict.kernel.freqtrade_runner.subprocess.run", side_effect=sneaky
    ):
        adapter = StrategyBacktestAdapter(venv_dir=fake_venv)
        with pytest.raises(runner.FundingDataError, match="fail-closed"):
            adapter.run_backtest(case_in, workdir=tmp_path)


def test_zero_trades_result_normalizes(fake_venv: Path, tmp_path: Path) -> None:
    """A result zip with an empty trade list yields an empty, conserved ledger."""
    stored = tmp_path / "stored"
    stored.mkdir()
    empty_zip = _make_modified_fixture_zip(stored, edits={"trades": [], "final_balance": 10000.0})

    def place_zip(cmd: list[str], **_kw: object) -> object:
        return _place_and_return(cmd, empty_zip)

    with patch(
        "kronos.research.verdict.kernel.freqtrade_runner.subprocess.run", side_effect=place_zip
    ):
        adapter = StrategyBacktestAdapter(venv_dir=fake_venv)
        ledger = adapter.run_backtest(golden_case_input("G05"), workdir=tmp_path / "wd")
    assert ledger.closed_trades == []
    assert ledger.final_equity == pytest.approx(10000.0)
    assert ledger.records[-1].equity == pytest.approx(10000.0)


def test_unmapped_exit_reason_fails_closed(fake_venv: Path, tmp_path: Path) -> None:
    """An unknown freqtrade exit_reason must abort normalization, not guess."""
    stored = tmp_path / "stored"
    stored.mkdir()
    modified_zip = _make_modified_fixture_zip(stored, edits={"exit_reason": "roi"})

    with patch(
        "kronos.research.verdict.kernel.freqtrade_runner.subprocess.run",
        side_effect=fake_freqtrade_run(modified_zip),
    ):
        adapter = StrategyBacktestAdapter(venv_dir=fake_venv)
        with pytest.raises(runner.ResultParseError, match="unmapped exit_reason"):
            adapter.run_backtest(golden_case_input("G01"), workdir=tmp_path / "wd")


def test_slippage_rejected_fail_closed() -> None:
    case_in = golden_case_input("G01").model_copy(update={"slippage_bps": 5.0})
    with pytest.raises(ValueError, match="slippage"):
        StrategyBacktestAdapter(venv_dir=Path("/unused")).run_backtest(case_in)


def test_parse_result_zip_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(runner.ResultParseError, match="not found"):
        runner.parse_result_zip(tmp_path / "nope.zip", strategy_name=STRATEGY_NAME)


# --- helpers ------------------------------------------------------------------------


def _place_and_return(cmd: list[str], zip_path: Path) -> object:
    """Mock subprocess.run: stage .last_result.json + zip under the workdir."""
    assert cmd[0].endswith("freqtrade"), cmd
    config_path = Path(cmd[cmd.index("-c") + 1])
    results_dir = config_path.parent / "user_data" / "backtest_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(zip_path, results_dir / zip_path.name)
    (results_dir / ".last_result.json").write_text(
        json.dumps({"latest_backtest": zip_path.name}), encoding="utf-8"
    )
    return subprocess.CompletedProcess(cmd, returncode=0, stdout="ok", stderr="")


def _make_modified_fixture_zip(workdir: Path, *, edits: dict[str, object]) -> Path:
    """Rewrite the committed fixture zip with edits applied to its first trade.

    ``trades`` / ``final_balance`` edit the strategy block itself; any other
    key edits the first trade record.
    """
    with zipfile.ZipFile(FIXTURE_ZIP) as archive:
        names = archive.namelist()
        main_name = next(n for n in names if n.endswith(".json") and "config" not in n)
        payload = json.loads(archive.read(main_name).decode("utf-8"))
        blobs = {n: archive.read(n) for n in names}
    strategy_block = payload["strategy"][next(iter(payload["strategy"]))]
    for key, value in edits.items():
        if key in ("trades", "final_balance"):
            strategy_block[key] = value
        else:
            strategy_block["trades"][0][key] = value
    blobs[main_name] = json.dumps(payload).encode("utf-8")
    target = workdir / "modified.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, blob in blobs.items():
            archive.writestr(name, blob)
    return target
