"""WebSocket connection manager with Redis pub/sub bridge — Phase 11 D-06.

The Celery worker dispatches alerts to a Redis channel
`notifications:{client_id}`. This manager subscribes per active client_id
and forwards to all WebSocket connections that have authenticated for
that client. A user must have an active ClientMembership to subscribe;
the JWT handshake validates this before the socket is registered.

Single-process FastAPI is sufficient for v2.0 launch volume (<100
concurrent users). v2.1 multi-process scaling reuses the same Redis
contract — no code change needed in the dispatcher.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks live WebSocket connections grouped by client_id.

    Thread-safety: the manager assumes single-event-loop usage (FastAPI
    default). Use asyncio.Lock to coordinate set mutations.
    """

    def __init__(self) -> None:
        # client_id → set[(user_id, websocket)]
        self._connections: dict[int, set] = {}
        self._redis = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket, *, client_id: int, user_id: int) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(client_id, set()).add((user_id, websocket))
        # Start the pub/sub listener on first connect
        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(self._listen_redis())

    async def disconnect(self, websocket, *, client_id: int, user_id: int) -> None:
        async with self._lock:
            conns = self._connections.get(client_id)
            if conns is not None:
                conns.discard((user_id, websocket))
                if not conns:
                    self._connections.pop(client_id, None)

    async def broadcast(self, *, client_id: int, message: dict) -> int:
        """Send message to all connections for client_id. Returns sent count."""
        sent = 0
        targets = list(self._connections.get(client_id, set()))
        for user_id, ws in targets:
            recipient_filter = message.get("recipient_user_id")
            if recipient_filter is not None and recipient_filter != user_id:
                continue
            try:
                await ws.send_text(json.dumps(message))
                sent += 1
            except Exception:
                logger.warning(
                    "WebSocket broadcast failed for client_id=%d user_id=%d",
                    client_id, user_id, exc_info=True,
                )
                # Stale connection — remove on next disconnect
        return sent

    async def _listen_redis(self) -> None:
        """Background task: subscribe to Redis pub/sub and broadcast.

        Hardening (#11) — outer reconnect loop with exponential backoff so
        a transient Redis disconnect or a malformed message no longer
        kills the bridge for the lifetime of the FastAPI process. Inner
        per-message try/except so one bad payload doesn't take down the
        listener.
        """
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("redis.asyncio unavailable — WebSocket pub/sub disabled")
            return

        import os
        url = os.environ.get("REDIS_URL")
        if not url:
            logger.warning("REDIS_URL not set — WebSocket pub/sub disabled")
            return

        backoff = 1.0
        max_backoff = 30.0
        while True:
            try:
                self._redis = aioredis.from_url(url)
                pubsub = self._redis.pubsub()
                await pubsub.psubscribe("notifications:*")
                logger.info("WebSocket pub/sub listener started")
                # Reset backoff once we've successfully subscribed.
                backoff = 1.0
                async for raw in pubsub.listen():
                    try:
                        if raw.get("type") not in ("pmessage", "message"):
                            continue
                        channel = raw.get("channel")
                        if isinstance(channel, bytes):
                            channel = channel.decode("utf-8")
                        try:
                            client_id = int(channel.split(":", 1)[1])
                        except Exception:
                            logger.warning(
                                "WebSocket bridge: malformed channel %r — skipping",
                                channel,
                            )
                            continue
                        data = raw.get("data")
                        if isinstance(data, bytes):
                            data = data.decode("utf-8")
                        try:
                            message = json.loads(data)
                        except Exception:
                            logger.warning(
                                "WebSocket bridge: malformed JSON on channel=%s — skipping",
                                channel,
                            )
                            continue
                        await self.broadcast(client_id=client_id, message=message)
                    except Exception:
                        # One bad message must not kill the listener.
                        logger.exception(
                            "WebSocket bridge: per-message handler raised — continuing",
                        )
            except Exception:
                logger.exception(
                    "WebSocket pub/sub listener disconnected — reconnecting in %.1fs",
                    backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, max_backoff)


_manager: Optional[ConnectionManager] = None


def get_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
