"""Deterministic tool registry and execution records for Agent runs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from kronos.agent.events import redact_secret_like_values, write_event
from kronos.agent.types import (
    AgentArtifactRef,
    AgentErrorCategory,
    AgentErrorRef,
    AgentEvent,
    AgentEventId,
    AgentEventLevel,
    AgentEventType,
    AgentRunId,
    AgentTaskId,
    AgentTaskStatus,
    AgentToolInvocationId,
)
from kronos.research.agent_planner import (
    run_research_agent_decision,
    run_research_agent_planner,
)


class AgentToolError(RuntimeError):
    """Raised when a deterministic tool cannot be executed."""


class AgentToolDefinition(BaseModel):
    """Metadata for one whitelisted deterministic tool."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    purpose_zh: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class AgentToolExecutionResult(BaseModel):
    """Return value from one deterministic tool handler."""

    model_config = ConfigDict(extra="forbid")

    output_summary: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentToolExecutionRecord(BaseModel):
    """Auditable record for one deterministic tool execution."""

    model_config = ConfigDict(extra="forbid")

    invocation_id: AgentToolInvocationId = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    status: AgentTaskStatus
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: list[AgentArtifactRef] = Field(default_factory=list)
    error_ref: AgentErrorRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


AgentToolHandler = Callable[[dict[str, Any]], AgentToolExecutionResult]


class AgentToolRegistry:
    """Whitelist registry for deterministic Agent tools."""

    def __init__(self, tools: list[AgentToolDefinition] | None = None) -> None:
        self._tools = {
            tool.name: tool.model_copy(deep=True)
            for tool in tools or default_tool_definitions()
        }

    def list_tools(self) -> list[AgentToolDefinition]:
        """Return all whitelisted tool definitions."""
        return [tool.model_copy(deep=True) for tool in self._tools.values()]

    def get_tool(self, name: str) -> AgentToolDefinition:
        """Return one whitelisted tool definition."""
        try:
            return self._tools[name].model_copy(deep=True)
        except KeyError as exc:
            raise AgentToolError(f"Tool is not whitelisted: {name}") from exc


