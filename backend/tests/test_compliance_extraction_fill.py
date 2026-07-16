"""Tests for compliance PDF text extraction + regex field fallback."""
from __future__ import annotations

from app.compliance.services.extraction_routing_service import (
    _stamp_extraction_fields,
    route_or_apply,
)
from app.compliance.services.notice_regex_fallback import extract_notice_fields_regex
from app.ml.classifier import extract_text_from_bytes


def test_extract_text_from_bytes_txt():
    text = extract_text_from_bytes(b"Show Cause Notice DRC-01/2026/1 GSTIN 27AABCT1234F1ZX", "txt")
    assert "DRC-01" in text
    assert "27AABCT1234F1ZX" in text


def test_regex_fallback_finds_gstin_and_drc():
    body = (
        "SHOW CAUSE NOTICE under GST. DRC-01/2026/4456 issued. "
        "GSTIN: 27AABCT1234F1ZX. Tax demand Rs. 1,25,000. Penalty Rs. 10,000."
    )
    env = extract_notice_fields_regex(body)
    fields = env["fields"]
    assert fields["gstin"]["value"] == "27AABCT1234F1ZX"
    assert "DRC" in str(fields["notice_number"]["value"]).upper()
    assert fields["authority"]["value"] == "GST"
    assert float(fields["tax_demand"]["value"]) == 125000.0
    assert env["model"] == "regex_fallback"


def test_review_queue_decision_still_fills_columns():
    """Low-confidence decision must still populate empty notice columns."""

    class _N:
        notice_number = None
        authority = None
        tax_demand = None
        penalty = None
        interest = None
        extraction_status = None
        extracted_fields = None
        extraction_confidence = None
        extracted_by_provider = None
        extracted_at = None

    notice = _N()
    envelope = extract_notice_fields_regex(
        "DRC-01/2026/99 GSTIN 29AAAAA0000A1Z5 tax demand Rs. 5000"
    )
    # Force low-confidence review path
    envelope["average_confidence"] = 0.2
    for f in envelope["fields"].values():
        f["confidence"] = 0.2
    decision = route_or_apply(envelope)
    assert decision["action"] == "review_queue"
    _stamp_extraction_fields(notice, envelope, decision, fill_columns=True)
    assert notice.extraction_status == "completed"
    assert notice.notice_number is not None or notice.tax_demand is not None
