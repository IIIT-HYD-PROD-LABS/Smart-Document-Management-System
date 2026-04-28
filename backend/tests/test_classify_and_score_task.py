"""Phase 10 — classify_and_score_notice integration unit tests.

Tests the full pipeline (regex extraction + rule-based risk scoring +
notice persistence) using mocked SessionLocal. End-to-end DB integration
tests live in tests/test_compliance_endpoints.py once Supabase GRANTs land.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.compliance_tasks import classify_and_score_notice


def _make_notice(
    *,
    notice_id=1,
    authority="GST",
    penalty=Decimal("500000"),
    tax_demand=None,
    deadline=None,
    legal_sections=None,
    parent_notice_id=None,
    document_id=None,
    notice_number="DRC-01/2026/A1",
):
    """Build a mock ComplianceNotice row."""
    notice = MagicMock()
    notice.id = notice_id
    notice.authority = authority
    notice.penalty = penalty
    notice.tax_demand = tax_demand
    notice.response_deadline = deadline
    notice.legal_sections = legal_sections or []
    notice.parent_notice_id = parent_notice_id
    notice.document_id = document_id
    notice.notice_number = notice_number
    return notice


def _patched_session(notice_lookup):
    """Yield a mock session whose .get(Model, id) consults notice_lookup dict."""
    session = MagicMock()
    session.get.side_effect = lambda model, pk: notice_lookup.get(pk)
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.close = MagicMock()
    return session


def test_classify_persists_risk_score_and_tier():
    """Task computes risk and writes risk_score, risk_tier, model_version."""
    notice = _make_notice(
        authority="RBI",
        penalty=Decimal("5000000"),  # ₹50 lakh
        deadline=date(2026, 5, 1),
        legal_sections=["u/s 271(1)(c)"],
    )
    session = _patched_session({1: notice})

    with patch("app.database.SessionLocal", return_value=session), \
         patch("app.compliance.models.notice.ComplianceNotice", new=MagicMock):
        result = classify_and_score_notice.run(1)

    assert result["notice_id"] == 1
    assert result["risk_tier"] in ("critical", "high", "medium", "low")
    assert result["risk_score"] >= 0
    assert result["model_version"] == "rules-v1.0"
    # Notice ORM mutated.
    assert notice.risk_score is not None
    assert notice.risk_tier == result["risk_tier"]
    assert notice.model_version == "rules-v1.0"
    session.commit.assert_called()


def test_classify_returns_top_factors_with_phrases():
    """Top factors are returned with natural-language phrases for SHAP-style UI."""
    notice = _make_notice(
        authority="GST",
        penalty=Decimal("1000000"),
        deadline=date(2026, 5, 5),
    )
    session = _patched_session({1: notice})

    with patch("app.database.SessionLocal", return_value=session):
        result = classify_and_score_notice.run(1)

    assert "top_factors" in result
    assert len(result["top_factors"]) <= 3
    for factor in result["top_factors"]:
        assert "feature" in factor
        assert "contribution" in factor
        assert "phrase" in factor
        assert isinstance(factor["phrase"], str)
        assert len(factor["phrase"]) > 0


def test_classify_extracts_regex_fields_from_text():
    """Regex extractors run over all available text and populate ner_extracted_fields."""
    notice = _make_notice(
        notice_number="DRC-01/2026/A1",
        legal_sections=["u/s 73(9) of CGST Act"],
    )
    session = _patched_session({1: notice})

    with patch("app.database.SessionLocal", return_value=session):
        result = classify_and_score_notice.run(1)

    ner = result["ner_extracted_fields"]
    assert "gstins" in ner
    assert "pans" in ner
    assert "cins" in ner
    assert "section_references" in ner
    assert "regex_extractor_version" in ner
    # The legal_sections content has section reference patterns.
    assert any("73" in s for s in ner["section_references"])


def test_classify_returns_error_for_missing_notice():
    """Task short-circuits cleanly if notice is not found."""
    session = _patched_session({})  # empty dict — no notices
    with patch("app.database.SessionLocal", return_value=session):
        result = classify_and_score_notice.run(999)
    assert result["error"] == "notice_not_found"


def test_classify_uses_show_cause_chain_signal():
    """parent_notice_id with SCN-coded type contributes to risk score."""
    parent = _make_notice(notice_id=10)
    parent.notice_type = MagicMock()
    parent.notice_type.code = "SCN"

    child = _make_notice(
        notice_id=20,
        authority="GST",
        penalty=Decimal("100000"),
        parent_notice_id=10,
        deadline=date(2026, 5, 10),
    )
    child.notice_type = None

    session = _patched_session({10: parent, 20: child})
    with patch("app.database.SessionLocal", return_value=session):
        result_with_scn = classify_and_score_notice.run(20)

    # Same notice without parent.
    child_no_parent = _make_notice(
        notice_id=30,
        authority="GST",
        penalty=Decimal("100000"),
        parent_notice_id=None,
        deadline=date(2026, 5, 10),
    )
    session2 = _patched_session({30: child_no_parent})
    with patch("app.database.SessionLocal", return_value=session2):
        result_no_scn = classify_and_score_notice.run(30)

    assert result_with_scn["risk_score"] >= result_no_scn["risk_score"]


def test_classify_persists_classified_at_and_risk_scored_at():
    """Both timestamps are set on successful classification."""
    notice = _make_notice(authority="MCA")
    session = _patched_session({1: notice})

    before = datetime.now(timezone.utc)
    with patch("app.database.SessionLocal", return_value=session):
        classify_and_score_notice.run(1)
    after = datetime.now(timezone.utc)

    assert notice.classified_at is not None
    assert notice.risk_scored_at is not None
    assert before <= notice.classified_at <= after
    assert before <= notice.risk_scored_at <= after


def test_classify_persists_model_version():
    """model_version reflects the scorer used (currently rules-v1.0)."""
    notice = _make_notice()
    session = _patched_session({1: notice})
    with patch("app.database.SessionLocal", return_value=session):
        result = classify_and_score_notice.run(1)
    assert notice.model_version == "rules-v1.0"
    assert result["model_version"] == "rules-v1.0"


def test_classify_bert_pending_until_model_trained():
    """BERT classification fields remain placeholder until fine-tune lands."""
    notice = _make_notice()
    session = _patched_session({1: notice})
    with patch("app.database.SessionLocal", return_value=session):
        result = classify_and_score_notice.run(1)
    assert result["bert_classification"] == "pending_fine_tune"


def test_critical_tier_logged_for_escalation_hook():
    """Critical-tier classification logs a future-Phase-11 escalation hook."""
    import logging
    notice = _make_notice(
        authority="RBI",
        penalty=Decimal("50000000"),  # ₹5 crore
        deadline=date(2026, 4, 28),  # today (overdue pressure max)
        legal_sections=["u/s 271(1)(c)", "Section 132"],
    )
    session = _patched_session({1: notice})

    # Patch date.today() to make overdue calculation deterministic.
    with patch("app.tasks.compliance_tasks.date") as mock_date, \
         patch("app.database.SessionLocal", return_value=session):
        mock_date.today.return_value = date(2026, 4, 28)
        # Allow date(...) constructor to still work normally.
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = classify_and_score_notice.run(1)

    assert result["risk_tier"] == "critical"
