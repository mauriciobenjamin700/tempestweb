# Reading remote data (`tempestweb.query`)

!!! tip "What you'll learn"
    How to keep the answer to a `GET` under a key, invalidate everything about a
    resource when a mutation lands, paginate, and put a change on screen
    **before** the server agrees — undoing it if the server refuses. 🚀

tempestweb already had both hard ends of remote data:

| Already there | What it does |
| --- | --- |
| [`native.http`](../advanced/native-reference.md) | requests with retry, backoff and idempotency |
| [`native.offline`](../advanced/offline-sync.md) | durable FIFO of mutations, dead-letter, conflict lane |
| [`native.sync`](../advanced/offline-sync.md) | delta-sync of a large collection, by watermark |

**Reading** had nothing. Without it, every app wrote a `dict` inside its own
`State` — and the part that always came out wrong was the invalidation.

## The problem

```python
# ❌ The hand-written cache
if "users-1" not in state.cache:
    state.cache["users-1"] = await fetch_users(page=1)

# ...and after renaming a user:
del state.cache["users-1"]     # what about page 2? the detail? the counter?
```

You need "throw away everything about users", and there is nobody to ask: you
either keep a second registry of which keys mean users, or you clear the whole
cache. Both are the bug.

## Step 1 — the key is hierarchical

```python
from tempestweb.query import keys

USERS = keys("users")

USERS.all()            # ('users',)
USERS.list(page=1)     # ('users', 'list', 'page=1')
USERS.detail(7)        # ('users', 'detail', '7')
```

A key is a **tuple**, so one is a prefix of another by plain comparison. That is
what makes "invalidate everything about users" a question that exists.

!!! note "Parameter order does not split the cache"
    `USERS.list(page=1, size=20)` and `USERS.list(size=20, page=1)` are the
    **same** key: parameters are sorted before they join. Without that, the same
    query written two ways caches twice and the second write never invalidates
    the first.

## Step 2 — your first `fetch`

A complete program:

```python
from dataclasses import dataclass, field

from tempest_core import App, Column, Text, Widget

from tempestweb import native
from tempestweb.query import OffsetPage, QueryCache, empty_offset_page, keys, offset_page

USERS = keys("users")


@dataclass
class State:
    """The screen's state."""

    cache: QueryCache = field(default_factory=QueryCache)
    page: OffsetPage = field(default_factory=empty_offset_page)


async def load(app: App[State], page: int) -> None:
    """Load one page, from cache while it is still fresh."""
    response = await app.state.cache.fetch(
        USERS.list(page=page),
        lambda: native.http.request("GET", f"/api/users?page={page}"),
    )
    app.set_state(lambda s: setattr(s, "page", offset_page(response.json)))


def view(app: App[State]) -> Widget:
    """Draw the rows the page brought."""
    return Column(
        key="body",
        children=[
            Text(key=f"row-{index}", content=str(row))
            for index, row in enumerate(app.state.page.items)
        ],
    )
```

Call `load` twice in a row and the second one **does not hit the network**: the
answer is still inside the freshness window (30 s by default).

!!! info "The cache is app state, not a hidden singleton"
    Notice `QueryCache` lives in `State`, like anything else. There is no
    module-level instance and no implicit context: the view reads from the cache
    it was handed, and a test builds its own with a fake clock.

### Two concurrent reads become one request

```python
import asyncio

await asyncio.gather(
    cache.fetch(USERS.list(), load_rows),
    cache.fetch(USERS.list(), load_rows),
    cache.fetch(USERS.list(), load_rows),
)
# load_rows ran ONCE
```

That is *single-flight*, and it is what a screen with three widgets reading the
same query needs. Without it, mounting the screen fires three identical requests.

## Step 3 — invalidate by prefix

```python
cache.invalidate(USERS.all())    # reaches list(page=1), list(page=2), detail(7)…
```

One call, one prefix, everything under it. And the **value stays**:

!!! note "Stale is not empty"
    `invalidate` marks entries old and **keeps the value**, so the screen goes on
    showing the last good answer while the refetch is in flight. The difference
    between that and a screen that flickers to empty is exactly this line.

    When the value is known to be **wrong** rather than merely old, use `drop`,
    which removes it.

!!! danger "A prefix is segment-wise, never character-wise"
    `("users",)` is a prefix of `("users", "list")` and is **not** a prefix of
    `("users-archive",)`. A `startswith` over joined strings gets that second one
    wrong — and gets it wrong silently, invalidating a resource that merely
    shares a name.

