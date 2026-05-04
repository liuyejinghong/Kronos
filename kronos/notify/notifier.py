"""Notifier implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

    from kronos.common.types import Level


@dataclass
class MemoryNotifier:
    """In-memory notifier for tests and local development."""

    sent: list[dict[str, Any]] = field(default_factory=list)

    def send(self, level: Level, title: str, body: str, data: dict[str, Any] | None = None) -> None:
        self.sent.append({
            "level": str(level),
            "title": title,
            "body": body,
            "data": data or {},
        })


@dataclass
class TelegramNotifier:
    """Telegram Bot notifier implementing the shared notifier protocol."""

    bot_token: str
    chat_id: str
    sender: Callable[..., httpx.Response] = httpx.post
    timeout: float = 10.0

    def send(self, level: Level, title: str, body: str, data: dict[str, Any] | None = None) -> None:
        payload = _telegram_payload(level, title, body, data or {})
        response = self.sender(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": payload,
                "parse_mode": "Markdown",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()


def _telegram_payload(level: Level, title: str, body: str, data: dict[str, Any]) -> str:
    lines = [f"*{str(level).upper()}* {title}", body]
    if data:
        lines.append("")
        for key, value in data.items():
            lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines)
