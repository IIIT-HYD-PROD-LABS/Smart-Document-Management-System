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
    # ── 1. Enable RLS on v1.0 tables ──
    # postgres role (production FastAPI) and the CI POSTGRES_USER both
    # bypass RLS via superuser/BYPASSRLS, so prod paths are unaffected.
    # However, test fixtures explicitly `SET ROLE app_runtime` to subject
    # the test body to RLS; without an `app_runtime`-permissive policy,
    # tests like test_compliance_notices::test_notice_upload_links_document
    # fail on INSERT into `documents`. Add a TO app_runtime ALL policy on
    # each v1.0 table so the FastAPI runtime role can do anything.
    #
    # This is NOT the same anti-pattern as the dropped "always true"
    # policy: that one targeted `PUBLIC` (effectively any signed-in
    # Supabase user). A `TO app_runtime` policy is scoped to the
    # internal runtime role only — anon, authenticated, service_role
    # still get zero access, satisfying the advisor while not breaking
    # the v1.0 single-tenant model (user_id filtering at app layer).
    for tbl in _RLS_ENABLE_TABLES:
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;")
        # alembic_version is metadata; the runtime role doesn't touch it.
        if tbl == "alembic_version":
            continue
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                EXECUTE 'DROP POLICY IF EXISTS app_runtime_full ON public.{tbl}';
                EXECUTE 'CREATE POLICY app_runtime_full ON public.{tbl} '
                        'AS PERMISSIVE FOR ALL TO app_runtime '
                        'USING (true) WITH CHECK (true)';
            END IF;
        END $do$;
        """)

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
    # PUBLIC always exists; the Supabase-specific roles (anon, authenticated,
    # service_role) only exist on Supabase. Wrap conditionally so the
    # migration is portable to vanilla Postgres (CI, dev) where those roles
    # are absent.
    #
    # Function-existence is also conditional: rls_auto_enable was created
    # manually on the user's Supabase via the UI and does NOT exist in the
    # codebase migration chain. On CI / fresh Postgres the function isn't
    # there, so the REVOKE must skip cleanly.
    def _conditional_revoke_secdef(fn: str, fn_name: str) -> None:
        # Single DO block: skip entirely if the function doesn't exist on
        # this DB. fn_name is the unqualified name for pg_proc lookup;
        # fn is the schema-qualified signature for REVOKE.
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = '{fn_name}'
            ) THEN
                EXECUTE 'REVOKE EXECUTE ON FUNCTION {fn} FROM PUBLIC';
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE EXECUTE ON FUNCTION {fn} FROM anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE EXECUTE ON FUNCTION {fn} FROM authenticated';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                    EXECUTE 'REVOKE EXECUTE ON FUNCTION {fn} FROM service_role';
                END IF;
            END IF;
        END $do$;
        """)

    def _conditional_grant_secdef(fn: str, fn_name: str, role: str) -> None:
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = '{fn_name}'
            ) THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION {fn} TO {role}';
            END IF;
        END $do$;
        """)

    # Map signature -> bare function name for pg_proc.proname lookups.
    _SECDEF_NAMES = {
        "public.is_cross_client_eligible(integer)": "is_cross_client_eligible",
        "public.user_has_client_membership(integer, integer)": "user_has_client_membership",
        "public.rls_auto_enable()": "rls_auto_enable",
    }

    for fn in _SECDEF_RUNTIME_FUNCS:
        _conditional_revoke_secdef(fn, _SECDEF_NAMES[fn])
        # app_runtime is created by Phase 9 migration 0017_db_roles, so it
        # always exists in this codebase.
        _conditional_grant_secdef(fn, _SECDEF_NAMES[fn], "app_runtime")

    for fn in _SECDEF_ADMIN_FUNCS:
        _conditional_revoke_secdef(fn, _SECDEF_NAMES[fn])
        # rls_auto_enable is an admin helper — only postgres should call it.

    # ── 4. Pin search_path on flagged trigger functions ──
    # These functions are created by Phase 4 (documents trigger) + Phase 13
    # (compliance_notices trigger) + Phase 9 (audit reject trigger) — all in
    # the migration chain — so they always exist when 0024 runs. Use a
    # defensive existence check anyway in case a future schema rename slips.
    _SEARCHPATH_NAMES = {
        "public.documents_search_vector_update()": "documents_search_vector_update",
        "public.compliance_notices_search_vector_update()": "compliance_notices_search_vector_update",
        "public.reject_audit_log_modification()": "reject_audit_log_modification",
    }
    for fn in _FIX_SEARCH_PATH_FUNCS:
        bare = _SEARCHPATH_NAMES[fn]
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = '{bare}'
            ) THEN
                EXECUTE 'ALTER FUNCTION {fn} SET search_path = pg_catalog, public';
            END IF;
        END $do$;
        """)

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

    # Revert search_path pin (only if functions exist — same defensive
    # pattern as upgrade)
    _SEARCHPATH_NAMES_DOWN = {
        "public.documents_search_vector_update()": "documents_search_vector_update",
        "public.compliance_notices_search_vector_update()": "compliance_notices_search_vector_update",
        "public.reject_audit_log_modification()": "reject_audit_log_modification",
    }
    for fn in _FIX_SEARCH_PATH_FUNCS:
        bare = _SEARCHPATH_NAMES_DOWN[fn]
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = '{bare}'
            ) THEN
                EXECUTE 'ALTER FUNCTION {fn} RESET search_path';
            END IF;
        END $do$;
        """)

    # Re-grant SECURITY DEFINER funcs to the broad set (function + role
    # existence both conditional, mirrors upgrade for portability)
    _SECDEF_NAMES_DOWN = {
        "public.is_cross_client_eligible(integer)": "is_cross_client_eligible",
        "public.user_has_client_membership(integer, integer)": "user_has_client_membership",
        "public.rls_auto_enable()": "rls_auto_enable",
    }
    for fn in _SECDEF_RUNTIME_FUNCS + _SECDEF_ADMIN_FUNCS:
        bare = _SECDEF_NAMES_DOWN[fn]
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = '{bare}'
            ) THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION {fn} TO PUBLIC';
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'GRANT EXECUTE ON FUNCTION {fn} TO anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'GRANT EXECUTE ON FUNCTION {fn} TO authenticated';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                    EXECUTE 'GRANT EXECUTE ON FUNCTION {fn} TO service_role';
                END IF;
            END IF;
        END $do$;
        """)

    # Re-add the permissive policy on document_permissions
    op.execute(
        'CREATE POLICY "Allow all for authenticated" ON public.document_permissions '
        'AS PERMISSIVE FOR ALL TO PUBLIC USING (true) WITH CHECK (true);'
    )

    # Drop the app_runtime permissive policies and disable RLS on the
    # v1.0 tables (matches pre-0024 state)
    for tbl in _RLS_ENABLE_TABLES:
        if tbl != "alembic_version":
            op.execute(f"DROP POLICY IF EXISTS app_runtime_full ON public.{tbl};")
        op.execute(f"ALTER TABLE public.{tbl} DISABLE ROW LEVEL SECURITY;")
