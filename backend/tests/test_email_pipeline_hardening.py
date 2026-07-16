"""Unit tests for default filter-rule seed list + attachment filename fallback."""
from __future__ import annotations

from app.email.services.classifier import classify
from app.email.services.default_filter_rules import DEFAULT_FILTER_RULES
from app.email.tasks.scanner_task import _iter_attachments


def test_default_rules_cover_gst_and_bills():
    routes = {r["route_to"] for r in DEFAULT_FILTER_RULES}
    assert "compliance_notice" in routes
    assert "bill" in routes
    assert all(r["priority"] > 0 for r in DEFAULT_FILTER_RULES)
    assert all(r["sender_pattern"] for r in DEFAULT_FILTER_RULES)


def test_subject_keywords_include_scn_and_drc():
    ok, conf = classify("a@cbic-gst.gov.in", "SCN u/s 73 DRC-01 issued")
    assert ok is True
    assert conf == 1.0


def test_iter_attachments_recovers_pdf_without_filename():
    payload = {
        "parts": [
            {
                "mimeType": "application/pdf",
                "filename": "",
                "body": {"attachmentId": "ATT123"},
            },
            {
                "mimeType": "multipart/mixed",
                "parts": [
                    {
                        "mimeType": "image/png",
                        "filename": "",
                        "body": {"attachmentId": "IMG9"},
                    }
                ],
            },
        ]
    }
    got = list(_iter_attachments(payload))
    assert ("attachment.pdf", "ATT123") in got
    assert ("attachment.png", "IMG9") in got


def test_iter_attachments_keeps_named_files():
    payload = {
        "parts": [
            {
                "mimeType": "application/pdf",
                "filename": "GST-notice.pdf",
                "body": {"attachmentId": "A1"},
            }
        ]
    }
    assert list(_iter_attachments(payload)) == [("GST-notice.pdf", "A1")]
