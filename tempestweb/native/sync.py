"""Native sync capability — read+write offline sync driven from Python.

Exposes the offline read-sync stack (``client/offline/{pull,sync-status,
sw-bridge}.js``) to a ``view()``: :func:`configure` registers a named source (an
endpoint + a local table), :func:`now` runs a single-flight sync (replay the
shared write queue, then pull remote changes), :func:`status` reads the current
state and :func:`watch` streams it — mirroring how ``native.network`` exposes
connectivity. The browser side lives in ``client/native/sync.js``.

The endpoint follows the convention ``GET <url>?since=<watermark>&cursor=<cursor>``
returning ``{rows, next_cursor, server_time}``; rows merge last-write-wins over
the owner-scoped store (tombstones delete, a locally-pending newer edit wins).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = [
    "SyncState",
    "SyncSummary",
    "configure",
    "now",
    "status",
    "watch",
]


class SyncSummary(BaseModel):
    """The outcome of one sync run.

    Attributes:
        sent: Mutations accepted and removed from the write queue.
        remaining: Mutations still pending upload.
        failed: Mutations dead-lettered this run.
        conflicts: Mutations moved to the conflict lane this run.
        applied: Remote rows applied by the pull.
    """

    model_config = ConfigDict(frozen=True)

    sent: int = 0
    remaining: int = 0
    failed: int = 0
    conflicts: int = 0
    applied: int = 0


class SyncState(BaseModel):
    """The observable state of a sync source.

    Attributes:
        phase: ``"idle"`` | ``"syncing"`` | ``"error"``.
        online: Last known connectivity.
        pending: Pending (unpushed) mutation count.
        last_synced_at: Epoch ms of the last successful sync, or None.
        last_summary: The last run's :class:`SyncSummary`, or None.
        error: The last error message, or None.
    """

    model_config = ConfigDict(frozen=True)

    phase: str = "idle"
    online: bool = True
    pending: int = 0
    last_synced_at: int | None = None
    last_summary: SyncSummary | None = None
    error: str | None = None


async def configure(
    name: str,
    url: str,
    database: str,
    table: str,
    *,
    key_path: str | None = None,
    owner_field: str | None = None,
    watermark_key: str | None = None,
) -> None:
    """Configure (or replace) a named sync source.

    Args:
        name: A stable name used to run/observe this source.
        url: The delta-sync endpoint (``GET`` with ``since``/``cursor`` query).
        database: The IndexedDB database name for the local table.
        table: The object-store (table) name rows merge into.
        key_path: The primary key path (default ``"id"``).
        owner_field: The owner-scoping field (default ``"owner"``).
        watermark_key: The localStorage key for the cursor (default
            ``f"{name}:watermark"``).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    args: dict[str, str] = {
        "name": name,
        "url": url,
        "database": database,
        "table": table,
    }
    if key_path is not None:
        args["key_path"] = key_path
    if owner_field is not None:
        args["owner_field"] = owner_field
    if watermark_key is not None:
        args["watermark_key"] = watermark_key
    await send_native_call("sync.configure", args)


async def now(name: str) -> SyncSummary:
    """Run one sync for a source now (replay the queue, then pull).

    Args:
        name: The configured source name.

    Returns:
        The :class:`SyncSummary` for the run.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("sync.now", {"name": name})
    return SyncSummary.model_validate(value)


async def status(name: str) -> SyncState:
    """Read a source's current sync state.

    Args:
        name: The configured source name.

    Returns:
        The current :class:`SyncState`.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("sync.status", {"name": name})
    return SyncState.model_validate(value)


async def watch(name: str) -> AsyncIterator[SyncState]:
    """Stream a source's sync state on every change (event channel / T-EV).

    Yields the current state immediately, then a fresh :class:`SyncState` on each
    transition, until the ``async for`` loop is exited (closing the subscription).

    Args:
        name: The configured source name.

    Yields:
        Each updated :class:`SyncState`.

    Raises:
        NativeError: If the browser reports the subscription failed.
        BrowserUnavailableError: If no bridge is installed, or it does not support
            the event channel.
    """
    async for value in native_events("sync.watch", {"name": name}):
        yield SyncState.model_validate(value)
