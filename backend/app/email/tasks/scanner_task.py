"""APScheduler-callable Gmail scan entry — Phase 15.

Body never persisted (D-34). RLS context set per Pitfall 6 (CRIT-2).
Scan lock per Pitfall 2 (Redis SETNX). Incremental sync via historyId
with full-scan fallback on 404 (Pattern 5).
"""
from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _decode_body(payload: dict) -> str:
    """Decode Gmail message payload body. Walks parts recursively."""
    body_data = payload.get("body", {}).get("data")
    if body_data:
        try:
            return _b64url_decode(body_data).decode("utf-8", errors="replace")
        except Exception:
            return ""
    for part in payload.get("parts", []) or []:
        mime = part.get("mimeType", "")
        if mime.startswith("text/"):
            data = part.get("body", {}).get("data")
            if data:
                try:
                    return _b64url_decode(data).decode("utf-8", errors="replace")
                except Exception:
                    continue
        sub_body = _decode_body(part)
        if sub_body:
            return sub_body
    return ""


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _iter_attachments(payload: dict):
    """Yield (filename, attachment_id) for any attachment-bearing part."""
    parts = payload.get("parts", []) or []
    for part in parts:
        if part.get("filename"):
            att_id = part.get("body", {}).get("attachmentId")
            if att_id:
                yield part["filename"], att_id
        # recurse into nested multipart
        yield from _iter_attachments(part)


