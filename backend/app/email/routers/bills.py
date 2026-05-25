"""Bill router — Phase 15 BILL-03, BILL-05, BILL-06.

Endpoints:
  GET  /api/email/bills?status=&biller_category=&due_before=&due_after=&is_recurring=
  GET  /api/email/bills/{id}
  POST /api/email/bills/{id}/mark-paid
  POST /api/email/bills/bulk-mark-paid

Service-layer mutation pattern (Phase 9 D-D): the router never mutates
the Bill ORM directly. Mark-paid + bulk go through bill_service.mark_paid
which writes the BILL_MARK_PAID audit row and cancels APScheduler jobs.

Bulk uses per-row SAVEPOINT (begin_nested) so a single failure does not
roll back the whole batch — mirrors Phase 9 LIFE-08 partial-failure
contract: results[] + summary{ok, failed}.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.email.models.bill import Bill
from app.email.schemas.bill import (
    BillMarkPaidRequest,
    BillResponse,
    PaymentMethod,
)
from app.email.services.bill_service import list_bills, mark_paid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bills"])


_VALID_STATUS = {"upcoming", "due_soon", "overdue", "paid"}


@router.get("/bills", response_model=list[BillResponse])
def get_bills(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    biller_category: Optional[str] = Query(default=None),
    due_before: Optional[date] = Query(default=None),
    due_after: Optional[date] = Query(default=None),
    is_recurring: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """List bills for the active client (BILL-03 dashboard).

    The `status` query parameter is a UI-friendly bucket name translated
    to the underlying payment_status + due_date logic at the service layer.
    """
    if status_filter is not None and status_filter not in _VALID_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status: {status_filter!r}. "
                f"Allowed: {sorted(_VALID_STATUS)}"
            ),
        )
    return list_bills(
        db,
        client_id=membership.client_id,
        status=status_filter,
        biller_category=biller_category,
        due_before=due_before,
        due_after=due_after,
        is_recurring=is_recurring,
    )


@router.get("/bills/{bill_id}", response_model=BillResponse)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Return a single bill by id. RLS scopes to the active client."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found",
        )
    return bill


@router.post("/bills/{bill_id}/mark-paid", response_model=BillResponse)
def mark_bill_paid(
    bill_id: int,
    body: BillMarkPaidRequest,
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Mark a bill paid (BILL-05).

    Delegates to bill_service.mark_paid — writes BILL_MARK_PAID audit
    row and cancels pending APScheduler reminder jobs.
    """
    try:
        return mark_paid(
            db,
            bill_id=bill_id,
            payment_date=body.payment_date,
            payment_reference=body.payment_reference,
            payment_method=body.payment_method,
            user_id=membership.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/bills/bulk-mark-paid")
def bulk_mark_bills_paid(
    ids: list[int] = Body(..., embed=True),
    payment_date: date = Body(..., embed=True),
    payment_reference: str = Body(..., embed=True),
    payment_method: PaymentMethod = Body(..., embed=True),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Bulk mark-as-paid with per-row error isolation.

    Each call to `mark_paid` is atomic and commits its own row. A row that
    raises (bill missing, invalid payment_method) leaves the database
    untouched for that row and is reported in `results` so the caller can
    surface partial failure to the user. The loop continues past failures.

        {
          "results": [{"id": 1, "status": "ok"}, ...],
          "summary": {"ok": N, "failed": M}
        }

    Note: the prior implementation wrapped each call in `db.begin_nested()`
    to act as a SAVEPOINT, but `mark_paid` itself issues `db.commit()` —
    under SQLAlchemy 2.x that ends the outer transaction context and raises
    `InvalidRequestError`. We rely on `mark_paid`'s own commit per row.
    """
    results: list[dict] = []
    ok = 0
    failed = 0
    for bid in ids:
        try:
            mark_paid(
                db,
                bill_id=bid,
                payment_date=payment_date,
                payment_reference=payment_reference,
                payment_method=payment_method,
                user_id=membership.user_id,
            )
            results.append({"id": bid, "status": "ok"})
            ok += 1
        except Exception as e:  # noqa: BLE001 — partial-failure semantics
            db.rollback()
            # Expire all ORM identity-map entries after rollback so a stale
            # Bill object from a prior successful iteration cannot resurface
            # as expired-but-still-cached state in the next loop iteration.
            db.expire_all()
            # Log the full exception server-side; surface only the exception
            # class name to the API caller so we do not leak SQL fragments,
            # bound parameters, or other internals (CodeQL py/stack-trace-exposure).
            logger.exception("bills.mark_paid_bulk failed for bill_id=%d", int(bid))
            results.append(
                {
                    "id": bid,
                    "status": "failed",
                    "error": type(e).__name__,
                }
            )
            failed += 1
    return {
        "results": results,
        "summary": {"ok": ok, "failed": failed},
    }
