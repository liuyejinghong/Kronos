"""Unit tests for notification system."""

from __future__ import annotations

from typing import Any

from kronos.common.types import Level
from kronos.notify import MemoryNotifier, TelegramNotifier, format_event


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


class _FakeSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, *, json: dict[str, Any], timeout: float) -> _FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse()


class TestNotifier:
    def test_memory_notifier_stores_events(self) -> None:
        notifier = MemoryNotifier()
        notifier.send(Level.INFO, "Run done", "body", {"run_id": "abc"})
        assert notifier.sent[0]["title"] == "Run done"

    def test_telegram_notifier_formats_message(self) -> None:
        sender = _FakeSender()
        notifier = TelegramNotifier(bot_token="token", chat_id="chat", sender=sender)
        notifier.send(Level.WARNING, "Risk", "Scaled", {"gross": 1.2})
        assert sender.calls[0]["url"].endswith("/sendMessage")
        assert "WARNING" in sender.calls[0]["json"]["text"]

    def test_format_event_keeps_structured_data(self) -> None:
        event = format_event(level=Level.CRITICAL, event_type="risk", title="halt", body="body", data={"x": 1})
        assert event["event_type"] == "risk"
        assert event["data"] == {"x": 1}