def run_scan(credential_id: int) -> None:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    from app.compliance.middleware.tenant_context import (
        set_tenant_context_for_celery,
    )
    from app.database import SessionLocal
    from app.email.models.credential import GmailCredential
    from app.email.models.fetch_log import GmailFetchLog
    from app.email.models.message_log import GmailMessageLog
    from app.email.services.access_token_cache import get_or_refresh_access_token
    from app.email.services.bill_extractor import extract_bill
    from app.email.services.bill_service import upsert_bill
    from app.email.services.ingestion_service import (
        ingest_attachment,
        ingest_message,
        process_classified_email,
    )
    from app.email.services.scanner_service import (
        acquire_scan_lock,
        record_fetch_outcome,
        release_scan_lock,
    )

    if not acquire_scan_lock(credential_id):
        logger.info("scan_lock not acquired for %s; skipping", credential_id)
        return

    db = SessionLocal()
    msgs_processed = 0
    try:
        # Pitfall 6: cross-mode lookup first so the credential row is visible
        set_tenant_context_for_celery(client_id=None, user_id=None, cross_mode=True)
        cred = (
            db.query(GmailCredential)
            .filter(GmailCredential.id == credential_id)
            .first()
        )
        if cred is None or cred.status != GmailCredential.STATUS_ACTIVE:
            return
        # Pitfall 6: scope to credential's tenant for downstream RLS-aware reads
        set_tenant_context_for_celery(
            client_id=cred.client_id,
            user_id=cred.user_id,
            cross_mode=False,
        )
        try:
            creds = get_or_refresh_access_token(db, credential_id)
        except Exception as e:
            logger.warning("access token refresh failed for %s: %s", credential_id, e)
            record_fetch_outcome(
                db,
                credential_id,
                GmailFetchLog.STATUS_FETCH_FAILED,
                error_message=type(e).__name__,
            )
            return

        service = build("gmail", "v1", credentials=creds)
        try:
            if cred.last_history_id:
                try:
                    history = (
                        service.users()
                        .history()
                        .list(
                            userId="me",
                            startHistoryId=cred.last_history_id,
                            historyTypes=["messageAdded"],
                        )
                        .execute()
                    )
                    message_ids = [
                        m["message"]["id"]
                        for r in history.get("history", [])
                        for m in r.get("messagesAdded", [])
                    ]
                    new_history_id = history.get("historyId")
                except HttpError as e:
                    if e.resp.status == 404:
                        full = (
                            service.users()
                            .messages()
                            .list(userId="me", maxResults=100)
                            .execute()
                        )
                        message_ids = [m["id"] for m in full.get("messages", [])]
                        # G6: the stale startHistoryId is gone (history pruned).
                        # Re-anchor to the mailbox's current historyId so the
                        # next scan is incremental again instead of repeatedly
                        # falling back to a full 100-message scan.
                        try:
                            profile = (
                                service.users()
                                .getProfile(userId="me")
                                .execute()
                            )
                            new_history_id = profile.get("historyId")
                        except HttpError as pe:
                            logger.warning(
                                "getProfile historyId re-anchor failed for %s: %s",
                                credential_id,
                                pe,
                            )
                            new_history_id = None
                    else:
                        raise
            else:
                full = (
                    service.users()
                    .messages()
                    .list(userId="me", maxResults=100)
                    .execute()
                )
                message_ids = [m["id"] for m in full.get("messages", [])]
                # G6: on the INITIAL full scan there is no startHistoryId to
                # advance, so anchor to the mailbox's current historyId. Without
                # this, last_history_id stays NULL and every subsequent run
                # repeats the full 100-message scan instead of going
                # incremental. Mirrors the 404 re-anchor branch above.
                try:
                    profile = (
                        service.users()
                        .getProfile(userId="me")
                        .execute()
                    )
                    new_history_id = profile.get("historyId")
                except HttpError as pe:
                    logger.warning(
                        "getProfile historyId anchor failed for %s: %s",
                        credential_id,
                        pe,
                    )
                    new_history_id = None

            for msg_id in message_ids:
                full_msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                payload = full_msg.get("payload", {})
                # D-34: body lives only in this Python frame
                body = _decode_body(payload)
                headers = payload.get("headers", [])
                sender = _get_header(headers, "From")
                subject = _get_header(headers, "Subject")
                created, log, route = ingest_message(
                    db,
                    credential=cred,
                    gmail_message_id=msg_id,
                    gmail_thread_id=full_msg.get("threadId"),
                    body=body,
                    sender=sender,
                    subject=subject,
                )
                msgs_processed += 1

                # G2/G6 idempotency: a re-observed message (history overlap or
                # 404 full-scan fallback) was already fully processed on first
                # ingest. Skip the side-effecting downstream pipeline so a
                # re-scan does not create a DUPLICATE bill / ComplianceNotice
                # / attachment Document for the same source email.
                if not created:
                    continue

                # Bill route — extract + upsert
                if route == GmailMessageLog.ROUTE_BILL:
                    sender_domain = sender.rsplit("@", 1)[-1].rstrip(">").lower() if "@" in sender else ""
                    try:
                        bill_data = extract_bill(body, sender_domain)
                        upsert_bill(
                            db,
                            credential=cred,
                            source_email_log=log,
                            **bill_data,
                        )
                    except Exception as e:
                        logger.warning("bill extraction failed for %s: %s", msg_id, e)

                # Attachment ingestion
                primary_attachment_doc_id: int | None = None
                for filename, att_id in _iter_attachments(payload):
                    try:
                        att = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=msg_id, id=att_id)
                            .execute()
                        )
                        att_bytes = _b64url_decode(att.get("data", ""))
                        if not att_bytes:
                            continue
                        doc = ingest_attachment(
                            db,
                            credential=cred,
                            message_log=log,
                            attachment_bytes=att_bytes,
                            filename=filename,
                            user_id=cred.user_id,
                        )
                        if doc is not None and primary_attachment_doc_id is None:
                            primary_attachment_doc_id = doc.id
                    except Exception as e:
                        logger.warning(
                            "attachment ingest failed (msg=%s name=%s): %s",
                            msg_id,
                            filename,
                            e,
                        )

                # B2 wiring (EMAIL-06): classifier verdict -> ComplianceNotice
                # OR review queue. Body still in Python local (D-34); cleared
                # after this call returns.
                try:
                    process_classified_email(
                        db,
                        credential=cred,
                        message_log=log,
                        body=body,
                        sender=sender,
                        subject=subject,
                        primary_attachment_doc_id=primary_attachment_doc_id,
                        system_user_id=cred.user_id,
                    )
                except Exception as e:
                    logger.warning(
                        "process_classified_email failed for msg=%s: %s",
                        msg_id,
                        e,
                    )
                # Body local goes out of scope at next iteration (D-34)

            if new_history_id:
                cred.last_history_id = new_history_id
                db.commit()

            status = (
                GmailFetchLog.STATUS_SUCCESS_WITH_RESULTS
                if msgs_processed > 0
                else GmailFetchLog.STATUS_SUCCESS_EMPTY
            )
            record_fetch_outcome(db, credential_id, status, msgs_processed)
        except HttpError as e:
            # Permanent auth failures (401 invalid_grant, 403 accessNotConfigured /
            # API disabled / scope revoked) repeat forever otherwise. Earlier
            # code only flipped the DB row to REVOKED; the APScheduler job
            # kept firing every cadence_minutes and re-recording FETCH_FAILED.
            # handle_invalid_grant flips the row AND removes the scheduler
            # job, so dead credentials stop wasting cycles entirely.
            status_code = getattr(getattr(e, "resp", None), "status", None)
            if status_code in (401, 403):
                logger.warning(
                    "Gmail credential %s revoked or unauthorized (HTTP %s), "
                    "calling handle_invalid_grant to stop scheduler retries",
                    credential_id,
                    status_code,
                )
                try:
                    from app.email.services.credential_vault import (
                        handle_invalid_grant,
                    )

                    handle_invalid_grant(db, credential_id)
                except Exception as he:
                    logger.warning(
                        "handle_invalid_grant fallback for %s: %s",
                        credential_id,
                        he,
                    )
                    cred.status = GmailCredential.STATUS_REVOKED
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                record_fetch_outcome(
                    db,
                    credential_id,
                    GmailFetchLog.STATUS_FETCH_FAILED,
                    error_message=f"HttpError{status_code}",
                )
                return
            # Other HttpErrors (5xx, 429) are transient — let APScheduler retry.
            logger.exception("Gmail scan failed for credential %s", credential_id)
            record_fetch_outcome(
                db,
                credential_id,
                GmailFetchLog.STATUS_FETCH_FAILED,
                error_message=type(e).__name__,
            )
            raise
        except Exception as e:
            logger.exception("Gmail scan failed for credential %s", credential_id)
            record_fetch_outcome(
                db,
                credential_id,
                GmailFetchLog.STATUS_FETCH_FAILED,
                error_message=type(e).__name__,
            )
            raise
    finally:
        db.close()
        release_scan_lock(credential_id)
