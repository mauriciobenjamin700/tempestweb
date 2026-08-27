"""The read side of remote data: cache, keys, pagination, optimistic updates.

tempestweb had both hard ends and nothing in between. `native.http` retries with
backoff and idempotency, `native.offline` holds a durable FIFO of mutations, and
`native.sync` reconciles a collection by watermark. **Reading** had nothing:
nowhere to keep the answer to a GET under a key, invalidate it when a mutation
lands, paginate, or put a change on screen before the server agreed to it.

Every app wrote that as a `dict` inside its own `State`, and the part that always
came out wrong was the invalidation.

**Modules**

    * :mod:`keys` — hierarchical keys, so invalidation is by prefix.
    * :mod:`cache` — :class:`QueryCache`: staleness, single-flight, rollback.
    * :mod:`pagination` — the offset and cursor shapes, typed.
    * :mod:`optimistic` — `upsert_by_id` / `remove_by_id` over a cached list.
    * :mod:`policy` — how long an answer is fresh, and what is worth retrying.
    * :mod:`persistence` — writing the cache to the store the app already has.

Example:
    ```python
    from tempestweb import native
    from tempestweb.query import QueryCache, keys, offset_page, upsert_by_id

    USERS = keys("users")
    CACHE = QueryCache()

    response = await CACHE.fetch(
        USERS.list(page=1),
        lambda: native.http.request("GET", "/api/users?page=1"),
    )
    page = offset_page(response.json)

    with CACHE.optimistic(USERS.all(), lambda rows: upsert_by_id(rows, edited)):
        await native.http.request("PATCH", "/api/users/7", json=edited)
    ```

If the `PATCH` raises, the block's rollback puts back exactly the entries it
replaced — no refetch needed to undo something the server never accepted.

!!! note "The cache is app state, not a hidden singleton"
    A `QueryCache` is created by the app and kept in its `State`. There is no
    module-level instance and no implicit context: the view reads from the cache
    it was handed, and a test builds its own with a fake clock.

!!! warning "Modes A and B only"
    Mode C transpiles the app's own Python into JavaScript and serves a fixed set
    of modules — `tempest_core`, `tempestweb.components` and `tempestweb.native`.
    Importing this package from a Mode C app is refused at build time with a
    named error.

!!! info "This does not replace `native.sync`"
    Delta-sync is still the way to reconcile a large collection against a
    watermark. This cache is for reading a screen.

Import everything from this package level rather than from submodules.
"""

from __future__ import annotations

from tempestweb.query.cache import (
    Clock,
    Listener,
    Patcher,
    QueryCache,
    QueryEntry,
    Rollback,
)
from tempestweb.query.keys import QueryKey, QueryKeys, is_under, keys
from tempestweb.query.optimistic import (
    ID_FIELD,
    remove_by_id,
    replace_where,
    upsert_by_id,
)
from tempestweb.query.pagination import (
    CURSOR_KEY,
    DEFAULT_PAGE_KEYS,
    ITEMS_KEY,
    PAGE_KEY,
    PAGE_SIZE_KEY,
    TOTAL_KEY,
    CursorPage,
    OffsetPage,
    PageKeys,
    cursor_page,
    empty_cursor_page,
    empty_offset_page,
    is_cursor_page,
    is_offset_page,
    offset_page,
)
from tempestweb.query.persistence import (
    STORAGE_PREFIX,
    PersistResult,
    QueryStorage,
    RestoreResult,
    persist,
    restore,
)
from tempestweb.query.policy import (
    CACHE_TIME_MS,
    MAX_QUERY_ATTEMPTS,
    REFETCH_TIME_MS,
    RETRYABLE_STATUS,
    STALE_TIME_MS,
    should_retry_query,
)

__all__ = [
    "QueryCache",
    "QueryEntry",
    "Rollback",
    "Clock",
    "Listener",
    "Patcher",
    "QueryKey",
    "QueryKeys",
    "keys",
    "is_under",
    "OffsetPage",
    "CursorPage",
    "PageKeys",
    "DEFAULT_PAGE_KEYS",
    "offset_page",
    "cursor_page",
    "empty_offset_page",
    "empty_cursor_page",
    "is_offset_page",
    "is_cursor_page",
    "ITEMS_KEY",
    "TOTAL_KEY",
    "PAGE_KEY",
    "PAGE_SIZE_KEY",
    "CURSOR_KEY",
    "upsert_by_id",
    "remove_by_id",
    "replace_where",
    "ID_FIELD",
    "STALE_TIME_MS",
    "CACHE_TIME_MS",
    "REFETCH_TIME_MS",
    "MAX_QUERY_ATTEMPTS",
    "RETRYABLE_STATUS",
    "should_retry_query",
    "QueryStorage",
    "PersistResult",
    "RestoreResult",
    "persist",
    "restore",
    "STORAGE_PREFIX",
]
