"""Saving a cache across reloads, on the store the app already has.

An offline-first screen that shows the last known answer while the network wakes
up needs the cache to survive a reload. tempestweb already ships that storage —
``native.storage``, over the IndexedDB key/value store in
``client/native/idb-kv.js`` — so nothing is reimplemented here. This module is
only the bridge: which keys to write under, and how a tuple key and a JSON value
become a string and back.

Example:
    ```python
    from tempestweb import native
    from tempestweb.query import QueryCache, persist, restore

    CACHE = QueryCache()

    await restore(CACHE, native.storage)  # on boot
    ...
    await persist(CACHE, native.storage)  # when the screen is done
    ```

The storage argument is a :class:`QueryStorage`, which the ``native.storage``
module satisfies as it stands. A test passes a dictionary-backed fake, and an
app with its own store passes that — no import of ``native`` happens here, which
is what keeps this module runnable without a browser.

!!! warning "Only JSON-able values persist"
    A cache entry holding an `HttpResponse`, a dataclass or a `datetime` cannot
    be written as JSON. :func:`persist` **skips** those entries and reports how
    many it skipped, rather than raising: a screen that cached one unserializable
    value should still persist the other nine.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tempestweb.query.cache import QueryCache
from tempestweb.query.keys import QueryKey

__all__ = [
    "QueryStorage",
    "PersistResult",
    "RestoreResult",
    "persist",
    "restore",
    "STORAGE_PREFIX",
]

#: Every persisted entry is stored under a key starting with this, so
#: :func:`restore` finds them and nothing else the app stored is touched.
STORAGE_PREFIX = "tw-query:"


@runtime_checkable
class QueryStorage(Protocol):
    """The slice of ``native.storage`` this module needs.

    Declared as a Protocol rather than importing ``native.storage`` directly so
    the module runs without a browser bridge — a test passes a fake, and the
    dependency arrow never points from ``query`` into ``native``.
    """

    def put(self, name: str, content: str) -> Awaitable[None]:
        """Store a string under a key.

        Args:
            name: The storage key.
            content: The string to store.

        Returns:
            An awaitable completing when the write lands.
        """
        ...

    def get(self, name: str) -> Awaitable[str]:
        """Read the string stored under a key.

        Args:
            name: The storage key.

        Returns:
            An awaitable resolving to the stored string.
        """
        ...

    def remove(self, name: str) -> Awaitable[None]:
        """Delete the value stored under a key.

        Args:
            name: The storage key.

        Returns:
            An awaitable completing when the delete lands.
        """
        ...

    def list_keys(self) -> Awaitable[list[str]]:
        """List every key the store holds.

        Returns:
            An awaitable resolving to the keys.
        """
        ...


@dataclass(frozen=True)
class PersistResult:
    """What :func:`persist` did.

    Attributes:
        written: How many entries reached the store.
        skipped: How many were left behind because their value is not JSON-able.
    """

    written: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class RestoreResult:
    """What :func:`restore` did.

    Attributes:
        restored: How many entries were read back into the cache.
        discarded: How many stored records could not be read and were deleted.
    """

    restored: int = 0
    discarded: int = 0


async def persist(
    cache: QueryCache,
    storage: QueryStorage,
    *,
    prefix: str = STORAGE_PREFIX,
) -> PersistResult:
    """Write every JSON-able cache entry to the store.

    Args:
        cache: The cache to write out.
        storage: Where to write — ``native.storage``, or a fake in a test.
        prefix: The storage-key prefix, so :func:`restore` finds these and
            nothing else.

    Returns:
        A :class:`PersistResult` counting what was written and what was skipped.
    """
    written = 0
    skipped = 0
    for key in cache.keys:
        value = cache.get(key)
        try:
            payload = json.dumps({"key": list(key), "value": value})
        except (TypeError, ValueError):
            skipped += 1
            continue
        await storage.put(_name(prefix, key), payload)
        written += 1
    return PersistResult(written=written, skipped=skipped)


async def restore(
    cache: QueryCache,
    storage: QueryStorage,
    *,
    prefix: str = STORAGE_PREFIX,
) -> RestoreResult:
    """Read persisted entries back into a cache.

    Entries land **fresh**, stamped with the cache's clock at restore time.
    Reviving them stale would send a boot screen straight back to the network,
    which is the thing persisting was supposed to avoid; a screen that wants the
    network anyway calls :meth:`~tempestweb.query.QueryCache.invalidate` right
    after.

    Args:
        cache: The cache to fill.
        storage: Where to read from.
        prefix: The storage-key prefix written by :func:`persist`.

    Returns:
        A :class:`RestoreResult` counting what came back and what was thrown
        away. A record that no longer parses is **deleted** rather than left to
        fail on every boot — the shape of a cached value changes when the app
        does, and a store that cannot be read is a store that must be cleared.
    """
    restored = 0
    discarded = 0
    for name in await storage.list_keys():
        if not name.startswith(prefix):
            continue
        key = await _read(storage, name, cache)
        if key is None:
            await storage.remove(name)
            discarded += 1
        else:
            restored += 1
    return RestoreResult(restored=restored, discarded=discarded)


async def _read(
    storage: QueryStorage,
    name: str,
    cache: QueryCache,
) -> QueryKey | None:
    """Read one stored record into the cache.

    Args:
        storage: Where to read from.
        name: The storage key.
        cache: The cache to fill.

    Returns:
        The cache key that was filled, or ``None`` when the record could not be
        read — a corrupt string, a shape from an older version, or a read that
        failed outright.
    """
    try:
        raw = await storage.get(name)
    except Exception:  # noqa: BLE001 — any storage failure means "cannot read"
        return None
    try:
        record = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    stored = record.get("key")
    if not isinstance(stored, list) or not all(
        isinstance(part, str) for part in stored
    ):
        return None
    key: QueryKey = tuple(stored)
    cache.set(key, record.get("value"))
    return key


def _name(prefix: str, key: QueryKey) -> str:
    """Render a cache key as a storage key.

    Args:
        prefix: The storage-key prefix.
        key: The cache key.

    Returns:
        The storage key, with the segments JSON-encoded so a segment containing
        the separator cannot forge a different key.
    """
    return prefix + json.dumps(list(key), separators=(",", ":"))
