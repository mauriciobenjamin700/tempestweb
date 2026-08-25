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
import json
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from tempestweb.transports.base import (
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
    encode_theme,
)

__all__ = ["WebSocketTransport"]

_LOGGER = logging.getLogger("tempestweb.transports.websocket")


class WebSocketTransport:
    """:class:`~tempestweb.transports.base.PatchTransport` over a WebSocket.

    The caller is expected to have already ``accept``-ed the socket. The
    transport then runs until the peer disconnects or :meth:`close` is called.

    Attributes:
        websocket: The underlying Starlette WebSocket.
    """

    def __init__(
        self,
        websocket: WebSocket,
        *,
        allow_inbound: Callable[[], bool] | None = None,
    ) -> None:
        """Initialize the transport over an accepted WebSocket.

        Args:
            websocket: The accepted Starlette WebSocket connection.
            allow_inbound: Optional per-frame admission check (S2). Called once
                per inbound envelope; returning ``False`` closes the socket with
                ``1013`` (try again later) instead of routing the frame, so a
                flood over an already-accepted connection is bounded the same way
                a flood of new connections is. ``None`` accepts every frame.
        """
        self.websocket: WebSocket = websocket
        self._allow_inbound: Callable[[], bool] | None = allow_inbound
        self._events: asyncio.Queue[Event] = asyncio.Queue()
        self._native_result_handler: Callable[[NativeResult], None] | None = None
        self._native_event_handler: Callable[[NativeEvent], None] | None = None
        self._closed: bool = False
        self._recv_task: asyncio.Task[None] | None = None
        self._send_lock: asyncio.Lock = asyncio.Lock()

    def _ensure_pump(self) -> None:
        """Start the inbound demux task if it is not already running."""
        if self._recv_task is None and not self._closed:
            self._recv_task = asyncio.ensure_future(self._pump())

    async def _receive_envelope(self) -> dict[str, Any] | None:
        """Read the next frame from the socket and decode it as a wire envelope.

        Both a text and a binary frame are accepted: the wire format is JSON
        either way, and a client library or proxy is free to pick the binary
        opcode. A frame that carries no payload, is not JSON, or is not a JSON
        object is **dropped** (with a warning) rather than ending the pump — in
        Mode B the connection *is* the session, so one malformed frame must not
        cost the client its whole application state.

        Returns:
            The decoded envelope, or ``None`` when the frame was unusable.

        Raises:
            WebSocketDisconnect: If the peer disconnected.
        """
        message = await self.websocket.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000), message.get("reason"))
        raw: str | None = message.get("text")
        if raw is None:
            payload: bytes | None = message.get("bytes")
            raw = None if payload is None else payload.decode("utf-8", "replace")
        if raw is None:
            _LOGGER.warning("tempestweb: dropped a websocket frame with no payload")
            return None
        try:
            envelope: Any = json.loads(raw)
        except ValueError:
            _LOGGER.warning("tempestweb: dropped a websocket frame that is not JSON")
            return None
        if not isinstance(envelope, dict):
            _LOGGER.warning(
                "tempestweb: dropped a websocket frame that is not a JSON object"
            )
            return None
        return envelope

    async def _pump(self) -> None:
        """Read envelopes from the socket and route them by ``kind``.

        ``event`` envelopes are queued for :meth:`recv_event`; ``native_result``
        envelopes go to the registered handler. On disconnect the transport is
        marked closed and a sentinel unblocks any pending :meth:`recv_event`.

        A frame refused by ``allow_inbound`` (the per-IP event budget) ends the
        connection with ``1013`` rather than being dropped silently, so the peer
        learns it is over budget instead of watching its events vanish. An
        undecodable frame is dropped by :meth:`_receive_envelope` and the pump
        keeps reading.
        """
        try:
            while not self._closed:
                envelope = await self._receive_envelope()
                if envelope is None:
                    continue
                if self._allow_inbound is not None and not self._allow_inbound():
                    await self.websocket.close(code=1013)
                    break
                kind = envelope.get("kind")
                if kind == "event":
                    data = envelope.get("data")
                    if isinstance(data, dict):
                        await self._events.put(data)
                elif kind == "native_result":
                    if self._native_result_handler is not None:
                        self._native_result_handler(envelope)
                elif kind == "native_event":
                    if self._native_event_handler is not None:
                        self._native_event_handler(envelope)
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

    async def send_theme(self, mode: str) -> None:
        """Send a ``theme`` envelope so the base sheet follows the app's theme.

        Args:
            mode: The resolved theme mode (``"light"`` or ``"dark"``).

        Raises:
            TransportClosedError: If the socket is no longer connected.
        """
        await self._send(encode_theme(mode))

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

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Send a ``native_subscribe`` envelope to open a stream on the client.

        Args:
            sub_id: Correlation id every ``native_event`` of this stream carries.
            capability: Stable streaming capability name.
            args: JSON-able subscription arguments.

        Raises:
            TransportClosedError: If the socket is no longer connected.
        """
        await self._send(encode_native_subscribe(sub_id, capability, args))

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Send a ``native_unsubscribe`` envelope to cancel a stream.

        Args:
            sub_id: The id of the subscription to close.

        Raises:
            TransportClosedError: If the socket is no longer connected.
        """
        await self._send(encode_native_unsubscribe(sub_id))

    async def _send(self, envelope: dict[str, Any]) -> None:
        """Serialize and send one envelope, mapping disconnects to closed errors.

        Sends are serialized behind a lock. The session spawns one task per tick
        (a coalesced rebuild cannot await), so without it two batches can be
        in ``send_json`` at once and, under backpressure, reach the wire out of
        order — and patches are index-relative, so a swapped pair corrupts the
        client's tree. :class:`asyncio.Lock` wakes waiters FIFO, so the order the
        session queued the batches in is the order they are written.

        Args:
            envelope: The JSON-able wire envelope to send.

        Raises:
            TransportClosedError: If the socket is closed or disconnects mid-send.
        """
        async with self._send_lock:
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

    def on_native_event(self, handler: Callable[[NativeEvent], None]) -> None:
        """Register the sink for inbound ``native_event`` envelopes (T-EV).

        Args:
            handler: Callback receiving each JSON-able ``native_event`` payload.
        """
        self._native_event_handler = handler

    async def close(self) -> None:
        """Tear down the transport and close the WebSocket. Idempotent."""
        was_closed = self._closed
        self._closed = True
        if self._recv_task is not None:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001 - a pump crash must be logged, not lost
                _LOGGER.exception("tempestweb: websocket inbound pump failed")
            self._recv_task = None
        if not was_closed and self.websocket.client_state == WebSocketState.CONNECTED:
            with suppress(WebSocketDisconnect, RuntimeError):
                await self.websocket.close()
