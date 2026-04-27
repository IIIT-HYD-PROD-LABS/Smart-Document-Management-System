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
from typing import Any

PII_FIELDS = frozenset({
    "gstin", "pan", "cin", "din",
    "penalty", "tax_demand", "interest", "total_liability",
    "registration_value",
})


def redact_pii(_logger: Any, _method_name: Any, event_dict: dict) -> dict:
    """structlog processor: replaces PII field values with [REDACTED].

    Signature matches structlog's processor protocol:
    https://www.structlog.org/en/stable/processors.html
    """
    return {
        k: ("[REDACTED]" if k in PII_FIELDS else v)
        for k, v in event_dict.items()
    }
