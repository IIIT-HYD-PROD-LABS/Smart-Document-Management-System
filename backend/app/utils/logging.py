"""Structured logging configuration using structlog."""

import logging
import re
import sys

import structlog

from app.config import settings

# Keys whose values must never appear in logs
_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "token", "access_token", "refresh_token",
    "api_key", "apikey", "authorization", "cookie", "session_id",
    "credit_card", "ssn", "private_key",
})

# Pattern to detect email addresses in string values
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def sanitize_sensitive_data(_, __, event_dict: dict) -> dict:
    """Scrub PII and secrets from structured log fields (defense-in-depth).

    - Redacts values of known-sensitive keys entirely.
    - Masks email addresses found in string values of any key.
    """
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], str) and _EMAIL_RE.search(event_dict[key]):
            event_dict[key] = _EMAIL_RE.sub("***@***.***", event_dict[key])
    return event_dict


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
        sanitize_sensitive_data,
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
