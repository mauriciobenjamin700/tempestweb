"""SSE inbound-event routing across instances (Track S — S4).

WebSocket sessions are self-contained (one duplex connection on one worker), so
they need **no** sticky sessions. SSE is the exception: it splits into a ``GET``
patch stream and separate ``POST`` event requests, which must reach the worker
holding the stream. In-process that means the ``POST`` looks up a local
registry — hence the sticky-session requirement for multi-instance SSE.

A :class:`SessionRouter` abstracts that routing so SSE can scale **without**
sticky sessions: the default :class:`InProcessRouter` keeps today's behavior; the
:class:`RedisSessionRouter` publishes inbound events to a Redis channel per
session and the instance holding the stream (subscribed) feeds its transport —
so a ``POST`` landing on any instance is delivered.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from tempestweb.transports.sse import SSETransport

__all__ = ["InProcessRouter", "RedisSessionRouter", "SessionRouter"]

#: A teardown coroutine returned by :meth:`SessionRouter.bind`.
Teardown = Callable[[], Awaitable[None]]


class SessionRouter(Protocol):
    """Routes SSE inbound events to the transport holding the stream."""

    async def bind(self, session_id: str, transport: SSETransport) -> Teardown:
        """Start delivering inbound events for ``session_id`` to ``transport``.

        Called when an SSE stream opens on this instance. Returns a teardown
        coroutine to call when the stream closes.
        """
        ...

    async def deliver(
        self, session_id: str, envelope: dict[str, Any], local: SSETransport | None
    ) -> bool:
        """Deliver one inbound envelope for ``session_id``.

        Args:
            session_id: The target session.
            envelope: The wire envelope (event / native_result).
            local: The transport on this instance, or ``None`` if not local.

        Returns:
            ``True`` if the event was delivered or handed off; ``False`` if it
            could not be routed (the caller returns ``404``).
        """
        ...


class InProcessRouter:
    """Single-instance router: an inbound event feeds the local transport only."""

    async def bind(self, session_id: str, transport: SSETransport) -> Teardown:
        """No cross-instance delivery is needed in-process."""

        async def _teardown() -> None:
            return None

        return _teardown

    async def deliver(
        self, session_id: str, envelope: dict[str, Any], local: SSETransport | None
    ) -> bool:
        """Feed the local transport; report ``False`` when the session is remote."""
        if local is None:
            return False
        local.feed_inbound(envelope)
        return True


class RedisSessionRouter:
    """Cross-instance SSE router over Redis pub/sub (drops the sticky need).

    Each session maps to a channel ``<prefix><session_id>``. The instance holding
    the stream subscribes and feeds its transport; a ``POST`` on any instance
    publishes to the channel (or feeds directly when the session is local).
    """

    def __init__(self, client: Any, *, prefix: str = "tw:sse:") -> None:  # noqa: ANN401 - a redis.asyncio client (duck-typed)
        """Initialize with a redis.asyncio-compatible client.

        Args:
            client: A client exposing ``publish(channel, data)`` and
                ``pubsub()`` (redis.asyncio, or a compatible fake in tests).
            prefix: The channel key prefix.
        """
        self._client: Any = client
        self._prefix: str = prefix

    @classmethod
    def from_url(cls, url: str, *, prefix: str = "tw:sse:") -> RedisSessionRouter:
        """Build a router from a Redis URL (requires the ``[cache]`` extra).

        Args:
            url: A ``redis://`` connection URL.
            prefix: The channel key prefix.

        Returns:
            A configured :class:`RedisSessionRouter`.

        Raises:
            RuntimeError: If ``redis`` is not installed.
        """
        try:
            import redis.asyncio as redis  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised via the error path
            raise RuntimeError(
                "redis is required for RedisSessionRouter; install "
                'tempest-fastapi-sdk[cache] or "redis".'
            ) from exc
        return cls(redis.from_url(url, decode_responses=True), prefix=prefix)

    async def bind(self, session_id: str, transport: SSETransport) -> Teardown:
        """Subscribe to the session's channel and feed the transport."""
        channel = self._prefix + session_id
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)

        async def _reader() -> None:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                try:
                    transport.feed_inbound(json.loads(data))
                except (ValueError, TypeError):  # pragma: no cover - defensive
                    continue

        task = asyncio.ensure_future(_reader())

        async def _teardown() -> None:
            task.cancel()
            try:
                await pubsub.unsubscribe(channel)
            finally:
                aclose = getattr(pubsub, "aclose", None) or pubsub.close
                await aclose()

        return _teardown

    async def deliver(
        self, session_id: str, envelope: dict[str, Any], local: SSETransport | None
    ) -> bool:
        """Feed a local transport directly, else publish for the holding instance."""
        if local is not None:
            local.feed_inbound(envelope)
            return True
        await self._client.publish(self._prefix + session_id, json.dumps(envelope))
        return True
