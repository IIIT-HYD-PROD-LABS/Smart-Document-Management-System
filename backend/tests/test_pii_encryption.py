"""INFRA-06: Fernet PII encryption roundtrip."""

import pytest


def test_fernet_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", key.decode())
    from app.compliance.utils.pii_encryption import decrypt_field, encrypt_field
    plaintext = "27AAAAA0000A1Z5"
    ct = encrypt_field(plaintext)
    assert ct != plaintext.encode()
    assert decrypt_field(ct) == plaintext


def test_decrypt_with_wrong_key_raises(monkeypatch):
    from cryptography.fernet import Fernet, InvalidToken
    from app.compliance.utils.pii_encryption import decrypt_field, encrypt_field
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    ct = encrypt_field("test")
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    with pytest.raises(InvalidToken):
        decrypt_field(ct)
