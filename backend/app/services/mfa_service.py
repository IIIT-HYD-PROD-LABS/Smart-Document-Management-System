"""TOTP-based multi-factor authentication.

Pure, DB-free logic: secret generation, QR provisioning, code verification,
single-use backup codes, and the short-lived post-password challenge token.
The router/service layer is responsible for persistence.

At-rest storage:
  - The TOTP shared secret is Fernet-encrypted (``encrypt_secret``) into
    ``users.totp_secret_enc`` (BYTEA), same pattern as Gmail creds / BYOK keys.
  - Backup codes are high-entropy (80-bit) random strings, hashed with SHA-256
    (no dictionary surface that warrants a slow hash), and the hash list is then
    Fernet-encrypted into ``users.mfa_backup_codes_enc``.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pyotp

from app.config import settings
from app.compliance.utils.pii_encryption import encrypt_field, decrypt_field

MFA_CHALLENGE_TYPE = "mfa_challenge"


# --------------------------------------------------------------------------- #
# TOTP secret + verification
# --------------------------------------------------------------------------- #
def generate_totp_secret() -> str:
    """A fresh base32 TOTP secret compatible with authenticator apps."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    """otpauth:// URI encoded into the enrollment QR."""
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=settings.MFA_ISSUER
    )


def qr_data_uri(secret: str, account_email: str) -> str:
    """PNG data URI of the provisioning QR, so the frontend can render it with a
    plain <img> and no client-side QR dependency."""
    import qrcode

    img = qrcode.make(provisioning_uri(secret, account_email))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code, allowing +/-1 time step (30s) for clock drift."""
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1)


def encrypt_secret(secret: str) -> bytes:
    return encrypt_field(secret)


def decrypt_secret(blob: bytes) -> str:
    return decrypt_field(blob)


# --------------------------------------------------------------------------- #
# Backup codes (single use)
# --------------------------------------------------------------------------- #
def _normalize_code(code: str) -> str:
    return str(code).strip().upper().replace("-", "").replace(" ", "")


def _hash_code(code: str) -> str:
    return hashlib.sha256(_normalize_code(code).encode("utf-8")).hexdigest()


def generate_backup_codes(n: int | None = None) -> list[str]:
    """Generate n human-formatted single-use backup codes (displayed once)."""
    count = n if n is not None else settings.MFA_BACKUP_CODE_COUNT
    codes: list[str] = []
    while len(codes) < count:
        raw = secrets.token_hex(10).upper()  # 20 hex chars
        formatted = f"{raw[:5]}-{raw[5:10]}-{raw[10:15]}-{raw[15:20]}"
        if formatted not in codes:
            codes.append(formatted)
    return codes


def encrypt_backup_codes(codes: list[str]) -> bytes:
    """Hash each code (SHA-256, hyphen/case-insensitive) and Fernet-encrypt the
    hash list for at-rest storage."""
    return encrypt_field(json.dumps([_hash_code(c) for c in codes]))


def verify_and_consume_backup_code(blob: bytes, code: str) -> tuple[bool, bytes | None]:
    """(matched, new_blob). On a match the used hash is removed and a fresh
    encrypted blob is returned so the code cannot be replayed. On no match,
    returns (False, None) and the caller leaves the stored blob untouched."""
    if blob is None or not code:
        return False, None
    try:
        hashes = json.loads(decrypt_field(blob))
    except Exception:
        return False, None
    h = _hash_code(code)
    if h not in hashes:
        return False, None
    hashes.remove(h)
    return True, encrypt_field(json.dumps(hashes))


# --------------------------------------------------------------------------- #
# Challenge token: proves "password step passed, awaiting second factor"
# --------------------------------------------------------------------------- #
def issue_challenge_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": MFA_CHALLENGE_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.MFA_CHALLENGE_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_challenge_token(token: str) -> int:
    """Return the user_id from a valid challenge token, else raise ValueError.

    Distinct ``type`` claim and standalone decode keep it from being usable as
    an access token (and vice-versa: decode_access_token rejects this type)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as e:
        raise ValueError("invalid or expired challenge token") from e
    if payload.get("type") != MFA_CHALLENGE_TYPE:
        raise ValueError("wrong token type")
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError) as e:
        raise ValueError("malformed challenge token") from e
