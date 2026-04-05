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
