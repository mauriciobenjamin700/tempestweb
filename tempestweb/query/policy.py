"""How long a cached answer is fresh, and when a failed query is worth retrying.

These are the numbers every app picks badly on the first try. They live here as
named constants so a call site can override one without inventing all four, and
so changing the default is a one-line diff instead of a search.

The values match the `tempest-react-sdk` defaults, which in turn match what
TanStack Query settled on after enough production use to be worth copying.
"""

from __future__ import annotations

__all__ = [
    "STALE_TIME_MS",
    "CACHE_TIME_MS",
    "REFETCH_TIME_MS",
    "MAX_QUERY_ATTEMPTS",
    "RETRYABLE_STATUS",
    "should_retry_query",
]

#: How long a fetched value is served without going back to the network.
#: Ported from ``tempest-react-sdk``'s ``STALE_TIME``.
STALE_TIME_MS = 30_000.0

#: How long an unused entry is kept before it is dropped. Longer than
#: :data:`STALE_TIME_MS` on purpose: a stale entry is still worth showing while
#: its refetch is in flight, which is the difference between a screen that
#: flickers to empty and one that does not.
#: Ported from ``tempest-react-sdk``'s ``CACHE_TIME``.
CACHE_TIME_MS = 300_000.0

#: How often a screen that polls should ask again.
#: Ported from ``tempest-react-sdk``'s ``REFETCH_TIME``.
REFETCH_TIME_MS = 60_000.0

#: How many times a query is attempted in total, the first try included.
MAX_QUERY_ATTEMPTS = 3

#: The status codes worth a second attempt: the server said "later", not "no".
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def should_retry_query(attempt: int, status: int | None) -> bool:
    """Report whether a failed read is worth attempting again.

    A **read** — this is the query side. Retrying a GET is free; the write side
    is :func:`tempestweb.native.http.request`, which retries only what carries
    an idempotency key.

    Args:
        attempt: How many attempts have already happened, the failed one
            included. The first failure passes ``1``.
        status: The HTTP status the server answered, or ``None`` for a
            network-level failure (no response at all).

    Returns:
        Whether to try again. A network-level failure is retried; a status the
        server chose is retried only when it means "later" — a 404 or a 403 will
        answer the same way forever, and retrying it just makes the user wait
        three times as long for the same error.
    """
    if attempt >= MAX_QUERY_ATTEMPTS:
        return False
    if status is None:
        return True
    return status in RETRYABLE_STATUS
