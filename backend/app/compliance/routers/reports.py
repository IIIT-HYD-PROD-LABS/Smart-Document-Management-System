"""On-demand report router — Phase 9 CLIENT-07.

POST /reports/health-summary — synchronous monthly health summary.

Permission: REPORT_EXPORT (compliance_head, ca_consultant, auditor, cfo per
the registry). REPORT_VIEW would also work for the read-only summary, but
REPORT_EXPORT is the more conservative choice — it keeps the gate closed
to roles that should not be able to extract per-client metrics.

Phase 11 will add scheduled monthly reports + Celery; Phase 9 ships
synchronous on-demand only (D-19).

Phase 13 v2.0.1 — CSV export endpoints retrofitted onto the three Phase 13
analytics aggregations + monthly health summary so users can persist a
point-in-time snapshot. Uses stdlib csv + StreamingResponse (no new deps);
PDF/Excel still deferred to v2.1.
"""
import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.compliance.services.report_service import (
    generate_health_summary,
    notice_volume_by_status,
    penalty_by_authority,
    response_time_distribution,
)
from app.database import get_db


def _csv_stream(headers: list[str], rows: list[dict]) -> io.StringIO:
    """Build an in-memory CSV. Returns a StringIO ready for StreamingResponse."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    return buf


def _csv_response(buf: io.StringIO, filename_prefix: str) -> StreamingResponse:
    """Wrap a StringIO as an attachment download with date-stamped filename.

    Explicit charset=utf-8 in the media_type so older Excel and BOM-sniffing
    importers don't misinterpret authority/status names with non-ASCII chars.
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{filename_prefix}_{today}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


# ──────────────────────────────────────────────────────────────────────
# Phase 13 v2.0 — analytics endpoints
# ──────────────────────────────────────────────────────────────────────

class AuthorityPenaltyRow(BaseModel):
    authority: str
    count: int
    total_penalty: float
    total_tax_demand: float


class StatusVolumeRow(BaseModel):
    status: str
    count: int


class ResponseTimeStats(BaseModel):
    p50: float
    p90: float
    p95: float
    mean: float
    count: int


@router.get(
    "/penalty-by-authority",
    response_model=list[AuthorityPenaltyRow],
    summary="Penalty + tax-demand totals grouped by authority",
)
def penalty_by_authority_endpoint(
    window_days: int = 90,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_VIEW)
    ),
    db: Session = Depends(get_db),
):
    rows = penalty_by_authority(
        db, client_id=membership.client_id, window_days=window_days
    )
    return [AuthorityPenaltyRow(**r) for r in rows]


@router.get(
    "/notice-volume-by-status",
    response_model=list[StatusVolumeRow],
    summary="Notice counts grouped by status",
)
def notice_volume_by_status_endpoint(
    window_days: int = 90,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_VIEW)
    ),
    db: Session = Depends(get_db),
):
    rows = notice_volume_by_status(
        db, client_id=membership.client_id, window_days=window_days
    )
    return [StatusVolumeRow(**r) for r in rows]


@router.get(
    "/response-time",
    response_model=ResponseTimeStats,
    summary="Response time percentile distribution (resolved/submitted notices)",
)
def response_time_endpoint(
    window_days: int = 90,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_VIEW)
    ),
    db: Session = Depends(get_db),
):
    return ResponseTimeStats(
        **response_time_distribution(
            db, client_id=membership.client_id, window_days=window_days
        )
    )


# ──────────────────────────────────────────────────────────────────────
# Phase 13 v2.0.1 — CSV export endpoints
#
# REPORT_EXPORT (not REPORT_VIEW) gates these. Mirrors the conservative
# scope on /health-summary — viewing aggregates in the dashboard is okay
# for legal_team/finance_team, but extracting them as a file artifact is
# scoped to compliance_head/ca_consultant/auditor/cfo per the registry.
# ──────────────────────────────────────────────────────────────────────


@router.get(
    "/penalty-by-authority/export",
    summary="Download penalty-by-authority aggregation as CSV",
)
def export_penalty_by_authority(
    window_days: int = 90,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_EXPORT)
    ),
    db: Session = Depends(get_db),
):
    rows = penalty_by_authority(
        db, client_id=membership.client_id, window_days=window_days
    )
    buf = _csv_stream(
        headers=["authority", "count", "total_penalty", "total_tax_demand"],
        rows=rows,
    )
    return _csv_response(buf, "penalty_by_authority")


@router.get(
    "/notice-volume-by-status/export",
    summary="Download notice-volume-by-status aggregation as CSV",
)
def export_notice_volume_by_status(
    window_days: int = 90,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_EXPORT)
    ),
    db: Session = Depends(get_db),
):
    rows = notice_volume_by_status(
        db, client_id=membership.client_id, window_days=window_days
    )
    buf = _csv_stream(headers=["status", "count"], rows=rows)
    return _csv_response(buf, "notice_volume_by_status")


@router.get(
    "/response-time/export",
    summary="Download response-time percentile stats as CSV",
)
def export_response_time(
    window_days: int = 90,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_EXPORT)
    ),
    db: Session = Depends(get_db),
):
    stats = response_time_distribution(
        db, client_id=membership.client_id, window_days=window_days
    )
    # Three columns so units are explicit. Earlier shape mixed `days` (float
    # percentile) and `count` (integer sample size) under a single "days"
    # header which was semantically wrong: the count is not a day-value.
    buf = _csv_stream(
        headers=["metric", "value", "unit"],
        rows=[
            {"metric": "p50_median", "value": stats["p50"], "unit": "days"},
            {"metric": "p90", "value": stats["p90"], "unit": "days"},
            {"metric": "p95", "value": stats["p95"], "unit": "days"},
            {"metric": "mean", "value": stats["mean"], "unit": "days"},
            {"metric": "sample_count", "value": stats["count"], "unit": "notices"},
        ],
    )
    return _csv_response(buf, "response_time_distribution")


@router.post(
    "/health-summary/export",
    summary="Download monthly health summary as CSV",
)
def export_health_summary(
    payload: HealthSummaryRequest,
    db: Session = Depends(get_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_EXPORT)
    ),
):
    """CSV form of the monthly health summary — same data as the JSON endpoint."""
    try:
        result = generate_health_summary(
            db=db,
            client_id=payload.client_id,
            month=payload.month,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    metrics = result.get("metrics", {})
    rows = [
        {"client_id": result.get("client_id"), "month": result.get("month"), "metric": k, "value": v}
        for k, v in metrics.items()
    ]
    buf = _csv_stream(headers=["client_id", "month", "metric", "value"], rows=rows)
    month_slug = (payload.month or "").replace("-", "")
    return _csv_response(buf, f"health_summary_{month_slug}")
