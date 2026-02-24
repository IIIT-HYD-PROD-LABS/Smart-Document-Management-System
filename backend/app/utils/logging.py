"""Structured logging configuration using structlog."""

import logging
import sys

import structlog

from app.config import settings


def drop_color_message_key(_, __, event_dict: dict) -> dict:
    """Remove uvicorn's color_message key from log events."""
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging() -> None:
    """
    Configure structlog with JSON (production) or console (development) rendering.

    Call this BEFORE creating the FastAPI application so that all
    loggers --- including uvicorn's --- are captured by structlog.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        drop_color_message_key,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_JSON_FORMAT:
        # Production: JSON lines to stderr
        renderer_processors: list[structlog.types.Processor] = [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: coloured, human-readable output
        renderer_processors = [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *renderer_processors,
        ],
    )

    # Root logger: clear existing handlers, add our own
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
