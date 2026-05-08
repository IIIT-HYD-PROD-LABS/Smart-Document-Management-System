"""Seed demo users with one membership each on the demo tenant.

Lets you log in as each of the seven compliance roles separately and
exercise the role-specific UI flow (drafter writes, reviewer approves,
legal approves, CFO approves, auditor reads the trail).

Idempotent — keyed on username. Re-run is a no-op for already-present
rows. The membership row is upserted on (user_id, client_id).

All passwords default to `demo1234` (8 chars min, matches Pydantic
RegisterRequest constraint). Override per-user via the spec list below.

Run inside the backend container:
    docker compose exec backend python /app/scripts/seed_demo_users.py

Honours the same DEMO_CLIENT_ID / DEMO_USER_ID env conventions as
seed_demo_notices.py (defaults to first active admin's first
compliance_head membership).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

# Bypass the tenant-context listener that app.database wires onto its
# default engine. That listener sets `app.user_id` from the request's
# ContextVars before every query; in a CLI seed there's no request, so
# the var is NULL and RLS policies on compliance_* tables hide every
# row. A clean engine without the listener gives us BYPASSRLS at the
# postgres role level.
_seed_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_seed_engine)


DEMO_PASSWORD = "demo1234"


# username, email, role (v1.0 admin/editor/viewer), compliance_role
USER_SPECS: list[tuple[str, str, str, str]] = [
    ("staff_demo",    "staff.demo@taxsync.local",    "editor", "staff"),
    ("legal_demo",    "legal.demo@taxsync.local",    "editor", "legal_team"),
    ("cfo_demo",      "cfo.demo@taxsync.local",      "editor", "cfo"),
    ("auditor_demo",  "auditor.demo@taxsync.local",  "viewer", "auditor"),
    ("ca_demo",       "ca.demo@taxsync.local",       "admin",  "ca_consultant"),
]


def resolve_target_client(db) -> int:
    cid = os.environ.get("DEMO_CLIENT_ID")
    if cid:
        return int(cid)
    # Schema-qualify `public.users`. The Supabase project has `auth.users`
    # too, and an unqualified JOIN can resolve to that depending on the
    # connection's search_path.
    row = db.execute(
        text(
            """
            SELECT m.client_id
            FROM compliance_client_memberships m
            JOIN public.users u ON u.id = m.user_id
            WHERE u.role = 'admin' AND u.is_active
              AND m.compliance_role = 'compliance_head'
            ORDER BY m.id ASC LIMIT 1
            """
        )
    ).first()
    if not row:
        raise SystemExit("No demo client found; set DEMO_CLIENT_ID")
    return row[0]


def upsert_user_with_membership(
    db,
    client_id: int,
    username: str,
    email: str,
    role: str,
    compliance_role: str,
) -> tuple[int, bool, bool]:
    """Returns (user_id, user_created, membership_created)."""
    now = datetime.now(timezone.utc)

    user_row = db.execute(
        text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).first()
    if user_row:
        user_id = user_row[0]
        user_created = False
    else:
        user_id = db.execute(
            text(
                """
                INSERT INTO users (
                    username, email, hashed_password, full_name,
                    is_active, auth_provider, role, created_at, updated_at
                ) VALUES (
                    :u, :e, :p, :fn, TRUE, 'local', :r, :now, :now
                ) RETURNING id
                """
            ),
            {
                "u": username,
                "e": email,
                "p": hash_password(DEMO_PASSWORD),
                "fn": username.replace("_", " ").title(),
                "r": role,
                "now": now,
            },
        ).scalar()
        user_created = True

    mem_row = db.execute(
        text(
            "SELECT id FROM compliance_client_memberships "
            "WHERE user_id = :u AND client_id = :c"
        ),
        {"u": user_id, "c": client_id},
    ).first()
    if mem_row:
        membership_created = False
        # Make sure the role matches the spec — handles re-seeds where
        # the spec was changed.
        db.execute(
            text(
                "UPDATE compliance_client_memberships "
                "SET compliance_role = :cr "
                "WHERE id = :id AND compliance_role <> :cr"
            ),
            {"cr": compliance_role, "id": mem_row[0]},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO compliance_client_memberships
                (user_id, client_id, compliance_role, created_at)
                VALUES (:u, :c, :cr, :now)
                """
            ),
            {"u": user_id, "c": client_id, "cr": compliance_role, "now": now},
        )
        membership_created = True

    return user_id, user_created, membership_created


def main() -> int:
    db = SessionLocal()
    try:
        # FORCE ROW LEVEL SECURITY on compliance_* overrides postgres-role
        # BYPASSRLS. SET row_security = off is the documented escape
        # hatch for admin scripts (Postgres >= 9.5; requires SUPERUSER
        # or BYPASSRLS — postgres has both on Supabase).
        db.execute(text("SET row_security = off"))
        client_id = resolve_target_client(db)
        print(f"Target client: {client_id}")
        print()

        rows = []
        for username, email, role, compliance_role in USER_SPECS:
            uid, uc, mc = upsert_user_with_membership(
                db, client_id, username, email, role, compliance_role
            )
            rows.append((uid, username, email, compliance_role, uc, mc))

        db.commit()

        print(f"{'id':>4}  {'username':14s}  {'email':30s}  {'role':14s}  user / member")
        for uid, u, e, cr, uc, mc in rows:
            uflag = "new" if uc else "skip"
            mflag = "new" if mc else "skip"
            print(f"{uid:>4}  {u:14s}  {e:30s}  {cr:14s}  {uflag} / {mflag}")
        print()
        print(f"All accounts share password:  {DEMO_PASSWORD}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
