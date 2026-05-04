"""Idle scanner skeleton for local Agent runtime."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.types import AgentTask, AgentTaskStatus


class IdleScanStatus(StrEnum):
    """Idle scanner result status."""

    NO_MATERIAL = "no_material"
    MATERIAL_FOUND = "material_found"


class MaterialItem(BaseModel):
    """Research material that can seed a future Agent task."""

    model_config = ConfigDict(extra="forbid")

    material_id: str = Field(min_length=1)
    title_zh: str = Field(min_length=1)
    source_type: str = Field(min_length=1)


class IdleScanResult(BaseModel):
    """Result of one idle material scan."""

    model_config = ConfigDict(extra="forbid")

    status: IdleScanStatus
    material: MaterialItem | None = None
    should_start_task: bool = False
    reason_zh: str = Field(min_length=1)


class MaterialDetector(Protocol):
    """Placeholder interface for future material detectors."""

    def detect(self) -> list[MaterialItem]:
        """Return currently available research materials."""


class StaticMaterialDetector:
    """Simple deterministic detector used by tests and local skeleton wiring."""

    def __init__(self, materials: list[MaterialItem] | None = None) -> None:
        self._materials = list(materials or [])

    def detect(self) -> list[MaterialItem]:
        """Return the configured material list."""
        return list(self._materials)


class AgentIdleScanner:
    """Decide whether idle Agent runtime should start a new research task."""

    def __init__(self, detector: MaterialDetector) -> None:
        self.detector = detector
        self._seen_material_ids: set[str] = set()

    def scan(self, *, current_task: AgentTask | None = None) -> IdleScanResult:
        """Scan for new material without reopening the same active task."""
        active_material_id = self._active_material_id(current_task)
        for material in self.detector.detect():
            if material.material_id == active_material_id:
                return IdleScanResult(
                    status=IdleScanStatus.NO_MATERIAL,
                    should_start_task=False,
                    reason_zh="当前材料已经在处理中, 不重复开启任务。",
                )
            if material.material_id not in self._seen_material_ids:
                self._seen_material_ids.add(material.material_id)
                return IdleScanResult(
                    status=IdleScanStatus.MATERIAL_FOUND,
                    material=material,
                    should_start_task=True,
                    reason_zh="发现新的研究材料, 可以开启下一轮 Agent 任务。",
                )

        return IdleScanResult(
            status=IdleScanStatus.NO_MATERIAL,
            should_start_task=False,
            reason_zh="没有新的研究材料。",
        )

    def _active_material_id(self, current_task: AgentTask | None) -> str | None:
        if current_task is None:
            return None
        if current_task.status not in {
            AgentTaskStatus.PENDING,
            AgentTaskStatus.QUEUED,
            AgentTaskStatus.RUNNING,
            AgentTaskStatus.WAITING_APPROVAL,
        }:
            return None
        material_id = current_task.metadata.get("material_id")
        return material_id if isinstance(material_id, str) else None
