"""Local secret storage abstraction for Agent provider credentials."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SECRET_STORE_DIRNAME = ".kronos-secrets"
SECRET_STORE_FILENAME = "agent_secrets.json"
SECRET_STORE_PATH_ENV = "KRONOS_SECRET_STORE_PATH"
DEFAULT_SECRET_STORE_PATH = Path(SECRET_STORE_DIRNAME) / SECRET_STORE_FILENAME


def resolve_secret_store_path(explicit: str | Path | None = None) -> Path:
    """Single authority for the secret store location.

    Precedence: explicit argument > KRONOS_SECRET_STORE_PATH > the Kronos
    project root (nearest ancestor with pyproject.toml + kronos/) > CWD.
    Every caller (CLI, Web, uninstall) must route through this function so
    they all agree on where credentials live.
    """
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get(SECRET_STORE_PATH_ENV)
    if env:
        return Path(env)
    project_root = _find_project_root()
    if project_root is not None:
        return project_root / SECRET_STORE_DIRNAME / SECRET_STORE_FILENAME
    return Path(DEFAULT_SECRET_STORE_PATH)


def _find_project_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "kronos").is_dir():
            return candidate
    return None


class SecretStoreError(ValueError):
    """Raised when a secret operation is invalid."""


class SecretMaskedStatus(BaseModel):
    """Masked provider secret status safe for logs, reports, and Web settings."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    configured: bool
    masked_value: str | None = None
    masked_secret: str | None = None
    storage_backend: str = "local_file"
    storage_path: str


class LocalSecretStore:
    """Small local file-backed secret store.

    The raw secret is intentionally retrievable only through `get_secret`.
    Status methods return masked values for user-facing surfaces.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = resolve_secret_store_path(path)

    def set_secret(
        self,
        *,
        provider: str,
        api_key: str,
        api_secret: str | None = None,
    ) -> SecretMaskedStatus:
        """Store or replace one provider API key."""
        if not provider.strip():
            raise SecretStoreError("provider is required.")
        if not api_key.strip():
            raise SecretStoreError("api_key is required.")
        if api_secret is not None and not api_secret.strip():
            raise SecretStoreError("api_secret is required.")
        payload = self._read_payload()
        item = {"api_key": api_key}
        if api_secret is not None:
            item["api_secret"] = api_secret
        payload[_normalize_provider(provider)] = item
        self._write_payload(payload)
        return self.get_status(provider)

    def delete_secret(self, provider: str) -> SecretMaskedStatus:
        """Delete one provider API key if present."""
        payload = self._read_payload()
        payload.pop(_normalize_provider(provider), None)
        self._write_payload(payload)
        return self.get_status(provider)

    def get_secret(self, provider: str) -> str | None:
        """Return the raw provider API key for backend-only model calls."""
        item = self._read_payload().get(_normalize_provider(provider), {})
        api_key = item.get("api_key")
        return api_key if isinstance(api_key, str) and api_key else None

    def get_secret_pair(self, provider: str) -> tuple[str, str] | None:
        """Return the raw API key and secret for backend-only exchange calls."""
        item = self._read_payload().get(_normalize_provider(provider), {})
        api_key = item.get("api_key")
        api_secret = item.get("api_secret")
        if not isinstance(api_key, str) or not api_key:
            return None
        if not isinstance(api_secret, str) or not api_secret:
            return None
        return api_key, api_secret

    def get_status(self, provider: str) -> SecretMaskedStatus:
        """Return a masked provider credential status."""
        secret = self.get_secret(provider)
        pair = self.get_secret_pair(provider)
        return SecretMaskedStatus(
            provider=_normalize_provider(provider),
            configured=secret is not None,
            masked_value=mask_secret(secret) if secret is not None else None,
            masked_secret=mask_secret(pair[1]) if pair is not None else None,
            storage_path=str(self.path),
        )

    def _read_payload(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SecretStoreError("Secret store payload must be a JSON object.")
        payload: dict[str, dict[str, str]] = {}
        for provider, item in raw.items():
            if isinstance(provider, str) and isinstance(item, dict):
                api_key = item.get("api_key")
                api_secret = item.get("api_secret")
                if isinstance(api_key, str):
                    payload[provider] = {"api_key": api_key}
                    if isinstance(api_secret, str):
                        payload[provider]["api_secret"] = api_secret
        return payload

    def _write_payload(self, payload: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)
        with suppress(OSError):
            self.path.chmod(0o600)


def mask_secret(secret: str) -> str:
    """Mask a secret while preserving a short suffix for operator recognition."""
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - 4)}{secret[-4:]}"


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("_", "-")
    if not normalized:
        raise SecretStoreError("provider is required.")
    return normalized
