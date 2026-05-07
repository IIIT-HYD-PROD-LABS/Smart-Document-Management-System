"""Bill ORM — Phase 15 BILL-01..06.

Hybrid model per D-19: source_document_id is nullable. Bills with PDF
attachments link to documents.id; text-only billers (no attachment) leave
it NULL. source_email_id always refers back to the originating
gmail_message_log row.

Per D-23: parent_bill_id self-FK groups recurring bills. The partial
UNIQUE index ux_bills_recurrence_key on
(client_id, biller_name_normalized, account_number_last4) WHERE
account_number_last4 IS NOT NULL prevents accidental duplicates while
allowing bills without last4 to coexist (Pitfall 8).

Per D-22: reminder_count caps lifetime reminders at 3. Marking paid
stops further sends; un-marking does NOT reset the count.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Bill(Base):
    __tablename__ = "bills"

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"

    CATEGORIES = ("utility", "telecom", "credit_card", "subscription", "other")
    PAYMENT_METHODS = (
        "upi",
        "netbanking",
        "card",
        "cash",
        "cheque",
        "autopay",
        "other",
    )
    RECURRENCE_PERIODS = ("monthly", "quarterly", "annual")

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    biller_name = Column(String(255), nullable=False)
    biller_name_normalized = Column(
        String(255),
        nullable=False,
        index=True,
    )
    biller_category = Column(String(30), nullable=False)
    amount_due = Column(Numeric(14, 2), nullable=False)
    currency = Column(
        String(3),
        nullable=False,
        server_default="INR",
    )
    due_date = Column(Date, nullable=True)
    account_number_last4 = Column(String(4), nullable=True)
    payment_status = Column(
        String(20),
        nullable=False,
        server_default="pending",
    )
    is_recurring = Column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    recurrence_period = Column(String(20), nullable=True)
    parent_bill_id = Column(
        Integer,
        ForeignKey("bills.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_email_id = Column(
        BigInteger,
        ForeignKey("gmail_message_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    payment_date = Column(Date, nullable=True)
    payment_reference = Column(String(255), nullable=True)
    payment_method = Column(String(20), nullable=True)
    extraction_prompt_rev = Column(String(20), nullable=True)
    reminder_count = Column(
        Integer,
        nullable=False,
        server_default="0",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "biller_category IN ('utility','telecom','credit_card','subscription','other')",
            name="ck_bills_biller_category",
        ),
        CheckConstraint(
            "payment_status IN ('pending','paid','overdue')",
            name="ck_bills_payment_status",
        ),
        CheckConstraint(
            "recurrence_period IS NULL OR recurrence_period IN "
            "('monthly','quarterly','annual')",
            name="ck_bills_recurrence_period",
        ),
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('upi','netbanking','card','cash','cheque','autopay','other')",
            name="ck_bills_payment_method",
        ),
    )

    parent = relationship(
        "Bill",
        remote_side="Bill.id",
        foreign_keys=[parent_bill_id],
        back_populates="children",
    )
    children = relationship(
        "Bill",
        foreign_keys=[parent_bill_id],
        back_populates="parent",
    )
    source_document = relationship(
        "Document", foreign_keys=[source_document_id]
    )
    source_email = relationship(
        "GmailMessageLog", foreign_keys=[source_email_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Bill(id={self.id}, biller_name='{self.biller_name}', "
            f"amount_due={self.amount_due}, payment_status='{self.payment_status}')>"
        )
