"""The read side of remote data: cache with keys, staleness, and rollback.

tempestweb had both hard ends of remote data and nothing in between.
:mod:`tempestweb.native.http` retries with backoff and idempotency,
:mod:`tempestweb.native.offline` holds a durable FIFO of mutations, and
:mod:`tempestweb.native.sync` reconciles a collection by watermark. What was
missing was **reading**: somewhere to keep the answer to a GET under a key,
invalidate it when a mutation lands, and put a change on screen before the
server has agreed to it.

Every app wrote that as a ``dict`` inside its own ``State``, and the part that
always came out wrong was the invalidation.

Example:
    ```python
    from tempestweb import native
    from tempestweb.query import QueryCache, keys, offset_page

    USERS = keys("users")
    CACHE = QueryCache()

    response = await CACHE.fetch(
        USERS.list(page=1),
        lambda: native.http.request("GET", "/api/users?page=1"),
    )
    page = offset_page(response.json)
    ```

!!! note "The cache is app state, not a hidden singleton"
    A :class:`QueryCache` is created by the app and kept in its ``State``, like
    anything else. There is no module-level instance and no implicit context —
    the view reads from the cache it was given, and a test builds its own.

!!! warning "Modes A and B only"
    Mode C transpiles the app's own Python into JavaScript and serves a fixed
    set of modules — ``tempest_core``, ``tempestweb.components`` and
    ``tempestweb.native``. Importing this package from a Mode C app is refused at
    build time with a named error.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypeVar, cast

from tempestweb.query.keys import QueryKey, is_under
from tempestweb.query.policy import CACHE_TIME_MS, STALE_TIME_MS

__all__ = [
    "QueryCache",
    "QueryEntry",
    "Rollback",
    "Clock",
    "Listener",
    "Patcher",
]

T = TypeVar("T")

#: Reads the current time in **milliseconds**. Injected so a test pins staleness
#: without sleeping, and so an app on a different time source can say so.
Clock = Callable[[], float]

#: Called after any change to the cache, so a view can be rebuilt.
Listener = Callable[[], None]

#: Turns a cached value into its replacement. Must not mutate the value it is
#: given — the rollback restores the object that was there, so an in-place edit
#: would survive the undo.
Patcher = Callable[[object], object]

#: Undoes a patch, restoring exactly the entries that were replaced.
Rollback = Callable[[], None]


@dataclass(frozen=True)
class QueryEntry:
    """One cached answer.

    Attributes:
        value: Whatever the loader returned.
        updated_at: When it was stored, in milliseconds from :data:`Clock`.
    """

    value: object
    updated_at: float


def _monotonic_ms() -> float:
    """Read the monotonic clock in milliseconds.

    Monotonic rather than wall time: staleness is a duration, and a wall clock
    that steps backwards (NTP, a user changing the date) would make every entry
    look fresh forever.

    Returns:
        Milliseconds since an arbitrary point.
    """
    return time.monotonic() * 1000.0


class QueryCache:
    """Keyed cache of read answers, with staleness, single-flight and rollback.

    The second read below never runs its loader: the first answer is still
    inside the staleness window, so the cache answers it.

    Example:
        ```python
        cache = QueryCache()
        rows = await cache.fetch(USERS.list(), load_from_network)
        again = await cache.fetch(USERS.list(), load_from_network)  # no request
        ```
    """

    def __init__(
        self,
        *,
        clock: Clock = _monotonic_ms,
        stale_ms: float = STALE_TIME_MS,
        cache_ms: float = CACHE_TIME_MS,
    ) -> None:
        """Build an empty cache.

        Args:
            clock: Reads the current time in milliseconds.
            stale_ms: How long an answer is served without going back to the
                network.
            cache_ms: How long an entry survives at all. Longer than
                ``stale_ms``, so a stale answer is still on screen while its
                refetch is in flight.
        """
        self._entries: dict[QueryKey, QueryEntry] = {}
        self._inflight: dict[QueryKey, asyncio.Future[object]] = {}
        self._listeners: list[Listener] = []
        self._clock = clock
        self._stale_ms = stale_ms
        self._cache_ms = cache_ms

    # -- reading ---------------------------------------------------------

    async def fetch(
        self,
        key: QueryKey,
        loader: Callable[[], Awaitable[T]],
        *,
        stale_ms: float | None = None,
        force: bool = False,
    ) -> T:
        """Answer from cache when fresh, otherwise run the loader once.

        Concurrent calls for the same key **share one loader run**: the second
        caller awaits the first one's result rather than issuing a second
        request. That is single-flight, and it is the behaviour a screen with
        three widgets reading the same query needs.

        Args:
            key: The cache key, from :func:`~tempestweb.query.keys`.
            loader: Called to produce the value when the cache cannot answer.
            stale_ms: Override the cache's staleness window for this read.
            force: Skip the freshness check and load anyway. The in-flight share
                still applies, so forcing twice concurrently still loads once.

        Returns:
            The value, cached or freshly loaded.

        Raises:
            Exception: Whatever the loader raises, to every caller sharing the
                run. A failed load leaves the previous entry alone — showing the
                last good answer beats blanking the screen because a refetch
                failed.
        """
        window = self._stale_ms if stale_ms is None else stale_ms
        now = self._clock()
        self._collect(now)

        if not force:
            entry = self._entries.get(key)
            if entry is not None and now - entry.updated_at < window:
                return cast(T, entry.value)

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(_awaited(loader()))
            self._inflight[key] = task
            task.add_done_callback(lambda done: self._settle(key, done))
        return cast(T, await asyncio.shield(task))

    def get(self, key: QueryKey) -> object | None:
        """Read a cached value without loading anything.

        Args:
            key: The cache key.

        Returns:
            The value, or ``None`` when nothing is cached under that key or the
            entry has aged past the cache window.
        """
        self._collect(self._clock())
        entry = self._entries.get(key)
        return None if entry is None else entry.value

    def is_stale(self, key: QueryKey, *, stale_ms: float | None = None) -> bool:
        """Report whether a key needs a trip to the network.

        Args:
            key: The cache key.
            stale_ms: Override the cache's staleness window.

        Returns:
            ``True`` when nothing is cached, or when the entry is older than the
            window.
        """
        window = self._stale_ms if stale_ms is None else stale_ms
        entry = self._entries.get(key)
        if entry is None:
            return True
        return self._clock() - entry.updated_at >= window

    @property
    def keys(self) -> tuple[QueryKey, ...]:
        """Every key currently held, in insertion order.

        Returns:
            The keys.
        """
        return tuple(self._entries)

    # -- writing ---------------------------------------------------------

    def set(self, key: QueryKey, value: object) -> None:
        """Store a value, stamping it fresh.

        Args:
            key: The cache key.
            value: The value to store.
        """
        self._entries[key] = QueryEntry(value=value, updated_at=self._clock())
        self._notify()

    def invalidate(self, prefix: QueryKey) -> int:
        """Mark everything under a prefix stale, keeping the values on screen.

        This is the operation the hierarchy exists for: ``invalidate(("users",))``
        reaches ``("users", "list", "page=1")``, ``("users", "detail", "7")`` and
        everything else about users, without the caller keeping a second registry
        of which keys mean users.

        The values stay, so a screen keeps showing the last good answer while the
        refetch is in flight. Use :meth:`drop` when the value is known to be
        wrong rather than merely old.

        Args:
            prefix: The prefix to invalidate. The empty tuple reaches everything.

        Returns:
            How many entries were marked.
        """
        stamp = self._clock() - self._stale_ms
        marked = 0
        for key, entry in self._entries.items():
            if is_under(prefix, key):
                self._entries[key] = QueryEntry(entry.value, stamp)
                marked += 1
        if marked:
            self._notify()
        return marked

    def drop(self, prefix: QueryKey) -> int:
        """Remove everything under a prefix.

        Args:
            prefix: The prefix to drop. The empty tuple clears the cache.

        Returns:
            How many entries were removed.
        """
        doomed = [key for key in self._entries if is_under(prefix, key)]
        for key in doomed:
            del self._entries[key]
        if doomed:
            self._notify()
        return len(doomed)

    def patch(self, prefix: QueryKey, patcher: Patcher) -> Rollback:
        """Apply an optimistic change to every entry under a prefix.

        A prefix rather than one key, because a rename has to reach every cached
        page the row appears on — patching only ``("users", "list", "page=1")``
        leaves page 2 showing the old name until something else invalidates it.

        Args:
            prefix: The prefix whose entries are patched.
            patcher: Turns each entry's value into its replacement. Must not
                mutate the value it is handed.

        Returns:
            A callable restoring exactly the entries this patch replaced,
            timestamps included. Calling it twice is harmless.

        Raises:
            Exception: Whatever ``patcher`` raises. Entries already patched are
                restored first, so a patch either lands everywhere it applies or
                nowhere — a half-applied optimistic update is a screen showing
                two different truths.
        """
        touched: dict[QueryKey, QueryEntry] = {}
        try:
            for key in tuple(self._entries):
                if not is_under(prefix, key):
                    continue
                entry = self._entries[key]
                touched[key] = entry
                self._entries[key] = QueryEntry(patcher(entry.value), entry.updated_at)
        except BaseException:
            self._restore(touched)
            raise
        if touched:
            self._notify()
        return lambda: self._restore(touched)

    @contextmanager
    def optimistic(self, prefix: QueryKey, patcher: Patcher) -> Iterator[Rollback]:
        """Apply a patch, and undo it if the block raises.

        The shape a mutation wants, because the rollback cannot be forgotten:

        ```python
        with cache.optimistic(USERS.all(), rename) as rollback:
            await native.http.request("PATCH", f"/api/users/{user_id}", json=body)
        ```

        Args:
            prefix: The prefix whose entries are patched.
            patcher: Turns each entry's value into its replacement.

        Yields:
            The rollback, for a block that decides to undo without raising.
        """
        rollback = self.patch(prefix, patcher)
        try:
            yield rollback
        except BaseException:
            rollback()
            raise

    def clear(self) -> None:
        """Drop every entry."""
        if self._entries:
            self._entries.clear()
            self._notify()

    # -- observing -------------------------------------------------------

    def on_change(self, listener: Listener) -> Callable[[], None]:
        """Register a callback fired after any change to the cache.

        This is how a cached read reaches the screen: the app subscribes once
        and asks for a rebuild.

        Args:
            listener: Called with no arguments after each change.

        Returns:
            A callable that unsubscribes.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Stop calling this listener."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    # -- internals -------------------------------------------------------

    def _settle(self, key: QueryKey, task: asyncio.Future[object]) -> None:
        """Store a completed load and release its in-flight slot.

        Storing here rather than in :meth:`fetch` means the value lands even
        when the caller that started the load was cancelled while awaiting —
        the request was paid for either way, so throwing the answer away would
        make the next read pay again.

        Args:
            key: The key that was loaded.
            task: The completed load.
        """
        self._inflight.pop(key, None)
        if task.cancelled() or task.exception() is not None:
            return
        self.set(key, task.result())

    def _restore(self, entries: dict[QueryKey, QueryEntry]) -> None:
        """Put back a set of entries exactly as they were.

        Args:
            entries: The entries to restore, keyed as they were stored.
        """
        if not entries:
            return
        for key, entry in entries.items():
            self._entries[key] = entry
        self._notify()

    def _collect(self, now: float) -> None:
        """Drop entries that have aged past the cache window.

        Args:
            now: The current time in milliseconds.
        """
        expired = [
            key
            for key, entry in self._entries.items()
            if now - entry.updated_at >= self._cache_ms
        ]
        for key in expired:
            del self._entries[key]

    def _notify(self) -> None:
        """Fire every listener."""
        for listener in tuple(self._listeners):
            listener()


async def _awaited(awaitable: Awaitable[object]) -> object:
    """Wrap any awaitable so :func:`asyncio.ensure_future` can schedule it.

    ``ensure_future`` takes coroutines and futures; a loader is free to return
    any awaitable, and this is the one line that bridges the two.

    Args:
        awaitable: What the loader returned.

    Returns:
        Whatever it resolves to.
    """
    return await awaitable
