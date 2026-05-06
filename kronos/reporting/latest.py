"""Find and summarize the latest product-facing Kronos report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPORT_FILENAMES = (
    "kronos_run_status.md",
    "agent_run_report.md",
    "auto_run_report.md",
    "research_workbench_report.md",
    "watchlist_evidence_report.md",
    "agent_research_decision.md",
    "agent_research_plan.md",
    "promotion_batch_report.md",
)

PRODUCT_SECTION_HEADINGS = (
    "## 第一屏结论",
    "## 一句话结论",
    "## 当前研究目标",
    "## 产品结论",
)


@dataclass(frozen=True)
class LatestReport:
    """A discovered report and the run directory it belongs to."""

    path: Path
    run_dir: Path
    modified_at: float
    sort_timestamp: float


def find_latest_report(base_path: str | Path = "reports/research") -> LatestReport | None:
    """Return the newest product-facing report under the research reports tree."""
    base = Path(base_path)
    experiments = base / "experiments"
    if not experiments.exists():
        return None

    candidates: list[LatestReport] = []
    for filename in REPORT_FILENAMES:
        for path in experiments.glob(f"*/{filename}"):
            if path.is_file():
                stat = path.stat()
                candidates.append(
                    LatestReport(
                        path=path,
                        run_dir=path.parent,
                        modified_at=stat.st_mtime,
                        sort_timestamp=_run_sort_timestamp(path.parent, stat.st_mtime),
                    )
                )

    if not candidates:
        return None
    return max(candidates, key=lambda report: (report.sort_timestamp, str(report.path)))


def summarize_report(path: str | Path, *, max_lines: int = 18) -> list[str]:
    """Extract a compact, user-readable summary from a Markdown report."""
    report_path = Path(path)
    lines = report_path.read_text(encoding="utf-8").splitlines()
    section = _first_matching_section(lines, PRODUCT_SECTION_HEADINGS)
    if section:
        return section[:max_lines]

    compact = [line for line in lines if line.strip()]
    return compact[:max_lines]


def _first_matching_section(lines: list[str], headings: tuple[str, ...]) -> list[str]:
    for idx, line in enumerate(lines):
        if line.strip() not in headings:
            continue
        section: list[str] = []
        for current in lines[idx + 1 :]:
            stripped = current.strip()
            if stripped.startswith("## ") and section:
                break
            if stripped:
                section.append(stripped)
        if section:
            return section
    return []


def _run_sort_timestamp(run_dir: Path, fallback: float) -> float:
    summary = _read_summary(run_dir / "agent_run_summary.json")
    if summary is None:
        summary = _read_summary(run_dir / "auto_run_summary.json")

    if summary is not None:
        timestamp = _summary_timestamp(summary)
        if timestamp is not None:
            return timestamp
        run_id = _summary_run_id(summary) or run_dir.name
    else:
        run_id = run_dir.name

    timestamp = _timestamp_from_run_id(run_id)
    return timestamp if timestamp is not None else fallback


def _read_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _summary_timestamp(summary: dict[str, Any]) -> float | None:
    for key in ("finished_at", "completed_at", "started_at"):
        value = summary.get(key)
        if isinstance(value, str):
            timestamp = _parse_iso_timestamp(value)
            if timestamp is not None:
                return timestamp
    run = summary.get("run")
    if isinstance(run, dict):
        for key in ("finished_at", "completed_at", "started_at"):
            value = run.get(key)
            if isinstance(value, str):
                timestamp = _parse_iso_timestamp(value)
                if timestamp is not None:
                    return timestamp
    return None


def _summary_run_id(summary: dict[str, Any]) -> str | None:
    run_id = summary.get("run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    run = summary.get("run")
    if isinstance(run, dict):
        nested = run.get("run_id")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _parse_iso_timestamp(value: str) -> float | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def _timestamp_from_run_id(run_id: str) -> float | None:
    for candidate in (run_id[:15], run_id[:8]):
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
            try:
                return datetime.strptime(candidate, fmt).timestamp()
            except ValueError:
                continue
    return None
