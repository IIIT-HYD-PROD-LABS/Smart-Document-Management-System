"""Phase 12 evidence-attachment service — link DMS Documents to ComplianceNotices.

Single point of mutation for `notice_evidence_attachments`. PDF merge with
TOC is deferred to v2.1 (RESEARCH-FINAL §1).

H-C second hardening — `attach_document` now requires the requesting user
to own the document OR have an explicit `DocumentPermission` row. Without
this check, any user with `NOTICE_ATTACH_EVIDENCE` could attach any
user's documents as evidence on their own notices (documents has no
compliance RLS).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.compliance.models.notice import ComplianceNotice
from app.compliance.models.response import NoticeEvidenceAttachment
from app.compliance.services.activity_service import log_activity
from app.models.document import Document
from app.services.audit_service import log_audit_event_strict as log_audit_event


class DocumentAccessDenied(PermissionError):
    """H-C — caller does not own or have shared access to the requested
    document. Routers map this to HTTP 403."""


def attach_document(
    db: Session,
    *,
    notice: ComplianceNotice,
    document_id: int,
    user_id: Optional[int],
    description: Optional[str] = None,
    display_order: int = 0,
) -> NoticeEvidenceAttachment:
    """Attach a Document to the notice as evidence.

    Idempotent: re-attaching the same document is a no-op (UNIQUE constraint
    enforces this; we return the existing row instead of raising).

    H-C second hardening — verifies caller owns the document or has a
    DocumentPermission row. Raises DocumentAccessDenied otherwise.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    if user_id is not None:
        is_owner = int(document.user_id) == int(user_id)
        if not is_owner:
            from app.models.document_permission import DocumentPermission
            shared = (
                db.query(DocumentPermission)
                .filter(
                    DocumentPermission.document_id == document_id,
                    DocumentPermission.user_id == user_id,
                )
                .first()
            )
            if shared is None:
                raise DocumentAccessDenied(
                    f"User {user_id} cannot attach document {document_id} as "
                    "evidence: not owner and no DocumentPermission row exists"
                )

    existing = (
        db.query(NoticeEvidenceAttachment)
        .filter(
            NoticeEvidenceAttachment.notice_id == notice.id,
            NoticeEvidenceAttachment.document_id == document_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    row = NoticeEvidenceAttachment(
        notice_id=notice.id,
        document_id=document_id,
        client_id=notice.client_id,
        display_order=display_order,
        description=description,
        added_by_user_id=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_activity(
        db,
        notice_id=notice.id,
        user_id=user_id,
        type="file_attached",
        details={
            "source": "evidence_attachment",
            "document_id": document_id,
            "description": description,
        },
    )
    db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_evidence_attached",
        resource_type="NoticeEvidenceAttachment",
        resource_id=row.id,
        details={
            "notice_id": notice.id,
            "document_id": document_id,
        },
    )
    return row


def detach_document(
    db: Session,
    *,
    notice: ComplianceNotice,
    document_id: int,
    user_id: Optional[int],
) -> bool:
    """Remove an evidence attachment. Returns True if removed, False if not present.

    R6 — symmetric with attach_document: the caller must own the document
    or hold a DocumentPermission row before they can detach it as evidence.
    Without this, attach was guarded but detach was not, letting any holder
    of NOTICE_ATTACH_EVIDENCE strip another user's document off a notice.
    """
    if user_id is not None:
        document = db.get(Document, document_id)
        if document is not None and int(document.user_id) != int(user_id):
            from app.models.document_permission import DocumentPermission
            shared = (
                db.query(DocumentPermission)
                .filter(
                    DocumentPermission.document_id == document_id,
                    DocumentPermission.user_id == user_id,
                )
                .first()
            )
            if shared is None:
                raise DocumentAccessDenied(
                    f"User {user_id} cannot detach document {document_id} from "
                    "evidence: not owner and no DocumentPermission row exists"
                )

    existing = (
        db.query(NoticeEvidenceAttachment)
        .filter(
            NoticeEvidenceAttachment.notice_id == notice.id,
            NoticeEvidenceAttachment.document_id == document_id,
        )
        .first()
    )
    if existing is None:
        return False

    attachment_id = existing.id
    db.delete(existing)
    db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_evidence_detached",
        resource_type="NoticeEvidenceAttachment",
        resource_id=attachment_id,
        details={"notice_id": notice.id, "document_id": document_id},
    )
    return True


def list_attachments(
    db: Session, *, notice_id: int, client_id: Optional[int] = None
) -> list[NoticeEvidenceAttachment]:
    """List evidence rows for a notice.

    R4 — when `client_id` is supplied (the router passes the parent
    notice's client_id, already tenant-checked) it is added as a
    defense-in-depth filter so an RLS regression cannot surface another
    tenant's attachment rows. Defaults to None for RLS-bypassed callers.
    """
    q = db.query(NoticeEvidenceAttachment).filter(
        NoticeEvidenceAttachment.notice_id == notice_id
    )
    if client_id is not None:
        q = q.filter(NoticeEvidenceAttachment.client_id == client_id)
    return q.order_by(
        NoticeEvidenceAttachment.display_order,
        NoticeEvidenceAttachment.created_at,
    ).all()
