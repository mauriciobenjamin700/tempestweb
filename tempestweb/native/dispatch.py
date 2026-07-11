"""Dispatch native Web-capability calls across the client/Python seam (Track N).

Native Web capabilities (``http``, ``audio``, ``share``, ``geolocation``,
``clipboard``, ``storage``, ``camera``, ``notifications``) are the web sibling of
:mod:`tempestroid.native`. Every capability is a **typed Python awaitable** that
application code calls without caring which execution mode it runs under. The one
seam that differs between the modes is the installed :class:`NativeBridge`. **That
single seam is the whole Mode-A vs Mode-B split:**

* **Mode A (WASM / browser).** Python runs in the browser under Pyodide. The
  installed bridge is an in-process FFI bridge
  (:class:`~tempestweb.native.bridges.FFIBridge`): it hands the call straight to
  ``client/native/*.js``, which calls ``fetch``,
  ``navigator.geolocation``, ``navigator.clipboard``, ``navigator.share`` and the
  rest directly. The result comes back as the resolved value of the FFI promise —
  no network hop, no wire format.

* **Mode B (server).** Python runs on the server; the browser is a thin client
  reached over a WebSocket (or SSE + POST). The installed bridge
  (:class:`~tempestweb.native.bridges.ProxyBridge`) serializes the call into the
  ``native_call`` envelope from ``docs/contract.md``, ships it down the patch
  transport, then suspends on an :class:`asyncio.Future`. ``client/native/*.js``
  runs the same Web API call in the browser and posts a ``native_result`` envelope
  back up the channel; :func:`resolve_native_result` matches it to the pending
  future by ``call_id``. **The Web API always executes in the browser** — Mode B
  simply proxies the call there and back over one round-trip.

The wire format (identical in both modes' *contract*, only transported differently)
is pinned by ``docs/contract.md``::

    // server -> client (Mode B): request a native capability
    { "kind": "native_call", "call_id": "c1",
      "capability": "geolocation.get", "args": {} }

    // client -> server (Mode B): typed result, or error
    { "kind": "native_result", "call_id": "c1", "ok": true,  "value": {} }
    { "kind": "native_result", "call_id": "c1", "ok": false,
      "error": "permission_denied" }

The envelope builders are pure (and therefore trivially testable); the bridge is
injected with :func:`install_bridge`, so this module imports cleanly with no
browser, no Pyodide, and no server present.
"""

from __future__ import annotations

import asyncio
import contextvars
import itertools
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol, cast, runtime_checkable

__all__ = [
    "NATIVE_RESULT_PREFIX",
    "BrowserUnavailableError",
    "EventBridge",
    "NativeBridge",
    "NativeError",
    "current_bridge",
    "install_bridge",
    "native_call",
    "native_events",
    "native_subscribe",
    "native_unsubscribe",
    "resolve_native_event",
    "resolve_native_result",
    "send_native_call",
    "uninstall_bridge",
]

#: Reserved token prefix the client uses (over the event channel, in Mode B) to
#: deliver a ``native_result`` back to its matching pending future when the
#: transport multiplexes native results onto the event lane.
NATIVE_RESULT_PREFIX = "__native_result__:"

#: Monotonic source of call ids (deterministic; avoids ``random``/``uuid`` so
#: envelopes are reproducible in tests). Each id is prefixed with ``"c"`` to match
#: the ``call_id`` convention in ``docs/contract.md`` (``"c1"``, ``"c2"``, ...).
_call_ids: itertools.count[int] = itertools.count(1)

#: Monotonic source of subscription ids for the native **event channel** (T-EV).
#: Prefixed with ``"s"`` (``"s1"``, ``"s2"``, ...) to distinguish them from the
#: request/response ``call_id``s in logs and wire frames.
_sub_ids: itertools.count[int] = itertools.count(1)


class NativeError(RuntimeError):
    """A native Web-capability call failed in the browser.

    Attributes:
        code: A short machine-readable error code (e.g. ``"permission_denied"``,
            ``"unavailable"``, ``"not_found"``, ``"insecure_context"``,
            ``"http_error"``, ``"timeout"``).
    """

    def __init__(self, code: str, message: str = "") -> None:
        """Initialize the error.

        Args:
            code: The machine-readable error code.
            message: A human-readable detail (optional).
        """
        self.code: str = code
        super().__init__(f"{code}: {message}" if message else code)


class BrowserUnavailableError(RuntimeError):
    """Raised when a native call is made with no :class:`NativeBridge` installed.

    The capability modules always reach the browser through an installed bridge.
    Off-platform (a plain Python process, a unit test that forgot to install a
    bridge), there is no browser to call, so dispatch fails fast with this error
    instead of silently no-op-ing.
    """


