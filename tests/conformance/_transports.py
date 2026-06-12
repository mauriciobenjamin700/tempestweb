"""Two mock transports with deliberately different internals.

Both satisfy :class:`tempestweb.transports.base.PatchTransport` and both render
into the shared reference DOM (:mod:`._dom`). They model the A-vs-B seam: Mode A
(WASM, in-process) hands patches across the FFI boundary essentially live, while
Mode B (server) serializes patches to JSON and ships them over a socket. The
internals differ on purpose — the A-vs-B guarantee is that *despite* the
different paths, the resulting DOM is byte-for-byte identical.

These are test doubles, not the real transports (which live in ``tempestweb/
transports/`` and are owned by track T2/T3). The harness only depends on the
Protocol, never on a concrete transport.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from tests.conformance._dom import DomNode, apply_batch


class MockTransportA:
    """In-process transport double (Mode A / WASM analogue).

    Patches are applied directly to the live :class:`DomNode` tree as Python
    objects, mimicking the ``pyodide.ffi`` bridge where no serialization round
    trip happens. Events are delivered through an in-memory queue.
    """

    def __init__(self, root: DomNode) -> None:
        """Initialize the transport over an initial rendered tree.

        Args:
            root: The initial DOM produced from the scenario's first view.
        """
        self.root: DomNode = root
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._closed: bool = False

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Apply a coalesced patch batch directly to the live tree.

        Args:
            patches: JSON-able patch dicts, in apply order.
        """
        # Mode A path: objects cross the boundary as-is, no JSON round trip.
        self.root = apply_batch(self.root, patches)

    async def send_navigate(self, path: str) -> None:
        """Sync the client URL on navigation — unused by this harness.

        Args:
            path: The new top-route path (ignored).
        """
        return None

    async def recv_event(self) -> dict[str, Any]:
        """Await the next queued client event.

        Returns:
            A JSON-able event dict.
        """
        return await self._events.get()

    def inject_event(self, event: dict[str, Any]) -> None:
        """Push a client event for :meth:`recv_event` to return (test helper).

        Args:
            event: A JSON-able event dict.
        """
        self._events.put_nowait(event)

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Proxy a native capability call — unused by the DOM-independence harness.

        Present only to satisfy the :class:`PatchTransport` Protocol; this suite
        exercises patch rendering, not native capabilities.

        Args:
            call_id: Correlation id for the awaited ``native_result``.
            capability: Stable capability name.
            args: JSON-able capability arguments.
        """

    def on_native_result(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a ``native_result`` sink — unused by this harness.

        Args:
            handler: Callback for ``native_result`` envelopes.
        """

    async def close(self) -> None:
        """Mark the transport closed."""
        self._closed = True


class MockTransportB:
    """Serializing transport double (Mode B / server analogue).

    Every patch batch is round-tripped through JSON before being applied, exactly
    as it would be on the wire over a WebSocket/SSE channel. This is the path most
    likely to perturb the result (number coercion, key ordering, tuple->list), so
    if A and B still match, the wire format is genuinely transport-independent.
    """

    def __init__(self, root: DomNode) -> None:
        """Initialize the transport over an initial rendered tree.

        Args:
            root: The initial DOM produced from the scenario's first view.
        """
        self.root: DomNode = root
        self._inbox: list[dict[str, Any]] = []
        self._closed: bool = False

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Serialize the batch to JSON, parse it back, then apply it.

        Args:
            patches: JSON-able patch dicts, in apply order.
        """
        # Mode B path: the patches genuinely traverse a JSON wire.
        wire: str = json.dumps(patches)
        decoded: list[dict[str, Any]] = json.loads(wire)
        self.root = apply_batch(self.root, decoded)

    async def send_navigate(self, path: str) -> None:
        """Sync the client URL on navigation — unused by this harness.

        Args:
            path: The new top-route path (ignored).
        """
        return None

    async def recv_event(self) -> dict[str, Any]:
        """Pop the next buffered client event.

        Returns:
            A JSON-able event dict.

        Raises:
            IndexError: If no event is buffered.
        """
        return self._inbox.pop(0)

    def inject_event(self, event: dict[str, Any]) -> None:
        """Buffer a client event, round-tripped through JSON (test helper).

        Args:
            event: A JSON-able event dict.
        """
        self._inbox.append(json.loads(json.dumps(event)))

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Proxy a native capability call — unused by the DOM-independence harness.

        Present only to satisfy the :class:`PatchTransport` Protocol; this suite
        exercises patch rendering, not native capabilities.

        Args:
            call_id: Correlation id for the awaited ``native_result``.
            capability: Stable capability name.
            args: JSON-able capability arguments.
        """

    def on_native_result(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a ``native_result`` sink — unused by this harness.

        Args:
            handler: Callback for ``native_result`` envelopes.
        """

    async def close(self) -> None:
        """Mark the transport closed."""
        self._closed = True
