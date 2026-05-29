"""Phase 17 EXTRACT-07 — Gmail ingestion integration (D-24, D-25).

Plan 17-04 GREEN. `process_classified_email` calls the extractor BEFORE
notice creation, optionally pulls notice_number/authority from the
envelope, and applies the artefact to the notice in both 'apply' and
'review_queue' branches.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch



def _mock_credential(client_id: int = 7):
    cred = MagicMock()
    cred.id = 11
    cred.client_id = client_id
    return cred


def _mock_message_log():
    log = MagicMock()
    log.id = 5
    log.gmail_message_id = "abc12345"
    log.body_sha256 = "deadbeef"
    log.sender_domain = "gst.gov.in"
    return log


def test_process_classified_email_calls_extractor_before_notice_create(
    extraction_envelope_fixture,
):
    """D-24: extract_notice_fields runs before db.add(ComplianceNotice)."""
    from app.email.services import ingestion_service

    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()

    call_order: list[str] = []

    def _ext_side_effect(*a, **kw):
        call_order.append("extract")
        return extraction_envelope_fixture

    def _add_side_effect(obj):
        call_order.append("notice_create")

    db.add.side_effect = _add_side_effect

    with patch.object(ingestion_service, "classify", return_value=(True, 1.0)), \
         patch.object(ingestion_service, "_extract_metadata", return_value={}), \
         patch("app.email.classifier_rules.authority_from_sender", return_value="GST"), \
         patch(
             "app.compliance.services.notice_extractor_service.extract_notice_fields",
             side_effect=_ext_side_effect,
         ), \
         patch(
             "app.compliance.services.extraction_routing_service.apply_extraction_to_notice"
         ), \
         patch("app.services.audit_service.log_audit_event_strict", return_value=True):

        ingestion_service.process_classified_email(
            db,
            credential=_mock_credential(),
            message_log=_mock_message_log(),
            body="notice body",
            sender="filing@gst.gov.in",
            subject="Show Cause Notice",
            primary_attachment_doc_id=None,
            system_user_id=1,
        )

    assert "extract" in call_order, "extractor must be called in Gmail path"
    assert "notice_create" in call_order, "notice must still be created"
    assert call_order.index("extract") < call_order.index("notice_create"), (
        "D-24: extraction must happen before notice create"
    )


def test_apply_branch_pulls_notice_number_from_envelope(extraction_envelope_fixture):
    """D-24: when decision is 'apply', extracted notice_number lands on the new ComplianceNotice."""
    from app.email.services import ingestion_service

    captured: dict = {}

    class _NoticeCapture:
        def __init__(self, **kw):
            captured.update(kw)
            self.id = 100
            self.client_id = kw.get("client_id")
            self.extraction_status = None
            self.response_deadline = None

    db = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()

    with patch.object(ingestion_service, "classify", return_value=(True, 1.0)), \
         patch.object(ingestion_service, "_extract_metadata", return_value={}), \
         patch("app.email.classifier_rules.authority_from_sender", return_value="GST"), \
         patch(
             "app.compliance.services.notice_extractor_service.extract_notice_fields",
             return_value=extraction_envelope_fixture,
         ), \
         patch(
             "app.compliance.services.extraction_routing_service.apply_extraction_to_notice"
         ), \
         patch("app.services.audit_service.log_audit_event_strict", return_value=True), \
         patch("app.compliance.models.notice.ComplianceNotice", _NoticeCapture):

        ingestion_service.process_classified_email(
            db,
            credential=_mock_credential(),
            message_log=_mock_message_log(),
            body="notice body",
            sender="filing@gst.gov.in",
            subject="Show Cause Notice",
            primary_attachment_doc_id=None,
            system_user_id=1,
        )

    assert captured.get("notice_number") == "DRC-01/2026/4456", (
        f"D-24: expected extracted notice_number; got {captured.get('notice_number')}"
    )
    assert captured.get("authority") == "GST"


def test_extraction_failure_falls_back_to_gmail_prefix_notice_number(
    extraction_envelope_fixture,
):
    """D-09 in Gmail path: extractor raises → falls back to sender-derived authority + GMAIL-{id} number."""
    from app.email.services import ingestion_service

    captured: dict = {}

    class _NoticeCapture:
        def __init__(self, **kw):
            captured.update(kw)
            self.id = 100
            self.client_id = kw.get("client_id")
            self.extraction_status = None
            self.response_deadline = None

    db = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()

    with patch.object(ingestion_service, "classify", return_value=(True, 1.0)), \
         patch.object(ingestion_service, "_extract_metadata", return_value={}), \
         patch("app.email.classifier_rules.authority_from_sender", return_value="GST"), \
         patch(
             "app.compliance.services.notice_extractor_service.extract_notice_fields",
             side_effect=RuntimeError("provider error"),
         ), \
         patch("app.services.audit_service.log_audit_event_strict", return_value=True), \
         patch("app.compliance.models.notice.ComplianceNotice", _NoticeCapture):

        ingestion_service.process_classified_email(
            db,
            credential=_mock_credential(),
            message_log=_mock_message_log(),
            body="notice body",
            sender="filing@gst.gov.in",
            subject="Show Cause Notice",
            primary_attachment_doc_id=None,
            system_user_id=1,
        )

    # Notice still created via fallback path
    assert captured.get("authority") == "GST", "fallback authority comes from sender domain"
    assert captured.get("notice_number", "").startswith("GMAIL-"), (
        "fallback notice_number must use the GMAIL- prefix"
    )


def test_audit_row_records_extraction_action(extraction_envelope_fixture):
    """D-24: NOTICE_AUTO_CREATED audit args carry phase17_extraction_action so it links to the prior NOTICE_AI_EXTRACT row by body_sha256."""
    from app.email.services import ingestion_service

    captured_audit: dict = {}

    def _capture(**kwargs):
        if kwargs.get("action") == "NOTICE_AUTO_CREATED":
            captured_audit.update(kwargs)
        return True

    db = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()

    with patch.object(ingestion_service, "classify", return_value=(True, 1.0)), \
         patch.object(ingestion_service, "_extract_metadata", return_value={}), \
         patch("app.email.classifier_rules.authority_from_sender", return_value="GST"), \
         patch(
             "app.compliance.services.notice_extractor_service.extract_notice_fields",
             return_value=extraction_envelope_fixture,
         ), \
         patch(
             "app.compliance.services.extraction_routing_service.apply_extraction_to_notice"
         ), \
         patch("app.services.audit_service.log_audit_event_strict", side_effect=_capture):

        ingestion_service.process_classified_email(
            db,
            credential=_mock_credential(),
            message_log=_mock_message_log(),
            body="notice body",
            sender="filing@gst.gov.in",
            subject="Show Cause Notice",
            primary_attachment_doc_id=None,
            system_user_id=1,
        )

    assert captured_audit.get("action") == "NOTICE_AUTO_CREATED"
    details = captured_audit.get("details") or {}
    assert details.get("phase17_extraction_action") == "apply"
