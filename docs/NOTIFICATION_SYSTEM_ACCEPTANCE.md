# Notification System Acceptance Mapping

This document records the currently implemented scope of `p3-notification-system`.

## Current Scope

Primary implementation paths:
- `kronos/notify/formatter.py`
- `kronos/notify/notifier.py`
- `kronos/notify/__init__.py`

Primary verification paths:
- `tests/unit/notify/test_notifier.py`
- `tests/unit/risk/test_risk_notification.py`

## Requirement Mapping

### Notifier Protocol Implementation

- Implemented through:
  - `MemoryNotifier`
  - `TelegramNotifier`

Both expose the shared `send(level, title, body, data)` interface.

### Telegram First Channel

- Implemented through `TelegramNotifier`, with injectable sender logic for tests.

### Severity Levels

- Implemented through the shared `Level` enum and notification payload usage.

### Structured Event Payloads

- Implemented through `format_event(...)`, preserving structured `data`.

### Risk / Runtime Event Integration

- Implemented for the risk-engine path through `emit_risk_notification(...)`.

## Known Limitations

- The current implementation provides the first Telegram channel and in-memory
  notifier, but does not yet include webhook or email channels.

- Notification routing is still simple and local; there is no broader event bus
  or retry orchestration layer.
