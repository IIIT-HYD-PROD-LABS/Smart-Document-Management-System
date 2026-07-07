"""Phase 17 EXTRACT-09 — accept-extraction endpoint + per-field audit (D-11, D-17, D-21).

Plan 17-05 GREEN. `POST /api/compliance/notices/{id}/accept-extraction`
writes accepted fields onto the canonical notice columns and emits one
audit row per accepted field carrying SHA-256 hashes of the original
and accepted values plus `was_edited`.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch



def test_accept_extraction_requires_two_permissions():
    """D-21: NOTICE_AI_EXTRACT permission must be registered (router gates on it)."""
    from app.compliance.services.permission_registry import CompliancePermission
    assert hasattr(CompliancePermission, "NOTICE_AI_EXTRACT"), (
        "Plan 17-02 must add CompliancePermission.NOTICE_AI_EXTRACT"
    )
    assert CompliancePermission.NOTICE_AI_EXTRACT.value == "notice:ai_extract"


def _stub_notice():
    notice = MagicMock()
    notice.id = 42
    notice.client_id = 7
    notice.extraction_status = "completed"
    notice.extracted_fields = {
        "fields": {
            "notice_number": {"value": "DRC-01/2026/4456", "confidence": 0.96},
            "authority": {"value": "GST", "confidence": 0.99},
            "issued_date": {"value": "2026-05-12", "confidence": 0.95},
            "tax_demand": {"value": 145000.0, "confidence": 0.92},
        },
        "average_confidence": 0.95,
        "model": "anthropic:claude-sonnet-test",
    }
    notice.notice_number = ""
    notice.authority = ""
    notice.received_date = None
    notice.tax_demand = None
    return notice


async def _patched_call(payload_items, *, notice=None, permission_ok=True):
    """Helper: invoke accept_extraction (async) with dependencies mocked."""
    from app.compliance.routers.notices import accept_extraction
    from app.compliance.schemas.extraction import (
        AcceptExtractionItem,
        AcceptExtractionPayload,
    )

    notice = notice if notice is not None else _stub_notice()
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.first.return_value = notice
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    current_user = MagicMock(id=99)
    # ClientMembership stores the role on `compliance_role`, not `role`.
    membership = MagicMock(
        compliance_role="compliance_head" if permission_ok else "auditor",
        client_id=7,
    )

    captured: list[dict] = []

    def _audit(**kwargs):
        captured.append(kwargs)
        return True

    payload = AcceptExtractionPayload(
        items=[AcceptExtractionItem(**item) for item in payload_items]
    )

    with patch("app.compliance.routers.notices.log_audit_event", side_effect=_audit):
        try:
            result = await accept_extraction(
                notice_id=42,
                payload=payload,
                current_user=current_user,
                db=db,
                membership=membership,
            )
        except Exception as exc:
            return None, captured, exc

    return result, captured, None


async def test_accept_extraction_writes_per_field_audit_row():
    """D-17: one audit row per accepted field with original/accepted SHA-256 + was_edited."""
    _result, captured, exc = await _patched_call(
        [
            {"field": "notice_number", "value": "DRC-01/2026/4456", "accept_as_is": True},
            {"field": "authority", "value": "GST", "accept_as_is": True},
        ]
    )
    assert exc is None
    actions = {row["action"] for row in captured}
    assert actions == {"notice_ai_extract_accepted"}
    assert len(captured) == 2

    by_field = {row["details"]["field"]: row["details"] for row in captured}
    for field in ("notice_number", "authority"):
        details = by_field[field]
        assert "original_value_sha256" in details
        assert "accepted_value_sha256" in details
        assert details["was_edited"] is False


async def test_accept_extraction_copies_fields_to_canonical_columns():
    """D-11: accepted notice_number, authority, dates, amounts land on the corresponding notice columns."""
    notice = _stub_notice()
    _result, _captured, exc = await _patched_call(
        [
            {"field": "notice_number", "value": "DRC-01/2026/4456", "accept_as_is": True},
            {"field": "authority", "value": "GST", "accept_as_is": True},
            {"field": "tax_demand", "value": 145000.0, "accept_as_is": True},
        ],
        notice=notice,
    )
    assert exc is None
    assert notice.notice_number == "DRC-01/2026/4456"
    assert notice.authority == "GST"
    assert notice.tax_demand == 145000.0


async def test_accept_extraction_flips_extraction_status_to_accepted():
    """D-11: extraction_status moves from 'completed' to 'accepted' after acceptance."""
    notice = _stub_notice()
    assert notice.extraction_status == "completed"
    _result, _captured, exc = await _patched_call(
        [{"field": "authority", "value": "GST", "accept_as_is": True}],
        notice=notice,
    )
    assert exc is None
    assert notice.extraction_status == "accepted"


async def test_edited_field_records_was_edited_true_in_audit():
    """D-17: when the user edited the value before accepting, was_edited=True and the hashes differ."""
    _result, captured, exc = await _patched_call(
        [
            {"field": "notice_number", "value": "DRC-01/2026/CORRECTED", "accept_as_is": False},
        ]
    )
    assert exc is None
    details = captured[0]["details"]
    assert details["was_edited"] is True
    assert details["original_value_sha256"] != details["accepted_value_sha256"]


async def test_accept_extraction_rejects_when_status_is_pending():
    """D-11: 409 Conflict when notice.extraction_status is not yet 'completed' or 'accepted'."""
    from fastapi import HTTPException

    notice = _stub_notice()
    notice.extraction_status = "pending"
    _result, _captured, exc = await _patched_call(
        [{"field": "authority", "value": "GST", "accept_as_is": True}],
        notice=notice,
    )
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 409


async def test_accept_extraction_coerces_currency_formatted_amount():
    """Regression: a currency-formatted amount must coerce to Decimal, not 500.

    Before the coercion fix, '₹1,45,000' reached the Numeric(18,2) column as a
    raw string and raised an uncaught StatementError/DataError -> HTTP 500.
    """
    from decimal import Decimal

    notice = _stub_notice()
    _result, _captured, exc = await _patched_call(
        [{"field": "tax_demand", "value": "₹1,45,000", "accept_as_is": False}],
        notice=notice,
    )
    assert exc is None
    assert notice.tax_demand == Decimal("145000.00")


async def test_accept_extraction_coerces_non_iso_indian_date():
    """Regression: a DD-MM-YYYY date must coerce to a date, not 500."""
    from datetime import date

    notice = _stub_notice()
    _result, _captured, exc = await _patched_call(
        [{"field": "issued_date", "value": "31-03-2025", "accept_as_is": False}],
        notice=notice,
    )
    assert exc is None
    assert notice.received_date == date(2025, 3, 31)


async def test_accept_extraction_rejects_unparseable_amount_with_422():
    """An amount that cannot be coerced yields a clean 422, never an uncaught 500."""
    from fastapi import HTTPException

    notice = _stub_notice()
    _result, _captured, exc = await _patched_call(
        [{"field": "tax_demand", "value": "see annexure", "accept_as_is": False}],
        notice=notice,
    )
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 422


async def test_accept_extraction_rejects_invalid_authority_with_422():
    """An authority outside the allowed set is rejected before the CHECK constraint."""
    from fastapi import HTTPException

    notice = _stub_notice()
    _result, _captured, exc = await _patched_call(
        [{"field": "authority", "value": "CUSTOMS", "accept_as_is": False}],
        notice=notice,
    )
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 422
