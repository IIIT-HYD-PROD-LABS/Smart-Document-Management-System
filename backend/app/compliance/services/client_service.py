"""Client onboarding + dashboard aggregates — Phase 9 CLIENT-03, CLIENT-05.

ponytail: The dashboard aggregate query can 500 under RLS when the tenant
  context is stale (Zustand localStorage carryover). Rather than crashing
  the whole client detail page, we catch-and-return-zeros so the UI card
  grid renders "—" / 0 gracefully for transient RLS mismatches.
  Upgrade path: pre-computed materialized views keyed by (client_id,
  last_updated) when page-scale requires it.

Two services live in this module because they share the same
Client/Registration/Membership/Notice ORM dependencies and the same
audit-write pattern:

  onboard_client(db, details, registrations, team, actor) -> Client
    Atomic 4-step wizard backend (D-16). Creates the parent Client row,
    then ALL ClientRegistration rows, then ALL ClientMembership rows in
    a SINGLE database transaction. Any IntegrityError or ValueError
    rolls back the entire onboarding — partial state is never visible
    (Pitfall covered by CLIENT-05 contract).

  get_dashboard_aggregates(db, client_id) -> dict
    Real-time per-client KPI computation. Always queries live data
    (D-18: no pre-computed aggregate table at Phase 9 scale). Returns:
        total, by_status (dict), by_authority (dict),
        by_risk_tier (dict — always {'unscored': total, ...} until
                     Phase 10 BERT scoring lands), overdue.
    The risk tier shape is forward-compatible with Phase 10 risk_score:
    once that column exists, this query swaps to a CASE WHEN bucketing
    over risk_score and the UI doesn't need to change.

The audit log entry is written via log_audit_event AFTER the business
commit succeeds, so a transient audit failure cannot abort onboarding.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.models.client import Client, ClientRegistration
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.models.user import User
from app.services.audit_service import log_audit_event


async def onboard_client(
    db: AsyncSession,
    details: dict,
    registrations: list[dict],
    team: list[dict],
    actor: User,
) -> Client:
    """Atomic client onboarding — Client + N Registrations + M Memberships.

    `details` keys: name (required), client_type (required), industry,
                    primary_contact_email.
    `registrations` row keys: type (GSTIN/PAN/CIN/DIN), value, state.
    `team` row keys: user_id, compliance_role, access_start, access_end.

    The actor is auto-added as `compliance_head` if not already present in
    the team payload — every onboarder needs at least one membership on
    the new client (otherwise they cannot operate it after creation).
    Team rows referencing non-existent user_ids are dropped (defensive
    against frontend wizards that ask users to type numeric IDs they
    can't reasonably know).

    Per CLIENT-05: rolls back the entire onboarding if any step fails;
    callers see Client with all dependents committed or no Client at all.
    """
    # Sanitise team: drop entries with missing/zero user_id or referencing
    # users that don't exist in the users table (FK would IntegrityError
    # otherwise — preserved as defensive even after the frontend fix).
    candidate_ids = [m.get("user_id") for m in team if m.get("user_id")]
    if candidate_ids:
        existing_ids = {
            uid
            for (uid,) in (
                await db.execute(
                    select(User.id).where(User.id.in_(candidate_ids))
                )
            ).all()
        }
    else:
        existing_ids = set()
    sanitised_team: list[dict] = []
    seen_user_ids: set[int] = set()
    for m in team:
        uid = m.get("user_id")
        if not uid or uid in seen_user_ids or uid not in existing_ids:
            continue
        sanitised_team.append(m)
        seen_user_ids.add(uid)

    # Auto-add the actor as compliance_head if they aren't already on the
    # team. Without this, an empty/invalid wizard team payload creates a
    # Client the actor cannot see (no membership → RLS hides it).
    if actor.id not in seen_user_ids:
        sanitised_team.insert(
            0,
            {"user_id": actor.id, "compliance_role": "compliance_head"},
        )

    # Email-based rows: resolved + emailed after the client row exists
    # (resolve_or_invite needs client_id + client_name for the invite).
    email_team: list[dict] = [m for m in team if m.get("email")]

    from app.services.invitation_service import (
        InvitationError,
        resolve_or_invite_async,
    )

    try:
        client = Client(
            name=details["name"],
            client_type=details["client_type"],
            industry=details.get("industry"),
            primary_contact_email=details.get("primary_contact_email"),
        )
        db.add(client)
        await db.flush()  # materialise client.id without committing

        for reg in registrations:
            db.add(
                ClientRegistration(
                    client_id=client.id,
                    type=reg["type"],
                    value=reg["value"],
                    state=reg.get("state"),
                    is_active=True,
                )
            )

        for member in sanitised_team:
            db.add(
                ClientMembership(
                    user_id=member["user_id"],
                    client_id=client.id,
                    compliance_role=member["compliance_role"],
                    access_start=member.get("access_start"),
                    access_end=member.get("access_end"),
                )
            )

        # Email-based team rows: resolve_or_invite within the same
        # transaction so a Pending User + Membership land together. The
        # invitation email is best-effort (failures logged, not raised)
        # because the wrapper commit must still go through.
        for member in email_team:
            try:
                uid, _invited, _dev_token = await resolve_or_invite_async(
                    db,
                    client_id=client.id,
                    client_name=client.name,
                    inviter=actor,
                    email=member.get("email"),
                    full_name=member.get("full_name"),
                )
            except InvitationError:
                # Bad email in the team payload should not roll back the
                # whole onboarding; skip the row.
                continue
            if uid in seen_user_ids:
                continue
            seen_user_ids.add(uid)
            db.add(
                ClientMembership(
                    user_id=uid,
                    client_id=client.id,
                    compliance_role=member["compliance_role"],
                    access_start=member.get("access_start"),
                    access_end=member.get("access_end"),
                )
            )

        await db.commit()
        await db.refresh(client)
    except Exception:
        await db.rollback()
        raise

    # AUDIT-02 — write after the business commit so audit issues
    # cannot roll back onboarding (audit_service swallows exceptions).
    log_audit_event(
        user_id=actor.id,
        action="client_onboarded",
        resource_type="Client",
        resource_id=client.id,
        details={
            "name": client.name,
            "client_type": client.client_type,
            "registration_count": len(registrations),
            "team_size": len(team),
        },
    )
    return client


async def get_dashboard_aggregates(db: AsyncSession, client_id: int) -> dict:
    """Per-client dashboard aggregates — CLIENT-03 / D-18.

    Real-time aggregation; no pre-computed table at Phase 9 scale.
    Returns the 5 keys consumed by the dashboard UI:

        {
          "total": int,
          "by_status": {status_value: count, ...},
          "by_authority": {authority_value: count, ...},
          "by_risk_tier": {"unscored": total, "critical": 0, "high": 0,
                           "medium": 0, "low": 0},
          "overdue": int  # response_deadline < today AND not in
                          # ('resolved', 'dismissed')
        }

    `by_risk_tier` always reports `unscored=total` at Phase 9 because risk
    scoring is a Phase 10 BERT classifier (D-06). The shape is preserved
    so the UI's five-color contract from 09-UI-SPEC works unchanged.

    ponytail: SQLAlchemyError (RLS mismatch, stale tenant context from
    Zustand localStorage carryover) returns a zeroed shape instead of
    crashing the client detail page. Upgrade when page-scale requires it.
    """
    try:
        total = await db.scalar(
            select(func.count(ComplianceNotice.id)).where(
                ComplianceNotice.client_id == client_id
            )
        )

        status_rows = (
            await db.execute(
                select(ComplianceNotice.status, func.count(ComplianceNotice.id))
                .where(ComplianceNotice.client_id == client_id)
                .group_by(ComplianceNotice.status)
            )
        ).all()
        by_status = {st: cnt for st, cnt in status_rows}

        auth_rows = (
            await db.execute(
                select(ComplianceNotice.authority, func.count(ComplianceNotice.id))
                .where(ComplianceNotice.client_id == client_id)
                .group_by(ComplianceNotice.authority)
            )
        ).all()
        by_authority = {a: cnt for a, cnt in auth_rows}

        # Real GROUP BY on the risk_tier column. NULL (rule-based output that
        # didn't run the classifier, manual entries pre-Phase 10) buckets as
        # "unscored" so the five-color contract from 09-UI-SPEC stays stable.
        risk_rows = (
            await db.execute(
                select(ComplianceNotice.risk_tier, func.count(ComplianceNotice.id))
                .where(ComplianceNotice.client_id == client_id)
                .group_by(ComplianceNotice.risk_tier)
            )
        ).all()
        by_risk_tier = {"unscored": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
        for tier, cnt in risk_rows:
            key = tier if tier in ("critical", "high", "medium", "low") else "unscored"
            by_risk_tier[key] = by_risk_tier[key] + cnt

        today = datetime.now(timezone.utc).date()
        overdue = await db.scalar(
            select(func.count(ComplianceNotice.id)).where(
                ComplianceNotice.client_id == client_id,
                ComplianceNotice.response_deadline < today,
                ComplianceNotice.status.notin_(("resolved", "dismissed")),
            )
        )

        return {
            "total": total,
            "by_status": by_status,
            "by_authority": by_authority,
            "by_risk_tier": by_risk_tier,
            "overdue": overdue,
        }
    except SQLAlchemyError:
        logger = logging.getLogger(__name__)
        logger.warning("dashboard_aggregates_failed", client_id=client_id, exc_info=True)
        return {
            "total": 0,
            "by_status": {},
            "by_authority": {},
            "by_risk_tier": {"unscored": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
            "overdue": 0,
        }
