"""Local secret storage abstraction for Agent provider credentials."""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SECRET_STORE_DIRNAME = ".kronos-secrets"
SECRET_STORE_FILENAME = "agent_secrets.json"
DEFAULT_SECRET_STORE_PATH = Path(SECRET_STORE_DIRNAME) / SECRET_STORE_FILENAME


class SecretStoreError(ValueError):
    """Raised when a secret operation is invalid."""


class SecretMaskedStatus(BaseModel):
    """Masked provider secret status safe for logs, reports, and Web settings."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    configured: bool
    masked_value: str | None = None
    storage_backend: str = "local_file"
    storage_path: str


class LocalSecretStore:
    """Small local file-backed secret store.

    The raw secret is intentionally retrievable only through `get_secret`.
    Status methods return masked values for user-facing surfaces.
    """

    def __init__(self, path: str | Path = DEFAULT_SECRET_STORE_PATH) -> None:
        self.path = Path(path)

    def set_secret(self, *, provider: str, api_key: str) -> SecretMaskedStatus:
        """Store or replace one provider API key."""
        if not provider.strip():
            raise SecretStoreError("provider is required.")
        if not api_key.strip():
            raise SecretStoreError("api_key is required.")
        payload = self._read_payload()
        payload[_normalize_provider(provider)] = {"api_key": api_key}
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

    def get_status(self, provider: str) -> SecretMaskedStatus:
        """Return a masked provider credential status."""
        secret = self.get_secret(provider)
        return SecretMaskedStatus(
            provider=_normalize_provider(provider),
            configured=secret is not None,
            masked_value=mask_secret(secret) if secret is not None else None,
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
                if isinstance(api_key, str):
                    payload[provider] = {"api_key": api_key}
        return payload

    def _write_payload(self, payload: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
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
