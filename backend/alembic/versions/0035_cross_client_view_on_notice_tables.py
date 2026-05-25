"""Add cross_client_view policy to the 7 notice_* tables that ship with
tenant_isolation only.

Revision ID: 0035_cross_client_view_on_notice_tables
Revises: 0034_phase17_notice_extraction
Create Date: 2026-05-25

Phase 9 introduced two RLS policies on every client-scoped table:
  * tenant_isolation     RESTRICTIVE, USING + WITH CHECK on client_id
  * cross_client_view    PERMISSIVE, SELECT-only, gated by
                         current_setting('app.cross_client_mode') = 'true'
                         AND is_cross_client_eligible(user_id::int)

Migration 0015 + 0018 wired both policies onto the v2.0 phase-9 tables.
The Phase 11 (alert) and Phase 12 (response) tables were added later and
shipped with `tenant_isolation` only, no `cross_client_view`. That means
a compliance_head with `crossClientMode = true` in the UI can see notice
rows in their visible clients but cannot see related alerts, response
drafts, approvals, or review-queue entries on those same notices.

This migration brings the seven Phase 11/12 notice_* tables back in line
with the Phase 9 convention. Read-only PERMISSIVE policy gated by
is_cross_client_eligible (defined in 0018).
"""
from alembic import op


revision = "0035_cross_client_view_on_notice_tables"
down_revision = "0034_phase17_notice_extraction"
branch_labels = None
depends_on = None


_TABLES = (
    "notice_alert_log",
    "notice_alert_rules",
    "notice_evidence_attachments",
    "notice_response_approvals",
    "notice_response_versions",
    "notice_responses",
    "notice_review_queue",
)


def upgrade() -> None:
    for table in _TABLES:
        # Drop any prior incarnation first so the migration is idempotent
        # and can re-run after a partial failure.
        op.execute(f"DROP POLICY IF EXISTS cross_client_view ON {table}")
        op.execute(
            f"""
            CREATE POLICY cross_client_view ON {table}
              AS PERMISSIVE
              FOR SELECT TO app_runtime
              USING (
                current_setting('app.cross_client_mode', true) = 'true'
                AND current_setting('app.user_id', true) IS NOT NULL
                AND current_setting('app.user_id', true) != ''
                AND is_cross_client_eligible(
                    current_setting('app.user_id', true)::int
                )
              )
            """
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS cross_client_view ON {table}")
