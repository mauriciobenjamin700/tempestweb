"""Mode A transport: an in-process bridge over ``pyodide.ffi``.

In Mode A there is no network. The Python reconciler and the JS DOM renderer run
in the **same browser tab** (Python on Pyodide), so this transport is a direct
in-process bridge:

- **Patches out (Python → client):** :meth:`WasmTransport.send_patches` calls a
  plain Python callable — the ``deliver`` sink. In the live browser that sink is
  a JS function passed in through ``pyodide.ffi`` (the client's
  ``onPatches`` callback); in tests it is an ordinary Python function that
  records the batches. The patch list is already JSON-able, so it crosses the FFI
  as a plain array of objects with no extra encoding.
- **Events in (client → Python):** the JS client calls :meth:`push_event` (also
  exposed across the FFI) with a wire event dict; the transport enqueues it and
  :meth:`recv_event` hands it to the runtime's event loop.

The transport never imports Pyodide: it is a pure asyncio object whose two ends
are a callable and a queue. :func:`bridge_to_pyodide` documents how the live
``public/index.html`` bootstrap connects those two ends to the JS client over
``pyodide.ffi`` — the only Pyodide-aware seam, kept out of the unit-tested core.

This implements the :class:`~tempestweb.transports.base.PatchTransport` Protocol;
the wire format is identical to Mode B's (see ``docs/contract.md``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tempestweb.transports.base import Event, Patch, TransportClosedError

__all__ = ["WasmTransport"]

#: The sink that delivers a patch batch to the client. In the browser this is a
#: JS callback passed through ``pyodide.ffi``; in tests it is a Python function.
DeliverPatches = Callable[[list[Patch]], Any]


class WasmTransport:
    """In-process :class:`PatchTransport` bridging Python and the JS client.

    Patches flow out through the ``deliver`` callable; events flow in through
    :meth:`push_event`, buffered on an :class:`asyncio.Queue` that
    :meth:`recv_event` drains. Closing the transport unblocks any pending
    :meth:`recv_event` with :class:`TransportClosedError` so the runtime's event
    loop exits cleanly when the page tears down.

    Attributes:
        closed: Whether the transport has been closed.
    """

    def __init__(self, deliver: DeliverPatches) -> None:
        """Initialize the transport.

        Args:
            deliver: The sink that hands a JSON-able patch batch to the client.
                In the browser this is the client's ``onPatches`` JS callback
                passed across ``pyodide.ffi``; in tests, a plain Python callable.
        """
        self._deliver: DeliverPatches = deliver
        self._events: asyncio.Queue[Event] = asyncio.Queue()
        self.closed: bool = False

    async def send_patches(self, patches: list[Patch]) -> None:
        """Deliver a coalesced batch of patches to the client for this tick.

        An empty batch is a no-op (the reconciler emits ``[]`` when nothing
        changed). The patch list is passed verbatim to the ``deliver`` sink; in
        the browser, crossing ``pyodide.ffi`` converts the Python list of dicts
        into a JS array of objects automatically.

        Args:
            patches: JSON-able patch dicts, in apply order. May be empty.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        if self.closed:
            raise TransportClosedError("wasm transport is closed")
        if not patches:
            return
        self._deliver(patches)

    async def recv_event(self) -> Event:
        """Await the next client event.

        Blocks until :meth:`push_event` enqueues an event, or the transport is
        closed.

        Returns:
            The next JSON-able wire event ``{"type", "key", "payload"}``.

        Raises:
            TransportClosedError: If the transport is (or becomes) closed.
        """
        if self.closed:
            raise TransportClosedError("wasm transport is closed")
        event = await self._events.get()
        if event is _CLOSE_SENTINEL:
            raise TransportClosedError("wasm transport is closed")
        return event

    def push_event(self, event: Event) -> None:
        """Enqueue a client event for the runtime to dispatch.

        Called by the JS client across ``pyodide.ffi`` whenever a DOM event
        fires (e.g. a button click). Safe to call from synchronous JS-driven
        code: it only touches the queue, never awaits.

        Args:
            event: The wire event ``{"type", "key", "payload"}``.

        Raises:
            TransportClosedError: If the transport has been closed.
        """
        if self.closed:
            raise TransportClosedError("wasm transport is closed")
        self._events.put_nowait(event)

    async def close(self) -> None:
        """Tear down the transport, unblocking any pending :meth:`recv_event`.

        Idempotent: closing an already-closed transport is a no-op.
        """
        if self.closed:
            return
        self.closed = True
        # Wake a blocked recv_event so the runtime's loop can exit.
        self._events.put_nowait(_CLOSE_SENTINEL)


#: Sentinel pushed onto the event queue by :meth:`WasmTransport.close` to unblock
#: a pending :meth:`WasmTransport.recv_event` with a clean closed signal.
_CLOSE_SENTINEL: Event = {"__close__": True}
