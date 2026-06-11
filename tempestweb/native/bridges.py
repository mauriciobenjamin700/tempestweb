"""Concrete :class:`NativeBridge` implementations for each execution mode (A5/B3).

Two bridges back the same capability API; which one is installed is the *entire*
Mode-A vs Mode-B split (see :mod:`tempestweb.native.dispatch`):

* :class:`ProxyBridge` — **Mode B (server).** Proxies every native envelope to
  the browser over the patch transport and awaits the round-trip result frame.
  It owns a ``request_id -> Future`` registry and a "send a frame down the
  socket" callable injected by the server session, so it is fully unit-testable
  with a fake sender — no FastAPI, no real socket.

* :class:`FFIBridge` — **Mode A (WASM / browser).** Hands the envelope straight
  to ``client/native.js`` in-process via a JS callable exposed by Pyodide
  (``window.__tempestweb_native__``). The result comes back as the resolved
  value of a JS promise, awaited directly — no network hop. The JS callable is
  injected, so the dispatch/await logic is testable with a fake in-process
  callable that mimics the FFI contract.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from tempestweb.native.dispatch import (
    BrowserUnavailableError,
    resolve_native_request,
)

__all__ = ["FFIBridge", "ProxyBridge"]


class ProxyBridge:
    """Mode B bridge: proxy native calls to the browser over the WS transport.

    The server has no Web APIs of its own, so every native call is forwarded to
    the thin client, which runs ``client/native.js`` against ``navigator.*`` and
    posts the result back. This bridge translates the :class:`NativeBridge`
    contract into "send a native frame, await the matching result frame".

    Attributes:
        send_frame: Injected callable that ships a JSON-able frame to the client
            (the server session wires this to the patch transport's send path).
    """

    def __init__(self, send_frame: Callable[[dict[str, Any]], None]) -> None:
        """Initialize the proxy bridge.

        Args:
            send_frame: Callable shipping a native frame to the client over the
                transport. For a fire-and-forget envelope it is the whole job;
                for a request envelope the client later posts a result frame
                back, which :meth:`resolve` matches to the pending future.
        """
        self.send_frame: Callable[[dict[str, Any]], None] = send_frame
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._closed: bool = False

    def send(self, envelope: dict[str, Any]) -> None:
        """Ship a fire-and-forget native envelope to the client.

        Args:
            envelope: A ``native_command`` envelope.

        Raises:
            BrowserUnavailableError: If the bridge has been closed.
        """
        if self._closed:
            raise BrowserUnavailableError("proxy bridge is closed")
        self.send_frame(envelope)

    async def request(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Ship a request envelope and await the client's result frame.

        Args:
            envelope: A ``native_request`` envelope carrying a ``request_id``.

        Returns:
            The result envelope posted back by the client.

        Raises:
            BrowserUnavailableError: If the bridge has been closed.
        """
        if self._closed:
            raise BrowserUnavailableError("proxy bridge is closed")
        request_id = str(envelope["request_id"])
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future
        try:
            self.send_frame(envelope)
            return await future
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, payload: dict[str, Any]) -> bool:
        """Resolve a pending request with a result frame from the client.

        The server session calls this when a native result frame arrives back
        over the transport.

        Args:
            request_id: The correlation id from the result frame.
            payload: The result envelope ``{"ok": ..., "data"/"error": ...}``.

        Returns:
            ``True`` if a matching pending future was resolved, else ``False``.
        """
        return resolve_native_request(request_id, payload, self._pending)

    def close(self) -> None:
        """Close the bridge and cancel any in-flight requests."""
        self._closed = True
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()


class FFIBridge:
    """Mode A bridge: call ``client/native.js`` in-process via Pyodide FFI.

    Under Pyodide, ``client/native.js`` exposes a single async dispatch function
    on the page (``window.__tempestweb_native__(envelope)``) returning a JS
    promise that resolves to a result envelope. This bridge awaits that promise
    directly — Python and the Web API share the browser's one event loop, so
    there is no serialization and no round-trip.

    The JS callable is injected (rather than reached through a hard ``import js``)
    so the dispatch logic is unit-testable with a fake async callable that mimics
    the FFI contract.

    Attributes:
        dispatch: The injected async JS callable ``(envelope) -> result``.
    """

    def __init__(
        self,
        dispatch: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        """Initialize the FFI bridge.

        Args:
            dispatch: An awaitable callable forwarding the envelope to
                ``client/native.js`` and resolving to its result envelope. In a
                real browser this is the Pyodide-proxied ``window`` function;
                in tests it is a fake coroutine function.
        """
        self.dispatch: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] = dispatch

    def send(self, envelope: dict[str, Any]) -> None:
        """Dispatch a fire-and-forget native envelope to ``client/native.js``.

        The result of the underlying promise is intentionally discarded; the
        coroutine is scheduled on the running loop so the call stays non-blocking
        and the JS side still runs.

        Args:
            envelope: A ``native_command`` envelope.
        """
        loop = asyncio.get_event_loop()
        loop.create_task(self._fire(envelope))

    async def _fire(self, envelope: dict[str, Any]) -> None:
        """Run a fire-and-forget dispatch, swallowing its result.

        Args:
            envelope: A ``native_command`` envelope.
        """
        await self.dispatch(envelope)

    async def request(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a request envelope and await the JS promise result.

        Args:
            envelope: A ``native_request`` envelope carrying a ``request_id``.

        Returns:
            The result envelope ``client/native.js`` resolved with.
        """
        result: dict[str, Any] = await self.dispatch(envelope)
        return result
