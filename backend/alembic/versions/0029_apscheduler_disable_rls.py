"""apscheduler_jobs is not tenant-scoped — disable RLS so the scheduler can write.

Revision ID: 0029_apscheduler_disable_rls
Revises: 0028_phase15_doc_source_field
Create Date: 2026-05-08

The Phase 15 Gmail OAuth callback fails on the final step
``schedule_gmail_scan()`` with::

    InsufficientPrivilege: new row violates row-level security policy
    for table "apscheduler_jobs"

Migration 0026 GRANTed CRUD on this table to ``app_runtime``, but RLS
got enabled on the table (either by Supabase's default-RLS-on-create
or by a global ALTER TABLE wave from migration 0024). With RLS
enabled and zero policies, every INSERT is denied by default.

``apscheduler_jobs`` has no tenant scoping — it stores cross-tenant
scheduler bookkeeping (next_run_time + serialized job_state) and is
always written from APScheduler's own SQLAlchemyJobStore, not from
user-driven queries. There is no tenant invariant to protect on this
table; RLS adds zero security here and breaks the scheduler.

Fix: ``ALTER TABLE apscheduler_jobs DISABLE ROW LEVEL SECURITY``.

Documented exemption — if a future Supabase security advisor flags this
table, the response is "internal scheduler bookkeeping; RLS adds no
defense, breaks APScheduler.SQLAlchemyJobStore.add_job()."
"""
from alembic import op


revision = "0029_apscheduler_disable_rls"
down_revision = "0028_phase15_doc_source_field"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE apscheduler_jobs DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE apscheduler_jobs ENABLE ROW LEVEL SECURITY")
