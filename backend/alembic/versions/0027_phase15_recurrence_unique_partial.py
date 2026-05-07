"""phase15: scope bills recurrence unique to series heads (parent_bill_id IS NULL)

The original 0025 partial unique on
``(client_id, biller_name_normalized, account_number_last4)``
where ``account_number_last4 IS NOT NULL`` blocked the recurring-bill
series from accumulating subsequent monthly entries — the second
month's bill collided with the first's row before
``bill_service.upsert_bill`` could attach ``parent_bill_id``. The intent
is "one head per series"; children carry ``parent_bill_id`` and must be
exempt from the unique. Replaces the constraint with a partial unique
that only fires for series heads.

Revision ID: 0027_phase15_recurrence_unique_partial
Revises: 0026_apscheduler_jobs_table
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0027_phase15_recurrence_unique_partial"
down_revision = "0026_apscheduler_jobs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ux_bills_recurrence_key", table_name="bills")
    op.create_index(
        "ux_bills_recurrence_key",
        "bills",
        ["client_id", "biller_name_normalized", "account_number_last4"],
        unique=True,
        postgresql_where=sa.text(
            "account_number_last4 IS NOT NULL AND parent_bill_id IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ux_bills_recurrence_key", table_name="bills")
    op.create_index(
        "ux_bills_recurrence_key",
        "bills",
        ["client_id", "biller_name_normalized", "account_number_last4"],
        unique=True,
        postgresql_where=sa.text("account_number_last4 IS NOT NULL"),
    )
