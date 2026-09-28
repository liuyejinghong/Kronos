"""Shared fixture for the kernel unit tests (mocked freqtrade subprocess).

Kept import-free of the test modules: pytest auto-loads this file, so the
mocked-subprocess fixture works regardless of rootdir/package layout.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

FIXTURE_ZIP = Path(__file__).resolve().parents[3] / "fixtures" / "research" / "kernel" / (
    "freqtrade_result_G01.zip"
)
"""Real G01 result zip from one pinned-kernel run (committed fixture)."""


@pytest.fixture()
def mock_freqtrade_subprocess() -> Generator[Path, None, None]:
    """Patch the runner's subprocess.run to materialize the fixture result zip.

    The fake derives the staged workdir from the ``-c`` argument and drops
    ``.last_result.json`` plus the fixture zip into
    ``<workdir>/user_data/backtest_results``.
    """

    def _run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        assert cmd[0].endswith("freqtrade"), cmd
        assert "--cache" in cmd and cmd[cmd.index("--cache") + 1] == "none", cmd
        config_path = Path(cmd[cmd.index("-c") + 1])
        results_dir = config_path.parent / "user_data" / "backtest_results"
        results_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURE_ZIP, results_dir / FIXTURE_ZIP.name)
        (results_dir / ".last_result.json").write_text(
            json.dumps({"latest_backtest": FIXTURE_ZIP.name}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="ok\n", stderr="")

    with patch(
        "kronos.research.verdict.kernel.freqtrade_runner.subprocess.run", side_effect=_run
    ):
        yield FIXTURE_ZIP
