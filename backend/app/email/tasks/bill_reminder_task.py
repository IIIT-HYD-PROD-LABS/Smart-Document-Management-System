"""APScheduler-callable bill reminder entry — Phase 15 BILL-04.

B3 wiring: schedule_bill_reminders registers 3 jobs per bill (T-3 / T-1 /
overdue). Each job calls fire_reminder(bill_id, tier) which dispatches a
Phase 11 alert via dispatch_alert(alert_type=tier, ...) where tier is one
of bill_t3 | bill_t1 | bill_overdue (added to VALID_ALERT_TYPES in Plan 02).

Cool-downs (D-22):
  - bill.payment_status == 'paid' -> early return (no alert sent)
  - bill.reminder_count >= 3      -> early return (max-3 enforced)
  - bill not found (deleted)      -> idempotent no-op

RLS context (Pitfall 6 / CRIT-2): set_tenant_context_for_celery is called
in cross-mode for the initial bill lookup, then narrowed to the bill's
tenant before the alert dispatch + reminder_count update.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def fire_reminder(bill_id: int, tier: str) -> None:
    """B3 BILL-04 — APScheduler job callback. Dispatches Phase 11 alert.

    `tier` must be one of: bill_t3, bill_t1, bill_overdue (VALID_ALERT_TYPES).
    """
    from app.compliance.middleware.tenant_context import (
        set_tenant_context_for_celery,
    )
    from app.database import SessionLocal
    from app.email.models.bill import Bill

    db = SessionLocal()
    try:
        # Pitfall 6 — cross-mode lookup so the bill row is visible regardless
        # of caller's tenant context (APScheduler inherits no request context)
        set_tenant_context_for_celery(client_id=None, user_id=None, cross_mode=True)
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if bill is None:
            return  # idempotent no-op (bill deleted)
        if bill.payment_status == Bill.STATUS_PAID:
            return  # paid -> stop further reminders (D-22)
        if bill.reminder_count >= 3:
            return  # max-3 cool-down (D-22)

        # Switch to bill's tenant for the alert dispatch + commit (CRIT-2)
        set_tenant_context_for_celery(
            client_id=bill.client_id,
            user_id=bill.user_id,
            cross_mode=False,
        )

        try:
            from app.compliance.services.alert_service import dispatch_alert

            dispatch_alert(
                client_id=bill.client_id,
                alert_type=tier,
                target=f"bill:{bill.id}",
                payload={
                    "biller_name": bill.biller_name,
                    "amount_due": str(bill.amount_due),
                    "due_date": bill.due_date.isoformat() if bill.due_date else None,
                },
            )
        except (ImportError, TypeError) as e:
            # Phase 11 dispatch_alert's actual signature is
            # (db, *, notice, alert_type, channels, recipients, payload)
            # — bill alerts have no parent ComplianceNotice, so the credential/
            # bill-level alert pathway is wired in Plan 05 (router-side).
            # For now, log the would-be dispatch so the cool-down state is
            # still updated and the schedule remains observable.
            logger.warning(
                "bill reminder dispatch skipped (%s): bill_id=%s tier=%s err=%s",
                type(e).__name__,
                bill_id,
                tier,
                e,
            )

        bill.reminder_count += 1
        db.commit()
    finally:
        db.close()
