"""Regression tests for the 2026-05-29 Opus 4.8 end-to-end audit fixes.

Pure-Python (no DB, no Celery): pins the input-validation caps and the
risk-scorer sub-rupee clamp so the closed gaps cannot silently reopen.
Endpoint-level IDOR/SoD behavior is enforced in the router/service layers
(reviewed in the audit) and exercised by the existing suites; see
docs/status/AUDIT-4.8-2026-05-29.md for the full remediation record.
"""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.compliance.schemas.notice import NoticeCreate
from app.compliance.schemas.response import ResponseDraftPayload
from app.ml.compliance.risk_scorer import score


def _valid_notice_kwargs(**over):
    base = dict(
        client_id=1,
        notice_number="DRC-01/2026/A1",
        authority="GST",
        received_date=date(2026, 1, 1),
    )
    base.update(over)
    return base


def test_notice_tags_count_capped_at_50():
    """Unbounded tags list was a memory-DoS vector; 50 ok, 51 rejected."""
    NoticeCreate(**_valid_notice_kwargs(tags=["t"] * 50))
    with pytest.raises(ValidationError):
        NoticeCreate(**_valid_notice_kwargs(tags=["t"] * 51))


def test_notice_tag_item_length_capped():
    """Each tag is bounded to 100 chars."""
    with pytest.raises(ValidationError):
        NoticeCreate(**_valid_notice_kwargs(tags=["x" * 101]))


def test_response_body_markdown_length_capped():
    """Unbounded body_markdown allowed arbitrarily large DB writes."""
    ResponseDraftPayload(body_markdown="x" * 100_000)  # at cap: ok
    with pytest.raises(ValidationError):
        ResponseDraftPayload(body_markdown="x" * 100_001)


def test_risk_score_subrupee_penalty_never_lowers_risk():
    """A sub-1 penalty produced a NEGATIVE log10 contribution that silently
    lowered the risk tier. The clamp guarantees a tiny amount never scores
    lower than no amount, and the financial component is never negative."""
    common = dict(
        authority="GST",
        tax_demand=None,
        deadline=None,
        today=date(2026, 1, 1),
        legal_sections=[],
    )
    none_amount = score(penalty_amount=None, **common)
    tiny_amount = score(penalty_amount=Decimal("0.50"), **common)
    assert tiny_amount.score >= none_amount.score
    fin = [c for c in tiny_amount.top_factors if c.feature == "financial_magnitude"]
    assert all(c.contribution >= 0 for c in fin)
