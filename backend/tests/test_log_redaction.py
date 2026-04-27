"""INFRA-06: structlog redaction filter strips PII fields."""

import pytest


def test_pii_stripped():
    from app.compliance.utils.log_redaction import redact_pii
    record = {
        "event": "notice_created",
        "gstin": "27AAAAA0000A1Z5",
        "pan": "AAAAA0000A",
        "penalty": 50000,
        "tax_demand": 100000,
        "interest": 5000,
        "total_liability": 155000,
        "client_id": 42,
    }
    out = redact_pii(None, None, record)
    assert out["gstin"] == "[REDACTED]"
    assert out["pan"] == "[REDACTED]"
    assert out["penalty"] == "[REDACTED]"
    assert out["tax_demand"] == "[REDACTED]"
    assert out["interest"] == "[REDACTED]"
    assert out["total_liability"] == "[REDACTED]"
    assert out["client_id"] == 42  # NOT redacted
    assert out["event"] == "notice_created"  # NOT redacted
