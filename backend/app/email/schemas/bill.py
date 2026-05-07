"""Bill Pydantic schemas — Phase 15 BILL-01..06.

PaymentMethod literal must match the bills.payment_method CHECK
constraint exactly. BillFilterParams.status uses UI-friendly buckets
(upcoming / due_soon / overdue / paid) — translated to the underlying
payment_status + due_date logic at the service layer.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

BillerCategory = Literal["utility", "telecom", "credit_card", "subscription", "other"]
PaymentStatus = Literal["pending", "paid", "overdue"]
PaymentMethod = Literal["upi", "netbanking", "card", "cash", "cheque", "autopay", "other"]
RecurrencePeriod = Literal["monthly", "quarterly", "annual"]
BillStatusBucket = Literal["upcoming", "due_soon", "overdue", "paid"]


class BillResponse(BaseModel):
    """Read-only Bill view for dashboard + detail pages."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    biller_name: str
    biller_category: str
    amount_due: Decimal
    currency: str
    due_date: Optional[date] = None
    account_number_last4: Optional[str] = None
    payment_status: str
    is_recurring: bool
    recurrence_period: Optional[str] = None
    parent_bill_id: Optional[int] = None
    source_document_id: Optional[int] = None
    source_email_id: Optional[int] = None
    payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    payment_method: Optional[str] = None
    created_at: datetime


class BillMarkPaidRequest(BaseModel):
    """Mark-as-paid payload — BILL-05."""

    payment_date: date
    payment_reference: str = Field(max_length=255)
    payment_method: PaymentMethod


class BillFilterParams(BaseModel):
    """GET /bills query params — BILL-03 dashboard filtering."""

    status: Optional[BillStatusBucket] = None
    biller_category: Optional[BillerCategory] = None
    due_before: Optional[date] = None
    due_after: Optional[date] = None
    is_recurring: Optional[bool] = None
