"""Classifier + resolve_route unit tests (EMAIL-04 / EMAIL-06)."""
from __future__ import annotations

from types import SimpleNamespace

from app.email.models.message_log import GmailMessageLog
from app.email.services.classifier import classify, resolve_route


def test_classify_full_match_cbic():
    ok, conf = classify("notice@cbic-gst.gov.in", "Show Cause Notice under GST")
    assert ok is True
    assert conf == 1.0


def test_classify_sender_only_is_uncertain():
    ok, conf = classify("helpdesk@incometax.gov.in", "Your filing is due")
    assert ok is False
    assert conf == 0.5


def test_classify_forwarded_advocate_is_ignored():
    ok, conf = classify("advocate@gmail.com", "Notice of demand attached")
    assert ok is False
    assert conf == 0.0


def test_classify_rbi_org_in():
    ok, conf = classify("regulatory@rbi.org.in", "Show Cause intimation")
    assert ok is True
    assert conf == 1.0


def test_resolve_route_filter_rule_wins():
    rules = [
        SimpleNamespace(
            enabled=True,
            sender_pattern=r"@vendor\.example\.com$",
            subject_pattern=r"invoice",
            route_to=GmailMessageLog.ROUTE_BILL,
            priority=10,
        )
    ]
    route = resolve_route(
        "billing@vendor.example.com",
        "Your invoice is ready",
        rules=rules,
    )
    assert route == GmailMessageLog.ROUTE_BILL


def test_resolve_route_lower_priority_wins():
    rules = [
        SimpleNamespace(
            enabled=True,
            sender_pattern=r"@gst\.gov\.in$",
            subject_pattern=None,
            route_to=GmailMessageLog.ROUTE_COMPLIANCE,
            priority=1,
        ),
        SimpleNamespace(
            enabled=True,
            sender_pattern=r"@gst\.gov\.in$",
            subject_pattern=None,
            route_to=GmailMessageLog.ROUTE_IGNORE,
            priority=50,
        ),
    ]
    route = resolve_route("a@gst.gov.in", "hello", rules=rules)
    assert route == GmailMessageLog.ROUTE_COMPLIANCE


def test_resolve_route_bill_heuristic():
    route = resolve_route(
        "noreply@airtel.com",
        "Your monthly bill amount due",
        body="INR 1,299 due on 12 May",
    )
    assert route == GmailMessageLog.ROUTE_BILL


def test_resolve_route_compliance_builtin():
    route = resolve_route(
        "notice@cbic-gst.gov.in",
        "Show Cause Notice",
        rules=[],
    )
    assert route == GmailMessageLog.ROUTE_COMPLIANCE
