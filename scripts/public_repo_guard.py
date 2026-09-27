"""Guard against committing internal Kronos planning and acceptance artifacts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath

BLOCKED_EXACT = {
    "MEMORY.md",
    "DECISIONS.md",
    "scripts/harness_memory_check.py",
}
BLOCKED_PREFIXES = (
    ".cursor/",
    "openspec/",
    "docs/agent-harness/",
    "docs/reviews/",
)
BLOCKED_DOC_PATTERNS = (
    "ACCEPTANCE",
    "ATTEMPT",
    "DOCKER_",
    "E2E",
    "EXTERNAL_",
    "FRESH_",
    "KRONOS_V",
    "NOVICE_",
    "PERSONA_ACCEPTANCE",
    "PRODUCT_DESIGN_REVIEW",
    "RELEASE_",
    "TESTNET_",
    "UX_EVALUATION",
    "UX_REVIEW",
    "V03_",
)
# Owner-approved public exceptions: version planning docs that are
# deliberately published for external review.
ALLOWED_EXACT = {
    "docs/RELEASE_0.5.0_STRATEGY_VERDICT_LOOP.md",
}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "failed to list git files\n")
        raise SystemExit(result.returncode)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_blocked(path: str) -> bool:
    if path in ALLOWED_EXACT:
        return False
    if path in BLOCKED_EXACT:
        return True
    if path.startswith(BLOCKED_PREFIXES):
        return True
    posix = PurePosixPath(path)
    if posix.parts and posix.parts[0] == "docs":
        name = posix.name
        return any(pattern in name for pattern in BLOCKED_DOC_PATTERNS)
    return False


def main() -> int:
    blocked = sorted(path for path in _tracked_files() if _is_blocked(path))
    if not blocked:
        print("Public repo guard passed.")
        return 0

    print("Public repo guard failed. Internal files are still tracked:")
    for path in blocked:
        print(f"  - {path}")
    print("\nMove these to local-only storage or remove them from Git tracking.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
