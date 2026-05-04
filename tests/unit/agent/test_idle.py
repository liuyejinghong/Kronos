"""Tests for Agent idle scanner skeleton."""

from __future__ import annotations

from kronos.agent.idle import (
    AgentIdleScanner,
    IdleScanStatus,
    MaterialItem,
    StaticMaterialDetector,
)
from kronos.agent.types import AgentRunId, AgentTask, AgentTaskId, AgentTaskStatus


def _material(material_id: str) -> MaterialItem:
    return MaterialItem(
        material_id=material_id,
        title_zh=f"材料 {material_id}",
        source_type="local_report",
    )


def test_idle_scanner_returns_no_material_for_empty_detector() -> None:
    scanner = AgentIdleScanner(StaticMaterialDetector())

    result = scanner.scan()

    assert result.status == IdleScanStatus.NO_MATERIAL
    assert result.should_start_task is False
    assert result.material is None


def test_idle_scanner_finds_new_material_once() -> None:
    scanner = AgentIdleScanner(StaticMaterialDetector([_material("material-1")]))

    first = scanner.scan()
    second = scanner.scan()

    assert first.status == IdleScanStatus.MATERIAL_FOUND
    assert first.should_start_task is True
    assert first.material is not None
    assert first.material.material_id == "material-1"
    assert second.status == IdleScanStatus.NO_MATERIAL
    assert second.should_start_task is False


def test_idle_scanner_does_not_repeat_active_material_task() -> None:
    scanner = AgentIdleScanner(StaticMaterialDetector([_material("material-1")]))
    current_task = AgentTask(
        run_id=AgentRunId("run-1"),
        task_id=AgentTaskId("task-1"),
        status=AgentTaskStatus.RUNNING,
        title_zh="处理材料",
        metadata={"material_id": "material-1"},
    )

    result = scanner.scan(current_task=current_task)

    assert result.status == IdleScanStatus.NO_MATERIAL
    assert result.should_start_task is False
    assert "不重复" in result.reason_zh
