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

#: The discriminator values a Mode B wire envelope may carry.
EnvelopeKind = Literal["patches", "event", "native_call", "native_result"]

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

    async def recv_event(self) -> Event:
        """Await the next user event from the client.

        Inbound ``native_result`` envelopes are *not* returned here; the transport
        routes them to the handler registered with :meth:`on_native_result`. This
        method yields only user events (``{"type", "key", "payload"}``), so the
        session loop stays a clean event pump.

        Returns:
            A JSON-able user event dict. Blocks until one is available.

        Raises:
            TransportClosedError: If the underlying channel is gone.
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
