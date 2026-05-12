"""Kronos test configuration and shared fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory structure."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    return tmp_path / "data"


@pytest.fixture
def sample_config_path(tmp_path: Path) -> Path:
    """Create a minimal TOML config file for testing."""
    config = tmp_path / "test.toml"
    config.write_text(
        '[runtime]\nmode = "dev"\ndata_path = "./data"\nlog_level = "DEBUG"\nlog_json = false\n'
    )
    return config


@pytest.fixture(autouse=True)
def isolated_candidate_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep tests from reading or writing the user's real candidate registry."""
    monkeypatch.setenv("KRONOS_CANDIDATES_PATH", str(tmp_path / ".kronos" / "candidates.json"))


@pytest.fixture(autouse=True)
def isolated_secret_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep tests from reading or writing the user's real local exchange/API credentials."""
    monkeypatch.setenv(
        "KRONOS_SECRET_STORE_PATH",
        str(tmp_path / ".kronos-secrets" / "agent_secrets.json"),
    )
