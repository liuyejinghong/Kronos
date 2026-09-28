"""Pytest config for the web integration tests (P19 local security boundary).

P19 enforces a per-process local session token plus Origin/Host checks on
every write route (``kronos.web.app.LocalSecurityMiddleware``). The landed
P14 / legacy web integration tests predate the token and are outside P19's
file ownership, so this conftest switches the middleware off for this
directory only, via the documented ``KRONOS_WEB_LOCAL_SECURITY`` env var.

``tests/integration/web/test_security.py`` re-enables enforcement per test
with ``monkeypatch.setenv`` and verifies the middleware itself. Production
(default, no env var) is always enforced.
"""

import os

os.environ.setdefault("KRONOS_WEB_LOCAL_SECURITY", "off")
