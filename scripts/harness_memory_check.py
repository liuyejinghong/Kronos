"""Validate the repository-local Agent Harness file set."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "MEMORY.md",
    "DECISIONS.md",
    "docs/agent-harness/PROGRESS_LOG.md",
    "docs/agent-harness/USAGE_GUIDE.md",
    "docs/agent-harness/SETUP_REPORT_20260509.md",
    ".cursor/rules/00-kronos-agent-harness.mdc",
    ".cursor/rules/10-kronos-memory-protocol.mdc",
    ".cursor/rules/20-kronos-product-context.mdc",
]

REQUIRED_MARKERS = {
    "AGENTS.md": ["Persistent Agent Harness", "MEMORY.md", "DECISIONS.md"],
    "CLAUDE.md": ["Persistent Agent Harness", "MEMORY.md", "DECISIONS.md"],
    "MEMORY.md": ["Boot Protocol", "Memory Write Triggers", "Verification Loop"],
    "DECISIONS.md": ["D-20260509-001", "D-20260509-005"],
}


def main() -> int:
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        if not path.is_file():
            failures.append(f"missing required file: {relative_path}")

    for relative_path, markers in REQUIRED_MARKERS.items():
        path = ROOT / relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in content:
                failures.append(f"{relative_path} missing marker: {marker}")

    if failures:
        print("Agent Harness check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Agent Harness check passed.")
    print(f"Validated {len(REQUIRED_FILES)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
