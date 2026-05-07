"""GmailFetchLog read-only listing — Phase 15 EMAIL-07.

Endpoint:
  GET /api/email/credentials/{cred_id}/activity?limit=50

Read-only. Three-state status (SUCCESS_EMPTY / SUCCESS_WITH_RESULTS /
FETCH_FAILED) lets the UI render a per-credential health indicator.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.email.models.credential import GmailCredential
from app.email.models.fetch_log import GmailFetchLog
from app.email.schemas.fetch_log import GmailFetchLogResponse

router = APIRouter(tags=["gmail-activity"])


@router.get(
    "/credentials/{credential_id}/activity",
    response_model=list[GmailFetchLogResponse],
)
def list_fetch_log(
    credential_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Return the last N fetch-log rows for a credential, newest first."""
    cred = (
        db.query(GmailCredential)
        .filter(GmailCredential.id == credential_id)
        .first()
    )
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    return (
        db.query(GmailFetchLog)
        .filter(GmailFetchLog.credential_id == credential_id)
        .order_by(GmailFetchLog.started_at.desc())
        .limit(limit)
        .all()
    )
