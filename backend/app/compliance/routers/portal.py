"""Portal export import — Phase B of the notice pipeline roadmap.

Users download PDFs from GST / IT / MCA / SEBI / RBI portals, then upload
them here. We never scrape gov sites. Files reuse the Document + Celery
OCR pipeline and optionally create a ComplianceNotice (source=portal).
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_async_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.storage_service import save_file
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal", tags=["compliance-portal"])

PortalKind = Literal["gst_portal", "it_efiling", "mca", "sebi", "rbi", "other"]

PORTAL_AUTHORITY: dict[str, str] = {
    "gst_portal": "GST",
    "it_efiling": "IT",
    "mca": "MCA",
    "sebi": "SEBI",
    "rbi": "RBI",
    "other": "GST",
}

PORTAL_LABELS: dict[str, str] = {
    "gst_portal": "GST portal export",
    "it_efiling": "Income Tax e-filing export",
    "mca": "MCA portal export",
    "sebi": "SEBI portal export",
    "rbi": "RBI portal export",
    "other": "Other gov portal export",
}


class PortalImportResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    notice_id: Optional[int] = None
    portal: str
    authority: Optional[str] = None
    notice_number: Optional[str] = None
    source: str = "portal"
    detail: str = "queued_for_ocr"


@router.get("/kinds")
async def list_portal_kinds(
    _membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
):
    """Return supported portal labels for the import UI."""
    return [
        {"id": k, "label": PORTAL_LABELS[k], "default_authority": PORTAL_AUTHORITY[k]}
        for k in PORTAL_AUTHORITY
    ]


@router.post(
    "/import",
    response_model=PortalImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_portal_export(
    file: UploadFile = File(...),
    portal: PortalKind = Form("gst_portal"),
    create_notice: bool = Form(True),
    authority: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_CREATE)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Upload a portal-exported document into the unified notice pipeline.

    1. Validate + store bytes (same as notice upload).
    2. Create Document with source=portal.
    3. Optionally create ComplianceNotice (source=portal, placeholder number).
    4. Queue process_document_task → OCR → field extract → intake.
    """
    # Reuse notice upload validators without circular import cost.
    from app.compliance.routers.notices import _read_validated_upload

    if portal not in PORTAL_AUTHORITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown portal kind: {portal}",
        )

    resolved_authority = (authority or PORTAL_AUTHORITY[portal]).upper()
    if resolved_authority not in {"GST", "IT", "MCA", "RBI", "SEBI"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="authority must be one of GST, IT, MCA, RBI, SEBI",
        )

    contents, ext = _read_validated_upload(file)
    file_path, s3_url = save_file(
        file_bytes=contents,
        original_filename=file.filename or f"portal-export.{ext}",
    )

    short = hashlib.sha256(contents).hexdigest()[:10]
    original = file.filename or f"portal-{short}.{ext}"

    doc = Document(
        user_id=current_user.id,
        filename=file_path.split("/")[-1] if file_path else original,
        original_filename=original,
        file_type=ext,
        file_size=len(contents),
        file_path=file_path,
        s3_url=s3_url,
        status=DocumentStatus.PENDING,
        source="portal",
    )
    db.add(doc)
    # The Document INSERT is emitted by this flush (we need doc.id below), so a
    # duplicate (user_id, original_filename) raises here, not at the later commit.
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        if file_path:
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with this filename was already imported",
        )
    doc_id = int(doc.id)
    user_id = int(current_user.id)

    notice_id: Optional[int] = None
    notice_number: Optional[str] = None

    if create_notice:
        notice_number = f"PORTAL-{portal[:3].upper()}-{short}"[:100]
        notice = ComplianceNotice(
            client_id=membership.client_id,
            notice_number=notice_number,
            authority=resolved_authority,
            status="received",
            source="portal",
            document_id=doc_id,
            created_by_user_id=user_id,
            received_date=date.today(),
        )
        db.add(notice)
        await db.flush()
        notice_id = int(notice.id)
        doc.notice_id = notice_id

        try:
            from app.compliance.services.activity_service import log_activity

            log_activity(
                db,  # type: ignore[arg-type]
                notice_id=notice_id,
                user_id=user_id,
                type="file_attached",
                details={
                    "source": "portal",
                    "portal": portal,
                    "document_id": doc_id,
                    "filename": original,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("portal activity log failed: %s", exc)

        try:
            from app.services.audit_service import log_audit_event_strict

            log_audit_event_strict(
                user_id=user_id,
                action="NOTICE_PORTAL_IMPORTED",
                resource_type="compliance_notice",
                resource_id=notice_id,
                details={
                    "portal": portal,
                    "document_id": doc_id,
                    "authority": resolved_authority,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("portal audit failed: %s", exc)

    await db.commit()
    await db.refresh(doc)

    # OCR + classify + (if notice) field fill + intake.
    try:
        from app.tasks.document_tasks import process_document_task

        task = process_document_task.delay(int(doc.id))
        doc.celery_task_id = task.id
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("portal celery dispatch failed: %s", exc)

    return PortalImportResult(
        document_id=int(doc.id),
        notice_id=notice_id,
        portal=portal,
        authority=resolved_authority if create_notice else None,
        notice_number=notice_number,
        detail="queued_for_ocr",
    )


@router.get("/health")
async def portal_pipeline_health(
    _membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
):
    """Lightweight status for the portal import surface."""
    return {
        "status": "ok",
        "pipeline": "ingest→ocr→extract→intake→calendar/audit/reports",
        "scraping": False,
        "supported_portals": list(PORTAL_AUTHORITY.keys()),
        "note": (
            "Upload portal-exported PDFs only. Official GSP/API connectors "
            "are a later phase; browser scraping of gov sites is not supported."
        ),
    }
