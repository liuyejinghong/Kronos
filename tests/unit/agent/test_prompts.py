"""Tests for Agent prompt version store."""

from __future__ import annotations

import pytest

from kronos.agent.prompts import PromptStoreError, PromptVersionStatus, PromptVersionStore


def test_prompt_update_creates_new_version_without_overwriting_history() -> None:
    store = PromptVersionStore()

    first = store.create_draft(
        role_id="researcher",
        title_zh="研究员 Prompt",
        content="第一版 prompt",
    )
    second = store.update_prompt(
        role_id="researcher",
        title_zh="研究员 Prompt",
        content="第二版 prompt",
    )
    history = store.list_prompt_versions("researcher")

    assert first.prompt_version == "researcher-prompt-v1"
    assert second.prompt_version == "researcher-prompt-v2"
    assert first.prompt_hash != second.prompt_hash
    assert [record.content for record in history] == ["第一版 prompt", "第二版 prompt"]
    assert [record.status for record in history] == [
        PromptVersionStatus.DRAFT,
        PromptVersionStatus.DRAFT,
    ]


def test_prompt_activation_requires_confirmation() -> None:
    store = PromptVersionStore()
    draft = store.create_draft(
        role_id="researcher",
        title_zh="研究员 Prompt",
        content="第一版 prompt",
    )

    with pytest.raises(PromptStoreError):
        store.activate_prompt(
            role_id="researcher",
            prompt_version=draft.prompt_version,
            confirmed=False,
        )

    assert store.get_active_prompt("researcher") is None


def test_prompt_activation_sets_one_active_version_per_role() -> None:
    store = PromptVersionStore()
    first = store.create_draft(
        role_id="researcher",
        title_zh="研究员 Prompt",
        content="第一版 prompt",
    )
    second = store.update_prompt(
        role_id="researcher",
        title_zh="研究员 Prompt",
        content="第二版 prompt",
    )

    store.activate_prompt(
        role_id="researcher",
        prompt_version=first.prompt_version,
        confirmed=True,
    )
    active = store.activate_prompt(
        role_id="researcher",
        prompt_version=second.prompt_version,
        confirmed=True,
    )
    history = store.list_prompt_versions("researcher")

    assert active.prompt_version == second.prompt_version
    assert active.activated_by_user is True
    assert store.get_active_prompt("researcher") == active
    assert [record.status for record in history] == [
        PromptVersionStatus.ARCHIVED,
        PromptVersionStatus.ACTIVE,
    ]


def test_prompt_history_returns_defensive_copies() -> None:
    store = PromptVersionStore()
    draft = store.create_draft(
        role_id="researcher",
        title_zh="研究员 Prompt",
        content="第一版 prompt",
    )

    mutated = draft.model_copy(update={"content": "mutated"})

    assert mutated.content == "mutated"
    assert store.list_prompt_versions("researcher")[0].content == "第一版 prompt"
