"""Phase 15 Plan 04 follow-up: pre-create apscheduler_jobs table.

Revision ID: 0026_apscheduler_jobs_table
Revises: 0025_phase15_gmail_mcp
Create Date: 2026-05-07

APScheduler's SQLAlchemyJobStore lazily creates this table on first
scheduler.start() via Base.metadata.create_all(). When the runtime
DB role (app_runtime) is the connecting user, that CREATE TABLE
raises InsufficientPrivilege because app_runtime does not own schema
public (Phase 9 INFRA-07 split).

Plan 11 deadline alerts and Plan 15-04 lifespan warm-up both depend
on the scheduler being usable. This migration creates the table as
the migration role (postgres / app_migrator), then grants
INSERT/UPDATE/DELETE/SELECT on it to app_runtime.

Schema mirrors apscheduler.jobstores.sqlalchemy.SQLAlchemyJobStore:
  - id          VARCHAR(191) PRIMARY KEY
  - next_run_time DOUBLE PRECISION (FLOAT(25))
  - job_state   BYTEA NOT NULL
  - ix_apscheduler_jobs_next_run_time index for tick scans
"""
from alembic import op
import sqlalchemy as sa


revision = "0026_apscheduler_jobs_table"
down_revision = "0025_phase15_gmail_mcp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apscheduler_jobs",
        sa.Column("id", sa.String(length=191), primary_key=True),
        sa.Column("next_run_time", sa.Float(precision=25), nullable=True),
        sa.Column("job_state", sa.LargeBinary, nullable=False),
    )
    op.create_index(
        "ix_apscheduler_jobs_next_run_time",
        "apscheduler_jobs",
        ["next_run_time"],
    )

    # Grant CRUD privileges to app_runtime so the SQLAlchemyJobStore can
    # add/remove/lookup jobs at runtime. CREATE TABLE itself is reserved
    # to the migration role.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE apscheduler_jobs TO app_runtime';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_apscheduler_jobs_next_run_time", table_name="apscheduler_jobs")
    op.drop_table("apscheduler_jobs")
