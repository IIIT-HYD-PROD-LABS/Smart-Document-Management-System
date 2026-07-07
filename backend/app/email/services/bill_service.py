"""Bill service — BILL-03, BILL-04, BILL-05, BILL-06.

D-22 cool-downs:
  - reminder_count caps lifetime reminders at 3
  - mark_paid stops further reminders (also cancels pending APScheduler jobs)
  - un-marking paid does NOT reset reminder_count

D-23 recurrence:
  - parent_bill_id linking via (client_id, biller_name_normalized,
    account_number_last4) match — partial unique index ux_bills_recurrence_key
    enforces dedup at the DB layer for bills with last4 set (Pitfall 8).

B3 wiring (BILL-04):
  - schedule_bill_reminders registers 3 APScheduler jobs calling
    app.email.tasks.bill_reminder_task:fire_reminder with explicit kwargs
    matching VALID_ALERT_TYPES tiers (bill_t3 / bill_t1 / bill_overdue).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional

from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.compliance.services.scheduler import get_scheduler
from app.email.models.bill import Bill
from app.email.models.credential import GmailCredential
from app.email.models.message_log import GmailMessageLog
from app.services.audit_service import log_audit_event_strict

logger = logging.getLogger(__name__)

REMINDER_MAX_PER_BILL = 3


def _reminder_job_id(bill_id: int, tier: str) -> str:
    return f"gmail_bill_reminder_{bill_id}_{tier}"


def detect_recurrence(db: Session, bill: Bill) -> Optional[Bill]:
    if not bill.account_number_last4:
        return None
    return (
        db.query(Bill)
        .filter(
            Bill.client_id == bill.client_id,
            Bill.biller_name_normalized == bill.biller_name_normalized,
            Bill.account_number_last4 == bill.account_number_last4,
            Bill.id != bill.id,
        )
        .order_by(Bill.created_at.asc())
        .first()
    )


def upsert_bill(
    db: Session,
    *,
    credential: GmailCredential,
    source_email_log: GmailMessageLog,
    biller_name: str,
    biller_name_normalized: str,
    biller_category: str,
    amount_due: Decimal,
    due_date: Optional[date],
    account_number_last4: Optional[str],
    extraction_prompt_rev: str,
) -> Bill:
    parent = (
        db.query(Bill)
        .filter(
            Bill.client_id == credential.client_id,
            Bill.biller_name_normalized == biller_name_normalized,
            Bill.account_number_last4 == account_number_last4,
            Bill.parent_bill_id.is_(None),
        )
        .order_by(Bill.created_at.asc())
        .first()
        if account_number_last4
        else None
    )
    bill = Bill(
        client_id=credential.client_id,
        user_id=credential.user_id,
        biller_name=biller_name,
        biller_name_normalized=biller_name_normalized,
        biller_category=biller_category,
        amount_due=amount_due,
        due_date=due_date,
        account_number_last4=account_number_last4,
        payment_status=Bill.STATUS_PENDING,
        source_email_id=source_email_log.id,
        extraction_prompt_rev=extraction_prompt_rev,
        parent_bill_id=parent.id if parent is not None else None,
        is_recurring=parent is not None,
    )
    db.add(bill)
    db.flush()
    if parent is not None:
        parent.is_recurring = True
    db.commit()
    db.refresh(bill)
    schedule_bill_reminders(bill)
    return bill


async def mark_paid(
    db: AsyncSession,
    *,
    bill_id: int,
    payment_date: date,
    payment_reference: str,
    payment_method: str,
    user_id: int,
    client_id: int,
) -> Bill:
    # SEC1: explicit client_id scope in addition to RLS — defence-in-depth so
    # mark_paid cannot mutate a bill belonging to another tenant.
    bill = (
        await db.execute(
            select(Bill).where(Bill.id == bill_id, Bill.client_id == client_id)
        )
    ).scalar_one_or_none()
    if bill is None:
        raise ValueError(f"Bill {bill_id} not found")
    if payment_method not in Bill.PAYMENT_METHODS:
        raise ValueError(
            f"Invalid payment_method: {payment_method!r}. "
            f"Allowed: {sorted(Bill.PAYMENT_METHODS)}"
        )
    bill.payment_status = Bill.STATUS_PAID
    bill.payment_date = payment_date
    bill.payment_reference = payment_reference
    bill.payment_method = payment_method
    await db.commit()
    await db.refresh(bill)
    log_audit_event_strict(
        user_id=user_id,
        action="BILL_MARK_PAID",
        resource_type="bill",
        resource_id=bill_id,
        details={
            "amount": str(bill.amount_due),
            "biller": bill.biller_name,
            "payment_method": payment_method,
            "payment_date": payment_date.isoformat(),
            "reference": payment_reference,
        },
    )
    sched = get_scheduler()
    if sched is not None:
        for tier in ("bill_t3", "bill_t1", "bill_overdue"):
            try:
                sched.remove_job(_reminder_job_id(bill_id, tier))
            except Exception:
                pass
    return bill


def schedule_bill_reminders(bill: Bill) -> None:
    """B3 BILL-04 wiring — registers 3 APScheduler jobs calling
    app.email.tasks.bill_reminder_task:fire_reminder. Tier strings match
    VALID_ALERT_TYPES exactly: bill_t3, bill_t1, bill_overdue.
    """
    if bill.due_date is None:
        return
    if bill.reminder_count >= REMINDER_MAX_PER_BILL:
        return
    sched = get_scheduler()
    if sched is None:
        return
    today = date.today()
    tiers = [
        ("bill_t3", bill.due_date - timedelta(days=3)),
        ("bill_t1", bill.due_date - timedelta(days=1)),
        ("bill_overdue", bill.due_date + timedelta(days=1)),
    ]
    for tier, run_on in tiers:
        if run_on < today:
            continue
        run_dt = datetime.combine(run_on, time(9, 0, tzinfo=timezone.utc))
        sched.add_job(
            func="app.email.tasks.bill_reminder_task:fire_reminder",
            trigger=DateTrigger(run_date=run_dt),
            kwargs={"bill_id": bill.id, "tier": tier},
            id=_reminder_job_id(bill.id, tier),
            replace_existing=True,
            misfire_grace_time=86400,
        )


def fire_bill_reminder(bill_id: int, tier: str) -> None:
    """Legacy thin-wrapper kept for backwards compatibility with any
    pre-existing schedule registrations. Delegates to the canonical
    bill_reminder_task.fire_reminder (B3).
    """
    from app.email.tasks.bill_reminder_task import fire_reminder as _delegate

    _delegate(bill_id=bill_id, tier=tier)


async def list_bills(
    db: AsyncSession,
    *,
    client_id: int,
    status: Optional[str] = None,
    biller_category: Optional[str] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    is_recurring: Optional[bool] = None,
) -> list[Bill]:
    q = select(Bill).where(Bill.client_id == client_id)
    today = date.today()
    if status == "upcoming":
        q = q.where(
            Bill.due_date > today + timedelta(days=7),
            Bill.payment_status != Bill.STATUS_PAID,
        )
    elif status == "due_soon":
        q = q.where(
            Bill.due_date > today,
            Bill.due_date <= today + timedelta(days=7),
            Bill.payment_status != Bill.STATUS_PAID,
        )
    elif status == "overdue":
        q = q.where(
            Bill.due_date < today,
            Bill.payment_status != Bill.STATUS_PAID,
        )
    elif status == "paid":
        q = q.where(Bill.payment_status == Bill.STATUS_PAID)
    if biller_category:
        q = q.where(Bill.biller_category == biller_category)
    if due_before:
        q = q.where(Bill.due_date <= due_before)
    if due_after:
        q = q.where(Bill.due_date >= due_after)
    if is_recurring is not None:
        q = q.where(Bill.is_recurring == is_recurring)
    q = q.order_by(
        Bill.due_date.asc().nulls_last(),
        Bill.created_at.desc(),
    )
    return (await db.execute(q)).scalars().all()