class AgentToolExecutor:
    """Execute whitelisted deterministic tools and emit event records."""

    def __init__(
        self,
        *,
        registry: AgentToolRegistry | None = None,
        run_dir: str | Path | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        self.registry = registry or AgentToolRegistry()
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.run_id = run_id
        self.task_id = task_id

    def execute(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
        handler: AgentToolHandler,
    ) -> AgentToolExecutionRecord:
        """Execute a whitelisted deterministic tool."""
        tool = self.registry.get_tool(tool_name)
        invocation_id = AgentToolInvocationId(f"tool-invocation-{uuid4().hex}")
        started = AgentToolExecutionRecord(
            invocation_id=invocation_id,
            tool_name=tool.name,
            status=AgentTaskStatus.RUNNING,
            input_summary=redact_secret_like_values(payload),
            metadata={"purpose_zh": tool.purpose_zh},
        )
        self._write_event(started, AgentEventType.TOOL_EXECUTION_STARTED)

        try:
            result = handler(dict(payload))
        except Exception as exc:
            failed = started.model_copy(
                update={
                    "status": AgentTaskStatus.FAILED,
                    "error_ref": AgentErrorRef(
                        error_code="agent_tool_failed",
                        message_zh=f"确定性工具执行失败: {tool.name}",
                        category=AgentErrorCategory.TOOL_EXECUTION,
                        impact_zh="本轮 Agent 无法形成可靠结论, 已停止在错误报告.",
                        recoverable=True,
                        user_action_zh="检查工具输入和对应 artifact 后重试。",
                    ),
                    "metadata": {
                        **started.metadata,
                        "error_type": type(exc).__name__,
                    },
                }
            )
            self._write_event(failed, AgentEventType.TOOL_EXECUTION_FAILED)
            return failed

        completed = started.model_copy(
            update={
                "status": AgentTaskStatus.COMPLETED,
                "output_summary": redact_secret_like_values(result.output_summary),
                "artifact_paths": result.artifact_paths,
                "metadata": {**started.metadata, **result.metadata},
            }
        )
        self._write_event(completed, AgentEventType.TOOL_EXECUTION_COMPLETED)
        return completed

    def _write_event(self, record: AgentToolExecutionRecord, event_type: AgentEventType) -> None:
        if self.run_dir is None or self.run_id is None or self.task_id is None:
            return
        write_event(
            build_tool_execution_event(
                run_id=self.run_id,
                task_id=self.task_id,
                record=record,
                event_type=event_type,
            ),
            run_dir=self.run_dir,
        )


def default_tool_definitions() -> list[AgentToolDefinition]:
    """Return the deterministic Agent tool whitelist."""
    artifact_output = {
        "type": "object",
        "required": ["artifact_paths", "output_summary"],
    }
    return [
        AgentToolDefinition(
            name="agent_propose",
            purpose_zh="读取上一轮研究摘要并生成下一轮 Agent 研究计划。",
            input_schema={
                "type": "object",
                "required": ["summary_json_path", "output_base_path", "run_id", "goal_zh"],
            },
            output_schema=artifact_output,
        ),
        AgentToolDefinition(
            name="research_workbench",
            purpose_zh="包装研究工作台产物, 供 Agent 引用确定性研究结果。",
            input_schema={"type": "object", "required": ["artifact_paths"]},
            output_schema=artifact_output,
        ),
        AgentToolDefinition(
            name="watchlist_evidence",
            purpose_zh="包装观察名单专项证据产物, 供 Agent 读取分切片证据。",
            input_schema={"type": "object", "required": ["artifact_paths"]},
            output_schema=artifact_output,
        ),
        AgentToolDefinition(
            name="agent_conclude",
            purpose_zh="读取确定性证据 JSON 并生成 Agent 处置建议。",
            input_schema={
                "type": "object",
                "required": ["evidence_json_paths", "output_base_path", "run_id"],
            },
            output_schema=artifact_output,
        ),
    ]


def agent_propose_tool(payload: dict[str, Any]) -> AgentToolExecutionResult:
    """Tool adapter for `run_research_agent_planner`."""
    result = run_research_agent_planner(
        summary_json_path=_string_payload(payload, "summary_json_path"),
        output_base_path=_string_payload(payload, "output_base_path"),
        run_id=_string_payload(payload, "run_id"),
        goal_zh=_string_payload(payload, "goal_zh"),
    )
    return AgentToolExecutionResult(
        output_summary=result.summary(),
        artifact_paths=_artifact_refs(result.artifact_paths),
        metadata={"source_run_id": result.source_run_id},
    )


def agent_conclude_tool(payload: dict[str, Any]) -> AgentToolExecutionResult:
    """Tool adapter for `run_research_agent_decision`."""
    evidence_json_paths = cast("list[str | Path]", _string_list_payload(payload, "evidence_json_paths"))
    result = run_research_agent_decision(
        evidence_json_paths=evidence_json_paths,
        output_base_path=_string_payload(payload, "output_base_path"),
        run_id=_string_payload(payload, "run_id"),
    )
    return AgentToolExecutionResult(
        output_summary=result.summary(),
        artifact_paths=_artifact_refs(result.artifact_paths),
        metadata={"decisions": result.summary()["decisions"]},
    )


def existing_artifact_tool(payload: dict[str, Any]) -> AgentToolExecutionResult:
    """Wrap existing deterministic research artifacts without rerunning tools."""
    artifact_paths = payload.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        raise AgentToolError("artifact_paths must be an object.")
    output_summary = payload.get("output_summary")
    if not isinstance(output_summary, dict):
        output_summary = {"wrapped_artifacts": len(artifact_paths)}
    return AgentToolExecutionResult(
        output_summary=output_summary,
        artifact_paths=_artifact_refs({
            str(name): str(path)
            for name, path in artifact_paths.items()
        }),
    )


def build_tool_execution_event(
    *,
    run_id: str,
    task_id: str,
    record: AgentToolExecutionRecord,
    event_type: AgentEventType,
) -> AgentEvent:
    """Build an event timeline record for one deterministic tool execution."""
    level = AgentEventLevel.INFO
    message_zh = f"确定性工具执行中: {record.tool_name}"
    if event_type == AgentEventType.TOOL_EXECUTION_COMPLETED:
        level = AgentEventLevel.DECISION
        message_zh = f"确定性工具执行完成: {record.tool_name}"
    elif event_type == AgentEventType.TOOL_EXECUTION_FAILED:
        level = AgentEventLevel.ERROR
        message_zh = f"确定性工具执行失败: {record.tool_name}"
    return AgentEvent(
        run_id=AgentRunId(run_id),
        task_id=AgentTaskId(task_id),
        event_id=AgentEventId(f"event-{uuid4().hex}"),
        event_type=event_type,
        level=level,
        status=record.status,
        message_zh=message_zh,
        artifact_paths=record.artifact_paths,
        error_ref=record.error_ref,
        metadata={
            "invocation_id": record.invocation_id,
            "tool_name": record.tool_name,
            "input_summary": record.input_summary,
            "output_summary": record.output_summary,
        },
    )


def _artifact_refs(artifact_paths: dict[str, str]) -> list[AgentArtifactRef]:
    return [
        AgentArtifactRef(
            name=name,
            path=path,
            artifact_type=_artifact_type(path),
        )
        for name, path in artifact_paths.items()
    ]


def _artifact_type(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or "artifact"


def _string_payload(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AgentToolError(f"{key} must be a non-empty string.")
    return value


def _string_list_payload(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise AgentToolError(f"{key} must be a non-empty string list.")
    result = [item for item in value if isinstance(item, str) and item]
    if len(result) != len(value):
        raise AgentToolError(f"{key} must be a non-empty string list.")
    return result
