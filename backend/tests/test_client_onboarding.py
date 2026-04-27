"""CLIENT-05: Onboarding workflow creates Client + Registrations + Memberships atomically."""

import pytest


pytestmark = pytest.mark.integration


def test_atomic_creation(db_as_app_runtime, mock_current_user):
    from app.compliance.models.client import Client
    from app.compliance.services.client_service import onboard_client
    result = onboard_client(
        db=db_as_app_runtime,
        details={"name": "Onboard Test Pvt Ltd", "client_type": "pvt_ltd"},
        registrations=[
            {"type": "GSTIN", "value": "27AAAAA0000A1Z5", "state": "27"},
            {"type": "PAN", "value": "AAAAA0000A"},
        ],
        team=[{"user_id": mock_current_user.id, "compliance_role": "compliance_head"}],
        actor=mock_current_user,
    )
    assert result.id is not None
    c = db_as_app_runtime.query(Client).filter(Client.id == result.id).first()
    assert c is not None
    assert len(c.registrations) == 2
    assert len(c.memberships) == 1
