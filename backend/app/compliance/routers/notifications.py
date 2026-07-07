"""Phase 11 WebSocket notifications endpoint.

Auth: client passes JWT via initial query string `?token=...`. Server
decodes, looks up user, verifies they have an active ClientMembership
for the requested client_id (passed as `?client_id=...`).

Cross-client subscription is intentionally NOT supported on the WebSocket
— a single connection corresponds to a single client tenant. Frontend
opens a new connection on client switch.

Hardening (#5, code-reviewer M): membership is RE-validated every
``MEMBERSHIP_RECHECK_SECONDS`` so an auditor whose ``access_end`` passes
mid-session is disconnected. The DB session used for auth is closed
before entering the receive loop so long-lived WebSocket connections
don't pin one connection-pool slot for their whole lifetime.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.middleware.auditor_expiry import is_membership_active
from app.compliance.middleware.tenant_context import current_user_id_var
from app.compliance.models.membership import ClientMembership
from app.compliance.websocket.manager import get_manager
from app.database import AsyncSessionLocal
from app.models.user import User
from app.utils.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()


# How long receive_text() blocks before we wake up to re-check membership.
MEMBERSHIP_RECHECK_SECONDS = 60.0


async def _validate_session(token: str, client_id: int) -> Optional[tuple[int, ClientMembership]]:
    """One-shot validation in a short-lived DB session. Returns
    (user_id, membership) on success, or None on auth failure."""
    db: AsyncSession = AsyncSessionLocal()
    try:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id is None:
                return None
            user_id = int(user_id)
        except Exception:
            return None

        # WebSocket scope does not run TenantContextMiddleware, so under
        # app_runtime the membership lookup below would fail-closed (zero rows).
        # Set app.user_id so the self_membership_view RLS policy authorizes the
        # user to read their own membership row.
        current_user_id_var.set(user_id)

        user = await db.get(User, user_id)
        if user is None:
            return None

        result = await db.execute(
            select(ClientMembership).where(
                ClientMembership.user_id == user_id,
                ClientMembership.client_id == client_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None or not is_membership_active(membership):
            return None

        # Detach from the session before we close it so the caller can
        # still read scalar attributes (id, access_end). We don't follow
        # relationships post-close.
        db.expunge(membership)
        return user_id, membership
    finally:
        await db.close()


async def _membership_still_active(user_id: int, client_id: int) -> bool:
    """Re-check on a fresh DB session; True iff membership still active."""
    db: AsyncSession = AsyncSessionLocal()
    try:
        # See _validate_session: set app.user_id so the self_membership_view
        # RLS policy authorizes this lookup under app_runtime (WS has no
        # middleware-set tenant context).
        current_user_id_var.set(user_id)
        result = await db.execute(
            select(ClientMembership).where(
                ClientMembership.user_id == user_id,
                ClientMembership.client_id == client_id,
            )
        )
        m = result.scalar_one_or_none()
        return m is not None and is_membership_active(m)
    finally:
        await db.close()


@router.websocket("/ws/notifications")
async def notifications_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    client_id: int = Query(...),
):
    """JWT-authenticated WebSocket per-client subscription."""
    auth = await _validate_session(token, client_id)
    if auth is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id, _membership = auth

    manager = get_manager()
    await manager.connect(websocket, client_id=client_id, user_id=user_id)
    last_recheck = asyncio.get_event_loop().time()

    async def _recheck_or_close() -> bool:
        """Returns True if connection should stay open, False if closed."""
        if not await _membership_still_active(user_id, client_id):
            logger.info(
                "WebSocket membership inactive for user_id=%d "
                "client_id=%d — closing",
                int(user_id), int(client_id),
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False
        try:
            decode_access_token(token)
        except Exception:
            logger.info(
                "WebSocket token invalid/expired for user_id=%d — closing",
                int(user_id),
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False
        return True

    try:
        while True:
            try:
                # Wake up periodically to re-validate membership even when
                # the client is silent — auditor windows expire mid-session.
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=MEMBERSHIP_RECHECK_SECONDS,
                )
                # H-F second hardening: a chatty client (frequent ping/heartbeat)
                # would never hit the TimeoutError branch, evading the recheck
                # forever. Force a recheck if more than MEMBERSHIP_RECHECK_SECONDS
                # has elapsed since the last one regardless of receive activity.
                now = asyncio.get_event_loop().time()
                if now - last_recheck >= MEMBERSHIP_RECHECK_SECONDS:
                    last_recheck = now
                    if not await _recheck_or_close():
                        return
            except asyncio.TimeoutError:
                last_recheck = asyncio.get_event_loop().time()
                if not await _recheck_or_close():
                    return
                continue
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket loop error")
    finally:
        await manager.disconnect(
            websocket, client_id=client_id, user_id=user_id
        )
