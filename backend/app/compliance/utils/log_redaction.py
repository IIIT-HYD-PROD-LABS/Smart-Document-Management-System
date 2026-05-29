"""structlog redaction processor — Phase 9 INFRA-06.

Strips PII fields from log records before serialization. Add to the structlog
processor chain BEFORE the JSON renderer.

Example:
    import structlog
    from app.compliance.utils.log_redaction import redact_pii

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            redact_pii,
            structlog.processors.JSONRenderer(),
        ]
    )
"""
from collections.abc import Callable
from typing import Any

PII_FIELDS = frozenset({
    "gstin", "pan", "cin", "din",
    "penalty", "tax_demand", "interest", "total_liability",
    "registration_value",
})

# Bound on recursion into nested structures; also breaks reference cycles.
_MAX_REDACT_DEPTH = 12


def _redact_value(
    value: Any,
    sensitive_keys: frozenset = PII_FIELDS,
    marker: str = "[REDACTED]",
    case_insensitive: bool = False,
    leaf_transform: Callable[[Any], Any] | None = None,
    _depth: int = 0,
) -> Any:
    """Recurse so secrets/PII nested inside dicts/lists are redacted too — a
    flat, top-level-only sweep would leak `details={"pan": ...}`-style payloads.

    Keys matching ``sensitive_keys`` (optionally case-insensitively) have their
    value replaced by ``marker``; ``leaf_transform`` is applied to any remaining
    scalar value. ``_depth`` bounds recursion so reference cycles can't loop
    forever.
    """
    if _depth >= _MAX_REDACT_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            k: (
                marker
                if (k.lower() if case_insensitive else k) in sensitive_keys
                else _redact_value(
                    v, sensitive_keys, marker, case_insensitive,
                    leaf_transform, _depth + 1,
                )
            )
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _redact_value(
                v, sensitive_keys, marker, case_insensitive,
                leaf_transform, _depth + 1,
            )
            for v in value
        ]
    return leaf_transform(value) if leaf_transform is not None else value


def redact_pii(_logger: Any, _method_name: Any, event_dict: dict) -> dict:
    """structlog processor: replaces PII field values with [REDACTED].

    Signature matches structlog's processor protocol:
    https://www.structlog.org/en/stable/processors.html
    """
    return _redact_value(event_dict)
