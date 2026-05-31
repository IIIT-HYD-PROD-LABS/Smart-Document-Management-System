"""RLS: let a user read their OWN membership rows (client-switcher bootstrap).

Revision ID: 0039_rls_self_membership_policy
Revises: 0038_rls_activation_grants
Create Date: 2026-06-01

Under app_runtime, GET /api/compliance/clients/me must list the requesting
user's memberships across ALL clients BEFORE any client is selected (the
client switcher needs the full list, so the request carries no X-Client-Id and
app.current_client_id is unset). The existing membership policies are
client-scoped or require cross_client_mode eligibility, so the discovery query
fail-closes to zero rows and the user can never see their own tenancies.

This adds a permissive SELECT policy: a user may always read membership rows
where user_id = app.user_id. app.user_id is set per-request by get_current_user
(app/utils/security.py) and inside the notifications WebSocket handler. This is
strictly self-scoped (you can only see memberships that are yours), so it adds
no cross-tenant exposure.
"""
from alembic import op


revision = "0039_rls_self_membership_policy"
down_revision = "0038_rls_activation_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS self_membership_view ON compliance_client_memberships;")
    op.execute(
        """
        CREATE POLICY self_membership_view ON compliance_client_memberships
          AS PERMISSIVE
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND user_id = current_setting('app.user_id', true)::int
          );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS self_membership_view ON compliance_client_memberships;")
