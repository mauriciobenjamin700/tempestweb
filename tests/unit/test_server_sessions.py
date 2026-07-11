"""Tests for the SSE session routers (Track S — S4).

The in-process router feeds the local transport; the Redis router publishes to a
channel when the session is remote and, when bound, feeds its transport from
messages published on any instance. A fake redis client (duck-typed pub/sub)
stands in for a live server.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from tempestweb.server.sessions import InProcessRouter, RedisSessionRouter
from tempestweb.transports.sse import SSETransport


async def test_in_process_router_feeds_local() -> None:
    router = InProcessRouter()
    transport = SSETransport()
    assert await router.deliver("s1", {"type": "x"}, transport) is True
    # Unknown (remote) session -> not routable in-process.
    assert await router.deliver("s1", {"type": "x"}, None) is False
    teardown = await router.bind("s1", transport)
    await teardown()  # no-op, does not raise


class _FakePubSub:
    def __init__(self, bus: dict[str, list[_FakePubSub]]) -> None:
        self._bus = bus
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._channel: str | None = None
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self._channel = channel
        self._bus.setdefault(channel, []).append(self)

    async def unsubscribe(self, channel: str) -> None:
        self._bus.get(channel, []).remove(self)

    async def aclose(self) -> None:
        self.closed = True

    def deliver(self, data: str) -> None:
        self._queue.put_nowait({"type": "message", "data": data})

    async def listen(self) -> Any:
        while True:
            yield await self._queue.get()


class _FakeRedis:
    """A minimal redis.asyncio-compatible client for tests."""

    def __init__(self) -> None:
        self.channels: dict[str, list[_FakePubSub]] = {}
        self.published: list[tuple[str, str]] = []

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self.channels)

    async def publish(self, channel: str, data: str) -> None:
        self.published.append((channel, data))
        for sub in self.channels.get(channel, []):
            sub.deliver(data)


async def test_redis_router_publishes_when_remote() -> None:
    client = _FakeRedis()
    router = RedisSessionRouter(client, prefix="tw:sse:")
    # No local transport -> publish to the channel.
    assert await router.deliver("abc", {"type": "click"}, None) is True
    assert client.published == [("tw:sse:abc", json.dumps({"type": "click"}))]


async def test_redis_router_feeds_local_without_publish() -> None:
    client = _FakeRedis()
    router = RedisSessionRouter(client)
    transport = SSETransport()
    assert await router.deliver("abc", {"type": "x"}, transport) is True
    assert client.published == []  # local fast path, no round-trip


async def test_redis_router_bind_delivers_published_events() -> None:
    client = _FakeRedis()
    router = RedisSessionRouter(client, prefix="tw:sse:")
    transport = SSETransport()
    fed: list[dict[str, Any]] = []
    transport.feed_inbound = fed.append  # type: ignore[method-assign]

    teardown = await router.bind("abc", transport)
    # A POST on another instance publishes to the channel.
    await router.deliver("abc", {"type": "remote"}, None)
    await asyncio.sleep(0.01)  # let the subscriber task run
    assert {"type": "remote"} in fed
    await teardown()
