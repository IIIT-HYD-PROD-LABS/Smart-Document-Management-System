"""Field-level PII encryption — Phase 9 INFRA-06.

Uses cryptography.fernet.Fernet (AES-128-CBC + HMAC-SHA256 + URL-safe encoding)
with rotation support via MultiFernet. The active key is read from FERNET_KEY
env var; if rotation is needed, set FERNET_KEY_OLD to the previous key.

Generate a key once via:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Tests use `monkeypatch.setenv("FERNET_KEY", ...)` — call `reset_cipher_cache()`
after each setenv so the lru_cache picks up the new key.
"""
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet


@lru_cache(maxsize=1)
def _build_cipher_for_key(active_key: str, old_key: Optional[str]) -> MultiFernet:
    keys = [Fernet(active_key.encode())]
    if old_key:
        keys.append(Fernet(old_key.encode()))
    return MultiFernet(keys)


def _get_cipher() -> MultiFernet:
    active_key = os.environ.get("FERNET_KEY")
    if not active_key:
        raise RuntimeError(
            "FERNET_KEY env var is not set. Generate one via "
            "Fernet.generate_key().decode() and add to .env."
        )
    old_key = os.environ.get("FERNET_KEY_OLD")
    return _build_cipher_for_key(active_key, old_key)


def encrypt_field(plaintext):
    """Encrypt a string. Returns bytes suitable for a BYTEA column.

    Returns None if plaintext is None (passes through nullable columns).
    """
    if plaintext is None:
        return None
    return _get_cipher().encrypt(plaintext.encode("utf-8"))


def decrypt_field(ciphertext):
    """Decrypt a Fernet token. Raises InvalidToken on tampering or wrong key.

    Returns None if ciphertext is None (passes through nullable columns).
    """
    if ciphertext is None:
        return None
    return _get_cipher().decrypt(ciphertext).decode("utf-8")


def reset_cipher_cache() -> None:
    """Test-only: clear the lru_cache so monkeypatched FERNET_KEY takes effect."""
    _build_cipher_for_key.cache_clear()
