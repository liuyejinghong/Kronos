"""Tests for user-facing configuration defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kronos.common.config import load_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_default_runtime_logging_is_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KRONOS_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg = load_config()

    assert cfg.runtime.log_level == "WARNING"


def test_load_config_does_not_print_pre_logging_messages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "dev.toml"
    config_path.write_text(
        '[runtime]\nmode = "dev"\nlog_level = "WARNING"\nlog_json = false\n',
        encoding="utf-8",
    )

    load_config(config_path)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
