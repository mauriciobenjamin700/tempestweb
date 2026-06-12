"""WebSocket transport for Mode B (phase B1).

Carries the wire format from ``docs/contract.md`` over a single bidirectional
WebSocket connection. Every frame is a JSON envelope:

- server → client: ``{"kind": "patches", "data": [...]}`` and
  ``{"kind": "native_call", ...}``.
- client → server: ``{"kind": "event", "data": {...}}`` and
  ``{"kind": "native_result", ...}``.

The transport owns a single inbound *demux*: a background receive task reads each
envelope and routes ``event`` payloads to a queue (drained by
:meth:`recv_event`) and ``native_result`` payloads to the handler registered via
:meth:`on_native_result`. This keeps the session loop a clean event pump while
still resolving proxied native calls.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from tempestweb.transports.base import (
    Event,
    NativeResult,
    Patch,
    TransportClosedError,
    encode_native_call,
    encode_navigate,
    encode_patches,
)

__all__ = ["WebSocketTransport"]


class WebSocketTransport:
    """:class:`~tempestweb.transports.base.PatchTransport` over a WebSocket.

    The caller is expected to have already ``accept``-ed the socket. The
    transport then runs until the peer disconnects or :meth:`close` is called.

    Attributes:
        websocket: The underlying Starlette WebSocket.
    """

    def __init__(self, websocket: WebSocket) -> None:
        """Initialize the transport over an accepted WebSocket.

        Args:
            websocket: The accepted Starlette WebSocket connection.
        """
        self.websocket: WebSocket = websocket
        self._events: asyncio.Queue[Event] = asyncio.Queue()
        self._native_result_handler: Callable[[NativeResult], None] | None = None
        self._closed: bool = False
        self._recv_task: asyncio.Task[None] | None = None

    def _ensure_pump(self) -> None:
        """Start the inbound demux task if it is not already running."""
        if self._recv_task is None and not self._closed:
            self._recv_task = asyncio.ensure_future(self._pump())

    async def _pump(self) -> None:
        """Read envelopes from the socket and route them by ``kind``.

        ``event`` envelopes are queued for :meth:`recv_event`; ``native_result``
        envelopes go to the registered handler. On disconnect the transport is
        marked closed and a sentinel unblocks any pending :meth:`recv_event`.
        """
        try:
            while not self._closed:
                envelope: dict[str, Any] = await self.websocket.receive_json()
                kind = envelope.get("kind")
                if kind == "event":
                    data = envelope.get("data")
                    if isinstance(data, dict):
                        await self._events.put(data)
                elif kind == "native_result":
                    if self._native_result_handler is not None:
                        self._native_result_handler(envelope)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            self._closed = True
            await self._events.put({})  # sentinel to unblock recv_event

    async def send_patches(self, patches: list[Patch]) -> None:
        """Send a patch batch as a ``patches`` envelope.

        Args:
            patches: JSON-able patch dicts for one tick. Empty batches are skipped.

        Raises:
            TransportClosedError: If the socket is no longer connected.
        """
        if not patches:
            return
        await self._send(encode_patches(patches))

    async def send_navigate(self, path: str) -> None:
        """Send a ``navigate`` envelope so the client syncs its URL (view → URL).

        Args:
            path: The new top-route path the app navigated to.

        Raises:
            TransportClosedError: If the socket is no longer connected.
        """
        await self._send(encode_navigate(path))

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Send a ``native_call`` envelope asking the client to run a capability.

        Args:
            call_id: Correlation id matching the awaited ``native_result``.
            capability: Stable capability name.
            args: JSON-able arguments for the capability.

        Raises:
            TransportClosedError: If the socket is no longer connected.
        """
        await self._send(encode_native_call(call_id, capability, args))

    async def _send(self, envelope: dict[str, Any]) -> None:
        """Serialize and send one envelope, mapping disconnects to closed errors.

        Args:
            envelope: The JSON-able wire envelope to send.

        Raises:
            TransportClosedError: If the socket is closed or disconnects mid-send.
        """
        if self._closed or self.websocket.client_state != WebSocketState.CONNECTED:
            raise TransportClosedError("websocket is closed")
        try:
            await self.websocket.send_json(envelope)
        except (WebSocketDisconnect, RuntimeError) as exc:
            self._closed = True
            raise TransportClosedError("websocket disconnected") from exc

    async def recv_event(self) -> Event:
        """Await the next user event from the client.

        Starts the inbound demux on first call. ``native_result`` envelopes are
        consumed by the demux, never returned here.

        Returns:
            The next user event dict.

        Raises:
            TransportClosedError: If the connection closed before an event.
        """
        self._ensure_pump()
        event = await self._events.get()
        if self._closed and not event:
            raise TransportClosedError("websocket disconnected")
        return event

    def on_native_result(self, handler: Callable[[NativeResult], None]) -> None:
        """Register the sink for inbound ``native_result`` envelopes.

        Args:
            handler: Callback receiving each JSON-able ``native_result`` payload.
        """
        self._native_result_handler = handler

    async def close(self) -> None:
        """Tear down the transport and close the WebSocket. Idempotent."""
        was_closed = self._closed
        self._closed = True
        if self._recv_task is not None:
            self._recv_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._recv_task
            self._recv_task = None
        if not was_closed and self.websocket.client_state == WebSocketState.CONNECTED:
            with suppress(WebSocketDisconnect, RuntimeError):
                await self.websocket.close()
