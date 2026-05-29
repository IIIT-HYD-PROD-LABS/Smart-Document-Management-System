"""GmailCredential CRUD — Phase 15 EMAIL-01, EMAIL-10.

Endpoints:
  GET    /api/email/credentials             -> list (RLS-scoped)
  PATCH  /api/email/credentials/{id}        -> update cadence_minutes
  DELETE /api/email/credentials/{id}        -> disable + remove scanner job

Pattern (Phase 9 D-D): routers do not mutate ORM directly except for
trivial field updates already gated by Pydantic schemas. Cadence change
also reschedules the APScheduler job to honour the new interval.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.email.models.credential import GmailCredential
from app.email.schemas.credential import (
    GmailCredentialResponse,
    GmailCredentialUpdate,
)
from app.email.services.scanner_service import schedule_gmail_scan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gmail-credentials"])


@router.get("/credentials", response_model=list[GmailCredentialResponse])
def list_credentials(
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """List Gmail credentials scoped to the active client (RLS enforces).

    Phase 9 RLS automatically filters by the X-Client-Id ContextVar, so
    no explicit client_id filter is needed here. The order surfaces the
    most-recently-connected credential first.
    """
    return (
        db.query(GmailCredential)
        .order_by(GmailCredential.created_at.desc())
        .all()
    )


@router.patch(
    "/credentials/{credential_id}",
    response_model=GmailCredentialResponse,
)
def update_credential(
    credential_id: int,
    body: GmailCredentialUpdate,
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Update credential cadence_minutes (5..1440 enforced by Pydantic)."""
    # SEC2: explicit client_id ownership check in addition to RLS — prevents a
    # cross-tenant credential mutation if the RLS context is misset.
    cred = (
        db.query(GmailCredential)
        .filter(
            GmailCredential.id == credential_id,
            GmailCredential.client_id == membership.client_id,
        )
        .first()
    )
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    if (
        body.cadence_minutes is not None
        and body.cadence_minutes != cred.cadence_minutes
    ):
        cred.cadence_minutes = body.cadence_minutes
        db.commit()
        db.refresh(cred)
        # Reschedule existing APScheduler job at the new interval.
        # replace_existing=True is set inside schedule_gmail_scan so this
        # is safe to call without first removing the old job.
        try:
            schedule_gmail_scan(cred.id, cadence_minutes=body.cadence_minutes)
        except Exception:  # noqa: BLE001 — non-fatal; cadence still saved
            # int() cast defends against CodeQL py/log-injection: even though
            # FastAPI types credential_id as int, the cast pins the value as
            # purely numeric in the log line so the static analyzer agrees.
            logger.exception(
                "schedule_gmail_scan_failed credential_id=%d", int(credential_id)
            )
    return cred


@router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Disable the credential and remove its scanner job (EMAIL-10).

    Soft-disable preserves the row for audit + provenance; hard-delete
    would orphan source_email_id FKs from already-ingested
    Documents/ComplianceNotices.
    """
    # SEC2: explicit client_id ownership check in addition to RLS.
    cred = (
        db.query(GmailCredential)
        .filter(
            GmailCredential.id == credential_id,
            GmailCredential.client_id == membership.client_id,
        )
        .first()
    )
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    cred.status = GmailCredential.STATUS_DISABLED
    db.commit()
    # Remove the APScheduler job so further polls don't run.
    try:
        from app.compliance.services.scheduler import get_scheduler

        sched = get_scheduler()
        if sched is not None:
            try:
                sched.remove_job(f"gmail_scan_{credential_id}")
            except Exception:  # noqa: BLE001 — job may already be absent
                pass
    except Exception:  # noqa: BLE001 — scheduler unavailable is non-fatal
        logger.exception(
            "scheduler_remove_failed credential_id=%d", int(credential_id)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
