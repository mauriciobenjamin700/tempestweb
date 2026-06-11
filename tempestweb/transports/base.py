"""Patch transport contract — the single seam that differs between Mode A and B.

Everything above this seam (the application's ``view()`` and state) and everything
below it (the JS client that mutates the DOM) is shared across both execution
modes. Only the transport changes:

- **Mode A (WASM):** :class:`tempestweb.transports.wasm.WasmTransport` bridges the
  reconciler to the JS client in-process via ``pyodide.ffi``.
- **Mode B (server):** :class:`tempestweb.transports.websocket.WebSocketTransport`
  carries patches and events over a WebSocket connection.

The wire format carried by a transport is documented in ``docs/contract.md`` and
pinned by the golden fixtures under ``tests/fixtures/``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# A patch is a plain JSON-able dict produced by ``Patch.model_dump(mode="json")``.
# See docs/contract.md for the five shapes (insert/remove/update/reorder/replace).
Patch = dict[str, Any]

# An event is a JSON-able dict captured by the client and routed back to a handler.
# Shape: {"type": "click" | "input" | ..., "key": <widget-key>, "payload": {...}}.
Event = dict[str, Any]


@runtime_checkable
class PatchTransport(Protocol):
    """Carries patches Python→client and events client→Python.

    Implementations must be safe to drive from an asyncio event loop. The
    reconciler hands fully-serialized patches to :meth:`send_patches`; user input
    arrives through :meth:`recv_event`.
    """

    async def send_patches(self, patches: list[Patch]) -> None:
        """Deliver a coalesced batch of patches to the client for this tick.

        Args:
            patches: JSON-able patch dicts, in apply order. May be empty (no-op).

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def recv_event(self) -> Event:
        """Await the next user event from the client.

        Returns:
            A JSON-able event dict. Blocks until an event is available.

        Raises:
            TransportClosedError: If the underlying channel is gone.
        """
        ...

    async def close(self) -> None:
        """Tear down the transport, releasing any underlying channel."""
        ...


class TransportClosedError(RuntimeError):
    """Raised when a transport operation is attempted on a closed channel."""
