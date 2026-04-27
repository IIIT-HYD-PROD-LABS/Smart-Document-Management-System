"""Auditor time-bound access enforcement — Phase 9 RBAC-04 / D-27.

Per RESEARCH Pitfall 4: an Auditor with access_end in the past must be
rejected on EVERY request, not just at membership creation. This module
exposes the helper used by:

  1. require_compliance_permission (in app.compliance.dependencies):
     called per request via FastAPI Depends, raises 403 if expired.

  2. Service-layer code that loads memberships outside an HTTP context
     (e.g. Celery tasks, batch jobs).

The check is intentionally a pure function over an in-memory ClientMembership
instance: callers decide what to do on inactive (raise HTTPException, log,
skip task, etc.).

ClientMembership.is_active_at(when) is the source-of-truth implementation;
this module wraps it with `datetime.now(timezone.utc)` defaulting + a
human-readable reason helper for nicer 403 messages.
"""
from datetime import datetime, timezone
from typing import Optional

from app.compliance.models.membership import ClientMembership


def is_membership_active(
    membership: ClientMembership,
    when: Optional[datetime] = None,
) -> bool:
    """Return True iff membership is active at `when` (default: now in UTC).

    Inactive cases:
      - access_start is set and `when` < access_start (not yet started)
      - access_end is set and `when` > access_end (expired)

    Membership with both fields NULL is unbounded (always active).
    """
    if when is None:
        when = datetime.now(timezone.utc)
    return membership.is_active_at(when)


def reason_inactive(
    membership: ClientMembership,
    when: Optional[datetime] = None,
) -> Optional[str]:
    """Return a human-readable reason if membership is inactive, else None.

    Useful for shaping 403 detail strings:
        if not is_membership_active(m):
            raise HTTPException(403, reason_inactive(m) or "Membership not active")
    """
    if when is None:
        when = datetime.now(timezone.utc)
    if membership.access_start and when < membership.access_start:
        return (
            f"Membership access has not started "
            f"(begins {membership.access_start.isoformat()})"
        )
    if membership.access_end and when > membership.access_end:
        return (
            f"Membership access has expired "
            f"(ended {membership.access_end.isoformat()})"
        )
    return None
