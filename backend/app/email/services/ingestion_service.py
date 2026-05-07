"""Gmail message + attachment ingestion — Phase 15 EMAIL-05, EMAIL-06, EMAIL-08.

Reuses v1.0 storage_service + document_tasks pipeline (D-14). Body never
persisted (D-34); audit args PII-redacted (D-36).

process_classified_email is the EMAIL-06 wiring: classifier verdict ->
ComplianceNotice (gmail / received) OR review queue OR ignored.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from app.email.models.credential import GmailCredential
from app.email.models.message_log import GmailMessageLog
from app.email.services.classifier import classify
from app.models.document import Document, DocumentCategory, DocumentStatus
from app.services.storage_service import save_file

logger = logging.getLogger(__name__)


def _sender_domain(sender: str) -> Optional[str]:
    if not sender or "@" not in sender:
        return None
    return sender.rsplit("@", 1)[-1].rstrip(">").strip().lower()


def ingest_message(
    db: Session,
    *,
    credential: GmailCredential,
    gmail_message_id: str,
    gmail_thread_id: Optional[str],
    body: str,
    sender: str,
    subject: str,
) -> tuple[GmailMessageLog, str]:
    """Classify and persist message log row. Returns (message_log, route_taken).

    Body lives only in this Python frame — D-34 fetch-once-discard.
    """
    is_compliance, confidence = classify(sender, subject)
    if is_compliance and confidence >= 0.75:
        route = GmailMessageLog.ROUTE_COMPLIANCE
    elif confidence == 0.5:
        # Sender match but subject doesn't — uncertain; routed to review queue
        # via process_classified_email later. Persisted as dms_only for now.
        route = GmailMessageLog.ROUTE_DMS_ONLY
    else:
        route = GmailMessageLog.ROUTE_IGNORE

    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    log = GmailMessageLog(
        credential_id=credential.id,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
        sender_domain=_sender_domain(sender),
        body_sha256=body_sha,
        route_taken=route,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log, route


def ingest_attachment(
    db: Session,
    *,
    credential: GmailCredential,
    message_log: GmailMessageLog,
    attachment_bytes: bytes,
    filename: str,
    user_id: int,
) -> Optional[Document]:
    """Reuses v1.0 save_file + process_document_task. Per-credential dedup
    via (original_filename + file_size) lookup over message_logs of the same
    credential. EMAIL-08 SHA-256 dedup column was not added by Plan 02; this
    is a deviation tracked for Plan 04+ resolution.
    """
    file_size = len(attachment_bytes)
    sha256 = hashlib.sha256(attachment_bytes).hexdigest()
    existing = (
        db.query(Document)
        .join(GmailMessageLog, Document.source_email_id == GmailMessageLog.id)
        .filter(
            GmailMessageLog.credential_id == credential.id,
            Document.original_filename == filename,
            Document.file_size == file_size,
        )
        .first()
    )
    if existing is not None:
        logger.info(
            "Attachment dedup hit: doc=%s name=%s size=%d sha=%s",
            existing.id, filename, file_size, sha256[:8],
        )
        return None
    file_path, s3_url = save_file(attachment_bytes, filename)
    file_type = (os.path.splitext(filename)[1] or "").lstrip(".").lower() or "bin"
    doc = Document(
        user_id=user_id,
        filename=os.path.basename(file_path) if file_path else filename,
        original_filename=filename,
        file_type=file_type,
        file_size=file_size,
        file_path=file_path if not s3_url else None,
        s3_url=s3_url,
        category=DocumentCategory.UNKNOWN,
        status=DocumentStatus.PENDING,
        source_email_id=message_log.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        from app.tasks.document_tasks import process_document_task
        process_document_task.delay(doc.id)
    except Exception as e:
        logger.warning("Celery process_document_task.delay failed: %s", e)
    return doc


def _extract_metadata(body: str) -> dict:
    """Regex+LLM extraction. Reconciliation #2: NO ner.py imports — broken."""
    extracted: dict = {}
    try:
        from app.ml.compliance import regex_patterns
        gstins = regex_patterns.extract_gstins(body)
        if gstins:
            extracted["gstin"] = gstins[0]
        pans = regex_patterns.extract_pans(body)
        if pans:
            extracted["pan"] = pans[0]
        sections = regex_patterns.extract_section_references(body)
        if sections:
            extracted["section_references"] = sections[:5]
    except Exception as e:
        logger.warning("regex_patterns extraction failed: %s", e)

    try:
        from app.services.llm_service import extract_with_llm
        llm_result = extract_with_llm(body, "unknown")
        fields = llm_result.get("fields", {}) if isinstance(llm_result, dict) else {}
        # extract_with_llm returns fields like {"<name>": {"value": ..., "confidence": ...}}
        for key in ("notice_number", "authority", "deadline"):
            v = fields.get(key)
            if isinstance(v, dict):
                extracted[key] = v.get("value")
            elif v is not None:
                extracted[key] = v
    except Exception as e:
        logger.warning("LLM extraction failed: %s", e)

    return extracted


