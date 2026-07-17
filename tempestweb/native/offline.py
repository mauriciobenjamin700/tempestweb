"""Native offline mutation-queue capability (P2).

Exposes a durable, replay-on-reconnect mutation queue to Python: a write made
while offline is appended to an IndexedDB-backed queue (carrying an idempotency
key the server dedups on) and replayed in FIFO order when connectivity returns.
The browser side lives in ``client/native/offline.js`` (wrapping the tested
``client/offline/{store,sync}.js``); this module is the typed awaitable surface.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "Mutation",
    "ReplayResult",
    "conflicts",
    "enqueue",
    "failed",
    "pending",
    "replay",
    "size",
]


class Mutation(BaseModel):
    """A queued offline mutation.

    Attributes:
        id: The queue row's primary key.
        owner: The owner scope the mutation belongs to.
        idempotency_key: The stable key the server dedups replays on.
        method: The HTTP method (``"POST"``/``"PUT"``/``"PATCH"``/``"DELETE"``).
        url: The target URL.
        attempts: How many replay attempts have been made.
        status: The row status (``"pending"``/``"done"``/``"failed"``/
            ``"conflict"``).
    """

    model_config = ConfigDict(frozen=True)

    id: str
    owner: str
    idempotency_key: str
    method: str
    url: str
    attempts: int = 0
    status: str = "pending"


class ReplayResult(BaseModel):
    """The outcome of a queue replay.

    Attributes:
        sent: How many mutations were accepted and removed.
        remaining: How many mutations are still pending.
        failed: How many mutations were dead-lettered this run (permanent client
            error, or transient attempts exhausted).
        conflicts: How many mutations were moved to the conflict lane this run
            (the server returned ``409``).
    """

    model_config = ConfigDict(frozen=True)

    sent: int = 0
    remaining: int = 0
    failed: int = 0
    conflicts: int = 0


async def enqueue(
    method: str,
    url: str,
    body: Any = None,  # noqa: ANN401 - JSON-able request body of any shape
    *,
    idempotency_key: str | None = None,
    owner: str | None = None,
) -> Mutation:
    """Enqueue a mutation for durable, replay-on-reconnect delivery.

    Args:
        method: The HTTP method.
        url: The target URL.
        body: The JSON-able request body.
        idempotency_key: An explicit key the server dedups on; generated when
            omitted.
        owner: The owner scope; defaults to the queue's default owner.

    Returns:
        The enqueued :class:`Mutation`.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "offline.enqueue",
        {
            "method": method,
            "url": url,
            "body": body,
            "idempotency_key": idempotency_key,
            "owner": owner,
        },
    )
    return Mutation.model_validate(value)


async def pending(owner: str | None = None) -> list[Mutation]:
    """List the pending mutations for an owner, oldest first.

    Args:
        owner: The owner scope; defaults to the queue's default owner.

    Returns:
        The pending mutations (an empty list when none are queued).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("offline.pending", {"owner": owner})
    return [Mutation.model_validate(m) for m in value.get("mutations", [])]


async def size(owner: str | None = None) -> int:
    """Count the pending mutations for an owner.

    Args:
        owner: The owner scope; defaults to the queue's default owner.

    Returns:
        The number of pending mutations.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("offline.size", {"owner": owner})
    return int(value.get("size", 0))


async def failed(owner: str | None = None) -> list[Mutation]:
    """List the dead-lettered (permanently failed) mutations for an owner.

    A mutation is dead-lettered when it hits a permanent client error (a
    non-retryable 4xx) or exhausts its retry attempts on a transient failure.
    These rows no longer block the queue and are surfaced here for inspection or
    a manual retry.

    Args:
        owner: The owner scope; defaults to the queue's default owner.

    Returns:
        The failed mutations (an empty list when none have failed).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("offline.failed", {"owner": owner})
    return [Mutation.model_validate(m) for m in value.get("mutations", [])]


async def conflicts(owner: str | None = None) -> list[Mutation]:
    """List the mutations parked in the conflict lane for an owner.

    A mutation lands here when the server rejects its replay with ``409``,
    signalling a write conflict that last-write-wins dedup cannot resolve. The
    row is kept (not dropped) so the app can reconcile it explicitly.

    Args:
        owner: The owner scope; defaults to the queue's default owner.

    Returns:
        The conflicting mutations (an empty list when none conflicted).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("offline.conflicts", {"owner": owner})
    return [Mutation.model_validate(m) for m in value.get("mutations", [])]


async def replay(owner: str | None = None) -> ReplayResult:
    """Replay the pending queue now.

    Drains in FIFO order: accepted rows are removed; a transient failure stops
    replay to preserve order and is dead-lettered once attempts are exhausted; a
    permanent 4xx is dead-lettered immediately; a ``409`` moves the row to the
    conflict lane. Neither a dead-letter nor a conflict blocks the rest of the
    queue.

    Args:
        owner: The owner scope; defaults to the queue's default owner.

    Returns:
        The :class:`ReplayResult` (sent, remaining, failed and conflict counts).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("offline.replay", {"owner": owner})
    return ReplayResult.model_validate(value)
