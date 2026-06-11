"""Per-connection application session (Mode B lifecycle).

A :class:`AppSession` is the server-side runtime for **one** connected client. It
owns an isolated :class:`~tempestweb._core.App` (so two connections never share
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
from collections.abc import Callable, Coroutine
from contextlib import suppress
from itertools import count
from typing import Any, Generic, TypeVar

from tempestweb._core import App, Widget
from tempestweb._core import Patch as CorePatch
from tempestweb._core.widgets import handler_accepts_event
from tempestweb.runtime.serialize import (
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

S = TypeVar("S")


class NativeCallError(RuntimeError):
    """Raised when a proxied native capability call fails on the client."""


class AppSession(Generic[S]):
    """Drives one client connection: state, transport, and task lifecycle.

    Each session builds its own :class:`~tempestweb._core.App` from a factory, so
    connections are fully isolated — a ``set_state`` in one never affects another.

    Type Args:
        S: The application state type.

    Attributes:
        transport: The patch transport carrying this client's patches and events.
        app: The isolated app instance, created in :meth:`start`.
    """

    def __init__(
        self,
        state_factory: Callable[[], S],
        view: Callable[[App[S]], Widget],
        transport: PatchTransport,
    ) -> None:
        """Initialize the session.

        Args:
            state_factory: Builds a fresh initial state for this connection. A
                factory (not a shared value) guarantees per-connection isolation.
            view: The shared ``view`` function (identical to Mode A's ``app.py``).
            transport: The transport carrying patches/events for this connection.
        """
        self._state_factory: Callable[[], S] = state_factory
        self._view: Callable[[App[S]], Widget] = view
        self.transport: PatchTransport = transport
        self.app: App[S] | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed: bool = False
        self._native_seq: count[int] = count(1)
        self._native_pending: dict[str, asyncio.Future[Any]] = {}
        transport.on_native_result(self._resolve_native_result)

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
        """Mount the session: build the initial scene and send initial patches.

        Builds the isolated app, records its initial scene, and pushes the initial
        patch batch (a root replace) so the client renders the first screen.
        """
        self.app = App(
            state=self._state_factory(),
            view=self._view,
            apply_patches=self._apply_patches,
        )
        scene = self.app.start()
        await self.transport.send_patches(scene_to_initial_patches(scene))

    async def dispatch(self, event: Event) -> None:
        """Resolve and invoke the handler for one client event.

        Looks up the live handler on the current scene by the event's ``key`` and
        ``type``, then invokes it. A handler that accepts a positional argument
        receives the raw payload; a zero-argument handler is called bare. Async
        handlers are awaited. Any ``set_state`` the handler triggers schedules the
        coalesced rebuild that pushes the resulting patches back to the client.

        Unknown keys / missing handlers are silently ignored (a stale event from a
        widget that no longer exists is not an error).

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
        handler = resolve_handler(scene, key, event_type)
        if handler is None:
            return
        payload = event.get("payload", {})
        result = handler(payload) if handler_accepts_event(handler) else handler()
        if asyncio.iscoroutine(result):
            await result

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
            TransportClosedError: If the connection drops before a result.
        """
        call_id = f"c{next(self._native_seq)}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._native_pending[call_id] = future
        try:
            await self.transport.send_native_call(call_id, capability, args)
            return await future
        finally:
            self._native_pending.pop(call_id, None)

    def _resolve_native_result(self, result: NativeResult) -> None:
        """Resolve the awaitable for an inbound ``native_result`` envelope.

        Registered as the transport's native-result sink. Matches ``call_id`` to
        a pending future and settles it with the value or a
        :class:`NativeCallError`. Unknown / stale ``call_id`` values are ignored.

        Args:
            result: The JSON-able ``native_result`` payload.
        """
        call_id = result.get("call_id")
        if not isinstance(call_id, str):
            return
        future = self._native_pending.get(call_id)
        if future is None or future.done():
            return
        if result.get("ok"):
            future.set_result(result.get("value"))
        else:
            error = result.get("error")
            future.set_exception(NativeCallError(str(error)))

    async def run(self) -> None:
        """Serve the client until the transport closes.

        Mounts (if not already) then loops: await the next event, dispatch it, let
        the rebuild loop flush patches. Returns cleanly when the transport closes.
        """
        if self.app is None:
            await self.start()
        try:
            while not self._closed:
                event = await self.transport.recv_event()
                await self.dispatch(event)
        except TransportClosedError:
            return
        finally:
            await self.close()

    async def close(self) -> None:
        """Unmount the session: cancel orphan tasks and tear down the transport.

        Idempotent. Cancels every tracked task spawned for this connection
        (structured concurrency) and awaits their cancellation, then closes the
        transport. Safe to call from :meth:`run`'s ``finally`` and externally.
        """
        if self._closed:
            return
        self._closed = True
        for future in self._native_pending.values():
            if not future.done():
                future.set_exception(TransportClosedError("session closed"))
        self._native_pending.clear()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        await self.transport.close()
