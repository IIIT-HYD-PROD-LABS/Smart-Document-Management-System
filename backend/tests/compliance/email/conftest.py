"""Phase 15 (Gmail MCP) test fixtures.

Mirrors backend/tests/conftest.py pattern. Imports parent fixtures
(db_as_app_runtime, client_a, client_b, *_user) without re-declaring.
The Phase 15 modules referenced here (app.email.*) DO NOT exist yet —
Plans 02-05 land them. Tests using these fixtures will pytest.skip()
until then. This is the intentional Wave 0 RED state.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fernet_test_key() -> bytes:
    """Deterministic Fernet key for test runs. NEVER use in prod.

    Fernet requires a 32-byte raw key, urlsafe-base64-encoded (44 bytes
    output). We derive 32 raw bytes via SHA-256 of a stable phrase so the
    encoded key is reproducible across CI runs and accepted by
    cryptography.fernet.Fernet.
    """
    raw = hashlib.sha256(b"phase15-fixture-key-deterministic").digest()
    return base64.urlsafe_b64encode(raw)


@pytest.fixture
def gmail_credential_factory(db_as_app_runtime, client_a) -> Callable:
    """Returns a factory that creates GmailCredential rows.

    Plan 02 lands the GmailCredential ORM. Until then, this fixture is a
    placeholder — tests using it will be marked pytest.skip().
    """
    def _factory(
        user_id: int,
        client_id: int = None,
        refresh_token: str = "test-refresh-token-xyz",
        **overrides,
    ):
        try:
            from app.email.models.credential import GmailCredential  # noqa: F401
        except ImportError:
            pytest.skip("GmailCredential ORM not yet implemented (Plan 02)")
        # Plan 02 fills this in; Wave 0 tests skip.
        return None
    return _factory


@pytest.fixture
def mock_gmail_service():
    """Patches googleapiclient.discovery.build and yields the MagicMock.

    Tests configure return values via the chainable mock:
        mock_gmail_service.users().messages().list().execute.return_value = {...}
    """
    try:
        import googleapiclient.discovery  # noqa: F401
    except ImportError:
        pytest.skip("google-api-python-client not yet installed (Plan 02 pip install)")
    with patch("googleapiclient.discovery.build") as build_mock:
        service = MagicMock()
        build_mock.return_value = service
        yield service


@pytest.fixture
def sample_compliance_email() -> dict:
    """Sample Gmail message JSON resembling a CBIC GST notice.

    Sender: notice@cbic-gst.gov.in (matches Phase 15 EMAIL-06 default rule).
    Body contains GSTIN + DRC-01 reference for NER extraction tests.
    """
    body = (
        "Dear Taxpayer, A Show Cause Notice u/s 73 has been issued. "
        "GSTIN: 27AABCT1234F1ZX. DRC-01 reference DRC-01/2026/12345. "
        "Please respond within 30 days."
    )
    return {
        "id": "test-msg-compliance-001",
        "threadId": "thread-001",
        "labelIds": ["INBOX"],
        "snippet": body[:100],
        "payload": {
            "headers": [
                {"name": "From", "value": "Notice Issuer <notice@cbic-gst.gov.in>"},
                {"name": "Subject", "value": "Show Cause Notice u/s 73 — Action Required"},
                {"name": "Date", "value": "Mon, 5 May 2026 10:00:00 +0530"},
            ],
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
        },
        "historyId": "hist-001",
    }


@pytest.fixture
def sample_bill_email_utility() -> dict:
    """Sample Gmail message JSON resembling a Tata Power utility bill.

    Sender: noreply@tatapower.com (matches Phase 15 BILL-01 default rule).
    Body has amount + due date + last-4 account for BILL-02 extractor tests.
    """
    body = (
        "Dear Customer, Your Tata Power bill is ready. "
        "Account number: 123456789012. Amount due: INR 4,250.00. "
        "Due date: 25th May 2026. Pay before due date to avoid late charges."
    )
    return {
        "id": "test-msg-bill-001",
        "threadId": "thread-bill-001",
        "labelIds": ["INBOX"],
        "snippet": body[:100],
        "payload": {
            "headers": [
                {"name": "From", "value": "Tata Power <noreply@tatapower.com>"},
                {"name": "Subject", "value": "Your Tata Power bill — May 2026"},
                {"name": "Date", "value": "Wed, 7 May 2026 09:00:00 +0530"},
            ],
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
        },
        "historyId": "hist-bill-001",
    }


@pytest.fixture
def sample_spam_email() -> dict:
    """Sample non-compliance, non-bill email for negative-classification tests."""
    body = "You won a lottery! Click here..."
    return {
        "id": "test-msg-spam-001",
        "labelIds": ["INBOX", "SPAM"],
        "payload": {
            "headers": [
                {"name": "From", "value": "winner@spam.example"},
                {"name": "Subject", "value": "Congratulations!"},
            ],
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
        },
    }


@pytest.fixture
def seeded_filter_rules(db_as_app_runtime, gmail_credential_factory):
    """Inserts default gov.in + tatapower rules. Skips if Plan 02 hasn't shipped yet."""
    try:
        from app.email.models.filter_rule import GmailFilterRule  # noqa: F401
    except ImportError:
        pytest.skip("GmailFilterRule ORM not yet implemented (Plan 02)")
    return None


@pytest.fixture
def body_sha256() -> Callable[[str], str]:
    """Deterministic body hash for audit-log assertions (D-35)."""
    def _hash(body: str) -> str:
        return hashlib.sha256(body.encode()).hexdigest()
    return _hash
