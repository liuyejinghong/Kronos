"""Pytest config for the web integration tests (P19 local security boundary).

P19 enforces a per-process local session token plus Origin/Host checks on
every write route (``kronos.web.app.LocalSecurityMiddleware``). The landed
P14 / legacy web integration tests predate the token and are outside P19's
file ownership, so this conftest switches the middleware off for this
directory only, via the documented ``KRONOS_WEB_LOCAL_SECURITY`` env var.

``tests/integration/web/test_security.py`` re-enables enforcement per test
with ``monkeypatch.setenv`` and verifies the middleware itself. Production
(default, no env var) is always enforced.

P14b: the real pipeline worker attached by ``create_app`` is also disabled
for this directory via its documented switch — these tests submit tasks and
then claim/commit them manually (or assert queued states), which would race
with an in-process poll loop. ``tests/integration/test_real_pipeline.py``
covers the attach path with the switch on.
"""

import os

os.environ.setdefault("KRONOS_WEB_LOCAL_SECURITY", "off")
os.environ.setdefault("KRONOS_PIPELINE_WORKER", "off")
