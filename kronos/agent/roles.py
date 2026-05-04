"""Agent role registry for the local Agent runtime."""

from __future__ import annotations

from kronos.agent.types import AgentPromptVersionId, AgentRole, AgentRoleId, AgentRoleKind

DEFAULT_MODEL_PROVIDER = "deepseek"
DEFAULT_MODEL_NAME = "deepseek-v4-pro"
DEEPSEEK_V4_PRO = "deepseek-v4-pro"
DEEPSEEK_V4_FLASH = "deepseek-v4-flash"

DEEPSEEK_MODELS = [
    {"id": DEEPSEEK_V4_PRO, "label_zh": "DeepSeek-V4-Pro", "label_en": "DeepSeek-V4-Pro"},
    {"id": DEEPSEEK_V4_FLASH, "label_zh": "DeepSeek-V4-Flash", "label_en": "DeepSeek-V4-Flash"},
]


class AgentRoleRegistryError(KeyError):
    """Raised when a role registry operation cannot be completed."""


def default_agent_roles() -> list[AgentRole]:
    """Return the default multi-role Agent committee.

    Heavy reasoning roles use DeepSeek-V4-Pro; lighter/faster roles use DeepSeek-V4-Flash.
    """
    return [
        AgentRole(
            role_id=AgentRoleId("researcher"),
            role_kind=AgentRoleKind.RESEARCHER,
            name_zh="研究员",
            prompt_version=AgentPromptVersionId("researcher-prompt-v1"),
            model_provider=DEFAULT_MODEL_PROVIDER,
            model_name=DEEPSEEK_V4_PRO,
        ),
        AgentRole(
            role_id=AgentRoleId("opposition_reviewer"),
            role_kind=AgentRoleKind.OPPOSITION_REVIEWER,
            name_zh="反方审查",
            prompt_version=AgentPromptVersionId("opposition-reviewer-prompt-v1"),
            model_provider=DEFAULT_MODEL_PROVIDER,
            model_name=DEEPSEEK_V4_PRO,
        ),
        AgentRole(
            role_id=AgentRoleId("risk_reviewer"),
            role_kind=AgentRoleKind.RISK_REVIEWER,
            name_zh="风控审查",
            prompt_version=AgentPromptVersionId("risk-reviewer-prompt-v1"),
            model_provider=DEFAULT_MODEL_PROVIDER,
            model_name=DEEPSEEK_V4_FLASH,
        ),
        AgentRole(
            role_id=AgentRoleId("decision_reviewer"),
            role_kind=AgentRoleKind.DECISION_REVIEWER,
            name_zh="投委会裁决",
            prompt_version=AgentPromptVersionId("decision-reviewer-prompt-v1"),
            model_provider=DEFAULT_MODEL_PROVIDER,
            model_name=DEEPSEEK_V4_PRO,
        ),
        AgentRole(
            role_id=AgentRoleId("execution_record_analyst"),
            role_kind=AgentRoleKind.TOOL_OPERATOR,
            name_zh="执行记录分析",
            prompt_version=AgentPromptVersionId("execution-record-analyst-prompt-v1"),
            model_provider=DEFAULT_MODEL_PROVIDER,
            model_name=DEEPSEEK_V4_FLASH,
        ),
    ]


class AgentRoleRegistry:
    """In-memory registry for configured Agent roles."""

    def __init__(self, roles: list[AgentRole] | None = None) -> None:
        role_list = roles if roles is not None else default_agent_roles()
        self._roles: dict[str, AgentRole] = {
            str(role.role_id): role.model_copy(deep=True)
            for role in role_list
        }

    def list_roles(self) -> list[AgentRole]:
        """Return all roles as defensive copies."""
        return [role.model_copy(deep=True) for role in self._roles.values()]

    def get_role(self, role_id: str) -> AgentRole:
        """Return one configured Agent role."""
        try:
            return self._roles[role_id].model_copy(deep=True)
        except KeyError as exc:
            raise AgentRoleRegistryError(f"Unknown Agent role: {role_id}") from exc

    def enable_role(self, role_id: str) -> AgentRole:
        """Enable one Agent role."""
        return self._set_enabled(role_id, enabled=True)

    def disable_role(self, role_id: str) -> AgentRole:
        """Disable one Agent role."""
        return self._set_enabled(role_id, enabled=False)

    def _set_enabled(self, role_id: str, *, enabled: bool) -> AgentRole:
        role = self.get_role(role_id)
        updated = role.model_copy(update={"enabled": enabled})
        self._roles[role_id] = updated
        return updated.model_copy(deep=True)
