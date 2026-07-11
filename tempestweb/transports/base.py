"""Patch transport contract — the single seam that differs between Mode A and B.

Everything above this seam (the application's ``view()`` and state) and everything
below it (the JS client that mutates the DOM) is shared across both execution
modes. Only the transport changes:

- **Mode A (WASM):** :class:`tempestweb.transports.wasm.WasmTransport` bridges the
  reconciler to the JS client in-process via ``pyodide.ffi``.
- **Mode B (server):** :class:`tempestweb.transports.websocket.WebSocketTransport`
  carries patches and events over a WebSocket connection, while
  :class:`tempestweb.transports.sse.SSETransport` carries the **same** stream over
  Server-Sent Events (patches) plus HTTP POST (events).

The wire format carried by a transport is documented in ``docs/contract.md`` and
pinned by the golden fixtures under ``tests/fixtures/``. Every Mode B message is a
JSON *envelope* tagging the payload with a ``kind``:

- ``{"kind": "patches", "data": [<Patch>, ...]}`` — server → client, one tick.
- ``{"kind": "event", "data": <Event>}`` — client → server, one user event.
- ``{"kind": "native_call", "call_id", "capability", "args"}`` — server → client.
- ``{"kind": "native_result", "call_id", "ok", "value"|"error"}`` — client → server.
- ``{"kind": "navigate", "path": "<route>"}`` — server → client, sync the URL
  when the app navigated imperatively (the reverse of the inbound ``navigate``
  event).

The envelope shape is identical for WebSocket and SSE; only the framing differs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol, runtime_checkable

# A patch is a plain JSON-able dict produced by ``Patch.model_dump(mode="json")``.
# See docs/contract.md for the five shapes (insert/remove/update/reorder/replace).
Patch = dict[str, Any]

# An event is a JSON-able dict captured by the client and routed back to a handler.
# Shape: {"type": "click" | "input" | ..., "key": <widget-key>, "payload": {...}}.
Event = dict[str, Any]

# A native call proxies a Web API capability from the server to the client (Mode B).
# Shape: {"call_id": str, "capability": str, "args": {...}}.
NativeCall = dict[str, Any]

# A native result returns a typed value (or error) back for a previous native call.
# Shape: {"call_id": str, "ok": bool, "value"|"error": ...}.
NativeResult = dict[str, Any]

# A native event is one item of a streaming subscription (T-EV), client → server.
# Shape: {"sub_id": str, "event"|"error"|"done": ...}.
NativeEvent = dict[str, Any]

#: The discriminator values a Mode B wire envelope may carry.
EnvelopeKind = Literal[
    "patches",
    "event",
    "native_call",
    "native_result",
    "native_subscribe",
    "native_unsubscribe",
    "native_event",
    "navigate",
]

#: A wire envelope: a JSON-able dict tagged by ``kind`` (see module docstring).
Envelope = dict[str, Any]


def encode_patches(patches: list[Patch]) -> Envelope:
    """Wrap a patch batch in a ``patches`` envelope (server → client).

    Args:
        patches: JSON-able patch dicts for one coalesced tick.

    Returns:
        The envelope ``{"kind": "patches", "data": patches}``.
    """
    return {"kind": "patches", "data": patches}


def encode_event(event: Event) -> Envelope:
    """Wrap a user event in an ``event`` envelope (client → server).

    Args:
        event: The JSON-able event dict.

    Returns:
        The envelope ``{"kind": "event", "data": event}``.
    """
    return {"kind": "event", "data": event}


def encode_navigate(path: str) -> Envelope:
    """Wrap an imperative app navigation in a ``navigate`` envelope (server → client).

    The reverse of the inbound ``navigate`` event: when the app's ``view``
    navigates (the top route changed), the server tells the client the new path
    so it can sync the URL via ``history.pushState`` (back/forward + bookmarks
    stay correct without a round-trip echoing the path back).

    Args:
        path: The new top-route path (e.g. ``"/settings"``).

    Returns:
        The envelope ``{"kind": "navigate", "path": path}``.
    """
    return {"kind": "navigate", "path": path}


def encode_native_call(call_id: str, capability: str, args: dict[str, Any]) -> Envelope:
    """Wrap a native capability request in a ``native_call`` envelope.

    Args:
        call_id: Correlation id matching the eventual ``native_result``.
        capability: Stable capability name (e.g. ``"geolocation.get"``).
        args: JSON-able arguments for the capability.

    Returns:
        The ``native_call`` envelope.
    """
    return {
        "kind": "native_call",
        "call_id": call_id,
        "capability": capability,
        "args": args,
    }


def encode_native_result(
    call_id: str,
    *,
    ok: bool,
    value: Any = None,  # noqa: ANN401 — JSON-able capability result, type varies
    error: str | None = None,
) -> Envelope:
    """Wrap a native capability result in a ``native_result`` envelope.

    Args:
        call_id: Correlation id of the originating ``native_call``.
        ok: Whether the capability succeeded.
        value: The JSON-able result value when ``ok`` is ``True``.
        error: The error string when ``ok`` is ``False``.

    Returns:
        The ``native_result`` envelope, carrying ``value`` or ``error``.
    """
    envelope: Envelope = {"kind": "native_result", "call_id": call_id, "ok": ok}
    if ok:
        envelope["value"] = value
    else:
        envelope["error"] = error
    return envelope


def encode_native_subscribe(
    sub_id: str, capability: str, args: dict[str, Any]
) -> Envelope:
    """Wrap a streaming subscription request in a ``native_subscribe`` envelope.

    Args:
        sub_id: Correlation id every event of this stream is tagged with.
        capability: Stable streaming capability name (e.g. ``"geolocation.watch"``).
        args: JSON-able arguments for the subscription.

    Returns:
        The ``native_subscribe`` envelope (server → client).
    """
    return {
        "kind": "native_subscribe",
        "sub_id": sub_id,
        "capability": capability,
        "args": args,
    }


def encode_native_unsubscribe(sub_id: str) -> Envelope:
    """Wrap a subscription cancellation in a ``native_unsubscribe`` envelope.

    Args:
        sub_id: The id of the subscription to close.

    Returns:
        The ``native_unsubscribe`` envelope (server → client).
    """
    return {"kind": "native_unsubscribe", "sub_id": sub_id}


def encode_native_event(sub_id: str, payload: dict[str, Any]) -> Envelope:
    """Wrap one streaming event in a ``native_event`` envelope (client → server).

    Args:
        sub_id: The subscription id this event belongs to.
        payload: One of ``{"event": <value>}``, ``{"error", "message"}`` or
            ``{"done": true}``.

    Returns:
        The ``native_event`` envelope.
    """
    return {"kind": "native_event", "sub_id": sub_id, **payload}


@runtime_checkable
class PatchTransport(Protocol):
    """Carries patches Python→client and events client→Python.

    Implementations must be safe to drive from an asyncio event loop. The
    reconciler hands fully-serialized patches to :meth:`send_patches`; user input
    arrives through :meth:`recv_event`. Native capability proxying (Mode B) reuses
    the same channel via :meth:`send_native_call` and the ``native_result`` events
    delivered through :meth:`recv_event`.
    """

    async def send_patches(self, patches: list[Patch]) -> None:
        """Deliver a coalesced batch of patches to the client for this tick.

        Args:
            patches: JSON-able patch dicts, in apply order. May be empty (no-op).

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def send_navigate(self, path: str) -> None:
        """Tell the client the app navigated to ``path`` (view → URL).

        Sent when the app's top route changes so the client can ``pushState`` the
        new URL. The reverse of the inbound ``navigate`` event. A transport whose
        client never syncs the URL may treat this as a no-op.

        Args:
            path: The new top-route path.

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ask the client to run a native Web API capability (Mode B proxy).

        Args:
            call_id: Correlation id matching the awaited ``native_result``.
            capability: Stable capability name (e.g. ``"geolocation.get"``).
            args: JSON-able arguments for the capability.

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Open a streaming subscription on the client (Mode B event channel).

        Args:
            sub_id: Correlation id every ``native_event`` of this stream carries.
            capability: Stable streaming capability name (e.g. ``"geolocation.watch"``).
            args: JSON-able subscription arguments.

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Cancel a streaming subscription on the client (Mode B event channel).

        Args:
            sub_id: The id of the subscription to close.

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def recv_event(self) -> Event:
        """Await the next user event from the client.

        Inbound ``native_result`` and ``native_event`` envelopes are *not* returned
        here; the transport routes them to the handlers registered with
        :meth:`on_native_result` / :meth:`on_native_event`. This method yields only
        user events (``{"type", "key", "payload"}``), so the session loop stays a
        clean event pump.

        Returns:
            A JSON-able user event dict. Blocks until one is available.

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    def on_native_event(self, handler: Callable[[NativeEvent], None]) -> None:
        """Register the sink for inbound ``native_event`` envelopes (T-EV).

        The transport invokes ``handler`` synchronously for each ``native_event``
        it receives, letting the session route it to the subscription keyed by
        ``sub_id``. A transport that never streams may ignore this.

        Args:
            handler: Callback receiving the JSON-able ``native_event`` payload
                ``{"sub_id", "event"|"error"|"done"}``.
        """
        ...

    def on_native_result(self, handler: Callable[[NativeResult], None]) -> None:
        """Register the sink for inbound ``native_result`` envelopes.

        The transport invokes ``handler`` synchronously for each
        ``native_result`` it receives, letting the session resolve the awaitable
        keyed by ``call_id``. A transport that never proxies native calls may
        ignore this.

        Args:
            handler: Callback receiving the JSON-able ``native_result`` payload
                ``{"call_id", "ok", "value"|"error"}``.
        """
        ...

    async def close(self) -> None:
        """Tear down the transport, releasing any underlying channel."""
        ...


class TransportClosedError(RuntimeError):
    """Raised when a transport operation is attempted on a closed channel."""
