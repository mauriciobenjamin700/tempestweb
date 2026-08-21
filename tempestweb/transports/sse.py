"""Server-Sent Events transport for Mode B (phase B5).

SSE is unidirectional (server → client), so this transport splits the duplex
``PatchTransport`` contract across two HTTP channels that together carry the
**same** wire format as the WebSocket transport:

- **server → client:** a long-lived ``text/event-stream`` response. Each tick's
  ``patches`` envelope (and any ``native_call``) is emitted as one SSE event whose
  ``data:`` line is the JSON envelope and whose ``id:`` line is a monotonic tick
  id. A named ``ping`` event is emitted on a fixed interval as a heartbeat.
- **client → server:** the client POSTs each ``event`` / ``native_result``
  envelope to a per-session URL; the server feeds it to this transport via
  :meth:`feed_inbound`.

Reconnection: the client reconnects with a ``Last-Event-ID`` header; the stream
replays every buffered envelope newer than that id before resuming live output,
so no tick is lost across a dropped connection.

The buffer is the **single** source of outbound envelopes: a stream is a cursor
over it, not a consumer of a queue. That is what makes a reconnect correct —
two streams (the dropped one and its replacement) would otherwise split one
queue between them, each getting half the ticks, and the replay would re-deliver
what the queue still held. A cursor also lets :meth:`SSETransport.missed_since`
report that the buffer no longer covers a client's gap, so the caller can push a
full resync instead of letting index-relative patches land on a stale tree. A
new stream takes over: the previous one is retired at its next wake-up.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from tempestweb.core.constants import (
    DEFAULT_SSE_PING_INTERVAL,
    DEFAULT_SSE_REPLAY_BUFFER,
)
from tempestweb.transports.base import (
    Envelope,
    Event,
    NativeEvent,
    NativeResult,
    Patch,
    TransportClosedError,
    encode_native_call,
    encode_native_subscribe,
    encode_native_unsubscribe,
    encode_navigate,
    encode_patches,
)

__all__ = ["SSETransport"]

#: Heartbeat interval (seconds) between ``ping`` events on the SSE stream.
DEFAULT_PING_INTERVAL: float = DEFAULT_SSE_PING_INTERVAL

#: How many recent envelopes to retain for ``Last-Event-ID`` replay.
DEFAULT_REPLAY_BUFFER: int = DEFAULT_SSE_REPLAY_BUFFER


class SSETransport:
    """:class:`~tempestweb.transports.base.PatchTransport` over SSE + HTTP POST.

    Outbound envelopes are buffered (and assigned monotonic ids) so the SSE
    stream can replay them after a reconnect. Inbound envelopes are pushed in by
    the POST endpoint via :meth:`feed_inbound`.

    Attributes:
        ping_interval: Seconds between heartbeat ``ping`` events.
    """

    def __init__(
        self,
        *,
        ping_interval: float = DEFAULT_PING_INTERVAL,
        replay_buffer: int = DEFAULT_REPLAY_BUFFER,
    ) -> None:
        """Initialize the SSE transport.

        Args:
            ping_interval: Seconds between heartbeat ``ping`` events.
            replay_buffer: Max recent envelopes retained for reconnect replay.
        """
        self.ping_interval: float = ping_interval
        self._replay_buffer: int = replay_buffer
        self._history: list[tuple[int, Envelope]] = []
        self._waiters: set[asyncio.Event] = set()
        self._stream_generation: int = 0
        self._events: asyncio.Queue[Event] = asyncio.Queue()
        self._native_result_handler: Callable[[NativeResult], None] | None = None
        self._native_event_handler: Callable[[NativeEvent], None] | None = None
        self._next_id: int = 0
        self._closed: bool = False

    async def send_patches(self, patches: list[Patch]) -> None:
        """Queue a patch batch as a ``patches`` envelope for the SSE stream.

        Args:
            patches: JSON-able patch dicts for one tick. Empty batches are skipped.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        if not patches:
            return
        self._enqueue(encode_patches(patches))

    async def send_navigate(self, path: str) -> None:
        """Queue a ``navigate`` envelope for the SSE stream (view → URL).

        Args:
            path: The new top-route path the app navigated to.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        self._enqueue(encode_navigate(path))

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Queue a ``native_call`` envelope for the SSE stream.

        Args:
            call_id: Correlation id matching the awaited ``native_result``.
            capability: Stable capability name.
            args: JSON-able arguments for the capability.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        self._enqueue(encode_native_call(call_id, capability, args))

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Queue a ``native_subscribe`` envelope for the SSE stream (T-EV).

        Args:
            sub_id: Correlation id every ``native_event`` of this stream carries.
            capability: Stable streaming capability name.
            args: JSON-able subscription arguments.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        self._enqueue(encode_native_subscribe(sub_id, capability, args))

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Queue a ``native_unsubscribe`` envelope for the SSE stream (T-EV).

        Args:
            sub_id: The id of the subscription to close.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        self._enqueue(encode_native_unsubscribe(sub_id))

    def _enqueue(self, envelope: Envelope) -> None:
        """Assign a tick id, append to the replay buffer, and wake the stream.

        The buffer is the only place an outbound envelope lives; the open stream
        reads it through its own cursor. Appending (rather than also pushing to a
        queue) is what keeps a reconnect from seeing a tick twice.

        Args:
            envelope: The JSON-able envelope to send to the client.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        if self._closed:
            raise TransportClosedError("sse transport is closed")
        self._next_id += 1
        self._history.append((self._next_id, envelope))
        if len(self._history) > self._replay_buffer:
            del self._history[: -self._replay_buffer]
        self._notify()

    def _notify(self) -> None:
        """Wake every open stream so it drains the envelopes it has not seen."""
        for waiter in self._waiters:
            waiter.set()

    @property
    def last_id(self) -> int:
        """The id of the most recently queued envelope (``0`` before the first)."""
        return self._next_id

    def missed_since(self, last_event_id: int) -> bool:
        """Whether the replay buffer no longer covers everything after an id.

        A reconnecting client asks to resume after the last tick it applied. When
        the buffer has since dropped one of the ticks in between, resuming would
        silently skip it — and patches are index-relative, so the client would
        keep applying to a tree that no longer matches. The caller answers a
        ``True`` here by pushing a full resync.

        Args:
            last_event_id: The client's ``Last-Event-ID`` (the last tick it saw).

        Returns:
            ``True`` when at least one envelope after ``last_event_id`` has been
            evicted from the buffer.
        """
        if last_event_id >= self._next_id:
            return False
        if not self._history:
            return True
        return self._history[0][0] > last_event_id + 1

    def feed_inbound(self, envelope: Envelope) -> None:
        """Route one inbound envelope POSTed by the client.

        ``event`` envelopes are queued for :meth:`recv_event`; ``native_result``
        envelopes go to the registered handler. Bare event dicts (no ``kind``)
        are also accepted as events for forward compatibility.

        Args:
            envelope: The JSON-able envelope from the client's POST body.
        """
        kind = envelope.get("kind")
        if kind == "event":
            data = envelope.get("data")
            if isinstance(data, dict):
                self._events.put_nowait(data)
        elif kind == "native_result":
            if self._native_result_handler is not None:
                self._native_result_handler(envelope)
        elif kind == "native_event":
            if self._native_event_handler is not None:
                self._native_event_handler(envelope)
        elif kind is None and "type" in envelope:
            self._events.put_nowait(envelope)

    async def recv_event(self) -> Event:
        """Await the next user event POSTed by the client.

        Returns:
            The next user event dict.

        Raises:
            TransportClosedError: If the transport closed before an event.
        """
        event = await self._events.get()
        if self._closed and not event:
            raise TransportClosedError("sse transport is closed")
        return event

    def on_native_result(self, handler: Callable[[NativeResult], None]) -> None:
        """Register the sink for inbound ``native_result`` envelopes.

        Args:
            handler: Callback receiving each JSON-able ``native_result`` payload.
        """
        self._native_result_handler = handler

    def on_native_event(self, handler: Callable[[NativeEvent], None]) -> None:
        """Register the sink for inbound ``native_event`` envelopes (T-EV).

        Args:
            handler: Callback receiving each JSON-able ``native_event`` payload.
        """
        self._native_event_handler = handler

    async def stream(self, last_event_id: int | None = None) -> AsyncIterator[str]:
        """Yield SSE-framed text for the ``text/event-stream`` response.

        Walks the replay buffer with a cursor: every buffered envelope past
        ``last_event_id`` is emitted in id order, then the stream waits for new
        ones, emitting a named ``ping`` heartbeat whenever it idles for
        ``ping_interval``. A fresh connection (``None``) starts at the beginning
        of the buffer, so envelopes queued before the stream opened — the initial
        mount, most importantly — are not lost.

        Opening a stream **retires** any earlier one on this transport: the
        previous cursor stops at its next wake-up. Two live streams would
        otherwise both be told about every envelope while the client that owns
        the session sees only its own, and (before the cursor rewrite) would have
        split one queue between them.

        Args:
            last_event_id: The client's ``Last-Event-ID`` (the last tick it saw),
                or ``None`` on a fresh connection.

        Yields:
            SSE wire chunks (``id:``/``event:``/``data:`` blocks terminated by a
            blank line), ready to write to the response body.
        """
        self._stream_generation += 1
        generation = self._stream_generation
        self._notify()
        waiter = asyncio.Event()
        self._waiters.add(waiter)
        cursor = 0 if last_event_id is None else last_event_id
        try:
            while not self._closed and generation == self._stream_generation:
                waiter.clear()
                pending = [item for item in self._history if item[0] > cursor]
                if pending:
                    for tick_id, envelope in pending:
                        yield _frame(tick_id, envelope)
                        cursor = tick_id
                    continue
                try:
                    await asyncio.wait_for(waiter.wait(), timeout=self.ping_interval)
                except TimeoutError:
                    yield ": ping\nevent: ping\ndata: {}\n\n"
        finally:
            self._waiters.discard(waiter)

    async def close(self) -> None:
        """Tear down the transport, unblocking the stream and event pump."""
        if self._closed:
            return
        self._closed = True
        self._events.put_nowait({})
        self._notify()  # wake every open stream so it observes the close


def _frame(tick_id: int, envelope: Envelope) -> str:
    """Render one envelope as an SSE event block.

    Args:
        tick_id: The monotonic tick id used for the SSE ``id:`` field.
        envelope: The JSON-able envelope to place in the ``data:`` field.

    Returns:
        The SSE wire text for this event (``id``/``data`` lines + blank line).
    """
    payload = json.dumps(envelope, separators=(",", ":"))
    return f"id: {tick_id}\ndata: {payload}\n\n"
