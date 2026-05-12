"""Tests for local Agent SecretStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from kronos.agent.secrets import (
    SECRET_STORE_PATH_ENV,
    LocalSecretStore,
    SecretStoreError,
    mask_secret,
)


def test_local_secret_store_returns_masked_status_without_raw_secret(tmp_path: Path) -> None:
    store = LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json")
    raw_key = "sk-test-secret-123456"

    status = store.set_secret(provider="deepseek", api_key=raw_key)

    assert status.configured is True
    assert status.masked_value is not None
    assert raw_key not in status.model_dump_json()
    assert status.masked_value.endswith("3456")
    assert store.get_secret("deepseek") == raw_key


def test_local_secret_store_rejects_empty_secret(tmp_path: Path) -> None:
    store = LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json")

    with pytest.raises(SecretStoreError):
        store.set_secret(provider="deepseek", api_key="")


def test_local_secret_store_can_delete_secret(tmp_path: Path) -> None:
    store = LocalSecretStore(tmp_path / ".kronos-secrets" / "agent_secrets.json")
    store.set_secret(provider="deepseek", api_key="sk-test-secret-123456")

    status = store.delete_secret("deepseek")

    assert status.configured is False
    assert status.masked_value is None
    assert store.get_secret("deepseek") is None


def test_local_secret_store_uses_env_path_when_no_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "isolated" / "agent_secrets.json"
    monkeypatch.setenv(SECRET_STORE_PATH_ENV, str(env_path))

    store = LocalSecretStore()
    store.set_secret(provider="deepseek", api_key="sk-test-secret-123456")

    assert env_path.exists()
    assert store.path == env_path


def test_secret_mask_keeps_only_short_suffix() -> None:
    assert mask_secret("abcd") == "****"
    assert mask_secret("sk-123456") == "*****3456"


def test_local_secret_store_path_is_gitignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert ".kronos-secrets/" in gitignore
