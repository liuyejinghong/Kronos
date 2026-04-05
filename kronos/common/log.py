"""Kronos structured logging configuration."""

from __future__ import annotations

import logging
from typing import Any

import structlog


def setup_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog for Kronos.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, output JSON lines. If False, output human-readable.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a named logger instance.

    Returns a structlog BoundLogger, typed as Any to avoid
    mypy issues with structlog's dynamic typing.
    """
    return structlog.get_logger(name)
