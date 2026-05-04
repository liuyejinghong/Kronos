"""Tests for Agent role registry."""

from __future__ import annotations

import pytest

from kronos.agent.roles import (
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_PRO,
    DEFAULT_MODEL_PROVIDER,
    AgentRoleRegistry,
    AgentRoleRegistryError,
    default_agent_roles,
)
from kronos.agent.types import AgentRoleKind


def test_default_roles_cover_initial_agent_committee() -> None:
    roles = default_agent_roles()
    role_ids = {role.role_id for role in roles}
    role_kinds = {role.role_kind for role in roles}

    assert role_ids == {
        "researcher",
        "opposition_reviewer",
        "risk_reviewer",
        "decision_reviewer",
        "execution_record_analyst",
    }
    assert {
        AgentRoleKind.RESEARCHER,
        AgentRoleKind.OPPOSITION_REVIEWER,
        AgentRoleKind.RISK_REVIEWER,
        AgentRoleKind.DECISION_REVIEWER,
        AgentRoleKind.TOOL_OPERATOR,
    } <= role_kinds
    assert {role.model_provider for role in roles} == {DEFAULT_MODEL_PROVIDER}
    assert {role.model_name for role in roles} == {DEEPSEEK_V4_PRO, DEEPSEEK_V4_FLASH}


def test_role_registry_can_disable_and_enable_role() -> None:
    registry = AgentRoleRegistry()

    disabled = registry.disable_role("risk_reviewer")
    enabled = registry.enable_role("risk_reviewer")

    assert disabled.enabled is False
    assert enabled.enabled is True
    assert registry.get_role("risk_reviewer").enabled is True


def test_role_registry_rejects_unknown_role() -> None:
    registry = AgentRoleRegistry()

    with pytest.raises(AgentRoleRegistryError):
        registry.get_role("missing_role")


def test_role_registry_returns_defensive_copies() -> None:
    registry = AgentRoleRegistry()
    role = registry.get_role("researcher")
    mutated = role.model_copy(update={"enabled": False})

    assert mutated.enabled is False
    assert registry.get_role("researcher").enabled is True
