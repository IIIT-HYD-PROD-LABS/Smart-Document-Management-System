"""Phase 15 — EMAIL-06 compliance auto-routing tests.

RED-state stub. Plan 03 lands `app.email.services.classifier.classify`,
the rule-based detector covering D-16 (revised) sender-domain regex
and subject keyword match.

Reconciliation #4: RBI uses `rbi.org.in` (NOT `.gov.in`) — sender regex
must include both gov.in and rbi.org.in domains explicitly.
"""
from __future__ import annotations

import pytest


def test_classify_returns_true_for_cbic_gst_sender_with_notice_subject():
    """Sender notice@cbic-gst.gov.in + subject 'Show Cause' returns (True, 1.0) (EMAIL-06)."""
    try:
        from app.email.services.classifier import classify  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — classifier not yet implemented")
    pytest.skip("Plan 03 — gov.in classifier assertion lands then")


def test_classify_returns_true_for_rbi_org_in_sender():
    """Sender regulatory@rbi.org.in + subject 'Show Cause' returns (True, 1.0) (reconciliation #4 — RBI uses .org.in)."""
    try:
        from app.email.services.classifier import classify  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — classifier not yet implemented")
    pytest.skip("Plan 03 — rbi.org.in classifier assertion lands then")


def test_classify_returns_uncertain_for_gov_in_sender_no_keyword():
    """gov.in sender + benign subject returns (False, 0.5) → review queue (EMAIL-06 + CLASS-04)."""
    try:
        from app.email.services.classifier import classify  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — classifier not yet implemented")
    pytest.skip("Plan 03 — review queue routing assertion lands then")


def test_classify_returns_false_for_forwarded_advocate_email():
    """gmail.com sender + notice keyword returns (False, 0.0) → dms_only (D-33 forwarded notice)."""
    try:
        from app.email.services.classifier import classify  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — classifier not yet implemented")
    pytest.skip("Plan 03 — D-33 forwarded-notice routing lands then")
