"""On-demand report router — Phase 9 CLIENT-07.

POST /reports/health-summary — synchronous monthly health summary.

Permission: REPORT_EXPORT (compliance_head, ca_consultant, auditor, cfo per
the registry). REPORT_VIEW would also work for the read-only summary, but
REPORT_EXPORT is the more conservative choice — it keeps the gate closed
to roles that should not be able to extract per-client metrics.

Phase 11 will add scheduled monthly reports + Celery; Phase 9 ships
synchronous on-demand only (D-19).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.compliance.services.report_service import generate_health_summary
from app.database import get_db


router = APIRouter(prefix="/reports", tags=["compliance-reports"])


class HealthSummaryRequest(BaseModel):
    client_id: int
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class HealthSummaryMetrics(BaseModel):
    notices_received: int
    notices_resolved: int
    outstanding: int


class HealthSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    client_id: int
    month: str
    metrics: HealthSummaryMetrics
    summary_html: str


@router.post("/health-summary", response_model=HealthSummaryResponse)
def health_summary(
    payload: HealthSummaryRequest,
    db: Session = Depends(get_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_EXPORT)
    ),
):
    """Generate a monthly compliance health summary — CLIENT-07."""
    try:
        return generate_health_summary(
            db=db,
            client_id=payload.client_id,
            month=payload.month,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
