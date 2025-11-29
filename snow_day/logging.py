from __future__ import annotations

import logging as py_logging
from typing import Optional

import structlog

from snow_day.config import LoggingConfig, app_config

_configured = False


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    global _configured
    if _configured:
        return

    config = config or app_config.logging
    level = getattr(py_logging, str(config.level).upper(), py_logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if config.json else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    py_logging.basicConfig(level=level)
    _configured = True


def get_logger(name: str = __name__):
    if not _configured:
        setup_logging()
    return structlog.get_logger(name)
