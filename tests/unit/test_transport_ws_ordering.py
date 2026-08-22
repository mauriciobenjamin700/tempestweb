"""Outbound frames leave the WebSocket transport in the order they were queued.

A Mode B session cannot await inside the core's coalesced rebuild, so it spawns
one send task per tick. Two tasks writing the same socket concurrently could
otherwise interleave, and patches are index-relative: a swapped pair corrupts the
client's tree. The transport serializes sends behind a FIFO lock; these tests pin
that, with a socket whose first write is deliberately slower than its second.
"""

from __future__ import annotations

import asyncio
from typing import Any

from starlette.websockets import WebSocketState

from tempestweb.transports.websocket import WebSocketTransport


class SlowFirstWebSocket:
    """A socket duble whose first ``send_json`` takes longer than its second."""

    def __init__(self, delays: list[float]) -> None:
        """Store the per-send delays and the order writes completed in."""
        self.client_state = WebSocketState.CONNECTED
        self._delays = iter(delays)
        self.written: list[int] = []

    async def send_json(self, envelope: dict[str, Any]) -> None:
        """Sleep this write's delay, then record the batch it carried."""
        await asyncio.sleep(next(self._delays, 0.0))
        self.written.append(envelope["data"][0]["tick"])


async def test_concurrent_sends_reach_the_wire_in_queue_order() -> None:
    """Two tasks queued in order write in order, even when the first is slower."""
    socket = SlowFirstWebSocket([0.05, 0.0])
    transport = WebSocketTransport(socket)  # type: ignore[arg-type]

    first = asyncio.ensure_future(transport.send_patches([{"tick": 1}]))
    second = asyncio.ensure_future(transport.send_patches([{"tick": 2}]))
    await asyncio.gather(first, second)

    assert socket.written == [1, 2]


async def test_sends_stay_ordered_across_envelope_kinds() -> None:
    """A patches batch queued before a navigate is written before it."""
    order: list[str] = []

    class RecordingWebSocket:
        """A socket duble recording the ``kind`` of every envelope written."""

        def __init__(self) -> None:
            """Start connected, with the first write slower than the second."""
            self.client_state = WebSocketState.CONNECTED
            self._delays = iter([0.05, 0.0])

        async def send_json(self, envelope: dict[str, Any]) -> None:
            """Sleep this write's delay, then record the envelope kind."""
            await asyncio.sleep(next(self._delays, 0.0))
            order.append(str(envelope["kind"]))

    transport = WebSocketTransport(RecordingWebSocket())  # type: ignore[arg-type]
    patches = asyncio.ensure_future(transport.send_patches([{"tick": 1}]))
    navigate = asyncio.ensure_future(transport.send_navigate("/settings"))
    await asyncio.gather(patches, navigate)

    assert order == ["patches", "navigate"]
