"""Find and summarize the latest product-facing Kronos report."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
                    )
                )

    if not candidates:
        return None
    return max(candidates, key=lambda report: (report.modified_at, str(report.path)))


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
