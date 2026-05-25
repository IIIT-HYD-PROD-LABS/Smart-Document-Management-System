"""Per-account brute-force lockout.

Complements the per-IP slowapi limit (5/min): that keys on source IP, so an
attacker rotating IPs against a single account defeats it. This tracks failures
per ACCOUNT in ``users.failed_login_count`` / ``users.locked_until``.

Policy: after ``MAX_FAILED_LOGINS`` consecutive failures the account locks for
``LOCKOUT_DURATION_MINUTES``, doubling each further failure past the threshold
(exponential backoff, capped at 24h). A successful auth resets the counter.

Functions mutate the passed ``user`` object; the caller owns the commit.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import settings

_MAX_BACKOFF_MINUTES = 24 * 60  # cap a single lock window at 24h


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def is_locked(user) -> bool:
    lu = getattr(user, "locked_until", None)
    return lu is not None and _aware(lu) > now_utc()


def seconds_remaining(user) -> int:
    lu = getattr(user, "locked_until", None)
    if lu is None:
        return 0
    return max(0, int((_aware(lu) - now_utc()).total_seconds()))


def register_failure(user) -> bool:
    """Increment the failure counter and lock (with backoff) once the threshold
    is crossed. Returns True if the account is now locked."""
    user.failed_login_count = (getattr(user, "failed_login_count", 0) or 0) + 1
    threshold = settings.MAX_FAILED_LOGINS
    if user.failed_login_count >= threshold:
        over = user.failed_login_count - threshold  # 0 on the first lock
        minutes = min(settings.LOCKOUT_DURATION_MINUTES * (2 ** over), _MAX_BACKOFF_MINUTES)
        user.locked_until = now_utc() + timedelta(minutes=minutes)
        return True
    return False


def reset(user) -> None:
    """Clear failure state after a successful authentication."""
    user.failed_login_count = 0
    user.locked_until = None