@runtime_checkable
class NativeBridge(Protocol):
    """The seam between a native capability and the browser's Web API.

    A bridge is installed once per running app (Mode A or Mode B) via
    :func:`install_bridge`. The capability modules call :meth:`call` without
    knowing which concrete bridge backs them.

    Implementations must be safe to drive from an asyncio event loop.
    """

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Deliver a ``native_call`` envelope and await its ``native_result``.

        Args:
            envelope: A ``native_call`` envelope carrying a ``call_id``,
                ``capability`` and ``args``.

        Returns:
            The result envelope ``{"ok": bool, "value"/"error": ...}`` as produced
            by ``client/native/*.js``.

        Raises:
            BrowserUnavailableError: If the browser channel is gone.
        """
        ...


@runtime_checkable
class EventBridge(Protocol):
    """A :class:`NativeBridge` that also serves the native **event channel** (T-EV).

    The request/response :meth:`NativeBridge.call` seam is single-shot. Streaming
    capabilities (``geolocation.watch``, sensors, network/visibility/orientation
    change, media/idle, cross-tab broadcast receive, ...) need many events per
    subscription over time, so a streaming bridge additionally implements
    :meth:`subscribe`/:meth:`unsubscribe`.

    A subscription delivers events through the injected ``emit`` callback. Each
    emitted payload is one of ``{"event": <value>}`` (a data event),
    ``{"error": <code>, "message": <detail>}`` (a terminal failure), or
    ``{"done": true}`` (the stream ended normally). ``emit`` may be called from a
    non-loop thread; implementations forward to the loop safely.
    """

    async def subscribe(
        self,
        capability: str,
        args: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> str:
        """Open a subscription and stream its events through ``emit``.

        Args:
            capability: The dotted streaming capability name (``"geolocation.watch"``).
            args: JSON-able subscription arguments.
            emit: Callback invoked once per event with an ``{"event"|"error"|"done"}``
                payload. Safe to call from any thread.

        Returns:
            The subscription id used to later :meth:`unsubscribe`.
        """
        ...

    async def unsubscribe(self, sub_id: str) -> None:
        """Close a subscription so the browser stops delivering its events.

        Args:
            sub_id: The id returned by :meth:`subscribe`. Unknown ids are ignored.
        """
        ...


#: The installed bridge, held in a :class:`~contextvars.ContextVar` so it is
#: **isolated per asyncio context**, not process-wide. In Mode A (one app per
#: process) the bootstrap sets it in the main context and every task sees it. In
#: Mode B each client connection runs ``AppSession.run`` in its own task, so each
#: ``install_bridge`` in :meth:`AppSession.start` sets the bridge only for that
#: connection's context — concurrent sessions never clobber one another's
#: ``await native.*`` path. ``None`` off-platform.
_bridge: contextvars.ContextVar[NativeBridge | None] = contextvars.ContextVar(
    "tempestweb_native_bridge", default=None
)


def install_bridge(bridge: NativeBridge) -> None:
    """Install the native bridge for the current execution mode and context.

    Called once during app bootstrap — by the WASM runtime (Mode A) with an
    in-process FFI bridge, or by each server session (Mode B) with its own
    transport bridge. The bridge is stored in a context-local variable, so a
    Mode-B server serving many connections keeps each session's bridge isolated
    (the call must run in that connection's task — which it does, since the
    session's :meth:`~tempestweb.runtime.session.AppSession.start` is awaited
    from its own ``run`` task).

    Args:
        bridge: The :class:`NativeBridge` implementation to route native calls
            through.
    """
    _bridge.set(bridge)


def uninstall_bridge() -> None:
    """Remove the installed bridge for the current context (off-platform state).

    Used by tests and by session teardown so a stale bridge never leaks across
    apps. Resets the context-local bridge to ``None`` in the calling context.
    """
    _bridge.set(None)


def current_bridge() -> NativeBridge:
    """Return the bridge installed in the current context, raising if none.

    Returns:
        The context-local :class:`NativeBridge`.

    Raises:
        BrowserUnavailableError: If no bridge has been installed in this context.
    """
    bridge = _bridge.get()
    if bridge is None:
        raise BrowserUnavailableError(
            "no native bridge installed (off-platform, or bootstrap incomplete)"
        )
    return bridge


def native_call(capability: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """Build a ``native_call`` envelope matching ``docs/contract.md``.

    Args:
        capability: The stable dotted capability name (e.g. ``"geolocation.get"``,
            ``"http.request"``, ``"clipboard.read"``).
        args: JSON-able arguments for the capability.
        call_id: The correlation id the client echoes back with the result.

    Returns:
        The serializable ``native_call`` envelope.
    """
    return {
        "kind": "native_call",
        "call_id": call_id,
        "capability": capability,
        "args": args,
    }


async def send_native_call(capability: str, args: dict[str, Any]) -> dict[str, Any]:
    """Send a ``native_call`` and await the browser's typed result.

    Builds an envelope with a fresh ``call_id``, hands it to the installed bridge,
    and unwraps the result: a successful ``value`` payload is returned; a failure
    (``ok`` is false) is raised as :class:`NativeError`. Must be called from the
    asyncio loop the app runs on (i.e. inside a widget handler).

    Args:
        capability: The stable dotted capability name.
        args: JSON-able arguments for the capability.

    Returns:
        The ``value`` payload of a successful result, as a ``dict``.

    Raises:
        BrowserUnavailableError: If no bridge is installed (off-platform).
        NativeError: If the browser reports the call failed (``ok`` is false).
    """
    call_id = f"c{next(_call_ids)}"
    result = await current_bridge().call(native_call(capability, args, call_id))
    if not result.get("ok", False):
        raise NativeError(
            str(result.get("error", "unknown")),
            str(result.get("message", "")),
        )
    value = result.get("value", {})
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def resolve_native_result(
    call_id: str,
    payload: dict[str, Any],
    pending: dict[str, asyncio.Future[dict[str, Any]]],
) -> bool:
    """Resolve a pending native call with the client's ``native_result`` (Mode B).

    Called (on the loop thread) by a Mode-B transport bridge when a
    ``native_result`` envelope tagged with ``call_id`` arrives back over the
    channel. Mode A has no use for this — its FFI bridge resolves its own promise
    inline.

    Args:
        call_id: The correlation id parsed from the ``native_result`` envelope.
        payload: The result envelope (``{"ok": ..., "value"/"error": ...}``).
        pending: The bridge's ``call_id -> Future`` registry.

    Returns:
        ``True`` if a matching pending future was resolved, ``False`` otherwise
        (unknown or already-settled id).
    """
    future = pending.get(call_id)
    if future is None or future.done():
        return False
    future.set_result(payload)
    return True


def native_subscribe(
    capability: str, args: dict[str, Any], sub_id: str
) -> dict[str, Any]:
    """Build a ``native_subscribe`` envelope for the event channel (T-EV).

    Args:
        capability: The dotted streaming capability name (``"geolocation.watch"``).
        args: JSON-able subscription arguments.
        sub_id: The correlation id the client tags every event of this stream with.

    Returns:
        The serializable ``native_subscribe`` envelope.
    """
    return {
        "kind": "native_subscribe",
        "sub_id": sub_id,
        "capability": capability,
        "args": args,
    }


def native_unsubscribe(sub_id: str) -> dict[str, Any]:
    """Build a ``native_unsubscribe`` envelope for the event channel (T-EV).

    Args:
        sub_id: The id of the subscription to close.

    Returns:
        The serializable ``native_unsubscribe`` envelope.
    """
    return {"kind": "native_unsubscribe", "sub_id": sub_id}


def resolve_native_event(
    sub_id: str,
    payload: dict[str, Any],
    subscriptions: dict[str, Callable[[dict[str, Any]], None]],
) -> bool:
    """Deliver an inbound ``native_event`` to its subscription's ``emit`` (Mode B).

    Called (on the loop thread) by a Mode-B transport bridge when a
    ``native_event`` frame tagged with ``sub_id`` arrives. Mode A has no use for
    this — its FFI bridge invokes ``emit`` inline from the JS callback.

    Args:
        sub_id: The subscription id parsed from the ``native_event`` frame.
        payload: The event payload (``{"event"|"error"|"done": ...}``).
        subscriptions: The bridge's ``sub_id -> emit`` registry.

    Returns:
        ``True`` if a matching subscription received the event, else ``False``.
    """
    emit = subscriptions.get(sub_id)
    if emit is None:
        return False
    emit(payload)
    return True


async def native_events(
    capability: str, args: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to a streaming capability and yield its events (T-EV).

    The plan-facing API for every streaming capability: it opens a subscription on
    the installed bridge, yields one ``dict`` per browser event, and guarantees the
    subscription is closed when the iterator is exhausted, broken out of, or its
    consumer is cancelled. Backpressure-free: events are buffered in an unbounded
    queue as the browser produces them.

    Example::

        async for pos in native_events("geolocation.watch", {"high_accuracy": True}):
            app.set_state(lambda s: setattr(s, "here", pos))

    Args:
        capability: The dotted streaming capability name.
        args: JSON-able subscription arguments.

    Yields:
        Each event's ``value`` payload, as a ``dict``.

    Raises:
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support streaming.
        NativeError: If the browser reports the subscription failed.
    """
    bridge = current_bridge()
    if not isinstance(bridge, EventBridge):
        raise BrowserUnavailableError(
            "the installed native bridge does not support the event channel"
        )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def emit(payload: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, payload)

    sub_id = await bridge.subscribe(capability, args, emit)
    try:
        while True:
            payload = await queue.get()
            if payload.get("done", False):
                return
            if "error" in payload:
                raise NativeError(
                    str(payload.get("error", "unknown")),
                    str(payload.get("message", "")),
                )
            event = payload.get("event", {})
            yield cast("dict[str, Any]", event) if isinstance(event, dict) else {}
    finally:
        await bridge.unsubscribe(sub_id)


def _next_sub_id() -> str:
    """Return a fresh subscription id (``"s1"``, ``"s2"``, ...).

    Returns:
        The next monotonic subscription id.
    """
    return f"s{next(_sub_ids)}"
