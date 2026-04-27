"""CLIENT-01, CLIENT-02: client + multi-GSTIN registrations."""

import pytest


pytestmark = pytest.mark.integration


def test_create_with_registrations(db_as_app_runtime):
    from app.compliance.models.client import Client, ClientRegistration
    c = Client(name="Acme Pvt Ltd", client_type="pvt_ltd")
    db_as_app_runtime.add(c)
    db_as_app_runtime.commit()
    r1 = ClientRegistration(
        client_id=c.id, type="GSTIN",
        value="27AAAAA0000A1Z5", state="27", is_active=True,
    )
    r2 = ClientRegistration(
        client_id=c.id, type="PAN",
        value="AAAAA0000A", is_active=True,
    )
    db_as_app_runtime.add_all([r1, r2])
    db_as_app_runtime.commit()
    regs = (
        db_as_app_runtime.query(ClientRegistration)
        .filter(ClientRegistration.client_id == c.id)
        .all()
    )
    assert len(regs) == 2


def test_multi_gstin(db_as_app_runtime):
    from app.compliance.models.client import Client, ClientRegistration
    c = Client(name="Multi-State Pvt Ltd", client_type="pvt_ltd")
    db_as_app_runtime.add(c)
    db_as_app_runtime.commit()
    for state, gstin in (("27", "27AAAAA0000A1Z5"), ("29", "29AAAAA0000A1Z9")):
        db_as_app_runtime.add(
            ClientRegistration(
                client_id=c.id, type="GSTIN",
                value=gstin, state=state, is_active=True,
            )
        )
    db_as_app_runtime.commit()
    regs = (
        db_as_app_runtime.query(ClientRegistration)
        .filter(
            ClientRegistration.client_id == c.id,
            ClientRegistration.type == "GSTIN",
        )
        .all()
    )
    assert len(regs) == 2
