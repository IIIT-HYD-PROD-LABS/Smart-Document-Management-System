"""Phase 15 — EMAIL-06 compliance auto-routing tests."""
from __future__ import annotations

from app.email.services.classifier import classify


def test_classify_returns_true_for_cbic_gst_sender_with_notice_subject():
    ok, conf = classify("notice@cbic-gst.gov.in", "Show Cause")
    assert ok is True and conf == 1.0


def test_classify_returns_true_for_rbi_org_in_sender():
    ok, conf = classify("regulatory@rbi.org.in", "Show Cause")
    assert ok is True and conf == 1.0


def test_classify_returns_uncertain_for_gov_in_sender_no_keyword():
    ok, conf = classify("desk@mca.gov.in", "Weekly newsletter")
    assert ok is False and conf == 0.5


def test_classify_returns_false_for_forwarded_advocate_email():
    ok, conf = classify("lawyer@gmail.com", "Notice of demand")
    assert ok is False and conf == 0.0
