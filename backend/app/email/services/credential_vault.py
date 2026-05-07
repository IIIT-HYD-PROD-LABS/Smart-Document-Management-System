"""Gmail credential vault — Phase 15 EMAIL-03 + EMAIL-10.

Reuses Phase 9 INFRA-06 Fernet helper (encrypt_field/decrypt_field) for
refresh-token-at-rest encryption. Plaintext refresh tokens never logged.

handle_invalid_grant flips status to revoked, removes the APScheduler job,
and emits a gmail.connection.lost Phase 11 alert event so the frontend
banner triggers (EMAIL-10).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.compliance.utils.pii_encryption import decrypt_field, encrypt_field
from app.email.models.credential import GmailCredential

logger = logging.getLogger(__name__)


def save_credential(
    db: Session,
    *,
    user_id: int,
    client_id: int,
    refresh_token: str,
    scopes: str | None = None,
    google_account_email: str | None = None,
) -> GmailCredential:
    if not refresh_token:
        raise ValueError("refresh_token is required")
    existing = (
        db.query(GmailCredential)
        .filter(
            GmailCredential.user_id == user_id,
            GmailCredential.client_id == client_id,
        )
        .first()
    )
    encrypted = encrypt_field(refresh_token)
    if existing:
        existing.refresh_token_enc = encrypted
        existing.scopes = scopes
        existing.google_account_email = google_account_email
        existing.status = GmailCredential.STATUS_ACTIVE
        cred = existing
    else:
        cred = GmailCredential(
            user_id=user_id,
            client_id=client_id,
            refresh_token_enc=encrypted,
            scopes=scopes,
            google_account_email=google_account_email,
            status=GmailCredential.STATUS_ACTIVE,
        )
        db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


def load_credential(db: Session, credential_id: int) -> tuple[GmailCredential, str]:
    cred = (
        db.query(GmailCredential)
        .filter(GmailCredential.id == credential_id)
        .first()
    )
    if cred is None:
        raise ValueError(f"GmailCredential {credential_id} not found")
    plaintext = decrypt_field(cred.refresh_token_enc)
    return cred, plaintext


def handle_invalid_grant(db: Session, credential_id: int) -> None:
    cred = (
        db.query(GmailCredential)
        .filter(GmailCredential.id == credential_id)
        .first()
    )
    if cred is None:
        return
    cred.status = GmailCredential.STATUS_REVOKED
    db.commit()

    from app.compliance.services.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is not None:
        try:
            sched.remove_job(f"gmail_scan_{credential_id}")
        except Exception as e:
            logger.warning(
                "scheduler.remove_job failed for credential %s: %s",
                credential_id,
                e,
            )

    try:
        from app.compliance.services.alert_service import dispatch_alert

        dispatch_alert(
            event_type="gmail.connection.lost",
            user_id=cred.user_id,
            client_id=cred.client_id,
            details={"credential_id": credential_id},
        )
    except (ImportError, TypeError) as e:
        # TypeError covers signature mismatch — Phase 11 dispatch_alert has
        # a different signature (takes notice + recipients). Wire-up to a
        # bill/credential-shaped alert pathway lands in Plan 05.
        logger.warning(
            "gmail.connection.lost alert emit skipped (%s): %s",
            type(e).__name__,
            e,
        )
