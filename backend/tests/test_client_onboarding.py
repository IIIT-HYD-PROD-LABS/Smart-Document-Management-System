"""CLIENT-05: Onboarding workflow creates Client + Registrations + Memberships atomically."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionBootstrap

pytestmark = pytest.mark.integration


async def test_atomic_creation(mock_current_user):
    """onboard_client is async (async-migration Phase 5); uses the owner
    bootstrap session directly (RLS-bypassed, same effective role as the
    sync `db_as_app_runtime` default used before this test converted) --
    this test exercises atomicity/aggregation correctness, not tenant
    isolation.
    """
    from app.compliance.models.client import Client
    from app.compliance.services.client_service import onboard_client

    async with AsyncSessionBootstrap() as db:
        result = await onboard_client(
            db=db,
            details={"name": "Onboard Test Pvt Ltd", "client_type": "pvt_ltd"},
            registrations=[
                {"type": "GSTIN", "value": "27AAAAA0000A1Z5", "state": "27"},
                {"type": "PAN", "value": "AAAAA0000A"},
            ],
            team=[{"user_id": mock_current_user.id, "compliance_role": "compliance_head"}],
            actor=mock_current_user,
        )
        assert result.id is not None

        c = (
            await db.execute(
                select(Client)
                .options(
                    selectinload(Client.registrations),
                    selectinload(Client.memberships),
                )
                .where(Client.id == result.id)
            )
        ).scalar_one_or_none()
        assert c is not None
        assert len(c.registrations) == 2
        assert len(c.memberships) == 1