## Step 4 — the optimistic change, and the undo

The screen has to change **now**, not after the round-trip. And if the server
refuses, it has to go back.

```python
from tempestweb import native
from tempestweb.query import upsert_by_id


async def rename(cache: QueryCache, user_id: int, name: str) -> None:
    """Rename on screen first, and undo if the server refuses."""
    edited = {"id": user_id, "name": name}
    with cache.optimistic(USERS.all(), lambda rows: upsert_by_id(rows, edited)):
        await native.http.request(
            "PATCH", f"/api/users/{user_id}", json={"name": name}
        )
```

If the `PATCH` raises, the block **restores exactly the entries it replaced** —
no network, no refetch, and it works offline.

!!! warning "Invalidating is not undoing"
    The obvious move — `cache.invalidate(...)` in the `except` — is a trip to the
    network, not an undo. It leaves the wrong change on screen until the refetch
    lands, and offline it does nothing at all. The rollback is synchronous and
    exact.

Want the control by hand? `patch` hands the rollback back:

```python
rollback = cache.patch(USERS.all(), lambda rows: upsert_by_id(rows, edited))
try:
    await native.http.request("PATCH", f"/api/users/{user_id}", json=edited)
except Exception:
    rollback()
    raise
```

!!! info "The patch reaches a prefix, not a key"
    A rename has to land on **every cached page** the row appears on. Patching
    only `("users", "list", "page=1")` leaves page 2 showing the old name until
    something else invalidates it.

    And it is atomic: if the patch raises halfway, what was already applied goes
    back. Two entries showing two different truths is worse than no change.

## Step 5 — the two ways to paginate

```python
from tempestweb.query import cursor_page, is_offset_page, offset_page

if is_offset_page(response.json):
    page = offset_page(response.json)
    page.pages, page.has_next, page.has_previous
else:
    page = cursor_page(response.json)
    page.next_cursor, page.has_next
```

| Shape | Knows | Costs |
| --- | --- | --- |
| **Offset** (`page` + `total`) | jump to page 7, show "of 12" | skips or repeats rows if the list changes between pages |
| **Cursor** (`next_cursor`) | never skips or repeats | does not know how many pages exist |

!!! note "A malformed page renders empty; it does not raise"
    `offset_page({"items": "not a list"})` answers an empty page. An empty
    listing is recoverable; an exception on the way to rendering is a blank
    screen.

Before the first answer, put `empty_offset_page()` in state instead of `None` —
the view never has to check before reading `.items`.

## Step 6 — surviving a reload

```python
from tempestweb import native
from tempestweb.query import persist, restore

await restore(cache, native.storage)   # on boot
...
await persist(cache, native.storage)   # when the screen is done
```

The storage is the `native.storage` that already exists, over the owner-scoped
IndexedDB store in `client/offline/store.js` — **nothing was reimplemented**. The
parameter is a `QueryStorage`, which that module satisfies as it stands; a test
passes a dictionary-backed fake.

!!! warning "Only JSON-able values persist"
    An entry holding an `HttpResponse`, a dataclass or a `datetime` cannot become
    JSON. `persist` **skips** those and reports how many it skipped, rather than
    raising: one unserializable entry must not stop the other nine from being
    saved.

Entries come back **fresh**. Reviving them stale would send the boot screen
straight to the network, which is exactly what persisting was meant to avoid.

## When **not** to use this

!!! info "It does not replace `native.sync`"
    Delta-sync is still the way to reconcile a **large collection** against a
    watermark. This cache is for reading a screen.

!!! warning "Mode A and Mode B — Mode C refuses"
    Mode C transcribes your app's Python into JavaScript and serves a closed set
    of modules. Importing `tempestweb.query` from a Mode C app is refused at build
    time, with a named error.

## Recap

- `keys("users")` builds **hierarchical** keys, which is what makes prefix
  invalidation possible at all.
- `cache.fetch(key, loader)` answers from cache while fresh, and concurrent reads
  of one key become **one** request.
- `invalidate(prefix)` marks entries old and keeps the value on screen;
  `drop(prefix)` removes them.
- `optimistic(prefix, patch)` applies now and **undoes exactly** if the block
  raises — no trip to the network.
- `offset_page` / `cursor_page` cover both shapes, and render empty rather than
  raise.
- `persist`/`restore` use the store that already exists, and only JSON-able
  values pass.
