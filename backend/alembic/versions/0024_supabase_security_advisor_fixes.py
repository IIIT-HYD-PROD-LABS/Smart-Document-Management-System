"""Supabase Security Advisor — close 5 CRITICAL + 6 HIGH findings.

Closes findings raised by Supabase's Security Advisor after Phase 13 ship:

CRITICAL
  1. RLS Disabled on public.users
  2. RLS Disabled on public.documents
  3. RLS Disabled on public.refresh_tokens
  4. RLS Disabled on public.alembic_version (low-PII but flagged)
  5. RLS Policy "Allow all for authenticated" on public.document_permissions
     uses USING (true) WITH CHECK (true) — RLS enabled but defeated.

HIGH
  6. SECURITY DEFINER fn public.is_cross_client_eligible executable by
     PUBLIC + anon + authenticated + service_role.
  7. SECURITY DEFINER fn public.user_has_client_membership: same.
  8. SECURITY DEFINER fn public.rls_auto_enable: same.
  9. Function search_path mutable — public.documents_search_vector_update
  10. Function search_path mutable — public.compliance_notices_search_vector_update
  11. Function search_path mutable — public.reject_audit_log_modification

Plus: revoke broad privileges from Supabase's `anon` and `authenticated`
roles. Those roles are not used by the FastAPI app (custom JWT, not
auth.uid()), so the revoke has zero functional impact but silences
~70% of the noisy "Public/Signed-In Users Can See Object in GraphQL
Schema" advisor warnings.

Out of scope: the "Auth RLS Initialization Plan" warnings on the
compliance_* tables — those flag `auth.uid()` re-eval per row, but the
policies use `current_setting('app.current_client_id')` which the
advisor's pattern-match falsely associates with auth.uid(). False
positives, no fix needed.

Defense-in-depth note on the v1.0 tables:
  After this migration, the FastAPI app continues to query users /
  documents / refresh_tokens via the `postgres` role, which has
  BYPASSRLS. RLS is enabled with no permissive policies, so any other
  role (anon, authenticated, app_runtime if ever used here) gets
  zero rows — closing the advisor finding without changing app
  behavior.
"""
from alembic import op


revision = "0024_supabase_security_advisor_fixes"
down_revision = "0023_phase13_search_vector_on_notices"
branch_labels = None
depends_on = None


# Tables flagged by the advisor that lack RLS. Enabling without policies is
# safe because the FastAPI app uses the `postgres` role (BYPASSRLS).
_RLS_ENABLE_TABLES = (
    "users",
    "documents",
    "refresh_tokens",
    "alembic_version",
)

# SECURITY DEFINER helpers used by the Phase 9 RLS policies. Only
# app_runtime needs to call the membership / cross-client helpers.
# rls_auto_enable is an admin-only schema migration helper.
_SECDEF_RUNTIME_FUNCS = (
    "public.is_cross_client_eligible(integer)",
    "public.user_has_client_membership(integer, integer)",
)
_SECDEF_ADMIN_FUNCS = (
    "public.rls_auto_enable()",
)

# Trigger functions that need a fixed search_path to prevent search_path
# injection (PG advisor lint W2001).
_FIX_SEARCH_PATH_FUNCS = (
    "public.documents_search_vector_update()",
    "public.compliance_notices_search_vector_update()",
    "public.reject_audit_log_modification()",
)


def upgrade() -> None:
    # ── 1. Enable RLS on v1.0 tables (postgres role bypasses, no behavior change) ──
    for tbl in _RLS_ENABLE_TABLES:
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;")

    # ── 2. Replace the "always true" permissive policy on document_permissions ──
    # The existing "Allow all for authenticated" policy uses USING(true) WITH
    # CHECK(true) — RLS enabled but defeated. The app accesses this table
    # via the `postgres` role (BYPASSRLS), so dropping the policy without
    # replacement is safe. Any future use via app_runtime will see no rows
    # until a real policy is added.
    op.execute(
        'DROP POLICY IF EXISTS "Allow all for authenticated" '
        'ON public.document_permissions;'
    )

    # ── 3. Lock down SECURITY DEFINER functions ──
    for fn in _SECDEF_RUNTIME_FUNCS:
        op.execute(
            f"REVOKE EXECUTE ON FUNCTION {fn} "
            f"FROM PUBLIC, anon, authenticated, service_role;"
        )
        # app_runtime is the FastAPI runtime role; it calls these from RLS policies.
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO app_runtime;")

    for fn in _SECDEF_ADMIN_FUNCS:
        op.execute(
            f"REVOKE EXECUTE ON FUNCTION {fn} "
            f"FROM PUBLIC, anon, authenticated, service_role;"
        )
        # rls_auto_enable is an admin helper — only postgres should call it.

    # ── 4. Pin search_path on flagged trigger functions ──
    for fn in _FIX_SEARCH_PATH_FUNCS:
        op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public;")

    # ── 5. Revoke broad access from Supabase roles that the app does not use ──
    # Wrapped in DO blocks so the migration is idempotent on non-Supabase
    # deployments where these roles may not exist.
    for role in ("anon", "authenticated"):
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}';
                EXECUTE 'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {role}';
                EXECUTE 'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM {role}';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {role}';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {role}';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM {role}';
            END IF;
        END $do$;
        """)


def downgrade() -> None:
    # Re-grant Supabase role privileges (defaults Supabase ships with).
    for role in ("anon", "authenticated"):
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {role}';
                EXECUTE 'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {role}';
                EXECUTE 'GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {role}';
            END IF;
        END $do$;
        """)

    # Revert search_path pin
    for fn in _FIX_SEARCH_PATH_FUNCS:
        op.execute(f"ALTER FUNCTION {fn} RESET search_path;")

    # Re-grant SECURITY DEFINER funcs to the broad set
    for fn in _SECDEF_RUNTIME_FUNCS + _SECDEF_ADMIN_FUNCS:
        op.execute(
            f"GRANT EXECUTE ON FUNCTION {fn} "
            f"TO PUBLIC, anon, authenticated, service_role;"
        )

    # Re-add the permissive policy on document_permissions
    op.execute(
        'CREATE POLICY "Allow all for authenticated" ON public.document_permissions '
        'AS PERMISSIVE FOR ALL TO PUBLIC USING (true) WITH CHECK (true);'
    )

    # Disable RLS on the v1.0 tables (matches pre-0024 state)
    for tbl in _RLS_ENABLE_TABLES:
        op.execute(f"ALTER TABLE public.{tbl} DISABLE ROW LEVEL SECURITY;")
