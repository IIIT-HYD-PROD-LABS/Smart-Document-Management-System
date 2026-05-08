"""MCP tool body implementations — Phase 15 EMAIL-02 + EMAIL-09.

Audit + RLS context applied at tool entry; PII redacted per D-36
(no body, sender, subject, attachment bytes — only IDs + SHA-256).
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

from fastmcp.exceptions import ToolError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.compliance.middleware.tenant_context import set_tenant_context_for_celery
from app.database import SessionLocal
from app.email.mcp.server import (
    GmailGetAttachmentArgs,
    GmailListAttachmentsArgs,
    GmailListLabelsArgs,
    GmailModifyLabelsArgs,
    GmailReadMessageArgs,
    GmailSearchArgs,
)
from app.email.models.credential import GmailCredential
from app.email.services.access_token_cache import get_or_refresh_access_token
from app.email.services.credential_vault import handle_invalid_grant
from app.services.audit_service import log_audit_event_strict

logger = logging.getLogger(__name__)

ALLOWED_SYSTEM_LABELS = {"dms-ingested", "dms-bill-flagged", "dms-compliance-flagged"}


def _open_session_with_creds(args: Any):
    set_tenant_context_for_celery(client_id=args.client_id, user_id=args.user_id, cross_mode=False)
    db = SessionLocal()
    cred = (
        db.query(GmailCredential)
        .filter(
            GmailCredential.user_id == args.user_id,
            GmailCredential.client_id == args.client_id,
        )
        .first()
    )
    if cred is None:
        db.close()
        raise ToolError("Gmail credential not found for this user/client")
    if cred.status != GmailCredential.STATUS_ACTIVE:
        db.close()
        raise ToolError(f"Gmail credential status is '{cred.status}'; reconnect required")
    try:
        creds = get_or_refresh_access_token(db, cred.id)
    except Exception as e:
        db.close()
        raise ToolError(f"Gmail token refresh failed: {type(e).__name__}")
    return db, cred, build("gmail", "v1", credentials=creds)


def _audit_call(*, user_id: int, client_id: int, tool: str, details: dict) -> None:
    log_audit_event_strict(
        user_id=user_id,
        action="MCP_TOOL_CALL",
        resource_type="gmail_tool",
        resource_id=None,
        details={"tool": tool, "client_id": client_id, **details},
    )


def gmail_search_impl(args: GmailSearchArgs) -> dict:
    db, cred, service = _open_session_with_creds(args)
    try:
        try:
            resp = service.users().messages().list(
                userId="me", q=args.query, maxResults=args.max_results,
            ).execute()
        except HttpError as e:
            if e.resp.status == 401:
                handle_invalid_grant(db, cred.id)
                raise ToolError("Gmail credential is invalid; user must reconnect.")
            if e.resp.status in (429, 500, 503):
                raise ToolError("Gmail rate limited; retry shortly.")
            raise
        message_ids = [m["id"] for m in resp.get("messages", [])]
        _audit_call(
            user_id=args.user_id,
            client_id=args.client_id,
            tool="gmail_search",
            details={
                "query_sha256": hashlib.sha256(args.query.encode()).hexdigest(),
                "result_count": len(message_ids),
                "max_results": args.max_results,
            },
        )
        return {"message_ids": message_ids, "next_page_token": resp.get("nextPageToken")}
    finally:
        db.close()


def gmail_read_message_impl(args: GmailReadMessageArgs) -> dict:
    db, cred, service = _open_session_with_creds(args)
    try:
        try:
            msg = service.users().messages().get(
                userId="me", id=args.message_id, format="full",
            ).execute()
        except HttpError as e:
            if e.resp.status == 401:
                handle_invalid_grant(db, cred.id)
                raise ToolError("Gmail credential is invalid; user must reconnect.")
            if e.resp.status == 404:
                raise ToolError(f"Message not found: {args.message_id}")
            if e.resp.status in (429, 500, 503):
                raise ToolError("Gmail rate limited; retry shortly.")
            raise
        payload = msg.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
        sender = headers.get("From", "")
        subject = headers.get("Subject", "")
        date = headers.get("Date", "")

        body = _decode_body(payload)
        body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else None
        attachments = _extract_attachments(payload)
        attachment_ids = [a["attachment_id"] for a in attachments if a["attachment_id"]]
        _audit_call(
            user_id=args.user_id,
            client_id=args.client_id,
            tool="gmail_read_message",
            details={
                "message_id": args.message_id,
                "body_sha256": body_sha,
                "attachment_ids": attachment_ids,
                "attachment_count": len(attachments),
            },
        )
        return {
            "message_id": args.message_id,
            "sender": sender,
            "subject": subject,
            "date": date,
            "body": body,
            "attachments": attachments,
        }
    finally:
        db.close()


def gmail_list_attachments_impl(args: GmailListAttachmentsArgs) -> dict:
    db, cred, service = _open_session_with_creds(args)
    try:
        try:
            # Use full format to surface part metadata including attachmentId; metadata
            # format alone omits parts.body fields needed for the dedup chain.
            msg = service.users().messages().get(
                userId="me", id=args.message_id, format="full",
            ).execute()
        except HttpError as e:
            if e.resp.status == 401:
                handle_invalid_grant(db, cred.id)
                raise ToolError("Gmail credential is invalid; user must reconnect.")
            if e.resp.status == 404:
                raise ToolError(f"Message not found: {args.message_id}")
            raise
        attachments = _extract_attachments(msg.get("payload", {}))
        _audit_call(
            user_id=args.user_id,
            client_id=args.client_id,
            tool="gmail_list_attachments",
            details={
                "message_id": args.message_id,
                "attachment_count": len(attachments),
            },
        )
        return {"message_id": args.message_id, "attachments": attachments}
    finally:
        db.close()


def gmail_get_attachment_impl(args: GmailGetAttachmentArgs) -> dict:
    db, cred, service = _open_session_with_creds(args)
    try:
        try:
            att = service.users().messages().attachments().get(
                userId="me", messageId=args.message_id, id=args.attachment_id,
            ).execute()
        except HttpError as e:
            if e.resp.status == 401:
                handle_invalid_grant(db, cred.id)
                raise ToolError("Gmail credential is invalid; user must reconnect.")
            if e.resp.status == 404:
                raise ToolError(f"Attachment not found: {args.attachment_id}")
            raise
        data_b64 = att.get("data", "")
        raw = (
            base64.urlsafe_b64decode(data_b64 + "=" * (4 - len(data_b64) % 4))
            if data_b64
            else b""
        )
        sha = hashlib.sha256(raw).hexdigest() if raw else None
        _audit_call(
            user_id=args.user_id,
            client_id=args.client_id,
            tool="gmail_get_attachment",
            details={
                "message_id": args.message_id,
                "attachment_id": args.attachment_id,
                "size": len(raw),
                "sha256": sha,
            },
        )
        return {
            "message_id": args.message_id,
            "attachment_id": args.attachment_id,
            "size": len(raw),
            "data_base64": data_b64,
            "sha256": sha,
        }
    finally:
        db.close()


def gmail_list_labels_impl(args: GmailListLabelsArgs) -> dict:
    db, cred, service = _open_session_with_creds(args)
    try:
        try:
            resp = service.users().labels().list(userId="me").execute()
        except HttpError as e:
            if e.resp.status == 401:
                handle_invalid_grant(db, cred.id)
                raise ToolError("Gmail credential is invalid; user must reconnect.")
            raise
        labels = resp.get("labels", [])
        _audit_call(
            user_id=args.user_id,
            client_id=args.client_id,
            tool="gmail_list_labels",
            details={"label_count": len(labels)},
        )
        return {
            "labels": [
                {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type")}
                for lbl in labels
            ]
        }
    finally:
        db.close()


def gmail_modify_labels_impl(args: GmailModifyLabelsArgs) -> dict:
    proposed = set(args.add_labels) | set(args.remove_labels)
    forbidden = proposed - ALLOWED_SYSTEM_LABELS
    if forbidden:
        raise ToolError(
            f"gmail_modify_labels rejects non-system labels: {sorted(forbidden)}. "
            f"Allowed: {sorted(ALLOWED_SYSTEM_LABELS)}"
        )
    db, cred, service = _open_session_with_creds(args)
    try:
        try:
            resp = service.users().messages().modify(
                userId="me",
                id=args.message_id,
                body={
                    "addLabelIds": args.add_labels,
                    "removeLabelIds": args.remove_labels,
                },
            ).execute()
        except HttpError as e:
            if e.resp.status == 401:
                handle_invalid_grant(db, cred.id)
                raise ToolError("Gmail credential is invalid; user must reconnect.")
            raise
        _audit_call(
            user_id=args.user_id,
            client_id=args.client_id,
            tool="gmail_modify_labels",
            details={
                "message_id": args.message_id,
                "add_labels": args.add_labels,
                "remove_labels": args.remove_labels,
            },
        )
        return {
            "message_id": args.message_id,
            "label_ids": resp.get("labelIds", []),
        }
    finally:
        db.close()


def _decode_body(payload: dict) -> str:
    data = payload.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data + "=" * (4 - len(data) % 4)).decode(
            "utf-8", errors="replace"
        )
    for part in payload.get("parts", []) or []:
        mime = part.get("mimeType", "") or ""
        if mime.startswith("text/"):
            d = part.get("body", {}).get("data")
            if d:
                return base64.urlsafe_b64decode(d + "=" * (4 - len(d) % 4)).decode(
                    "utf-8", errors="replace"
                )
        # Recurse into multipart/* parts
        if mime.startswith("multipart/"):
            nested = _decode_body(part)
            if nested:
                return nested
    return ""


def _extract_attachments(payload: dict) -> list[dict]:
    out: list[dict] = []

    def _walk(part: dict) -> None:
        if part.get("filename"):
            out.append(
                {
                    "attachment_id": part.get("body", {}).get("attachmentId"),
                    "filename": part.get("filename"),
                    "size": part.get("body", {}).get("size"),
                    "mime_type": part.get("mimeType"),
                }
            )
        for sub in part.get("parts", []) or []:
            _walk(sub)

    _walk(payload)
    return out
