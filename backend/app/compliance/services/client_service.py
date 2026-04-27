"""Client onboarding + dashboard aggregates — Phase 9 CLIENT-03, CLIENT-05.

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
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.compliance.models.client import Client, ClientRegistration
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.models.user import User
from app.services.audit_service import log_audit_event


def onboard_client(
    db: Session,
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

    Per CLIENT-05: rolls back the entire onboarding if any step fails;
    callers see Client with all dependents committed or no Client at all.
    """
    try:
        client = Client(
            name=details["name"],
            client_type=details["client_type"],
            industry=details.get("industry"),
            primary_contact_email=details.get("primary_contact_email"),
        )
        db.add(client)
        db.flush()  # materialise client.id without committing

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

        for member in team:
            db.add(
                ClientMembership(
                    user_id=member["user_id"],
                    client_id=client.id,
                    compliance_role=member["compliance_role"],
                    access_start=member.get("access_start"),
                    access_end=member.get("access_end"),
                )
            )

        db.commit()
        db.refresh(client)
    except Exception:
        db.rollback()
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


def get_dashboard_aggregates(db: Session, client_id: int) -> dict:
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
    """
    base = db.query(ComplianceNotice).filter(
        ComplianceNotice.client_id == client_id
    )
    total = base.count()

    status_rows = (
        db.query(
            ComplianceNotice.status, func.count(ComplianceNotice.id)
        )
        .filter(ComplianceNotice.client_id == client_id)
        .group_by(ComplianceNotice.status)
        .all()
    )
    by_status = {st: cnt for st, cnt in status_rows}

    auth_rows = (
        db.query(
            ComplianceNotice.authority, func.count(ComplianceNotice.id)
        )
        .filter(ComplianceNotice.client_id == client_id)
        .group_by(ComplianceNotice.authority)
        .all()
    )
    by_authority = {a: cnt for a, cnt in auth_rows}

    # Phase 9 placeholder — Phase 10 will populate from risk_score column.
    by_risk_tier = {
        "unscored": total,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    today = datetime.now(timezone.utc).date()
    overdue = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.client_id == client_id,
            ComplianceNotice.response_deadline < today,
            ComplianceNotice.status.notin_(("resolved", "dismissed")),
        )
        .count()
    )

    return {
        "total": total,
        "by_status": by_status,
        "by_authority": by_authority,
        "by_risk_tier": by_risk_tier,
        "overdue": overdue,
    }
