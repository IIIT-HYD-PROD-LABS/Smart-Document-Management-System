"""Phase 11 alert router — pending + rules read/upsert surface.

Endpoints under /api/compliance/alerts (mounted in main.py):

  GET   /pending            NOTICE_VIEW   list queued/failed alerts
  GET   /rules              NOTICE_VIEW   list alert rules for active client
  PUT   /rules              NOTICE_REVIEW upsert a per-client per-type rule

Deferred to v2.0.1 (intentionally not implemented yet):
  - GET  /log                — full alert delivery log read; defer until
                               we ship the operator dashboard surface
  - POST /retry/{alert_id}   — retry a failed alert; today operators can
                               flip delivery_status manually + re-fire
                               via dispatch_notice_alert.delay()
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.compliance.dependencies import (
    is_cross_client_mode,
    require_compliance_permission,
)
from app.compliance.models.alert import NoticeAlertLog, NoticeAlertRule
from app.compliance.models.membership import ClientMembership
from app.compliance.services.alert_service import list_pending_alerts
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db

router = APIRouter(prefix="/alerts", tags=["compliance-alerts"])


class AlertLogOut(BaseModel):
    id: int
    notice_id: int
    client_id: int
    alert_type: str
    recipient_user_id: Optional[int]
    recipient_email: Optional[str]
    channel: str
    delivery_status: str
    provider_message_id: Optional[str]
    error: Optional[str]
    created_at: str
    delivered_at: Optional[str]


class AlertRuleOut(BaseModel):
    id: int
    client_id: int
    notice_type_id: Optional[int]
    rules: dict
    is_active: bool


class AlertRulePayload(BaseModel):
    notice_type_id: Optional[int] = None
    rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


@router.get(
    "/pending",
    summary="List queued or failed alerts for the active client",
)
def get_pending_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    client_id = None if is_cross_client_mode() else membership.client_id
    items, total = list_pending_alerts(
        db, client_id=client_id, page=page, page_size=page_size
    )
    return {
        "items": [
            {
                "id": r.id,
                "notice_id": r.notice_id,
                "client_id": r.client_id,
                "alert_type": r.alert_type,
                "recipient_user_id": r.recipient_user_id,
                "recipient_email": r.recipient_email,
                "channel": r.channel,
                "delivery_status": r.delivery_status,
                "provider_message_id": r.provider_message_id,
                "error": r.error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
            }
            for r in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/rules",
    response_model=list[AlertRuleOut],
    summary="List alert rules for the active client",
)
def list_rules(
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(NoticeAlertRule)
        .filter(NoticeAlertRule.client_id == membership.client_id)
        .all()
    )
    return [
        AlertRuleOut(
            id=r.id,
            client_id=r.client_id,
            notice_type_id=r.notice_type_id,
            rules=r.rules or {},
            is_active=bool(r.is_active),
        )
        for r in rows
    ]


@router.put(
    "/rules",
    response_model=AlertRuleOut,
    summary="Create or update an alert rule for the active client",
)
def upsert_rule(
    body: AlertRulePayload,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_REVIEW)
    ),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(NoticeAlertRule)
        .filter(
            NoticeAlertRule.client_id == membership.client_id,
            NoticeAlertRule.notice_type_id == body.notice_type_id,
        )
        .first()
    )
    if existing is None:
        existing = NoticeAlertRule(
            client_id=membership.client_id,
            notice_type_id=body.notice_type_id,
            rules=body.rules,
            is_active=body.is_active,
        )
        db.add(existing)
    else:
        existing.rules = body.rules
        existing.is_active = body.is_active

    db.commit()
    db.refresh(existing)
    return AlertRuleOut(
        id=existing.id,
        client_id=existing.client_id,
        notice_type_id=existing.notice_type_id,
        rules=existing.rules or {},
        is_active=bool(existing.is_active),
    )
