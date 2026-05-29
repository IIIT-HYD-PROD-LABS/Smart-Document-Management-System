"""Dedup-guard uniqueness on documents + regulatory_calendar; drop ai cross_client_view.

Revision ID: 0037_dedup_constraints_and_drop_cross_client_ai
Revises: 0036_add_mfa_and_lockout_columns
Create Date: 2026-05-26

Three independent hardening changes, all reversible:

D1 — Prevent duplicate first-time uploads.
    A partial UNIQUE index on documents(user_id, original_filename) excluding
    rows whose status = 'failed'. Failed uploads are excluded so a user can
    retry the same filename after a processing failure, and the "new version"
    path (routers/documents.py) reuses the existing row rather than inserting
    a second one. DocumentStatus stores its lowercase .value via
    values_callable, so the predicate compares against the text 'failed'.

    Populated-table guard: a pre-existing populated `documents` table may
    already hold duplicate (user_id, original_filename) pairs among non-failed
    rows, which would make CREATE UNIQUE INDEX fail. We do NOT delete rows
    (data loss); instead, for each colliding group we keep the earliest upload
    (lowest id) active and flip the surplus rows to status='failed' so they
    fall outside the partial index. See risk note in the plan output.

AI1 — Remove the cross_client_view escalation policy on ai_credentials.
    Migration 0033 added a SELECT policy that let a "cross client mode" session
    read every tenant's encrypted API key. tenant_isolation (also from 0033)
    is the only policy that should remain. downgrade() recreates 0033's policy
    verbatim, including its is_cross_client_eligible() guard.

L4 — Natural-key uniqueness on compliance_regulatory_calendar.
    UNIQUE over (year, date, label, category, authority). `authority` is
    nullable and a plain UNIQUE constraint treats NULLs as distinct in
    Postgres, so two "general holiday" rows (authority IS NULL) with the same
    year/date/label/category would both be allowed. We instead build a unique
    index on COALESCE(authority, '') so NULL authorities collapse to one
    sentinel and are deduplicated like any other value. Pre-existing duplicate
    rows are removed (lowest id kept) before the index is created.
"""
from alembic import op


revision = "0037_dedup_constraints_and_drop_cross_client_ai"
down_revision = "0036_add_mfa_and_lockout_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- D1: documents(user_id, original_filename) partial unique ---
    # Flip surplus non-failed duplicates to 'failed' (keep earliest id active)
    # so the partial unique index below can be created on a populated table.
    op.execute(
        """
        UPDATE documents d
        SET status = 'failed'
        WHERE d.status <> 'failed'
          AND EXISTS (
              SELECT 1 FROM documents e
              WHERE e.user_id = d.user_id
                AND e.original_filename = d.original_filename
                AND e.status <> 'failed'
                AND e.id < d.id
          )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_user_filename
        ON documents (user_id, original_filename)
        WHERE status <> 'failed'
        """
    )

    # --- AI1: drop the cross-client read escalation policy ---
    op.execute("DROP POLICY IF EXISTS cross_client_view ON ai_credentials;")

    # --- L4: regulatory_calendar natural-key uniqueness ---
    # Remove pre-existing duplicate rows (keep lowest id). COALESCE collapses
    # NULL authority so general-holiday rows dedupe correctly.
    op.execute(
        """
        DELETE FROM compliance_regulatory_calendar a
        USING compliance_regulatory_calendar b
        WHERE a.id > b.id
          AND a.year = b.year
          AND a.date = b.date
          AND a.label = b.label
          AND a.category = b.category
          AND COALESCE(a.authority, '') = COALESCE(b.authority, '')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_calendar_natural_key
        ON compliance_regulatory_calendar
        (year, date, label, category, COALESCE(authority, ''))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_calendar_natural_key;")
    op.execute("DROP INDEX IF EXISTS uq_documents_user_filename;")

    # Recreate 0033's cross_client_view exactly as defined there, including the
    # guard that the policy is only created when app_runtime and the
    # is_cross_client_eligible() function both exist.
    op.execute(
        """
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime')
           AND EXISTS (
               SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
               WHERE n.nspname = 'public' AND p.proname = 'is_cross_client_eligible'
           ) THEN
            EXECUTE 'DROP POLICY IF EXISTS cross_client_view ON ai_credentials';
            EXECUTE $policy$
            CREATE POLICY cross_client_view ON ai_credentials
            AS PERMISSIVE FOR SELECT TO app_runtime
            USING (
                current_setting('app.cross_client_mode', true) = 'true'
                AND current_setting('app.user_id', true) IS NOT NULL
                AND current_setting('app.user_id', true) != ''
                AND is_cross_client_eligible(
                    current_setting('app.user_id', true)::int
                )
            )
            $policy$;
        END IF;
    END $do$;
    """
    )
