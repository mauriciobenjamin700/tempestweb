"""Transport-agnostic reload signalling for the dev loop.

The dev server watches the project for changes and, on each change, emits a
*reload signal*. How that signal reaches the running app is deliberately not
decided here:

- **Mode A (WASM):** a reload reloads the browser tab (hot restart).
- **Mode B (server):** a reload restarts the per-connection session and pushes
  to connected clients.

To keep the watcher independent of any transport, the reload mechanism is a tiny
publish/subscribe hub: producers call :meth:`ReloadSignal.trigger`; consumers
either register a synchronous callback via :meth:`ReloadSignal.subscribe` or
await the next reload via :meth:`ReloadSignal.wait`. A transport plugs in by
subscribing; tests plug in by awaiting.

The hub also closes: :meth:`ReloadSignal.close` releases every waiter with
``None``, which is how a consumer that would otherwise park forever — the
livereload SSE stream — ends when the dev server shuts down.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["ReloadKind", "ReloadEvent", "ReloadSignal"]


class ReloadKind(StrEnum):
    """The kind of reload a change should trigger.

    Attributes:
        RESTART: Re-run the app from scratch with clean state (the v1 default —
            "hot restart"). See ``docs/plan.md`` §5.1.
        RELOAD: Re-run preserving state ("hot reload"). Reserved for post-v1;
            the watcher never emits this yet but the type exists so transports
            can branch on it ahead of time.
    """

    RESTART = "restart"
    RELOAD = "reload"


@dataclass(frozen=True, slots=True)
class ReloadEvent:
    """A single reload notification.

    Attributes:
        kind: Whether to restart (clean state) or reload (preserve state).
        paths: The project-relative paths whose change triggered the reload.
            Empty when the reload was triggered manually (e.g. the ``R`` key).
        generation: A monotonically increasing counter, starting at 1, that lets
            a consumer detect missed reloads after a slow tick.
    """

    kind: ReloadKind = ReloadKind.RESTART
    paths: tuple[str, ...] = ()
    generation: int = 0


# A reload subscriber is any callable invoked with the emitted event.
ReloadCallback = Callable[[ReloadEvent], None]


@dataclass(slots=True)
class ReloadSignal:
    """A transport-agnostic publish/subscribe hub for reload events.

    The watcher (or the interactive cockpit) is the producer; a transport is the
    consumer. Neither side imports the other — they meet at this object.

    Example:
        >>> signal = ReloadSignal()
        >>> seen: list[ReloadEvent] = []
        >>> unsubscribe = signal.subscribe(seen.append)
        >>> event = signal.trigger(paths=["app.py"])
        >>> seen[0] is event
        True
        >>> event.generation
        1
        >>> unsubscribe()
    """

    _generation: int = 0
    _closed: bool = False
    _callbacks: list[ReloadCallback] = field(default_factory=list)
    _waiters: list[asyncio.Future[ReloadEvent | None]] = field(default_factory=list)

    @property
    def closed(self) -> bool:
        """Report whether the hub has been closed.

        Returns:
            ``True`` once :meth:`close` has been called.
        """
        return self._closed

    @property
    def generation(self) -> int:
        """Return the number of reloads emitted so far.

        Returns:
            The current generation counter (0 before the first reload).
        """
        return self._generation

    def subscribe(self, callback: ReloadCallback) -> Callable[[], None]:
        """Register a synchronous callback invoked on every reload.

        Args:
            callback: A function called with each :class:`ReloadEvent`.

        Returns:
            A zero-argument function that unregisters the callback when called.
        """
        self._callbacks.append(callback)

        def unsubscribe() -> None:
            """Remove the callback if it is still registered."""
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return unsubscribe

    def trigger(
        self,
        *,
        kind: ReloadKind = ReloadKind.RESTART,
        paths: list[str] | tuple[str, ...] = (),
    ) -> ReloadEvent:
        """Emit a reload event to every subscriber and waiter.

        Increments the generation counter, builds a :class:`ReloadEvent`, invokes
        every registered callback synchronously, and resolves any pending
        :meth:`wait` futures.

        Args:
            kind: The reload kind. Defaults to :attr:`ReloadKind.RESTART`.
            paths: The paths whose change caused the reload. Defaults to empty
                (a manual reload).

        Returns:
            The emitted :class:`ReloadEvent`.
        """
        self._generation += 1
        event = ReloadEvent(
            kind=kind,
            paths=tuple(paths),
            generation=self._generation,
        )
        for callback in list(self._callbacks):
            callback(event)
        waiters = self._waiters
        self._waiters = []
        for waiter in waiters:
            if not waiter.done():
                waiter.set_result(event)
        return event

    async def wait(self) -> ReloadEvent | None:
        """Await the next reload event, or the hub closing.

        Returns:
            The next :class:`ReloadEvent` emitted by :meth:`trigger`, or ``None``
            once :meth:`close` has been called — the signal a consumer loop uses
            to finish instead of parking forever.
        """
        if self._closed:
            return None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[ReloadEvent | None] = loop.create_future()
        self._waiters.append(future)
        return await future

    def close(self) -> None:
        """Close the hub, releasing every waiter with ``None``.

        Called when the dev server starts shutting down. Without it a consumer
        parked on :meth:`wait` — the livereload SSE stream, which is an endless
        generator — holds its HTTP response open, and the server waits on that
        response while the browser tab waits on the server. Idempotent.
        """
        self._closed = True
        waiters = self._waiters
        self._waiters = []
        for waiter in waiters:
            if not waiter.done():
                waiter.set_result(None)
