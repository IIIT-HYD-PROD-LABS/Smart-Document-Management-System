"""Default Gmail filter rules seeded on first connect."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.email.models.filter_rule import GmailFilterRule

# priority ASC wins. Patterns are operator-editable after seed.
DEFAULT_FILTER_RULES: list[dict] = [
    {
        "priority": 10,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?cbic-gst\.gov\.in$",
        "subject_pattern": r"(?i)notice|demand|show.?cause|SCN|DRC",
        "route_to": GmailFilterRule.ROUTE_COMPLIANCE,
    },
    {
        "priority": 15,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?incometax(?:indiaefiling)?\.gov\.in$",
        "subject_pattern": r"(?i)notice|intimation|demand|scrutiny|assessment",
        "route_to": GmailFilterRule.ROUTE_COMPLIANCE,
    },
    {
        "priority": 20,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?mca\.gov\.in$",
        "subject_pattern": r"(?i)notice|order|summons|inquiry",
        "route_to": GmailFilterRule.ROUTE_COMPLIANCE,
    },
    {
        "priority": 25,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?sebi\.gov\.in$",
        "subject_pattern": r"(?i)notice|order|adjudication|hearing",
        "route_to": GmailFilterRule.ROUTE_COMPLIANCE,
    },
    {
        "priority": 30,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?rbi\.org\.in$",
        "subject_pattern": r"(?i)notice|order|show.?cause",
        "route_to": GmailFilterRule.ROUTE_COMPLIANCE,
    },
    {
        "priority": 40,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?(?:gov|nic)\.in$",
        "subject_pattern": r"(?i)notice|show.?cause|demand|intimation|SCN",
        "route_to": GmailFilterRule.ROUTE_COMPLIANCE,
    },
    {
        "priority": 60,
        "sender_pattern": r"@(?:[a-z0-9-]+\.)?(?:tatapower|airtel|jio|bsnl|hdfcbank|icicibank|sbicard)\.com$",
        "subject_pattern": r"(?i)bill|invoice|statement|amount due",
        "route_to": GmailFilterRule.ROUTE_BILL,
    },
]


async def seed_default_filter_rules_async(
    db: AsyncSession, credential_id: int
) -> int:
    """Insert default rules if the credential has none. Returns count inserted."""
    existing = (
        await db.execute(
            select(GmailFilterRule.id).where(
                GmailFilterRule.credential_id == credential_id
            ).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0
    for spec in DEFAULT_FILTER_RULES:
        db.add(
            GmailFilterRule(
                credential_id=credential_id,
                priority=spec["priority"],
                sender_pattern=spec["sender_pattern"],
                subject_pattern=spec["subject_pattern"],
                route_to=spec["route_to"],
                enabled=True,
            )
        )
    await db.commit()
    return len(DEFAULT_FILTER_RULES)


def seed_default_filter_rules_sync(db: Session, credential_id: int) -> int:
    existing = (
        db.query(GmailFilterRule.id)
        .filter(GmailFilterRule.credential_id == credential_id)
        .first()
    )
    if existing is not None:
        return 0
    for spec in DEFAULT_FILTER_RULES:
        db.add(
            GmailFilterRule(
                credential_id=credential_id,
                priority=spec["priority"],
                sender_pattern=spec["sender_pattern"],
                subject_pattern=spec["subject_pattern"],
                route_to=spec["route_to"],
                enabled=True,
            )
        )
    db.commit()
    return len(DEFAULT_FILTER_RULES)
