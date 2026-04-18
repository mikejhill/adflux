"""Structured logging configuration for adflux.

We use :mod:`structlog` so the library can emit either human-readable or JSON
logs depending on the caller's preference. The library itself does not call
``configure`` on import — that's the application's job — but we expose a
convenience helper for the CLI and tests.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(*, json_output: bool = False, level: int = logging.INFO) -> None:
    """Configure structlog for either console or JSON output.

    Args:
        json_output: If True, emit JSON lines; otherwise, pretty console output.
        level: Standard-library logging level.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for ``name``."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