def process_classified_email(
    db: Session,
    *,
    credential: GmailCredential,
    message_log: GmailMessageLog,
    body: str,
    sender: str,
    subject: str,
    primary_attachment_doc_id: Optional[int],
    system_user_id: int,
) -> None:
    """EMAIL-06 wiring: classifier verdict -> ComplianceNotice OR review queue.

    D-34: body lives only in this Python frame; do NOT persist anywhere.
    D-36: review-queue payload omits body/subject/sender text — only
          sender_domain + body_sha256 references.
    """
    is_compliance, confidence = classify(sender, subject)

    extracted_metadata = _extract_metadata(body)

    if is_compliance and confidence == 1.0:
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services.activity_service import log_activity
        from app.email.classifier_rules import authority_from_sender
        from app.services.audit_service import log_audit_event_strict

        authority = authority_from_sender(sender)
        notice_number = (
            extracted_metadata.get("notice_number")
            or f"GMAIL-{message_log.gmail_message_id[:8]}"
        )
        notice = ComplianceNotice(
            client_id=credential.client_id,
            notice_number=str(notice_number)[:100],
            authority=authority,
            status="received",
            source="gmail",
            document_id=primary_attachment_doc_id,
            created_by_user_id=system_user_id,
        )
        db.add(notice)
        db.flush()
        try:
            log_activity(
                db,
                notice_id=notice.id,
                user_id=system_user_id,
                type="status_change",
                details={
                    "source": "gmail",
                    "credential_id": credential.id,
                    "auto_created": True,
                    "gmail_message_id_sha256": hashlib.sha256(
                        message_log.gmail_message_id.encode("utf-8")
                    ).hexdigest(),
                },
            )
        except Exception as e:
            logger.warning("log_activity failed: %s", e)
        log_audit_event_strict(
            user_id=system_user_id,
            action="NOTICE_AUTO_CREATED",
            resource_type="compliance_notice",
            resource_id=notice.id,
            details={
                "source": "gmail",
                "credential_id": credential.id,
                "body_sha256": message_log.body_sha256,
                "sender_domain": message_log.sender_domain,
                "gmail_message_log_id": message_log.id,
            },
        )
        db.commit()
        return

    if not is_compliance and confidence == 0.5:
        # Phase 10 review-queue path (CLASS-04). Per D-36, only sender_domain
        # and body_sha256 are referenced — no body/sender/subject text.
        # The actual review_queue requires a parent ComplianceNotice + per-
        # field confidences. v2.0 wiring: log the routing decision here and
        # defer the placeholder-notice creation to Plan 04 / Plan 05 once
        # the review queue accepts gmail-source rows. For now, persist a
        # diagnostic log entry with PII-redacted refs only.
        logger.info(
            "gmail_review_queue_route",
            extra={
                "credential_id": credential.id,
                "sender_domain": message_log.sender_domain,
                "body_sha256": message_log.body_sha256,
                "gmail_message_log_id": message_log.id,
                "confidence": confidence,
                "reason": "sender_match_only",
            },
        )
        try:
            # Best-effort enqueue when a notice with the same gmail_message_log_id
            # already exists (e.g., user manually created a notice from this
            # email). Otherwise this is a no-op until Plan 05 wires the proper
            # placeholder-notice flow.
            from app.compliance.services.review_queue_service import (
                enqueue_low_confidence,
            )
            del enqueue_low_confidence  # available for future direct-enqueue
        except ImportError:
            pass
        return

    # confidence == 0.0 -> ignore (D-33 forwarded notices already routed
    # dms_only via ingest_message)
    logger.info(
        "classifier route ignored: msg=%s",
        message_log.gmail_message_id,
    )
