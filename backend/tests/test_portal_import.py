"""Portal import unit tests (kinds map + router wiring smoke)."""
from __future__ import annotations

from app.compliance.routers.portal import PORTAL_AUTHORITY, PORTAL_LABELS


def test_every_portal_kind_has_authority_and_label():
    assert set(PORTAL_AUTHORITY) == set(PORTAL_LABELS)
    for kind, auth in PORTAL_AUTHORITY.items():
        assert auth in {"GST", "IT", "MCA", "SEBI", "RBI"}
        assert PORTAL_LABELS[kind]


def test_gst_and_it_defaults():
    assert PORTAL_AUTHORITY["gst_portal"] == "GST"
    assert PORTAL_AUTHORITY["it_efiling"] == "IT"
