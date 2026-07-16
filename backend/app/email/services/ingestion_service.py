"""Gmail message + attachment ingestion — Phase 15 EMAIL-05, EMAIL-06, EMAIL-08.

Reuses v1.0 storage_service + document_tasks pipeline (D-14). Body never
persisted (D-34) for compliance/bill routes; audit args PII-redacted
(D-36).

D-39 carve-out: when a message matches no rule but carries >=200 chars
of body text, we persist a synthetic .txt Document (source='gmail_body')
and run it through Phase 3 ML classification so v1.0 listings + search
can surface attachment-less Gmail content.

process_classified_email is the EMAIL-06 wiring: classifier verdict ->
ComplianceNotice (gmail / received) OR review queue OR ignored.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.email.classifier_rules import MIN_BODY_LENGTH_FOR_CLASSIFICATION
from app.email.models.credential import GmailCredential
from app.email.models.filter_rule import GmailFilterRule
from app.email.models.message_log import GmailMessageLog
from app.email.services.classifier import classify, resolve_route
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
    rules: Optional[Sequence[GmailFilterRule]] = None,
) -> tuple[bool, GmailMessageLog, str]:
    """Classify and persist message log row. Returns (created, message_log, route_taken).

    ``created`` is False when this message was already ingested (G2 dedup hit
    via history overlap or 404 full-scan fallback) so the caller can skip the
    side-effecting downstream pipeline (notice/bill creation) and avoid
    duplicating it on every re-scan.

    Body lives only in this Python frame for compliance/bill routes — D-34
    fetch-once-discard. The D-39 gmail_body carve-out (no-rule-match plus
    body >= MIN_BODY_LENGTH_FOR_CLASSIFICATION) deliberately persists the
    body as a synthetic .txt Document so v1.0 ML classification can run.

    ``rules``: pre-loaded enabled filter rules for this credential (priority
    ASC). When omitted, resolve_route uses only built-in classifier + bill
    heuristics.
    """
    route = resolve_route(sender, subject, body=body or "", rules=rules)

    # G2: a re-observed message (history overlap or 404 full-scan fallback)
    # would violate UNIQUE(credential_id, gmail_message_id). Treat an existing
    # row as already-ingested and skip — the D-39 body persist already ran on
    # first ingest, so do not re-run it.
    existing = (
        db.query(GmailMessageLog)
        .filter(
            GmailMessageLog.credential_id == credential.id,
            GmailMessageLog.gmail_message_id == gmail_message_id,
        )
        .first()
    )
    if existing is not None:
        return False, existing, existing.route_taken

    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    log = GmailMessageLog(
        credential_id=credential.id,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
        sender_domain=_sender_domain(sender),
        body_sha256=body_sha,
        route_taken=route,
    )
    # G2: SAVEPOINT guards the race where a concurrent scan inserts the same
    # message between the pre-query and this commit. Swallow IntegrityError and
    # fall back to the now-present row so the outer scan transaction is not
    # poisoned and the batch continues.
    try:
        with db.begin_nested():
            db.add(log)
        db.commit()
        db.refresh(log)
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(GmailMessageLog)
            .filter(
                GmailMessageLog.credential_id == credential.id,
                GmailMessageLog.gmail_message_id == gmail_message_id,
            )
            .first()
        )
        if existing is not None:
            return False, existing, existing.route_taken
        raise

    # D-39: rule miss + non-trivial body -> persist as gmail_body Document
    # so v1.0 ML classifies + indexes it. Best-effort; never fails the
    # caller's pipeline.
    if route == GmailMessageLog.ROUTE_IGNORE and len(body) >= MIN_BODY_LENGTH_FOR_CLASSIFICATION:
        try:
            _persist_body_as_document(
                db,
                credential=credential,
                message_log=log,
                body=body,
                subject=subject,
            )
        except Exception as e:
            logger.warning(
                "gmail_body persist failed: msg=%s err=%s",
                gmail_message_id,
                e,
            )

    return True, log, route


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
    # Gmail omits filenames on many attachments, so _iter_attachments names them
    # all "attachment.<ext>". Two different filename-less attachments for the same
    # user would then collide on uq_documents_user_filename (user_id,
    # original_filename). Content-address the generic placeholder so distinct
    # attachments stay distinct and identical bytes still dedup below.
    if filename.startswith("attachment."):
        _ext = filename[len("attachment.") :]
        filename = (
            f"attachment-{sha256[:12]}.{_ext}" if _ext else f"attachment-{sha256[:12]}"
        )
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
        source="gmail",
    )
    # uq_documents_user_filename guard: a concurrent or prior insert of the same
    # (user_id, original_filename) would raise IntegrityError and poison the whole
    # scan session. Insert inside a SAVEPOINT; on collision drop the orphaned file
    # and treat the attachment as already ingested.
    try:
        with db.begin_nested():
            db.add(doc)
        db.commit()
        db.refresh(doc)
    except IntegrityError:
        db.rollback()
        if file_path:
            try:
                os.remove(file_path)
            except OSError:
                pass
        logger.info(
            "Attachment dedup (unique index) name=%s sha=%s", filename, sha256[:8]
        )
        return None
    try:
        from app.tasks.document_tasks import process_document_task
        process_document_task.delay(doc.id)
    except Exception as e:
        logger.warning("Celery process_document_task.delay failed: %s", e)
    return doc


def _persist_body_as_document(
    db: Session,
    *,
    credential: GmailCredential,
    message_log: GmailMessageLog,
    body: str,
    subject: str,
) -> Optional[Document]:
    """D-39: persist a Gmail body as a synthetic .txt Document.

    Title (original_filename) defaults to the email subject truncated to
    200 chars; falls back to ``Email <sha8>.txt`` when the subject is
    empty. Runs through the v1.0 process_document_task so Phase 3 ML
    classification + Phase 5 LLM extraction populate Document.category
    and friends. source='gmail_body' lets the listing UI distinguish
    body-derived docs from real attachments (D-40, D-41).
    """
    body_bytes = body.encode("utf-8")
    file_size = len(body_bytes)

    raw_subject = (subject or "").strip()
    short_sha = message_log.body_sha256[:8] if message_log.body_sha256 else "msg"
    if raw_subject:
        # Strip control chars + cap at 200 chars (D-39). Append .txt so
        # downloads / previews get a sensible extension.
        clean = "".join(ch for ch in raw_subject if ch.isprintable() and ch != "\x00")
        title = clean[:196] + ".txt" if not clean.endswith(".txt") else clean[:200]
    else:
        title = f"Email {short_sha}.txt"

    file_path, s3_url = save_file(body_bytes, title)
    doc = Document(
        user_id=credential.user_id,
        filename=os.path.basename(file_path) if file_path else title,
        original_filename=title,
        file_type="txt",
        file_size=file_size,
        file_path=file_path if not s3_url else None,
        s3_url=s3_url,
        category=DocumentCategory.UNKNOWN,
        status=DocumentStatus.PENDING,
        source_email_id=message_log.id,
        source="gmail_body",
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
    route: Optional[str] = None,
) -> None:
    """EMAIL-06 wiring: classifier / route verdict -> ComplianceNotice OR review queue.

    D-34: body lives only in this Python frame; do NOT persist anywhere.
    D-36: review-queue payload omits body/subject/sender text — only
          sender_domain + body_sha256 references.

    ``route`` is the resolve_route() result from ingest_message. When the
    operator filter rules force compliance_notice, we create a notice even
    if the built-in classifier would have scored lower.
    """
    is_compliance, confidence = classify(sender, subject)
    forced_route = str(route or message_log.route_taken or "")

    # Operator / bill / ignore short-circuits
    if forced_route == GmailMessageLog.ROUTE_BILL:
        return
    if forced_route in (GmailMessageLog.ROUTE_IGNORE, GmailMessageLog.ROUTE_DMS_ONLY):
        # Honor an operator's explicit suppress / DMS-only route; do not let the
        # built-in classifier auto-create a notice against that intent. Body
        # persistence for these routes already ran in ingest_message.
        return
    if forced_route == GmailMessageLog.ROUTE_COMPLIANCE:
        is_compliance, confidence = True, 1.0

    # Prefer body; when body is short (PDF-only mail), still extract from
    # subject so Phase 17 has something until attachment OCR completes.
    extraction_text = (body or "").strip()
    if len(extraction_text) < 40:
        extraction_text = f"{subject or ''}\n{extraction_text}".strip()

    if is_compliance and confidence >= 0.75:
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services.activity_service import log_activity
        from app.email.classifier_rules import authority_from_sender
        from app.services.audit_service import log_audit_event_strict

        authority = authority_from_sender(sender)

        # Phase 17 D-24 — run extractor BEFORE notice create so extracted
        # values can land directly on the canonical columns. Non-fatal:
        # any failure falls back to the original "use sender-derived
        # authority + GMAIL-prefix notice_number" path.
        extraction_envelope: Optional[dict] = None
        extraction_decision: Optional[dict] = None
        try:
            from app.compliance.services.extraction_routing_service import (
                apply_extraction_to_notice,
                route_or_apply,
            )
            from app.compliance.services.notice_extractor_service import (
                extract_notice_fields,
            )

            extraction_envelope = extract_notice_fields(
                db,
                client_id=credential.client_id,
                user_id=system_user_id,
                text=extraction_text or body or "",
                notice_id=None,
            )
            extraction_decision = route_or_apply(extraction_envelope)
        except Exception as e:  # noqa: BLE001
            logger.warning("gmail_phase17_extraction_failed: %s", e)
            extraction_envelope = None
            extraction_decision = None

        # Pull extracted values when the decision authorises auto-apply (D-24).
        notice_number = None
        applied_authority = authority
        if extraction_decision and extraction_decision.get("action") == "apply":
            fields = (extraction_envelope or {}).get("fields") or {}
            ext_no = fields.get("notice_number") if isinstance(fields.get("notice_number"), dict) else None
            if ext_no and ext_no.get("value"):
                notice_number = str(ext_no["value"])
            ext_auth = fields.get("authority") if isinstance(fields.get("authority"), dict) else None
            if ext_auth and ext_auth.get("value") in {"GST", "IT", "MCA", "RBI", "SEBI"}:
                applied_authority = ext_auth["value"]

        if not notice_number:
            # Only run the secondary LLM metadata extraction when Phase 17 did
            # not yield a notice_number (and never for non-compliance mail).
            extracted_metadata = _extract_metadata(extraction_text or body or "")
            notice_number = (
                extracted_metadata.get("notice_number")
                or f"GMAIL-{message_log.gmail_message_id[:8]}"
            )

        notice = ComplianceNotice(
            client_id=credential.client_id,
            notice_number=str(notice_number)[:100],
            authority=applied_authority,
            status="received",
            source="gmail",
            document_id=primary_attachment_doc_id,
            created_by_user_id=system_user_id,
        )
        db.add(notice)
        db.flush()

        # Link the primary attachment Document to this notice for the
        # compliance workflow UI (AttachmentList / notice detail).
        if primary_attachment_doc_id is not None:
            try:
                doc = db.query(Document).filter(Document.id == primary_attachment_doc_id).first()
                if doc is not None and doc.notice_id is None:
                    doc.notice_id = notice.id
            except Exception as e:  # noqa: BLE001
                logger.warning("link attachment to notice failed: %s", e)

        # Persist the extraction envelope onto the notice regardless of
        # routing decision (D-23). When the gate failed, this also
        # enqueues a review-queue row.
        if extraction_envelope and extraction_decision:
            try:
                apply_extraction_to_notice(
                    db, notice, extraction_envelope, extraction_decision
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("gmail_phase17_apply_failed: %s", e)

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
                    "phase17_extraction_action": (
                        extraction_decision.get("action") if extraction_decision else "skipped"
                    ),
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
                "phase17_extraction_action": (
                    extraction_decision.get("action") if extraction_decision else "skipped"
                ),
            },
        )
        db.commit()
        db.refresh(notice)
        # Phase 10/11 — Gmail-ingested notices now enter the same classify +
        # risk-score + deadline-alert pipeline as manually created notices.
        from app.compliance.services.notice_service import process_notice_intake
        process_notice_intake(notice.id, notice.response_deadline)
        return

    if not is_compliance and confidence == 0.5:
        # Sender matched a gov domain but subject lacked keywords. Create a
        # lightweight notice so compliance can see it, then enqueue review.
        from app.compliance.models.notice import ComplianceNotice
        from app.email.classifier_rules import authority_from_sender
        from app.services.audit_service import log_audit_event_strict

        authority = authority_from_sender(sender)
        notice_number = f"GMAIL-REV-{message_log.gmail_message_id[:8]}"
        notice = ComplianceNotice(
            client_id=credential.client_id,
            notice_number=notice_number[:100],
            authority=authority,
            status="received",
            source="gmail",
            document_id=primary_attachment_doc_id,
            created_by_user_id=system_user_id,
        )
        db.add(notice)
        db.flush()
        if primary_attachment_doc_id is not None:
            try:
                doc = db.query(Document).filter(Document.id == primary_attachment_doc_id).first()
                if doc is not None and doc.notice_id is None:
                    doc.notice_id = notice.id
            except Exception as e:  # noqa: BLE001
                logger.warning("link attachment to review notice failed: %s", e)

        try:
            from decimal import Decimal

            from app.compliance.services.review_queue_service import enqueue_low_confidence

            enqueue_low_confidence(
                db,
                notice=notice,
                predicted_authority=authority,
                predicted_authority_confidence=Decimal("0.50"),
                predicted_type_id=None,
                predicted_type_confidence=Decimal("0.00"),
                model_version="gmail_sender_only_v1",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("enqueue_low_confidence failed: %s", e)

        log_audit_event_strict(
            user_id=system_user_id,
            action="NOTICE_AUTO_CREATED",
            resource_type="compliance_notice",
            resource_id=int(notice.id),
            details={
                "source": "gmail",
                "credential_id": credential.id,
                "body_sha256": message_log.body_sha256,
                "sender_domain": message_log.sender_domain,
                "gmail_message_log_id": message_log.id,
                "route": "review_queue",
                "confidence": 0.5,
            },
        )
        db.commit()
        db.refresh(notice)
        from app.compliance.services.notice_service import process_notice_intake
        process_notice_intake(int(notice.id), notice.response_deadline)
        logger.info(
            "gmail_review_queue_route",
            extra={
                "credential_id": credential.id,
                "sender_domain": message_log.sender_domain,
                "body_sha256": message_log.body_sha256,
                "gmail_message_log_id": message_log.id,
                "notice_id": notice.id,
                "confidence": confidence,
                "reason": "sender_match_only",
            },
        )
        return

    # confidence == 0.0 -> ignore (D-33 forwarded notices already routed
    # dms_only via ingest_message)
    logger.info(
        "classifier route ignored: msg=%s",
        message_log.gmail_message_id,
    )
