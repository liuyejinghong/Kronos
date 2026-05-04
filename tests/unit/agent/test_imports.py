"""Import tests for the Agent package skeleton."""

from __future__ import annotations

import importlib


def test_agent_package_imports_without_side_effects() -> None:
    module = importlib.import_module("kronos.agent")

    assert module.__name__ == "kronos.agent"
    assert module.__all__ == []
