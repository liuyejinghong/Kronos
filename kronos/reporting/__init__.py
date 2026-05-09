"""User-facing report discovery helpers."""

from __future__ import annotations

from kronos.reporting.latest import (
    LatestReport,
    find_latest_report,
    summarize_report,
    summarize_report_section,
)
from kronos.reporting.observation_plan import ObservationPlan, generate_observation_plan

__all__ = [
    "LatestReport",
    "ObservationPlan",
    "find_latest_report",
    "generate_observation_plan",
    "summarize_report",
    "summarize_report_section",
]
