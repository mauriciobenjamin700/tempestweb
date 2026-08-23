"""Per-connection application session (Mode B lifecycle).

A :class:`AppSession` is the server-side runtime for **one** connected client. It
owns an isolated :class:`~tempest_core.App` (so two connections never share
state), a :class:`~tempestweb.transports.base.PatchTransport`, and the structured
set of async tasks spawned while serving that client.

Lifecycle (phase B2):

- **connect = mount**: :meth:`start` builds the initial scene and pushes the
  initial patch batch so the client materializes the screen.
- **run**: :meth:`run` awaits client events, resolves each to a live handler,
  invokes it (sync or ``async``), and lets the app's coalesced rebuild loop emit
  the resulting patches back through the transport.
- **disconnect = unmount**: :meth:`close` cancels every orphan task spawned for
  this session (structured concurrency) and tears the transport down.

The session is transport-agnostic: the same class drives the WebSocket transport
(B1) and the SSE+POST transport (B5), because both satisfy ``PatchTransport``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from contextlib import suppress
from typing import Any, Generic, TypeVar

from tempest_core import App, Theme, Widget
from tempest_core import Patch as CorePatch
from tempestweb.native.bridges import ProxyBridge
from tempestweb.native.dispatch import (
    _next_call_id,
    install_bridge,
    native_call,
    uninstall_bridge,
)
from tempestweb.runtime.background import install_spawner, uninstall_spawner
from tempestweb.runtime.events import (
    apply_media,
    apply_navigate,
    apply_scroll,
    coerce_event,
    handler_wants_event,
)
from tempestweb.runtime.routing import route_to_path
from tempestweb.runtime.serialize import (
    find_node_type,
    patches_to_wire,
    resolve_handler,
    scene_to_initial_patches,
)
from tempestweb.transports.base import (
    Event,
    NativeResult,
    PatchTransport,
    TransportClosedError,
)

__all__ = ["AppSession", "NativeCallError"]

_LOGGER = logging.getLogger("tempestweb.session")

S = TypeVar("S")


class NativeCallError(RuntimeError):
    """Raised when a proxied native capability call fails on the client."""


class AppSession(Generic[S]):
    """Drives one client connection: state, transport, and task lifecycle.

    Each session builds its own :class:`~tempest_core.App` from a factory, so
    connections are fully isolated — a ``set_state`` in one never affects another.

    ``S`` is the application state type.

    Attributes:
        transport: The patch transport carrying this client's patches and events.
        app: The isolated app instance, created in :meth:`start`.
    """

    def __init__(
        self,
        state_factory: Callable[[], S],
        view: Callable[[App[S]], Widget],
        transport: PatchTransport,
        *,
        concurrent_dispatch: bool = False,
        theme: Theme | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            state_factory: Builds a fresh initial state for this connection. A
                factory (not a shared value) guarantees per-connection isolation.
            view: The shared ``view`` function (identical to Mode A's ``app.py``).
            transport: The transport carrying patches/events for this connection.
            concurrent_dispatch: Run each event's handler as its own task instead
                of awaiting it before reading the next event. Events for the
                **same widget key** still run in arrival order (a per-key lock), so
                two quick edits of one field cannot land out of order; handlers for
                different keys overlap. Off by default: it lets two handlers mutate
                the state concurrently, which an app must be written for. Prefer
                :func:`tempestweb.runtime.spawn` inside the slow handler when only
                one screen is affected.
            theme: The palette every component resolves its colors against.
                ``None`` keeps the Material baseline. It belongs here rather
                than only in CSS because components resolve their colors in
                **Python** — a filled button carries its fill as an inline
                style — so a page whose custom properties were rebranded
                still rendered baseline-purple buttons until the session
                handed the theme to the tree building them.
        """
        self._state_factory: Callable[[], S] = state_factory
        self._view: Callable[[App[S]], Widget] = view
        self._theme: Theme | None = theme
        self.transport: PatchTransport = transport
        self.app: App[S] | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._concurrent_dispatch: bool = concurrent_dispatch
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._key_lock_users: dict[str, int] = {}
        self._closed: bool = False
        # The Mode-B native bridge: it owns the call_id -> Future registry and
        # proxies each native_call down the transport. Its send_frame spawns the
        # async transport send as a tracked task; its resolve() is fed by the
        # transport's native_result sink. The session reuses this bridge for both
        # its own public native_call() and the dispatch-module path
        # (await native.<capability>()), so there is no duplicated proxy logic.
        self._bridge: ProxyBridge = ProxyBridge(self._send_native_frame)
        self._bridge_installed: bool = False
        # Last top-route path pushed to the client. The initial mount lands the
        # client on "/" (its document URL), so we only emit a navigate envelope
        # once the app navigates somewhere else (view → URL).
        self._last_path: str = "/"
        #: Last theme mode the client was told. The base stylesheet paints what
        #: no inline style covers (page background, field surfaces, hover/focus),
        #: so it needs the mode; the Theme itself never crosses the wire.
        self._last_mode: str | None = None
        transport.on_native_result(self._resolve_native_result)
        transport.on_native_event(self._deliver_native_event)

    def _send_native_frame(self, envelope: dict[str, Any]) -> None:
        """Ship a native envelope to the client over the transport (kind-routed).

        Wired into the :class:`ProxyBridge` as its synchronous ``send_frame``: the
        bridge builds the envelope (``native_call`` for a single-shot call, or
        ``native_subscribe`` / ``native_unsubscribe`` for the event channel) and
        this forwards it to the matching transport send. Sending is async, so the
        coroutine is spawned as a tracked session task (cancelled on :meth:`close`).

        Args:
            envelope: A ``native_call`` / ``native_subscribe`` / ``native_unsubscribe``
                envelope produced by the bridge.
        """
        kind = envelope.get("kind")
        if kind == "native_call":
            self._spawn(
                self.transport.send_native_call(
                    str(envelope["call_id"]),
                    str(envelope["capability"]),
                    dict(envelope.get("args", {})),
                )
            )
        elif kind == "native_subscribe":
            self._spawn(
                self.transport.send_native_subscribe(
                    str(envelope["sub_id"]),
                    str(envelope["capability"]),
                    dict(envelope.get("args", {})),
                )
            )
        elif kind == "native_unsubscribe":
            self._spawn(self.transport.send_native_unsubscribe(str(envelope["sub_id"])))

    def _apply_patches(self, patches: list[CorePatch]) -> None:
        """App ``apply_patches`` callback: forward a rebuilt batch to the client.

        The app calls this synchronously from its coalesced rebuild (scheduled via
        ``loop.call_soon``). Sending over a transport is async, so we spawn a
        tracked task that survives until the batch is flushed; the task is tracked
        so :meth:`close` can cancel it if the client disconnects mid-flush.

        Args:
            patches: The IR patches for this tick (already coalesced by the core).
        """
        if self._closed or not patches:
            return
        wire = patches_to_wire(patches)
        self._spawn(self.transport.send_patches(wire))
        self._emit_nav_if_changed()
        self._emit_theme_if_changed()

    def _emit_nav_if_changed(self) -> None:
        """Push a ``navigate`` envelope when the app's top route changed.

        Called after each coalesced rebuild: if the app navigated imperatively
        (``app.push`` / ``app.pop`` / ``app.reset`` inside a handler), the top
        route's path differs from the last one the client saw, so we tell the
        client to ``pushState`` the new URL. No-op when the path is unchanged,
        the session is closed, or the app has not mounted yet. This is the
        view → URL leg; the reverse (URL → view) arrives as a ``navigate`` event.
        """
        if self._closed or self.app is None:
            return
        nav = getattr(self.app, "nav", None)
        if nav is None:
            return
        path = route_to_path(nav.top)
        if path != self._last_path:
            self._last_path = path
            self._spawn(self.transport.send_navigate(path))

    def _emit_theme_if_changed(self) -> None:
        """Push a ``theme`` envelope when the resolved theme mode changed.

        Called after each coalesced rebuild, next to :meth:`_emit_nav_if_changed`
        and for the same reason: something the browser owns has to follow what the
        app decided. Here it is the base stylesheet — the page background, a
        field's surface and every hover/focus state are CSS, so without the mode
        they stayed light while the tree above them went dark.

        The mode is resolved **the way a widget resolves it** — ``Theme.is_dark()``
        with no platform flag — because that is the whole point: the attribute
        exists to make the sheet agree with the inline styles already in the tree.
        A ``SYSTEM`` theme resolves light in the core, so an app that wants to
        follow the OS reads ``app.media.platform_dark_mode`` in its own ``view``
        and calls ``set_theme`` — and then both halves move together.

        The first ``light`` is not sent: the sheet's own tokens **are** the light
        palette, so marking light at mount would spend a frame saying what the CSS
        already says. Every later change is sent, including the return to light
        after a dark spell.

        No-op when the mode is unchanged, the session is closed, or the app has
        not mounted.
        """
        if self._closed or self.app is None:
            return
        mode = self._resolved_mode()
        if mode is None or mode == self._last_mode:
            return
        first_and_light = self._last_mode is None and mode == "light"
        self._last_mode = mode
        if first_and_light:
            return
        self._spawn(self.transport.send_theme(mode))

    def _resolved_mode(self) -> str | None:
        """Resolve the app's theme mode to ``"light"``/``"dark"``.

        Returns:
            The resolved mode, or ``None`` when the app carries no theme at all.
        """
        if self.app is None:
            return None
        theme = getattr(self.app, "theme", None)
        if theme is None:
            return None
        return "dark" if theme.is_dark() else "light"

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        """Schedule a coroutine as a tracked session task.

        Tracked tasks are cancelled on :meth:`close`, so no orphan task outlives
        the connection (structured concurrency at disconnect).

        Args:
            coro: The coroutine to run as a background task.
        """
        task: asyncio.Task[None] = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def start(self) -> None:
        """Mount the session: install the bridge and send initial patches.

        Builds the isolated app, installs this session's :class:`ProxyBridge` as
        the process-wide native bridge (so ``await native.<capability>()`` inside a
        handler proxies to the client), records the initial scene, and pushes the
        initial patch batch (a root replace) plus the resolved theme mode, so the
        client renders the first screen on the right palette instead of flashing
        light and correcting itself.

        Note:
            ``install_bridge`` stores the bridge in a context-local variable (see
            :mod:`tempestweb.native.dispatch`). Because this ``start`` is awaited
            from the session's own ``run`` task, the bridge is isolated to that
            connection's asyncio context: concurrent server sessions each resolve
            ``await native.*`` through their **own** bridge, never clobbering one
            another. :meth:`native_call` also uses this session's bridge directly.
        """
        self.app = (
            App(
                state=self._state_factory(),
                view=self._view,
                apply_patches=self._apply_patches,
            )
            if self._theme is None
            else App(
                state=self._state_factory(),
                view=self._view,
                apply_patches=self._apply_patches,
                theme=self._theme,
            )
        )
        install_bridge(self._bridge)
        install_spawner(self._spawn)
        self._bridge_installed = True
        scene = self.app.start()
        await self.transport.send_patches(scene_to_initial_patches(scene))
        mode = self._resolved_mode()
        if mode is not None:
            self._last_mode = mode
            if mode != "light":
                await self.transport.send_theme(mode)

    async def dispatch(self, event: Event) -> None:
        """Resolve and invoke the handler for one client event.

        Looks up the live handler on the current scene by the event's ``key`` and
        ``type``, then invokes it. A handler that accepts a positional argument
        receives the raw payload; a zero-argument handler is called bare. Async
        handlers are awaited. Any ``set_state`` the handler triggers schedules the
        coalesced rebuild that pushes the resulting patches back to the client.

        Unknown keys / missing handlers are silently ignored (a stale event from a
        widget that no longer exists is not an error). Three event types are
        handled by the runtime instead of an app handler: ``scroll`` slides a
        virtualized window, ``navigate`` applies a URL change, and ``resync``
        re-sends the whole scene (the client asks for it when it could not apply
        a batch).

        The theme mode is re-checked after every handler, not only after a batch:
        a theme swap can change nothing in the tree — an app whose ``view`` does
        not pass the theme to any widget rebuilds to the identical IR, so the core
        emits no patch and the batch hook never runs — and the base stylesheet
        still has to hear about it.

        Args:
            event: The JSON-able client event ``{"type", "key", "payload"}``.
        """
        if self.app is None or self._closed:
            return
        scene = self.app.current_tree
        if scene is None:
            return
        key = event.get("key")
        event_type = event.get("type")
        if not isinstance(key, str) or not isinstance(event_type, str):
            return
        if event_type == "resync":
            await self.resync()
            return
        if event_type == "scroll":
            apply_scroll(self.app, key, event.get("payload", {}))
            return
        if event_type == "navigate":
            apply_navigate(self.app, event.get("payload", {}))
            return
        if event_type == "media":
            apply_media(self.app, event.get("payload", {}))
            return
        handler = resolve_handler(scene, key, event_type)
        if handler is None:
            return
        payload = event.get("payload", {})
        arg = coerce_event(find_node_type(scene, key), event_type, payload)
        result = handler(arg) if handler_wants_event(handler) else handler()
        if asyncio.iscoroutine(result):
            await result
        self._emit_theme_if_changed()

    async def resync(self) -> None:
        """Re-send the current scene as a full initial patch batch.

        The client's tree is only correct while it has applied *every* patch in
        order. When that chain breaks — a batch it could not apply, or an SSE
        reconnect whose gap the replay buffer no longer covers — no further
        index-relative patch can be trusted, and a resync is the only repair: one
        root replace carrying the scene as it stands now.

        A no-op before the session has mounted or after it closed.
        """
        if self._closed or self.app is None:
            return
        scene = self.app.current_tree
        if scene is None:
            return
        await self.transport.send_patches(scene_to_initial_patches(scene))

    async def native_call(self, capability: str, args: dict[str, Any]) -> Any:  # noqa: ANN401 — value type depends on the capability
        """Proxy a native Web API capability to the client and await its result.

        Sends a ``native_call`` envelope, suspends until the matching
        ``native_result`` arrives (correlated by ``call_id``), then returns the
        client's value or raises on failure. This is the server-side leg of the
        4th boundary crossing (see ``docs/contract.md``); in Mode A the same API
        resolves in-process without a round-trip.

        Args:
            capability: Stable capability name (e.g. ``"geolocation.get"``).
            args: JSON-able arguments forwarded to the client capability.

        Returns:
            The JSON-able ``value`` the client returned for the capability.

        Raises:
            NativeCallError: If the client reports the capability failed.
            NativeError: With code ``timeout`` if the client never answers.
            TransportClosedError: If the connection drops before a result.
        """
        call_id = _next_call_id()
        result = await self._bridge.call(native_call(capability, args, call_id))
        if not result.get("ok", False):
            raise NativeCallError(str(result.get("error")))
        return result.get("value")

    def _resolve_native_result(self, result: NativeResult) -> None:
        """Resolve the awaitable for an inbound ``native_result`` envelope.

        Registered as the transport's native-result sink. Delegates to the
        :class:`ProxyBridge`, which matches ``call_id`` to its pending future and
        settles it with the full result payload. Unknown / stale ``call_id`` values
        are ignored. The success/error split is applied by the awaiter
        (:meth:`native_call` or the dispatch-module ``send_native_call``).

        Args:
            result: The JSON-able ``native_result`` payload.
        """
        call_id = result.get("call_id")
        if not isinstance(call_id, str):
            return
        self._bridge.resolve(call_id, result)

    def _deliver_native_event(self, event: dict[str, Any]) -> None:
        """Route an inbound ``native_event`` frame to its subscription (T-EV).

        Registered as the transport's native-event sink. Delegates to the
        :class:`ProxyBridge`, which matches ``sub_id`` to the subscription's ``emit``
        and forwards the event/error/done payload. Unknown / stale ``sub_id`` values
        are ignored. The awaiting ``async for`` (via ``native_events``) turns the
        payload into a yielded value, a raised :class:`NativeError`, or loop end.

        Args:
            event: The JSON-able ``native_event`` payload
                ``{"sub_id", "event"|"error"|"done"}``.
        """
        sub_id = event.get("sub_id")
        if not isinstance(sub_id, str):
            return
        payload = {k: v for k, v in event.items() if k not in ("kind", "sub_id")}
        self._bridge.deliver_event(sub_id, payload)

    async def run(self) -> None:
        """Serve the client until the transport closes.

        Mounts (if not already) then loops: await the next event, dispatch it, let
        the rebuild loop flush patches. Returns cleanly when the transport closes.

        A handler that raises is logged and the loop carries on, exactly as in
        concurrent mode. It used to end the connection instead — and in Mode B the
        connection *is* the session, so one buggy handler (a validation error in a
        rebuilt widget, say) dropped the client's whole state; the client silently
        reconnected onto a fresh session and the screen jumped back to its initial
        view with nothing in the server log to explain it.
        """
        if self.app is None:
            await self.start()
        try:
            while not self._closed:
                event = await self.transport.recv_event()
                if self._concurrent_dispatch:
                    self._spawn(self._dispatch_ordered_by_key(event))
                else:
                    try:
                        await self.dispatch(event)
                    except Exception:  # noqa: BLE001 - a bad handler must not end the session
                        _LOGGER.exception(
                            "tempestweb: handler for %r raised", event.get("key")
                        )
        except TransportClosedError:
            return
        finally:
            await self.close()

    async def _dispatch_ordered_by_key(self, event: Event) -> None:
        """Dispatch one event under its widget's lock (concurrent mode).

        The lock is per event ``key``, so a widget's own events stay in arrival
        order — two quick edits of the same field cannot apply out of order —
        while handlers for different widgets overlap.

        A handler that raises is logged and dropped, as it is in serial mode: one
        failing handler must not take down a session that is still serving other
        events, and an unretrieved task exception would vanish into the event
        loop's warning instead of the app's log.

        The lock is reference-counted and dropped once nobody is queued behind
        it: a long session over a list whose rows carry per-item keys would
        otherwise accumulate one lock per key it ever saw, released only at
        teardown.

        Args:
            event: The JSON-able client event.
        """
        key = str(event.get("key") or "")
        lock = self._key_locks.get(key)
        if lock is None:
            lock = self._key_locks[key] = asyncio.Lock()
        self._key_lock_users[key] = self._key_lock_users.get(key, 0) + 1
        try:
            async with lock:
                try:
                    await self.dispatch(event)
                except Exception:  # noqa: BLE001 - one bad handler must not end the session
                    _LOGGER.exception("tempestweb: handler for %r raised", key)
        finally:
            remaining = self._key_lock_users[key] - 1
            if remaining > 0:
                self._key_lock_users[key] = remaining
            else:
                del self._key_lock_users[key]
                self._key_locks.pop(key, None)

    async def close(self) -> None:
        """Unmount the session: cancel orphan tasks and tear down the transport.

        Idempotent. Cancels every tracked task spawned for this connection
        (structured concurrency) and awaits their cancellation, then closes the
        transport. Safe to call from :meth:`run`'s ``finally`` and externally.
        """
        if self._closed:
            return
        self._closed = True
        # Settle any in-flight native_call awaiters with the documented
        # TransportClosedError before tearing the bridge down (the bridge's own
        # close() would cancel them, but native_call() promises TransportClosedError
        # on disconnect). Then close + uninstall the bridge so a stale process-wide
        # bridge never leaks into the next session or test.
        self._bridge.fail_pending(TransportClosedError("session closed"))
        self._bridge.close()
        if self._bridge_installed:
            uninstall_bridge()
            uninstall_spawner()
            self._bridge_installed = False
        self._key_locks.clear()
        self._key_lock_users.clear()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        await self.transport.close()
