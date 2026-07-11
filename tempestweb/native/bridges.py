"""Concrete :class:`NativeBridge` implementations for each execution mode (N/B3).

Two bridges back the same capability API; which one is installed is the *entire*
Mode-A vs Mode-B split (see :mod:`tempestweb.native.dispatch`):

* :class:`ProxyBridge` — **Mode B (server).** Proxies every ``native_call`` to the
  browser over the patch transport and awaits the matching ``native_result``
  envelope. It owns a ``call_id -> Future`` registry and a "send a frame down the
  channel" callable injected by the server session, so it is fully unit-testable
  with a fake sender — no FastAPI, no real socket.

* :class:`FFIBridge` — **Mode A (WASM / browser).** Hands the call straight to
  ``client/native/*.js`` in-process via a JS callable exposed by Pyodide
  (``window.__tempestweb_native__``). The result comes back as the resolved value
  of a JS promise, awaited directly — no network hop. The JS callable is injected,
  so the dispatch/await logic is testable with a fake in-process callable that
  mimics the FFI contract.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from tempestweb.native.dispatch import (
    BrowserUnavailableError,
    _next_sub_id,
    native_subscribe,
    native_unsubscribe,
    resolve_native_event,
    resolve_native_result,
)

__all__ = ["FFIBridge", "ProxyBridge"]


class ProxyBridge:
    """Mode B bridge: proxy native calls to the browser over the WS/SSE transport.

    The server has no Web APIs of its own, so every ``native_call`` is forwarded to
    the thin client, which runs ``client/native/*.js`` against the browser Web API
    and posts a ``native_result`` back. This bridge translates the
    :class:`~tempestweb.native.dispatch.NativeBridge` contract into "send a
    ``native_call`` frame, await the matching ``native_result`` frame".

    Attributes:
        send_frame: Injected callable that ships a JSON-able frame to the client
            (the server session wires this to the patch transport's send path).
    """

    def __init__(self, send_frame: Callable[[dict[str, Any]], None]) -> None:
        """Initialize the proxy bridge.

        Args:
            send_frame: Callable shipping a ``native_call`` frame to the client over
                the transport. The client later posts a ``native_result`` frame
                back, which :meth:`resolve` matches to the pending future.
        """
        self.send_frame: Callable[[dict[str, Any]], None] = send_frame
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        #: Open event-channel subscriptions (T-EV): ``sub_id -> emit`` callback.
        self._subscriptions: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._closed: bool = False

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Ship a ``native_call`` frame and await the client's ``native_result``.

        Args:
            envelope: A ``native_call`` envelope carrying a ``call_id``.

        Returns:
            The ``native_result`` envelope posted back by the client.

        Raises:
            BrowserUnavailableError: If the bridge has been closed.
        """
        if self._closed:
            raise BrowserUnavailableError("proxy bridge is closed")
        call_id = str(envelope["call_id"])
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[call_id] = future
        try:
            self.send_frame(envelope)
            return await future
        finally:
            self._pending.pop(call_id, None)

    def resolve(self, call_id: str, payload: dict[str, Any]) -> bool:
        """Resolve a pending call with a ``native_result`` frame from the client.

        The server session calls this when a ``native_result`` frame arrives back
        over the transport.

        Args:
            call_id: The correlation id from the ``native_result`` frame.
            payload: The result envelope ``{"ok": ..., "value"/"error": ...}``.

        Returns:
            ``True`` if a matching pending future was resolved, else ``False``.
        """
        return resolve_native_result(call_id, payload, self._pending)

    async def subscribe(
        self,
        capability: str,
        args: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> str:
        """Open an event-channel subscription and ship a ``native_subscribe`` frame.

        Args:
            capability: The dotted streaming capability name.
            args: JSON-able subscription arguments.
            emit: Callback the session invokes (via :meth:`deliver_event`) for each
                inbound ``native_event`` frame tagged with the returned id.

        Returns:
            The subscription id.

        Raises:
            BrowserUnavailableError: If the bridge has been closed.
        """
        if self._closed:
            raise BrowserUnavailableError("proxy bridge is closed")
        sub_id = _next_sub_id()
        self._subscriptions[sub_id] = emit
        self.send_frame(native_subscribe(capability, args, sub_id))
        return sub_id

    async def unsubscribe(self, sub_id: str) -> None:
        """Close a subscription and ship a ``native_unsubscribe`` frame.

        Args:
            sub_id: The id returned by :meth:`subscribe`.
        """
        self._subscriptions.pop(sub_id, None)
        if not self._closed:
            self.send_frame(native_unsubscribe(sub_id))

    def deliver_event(self, sub_id: str, payload: dict[str, Any]) -> bool:
        """Deliver an inbound ``native_event`` frame to its subscription (Mode B).

        The server session calls this when a ``native_event`` frame arrives. A
        terminal event (``done`` or ``error``) also drops the subscription.

        Args:
            sub_id: The subscription id from the ``native_event`` frame.
            payload: The event payload (``{"event"|"error"|"done": ...}``).

        Returns:
            ``True`` if a matching subscription received it, else ``False``.
        """
        delivered = resolve_native_event(sub_id, payload, self._subscriptions)
        if payload.get("done", False) or "error" in payload:
            self._subscriptions.pop(sub_id, None)
        return delivered

    def fail_pending(self, exc: BaseException) -> None:
        """Settle every in-flight call with ``exc`` (without closing the bridge).

        Lets the owner (e.g. a Mode-B session at teardown) fail outstanding calls
        with a domain-specific error — such as a transport-closed error — instead
        of the plain :class:`asyncio.CancelledError` that :meth:`close` raises.

        Args:
            exc: The exception to set on each not-yet-settled pending future.
        """
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()
        self._end_subscriptions(str(exc) or "transport_closed")

    def close(self) -> None:
        """Close the bridge, cancel in-flight calls, and end all subscriptions."""
        self._closed = True
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        self._end_subscriptions("transport_closed")

    def _end_subscriptions(self, error: str) -> None:
        """Terminate every open subscription so its ``native_events`` loop ends.

        Args:
            error: The error code delivered to each subscription's ``emit`` so the
                consuming iterator raises (instead of hanging) at teardown.
        """
        for emit in list(self._subscriptions.values()):
            emit({"error": error})
        self._subscriptions.clear()


class FFIBridge:
    """Mode A bridge: call ``client/native/*.js`` in-process via Pyodide FFI.

    Under Pyodide, ``client/native/index.js`` exposes a single async dispatch
    function on the page (``window.__tempestweb_native__(envelope)``) returning a
    JS promise that resolves to a ``native_result`` envelope. This bridge awaits
    that promise directly — Python and the Web API share the browser's one event
    loop, so there is no serialization and no round-trip.

    The JS callable is injected (rather than reached through a hard ``import js``)
    so the dispatch logic is unit-testable with a fake async callable that mimics
    the FFI contract.

    Attributes:
        dispatch: The injected async JS callable ``(envelope) -> native_result``.
    """

    def __init__(
        self,
        dispatch: Callable[[str], Awaitable[str]],
        subscribe_js: (
            Callable[[str, Callable[[str], None]], Awaitable[str]] | None
        ) = None,
        unsubscribe_js: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize the FFI bridge.

        Args:
            dispatch: An awaitable callable that takes a ``native_call`` envelope as
                a **JSON string** and resolves to the ``native_result`` envelope as
                a JSON string. Strings are used (not dicts) because they cross the
                Pyodide FFI boundary cleanly — no PyProxy/JsProxy conversion, the
                same convention as the patch/event callbacks. In a real browser this
                wraps ``window.__tempestweb_native__``; in tests it is a fake.
            subscribe_js: Awaitable callable ``(envelope_json, emit) -> sub_id`` that
                opens an event-channel subscription (T-EV), wrapping
                ``window.__tempestweb_native_subscribe__``. ``emit`` is a Python
                callback the browser invokes with each event as a **JSON string**.
                ``None`` when the Mode-A bootstrap has not wired streaming.
            unsubscribe_js: Awaitable callable ``(sub_id) -> None`` closing a
                subscription, wrapping ``window.__tempestweb_native_unsubscribe__``.
        """
        self.dispatch: Callable[[str], Awaitable[str]] = dispatch
        self.subscribe_js: (
            Callable[[str, Callable[[str], None]], Awaitable[str]] | None
        ) = subscribe_js
        self.unsubscribe_js: Callable[[str], Awaitable[None]] | None = unsubscribe_js

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a ``native_call`` envelope and await the JS promise result.

        The envelope crosses to JS as a JSON string and the ``native_result`` comes
        back as one, so nothing relies on FFI object conversion.

        Args:
            envelope: A ``native_call`` envelope carrying a ``call_id``.

        Returns:
            The ``native_result`` envelope ``client/native/*.js`` resolved with.
        """
        raw: str = await self.dispatch(json.dumps(envelope))
        result: dict[str, Any] = json.loads(raw)
        return result

    async def subscribe(
        self,
        capability: str,
        args: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> str:
        """Open an event-channel subscription in-process via the JS FFI (T-EV).

        The subscribe envelope crosses to JS as a JSON string; the browser calls
        the wrapped ``emit`` with each event as a JSON string, which this method
        parses back into a ``dict`` before handing it to the Python ``emit``.

        Args:
            capability: The dotted streaming capability name.
            args: JSON-able subscription arguments.
            emit: Callback invoked with each ``{"event"|"error"|"done": ...}`` dict.

        Returns:
            The subscription id.

        Raises:
            BrowserUnavailableError: If Mode-A streaming was not wired at bootstrap.
        """
        if self.subscribe_js is None:
            raise BrowserUnavailableError(
                "mode A native event channel is not wired (no subscribe callable)"
            )
        sub_id = _next_sub_id()
        envelope = native_subscribe(capability, args, sub_id)

        def emit_str(raw: str) -> None:
            emit(json.loads(raw))

        await self.subscribe_js(json.dumps(envelope), emit_str)
        return sub_id

    async def unsubscribe(self, sub_id: str) -> None:
        """Close an event-channel subscription via the JS FFI.

        Args:
            sub_id: The id returned by :meth:`subscribe`.
        """
        if self.unsubscribe_js is not None:
            await self.unsubscribe_js(sub_id)
