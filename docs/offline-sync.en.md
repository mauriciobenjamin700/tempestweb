# Offline + backend sync

!!! abstract "What you'll learn"
    How to wire tempestweb's **offline queue** (the client) to a **FastAPI backend
    built with [`tempest-fastapi-sdk`](https://pypi.org/project/tempest-fastapi-sdk/)**
    for an **end-to-end offline-first app**: the app queues mutations locally when
    there's no network and **syncs** them when connectivity returns — without ever
    applying anything twice. 🚀

The [PWA & offline](pwa.md) page covers the offline queue on the **client** side
(service worker, IndexedDB, `native.offline`). Here we close the loop: the other
end of the mutation is a **real server** that receives, persists and dedups the
replays. Nothing new in your `view()` — just a well-built endpoint on the far
side. ✅

---

## Why offline-first

A traditional app writes straight to the network: no network, the write **fails**
and the user loses what they typed. Offline-first flips that around:

1. **Queue locally first.** Every mutation goes into a durable IndexedDB queue —
   the write "succeeds" immediately, even with no network.
2. **Sync when the network returns.** When connectivity is back (the `online`
   event, Background Sync, or an explicit replay), the queue drains in **FIFO**
   order against the backend.
3. **Never apply twice.** Each mutation carries an **idempotency key**; the server
   dedups, so re-sending an already-applied mutation is harmless.

!!! info "Two directions, two mechanisms"
    - **Push (writes)** — app → server. This is what the `native.offline` queue
      does for you: enqueue, replay, idempotency.
    - **Pull (reads)** — server → app. There's no queue for this; it's a
      **delta-sync** pattern you assemble with `native.http` + the repository's
      `updated_at__gt` filter. We cover both below.

---

## Architecture

```text
┌──────────────────────── Browser (tempestweb app) ─────────────────────────┐
│                                                                            │
│  view()  ──enqueue──►  native.offline  ──►  OfflineQueue  ──►  IndexedDB   │
│  (Python)              (durable write)      (FIFO + key)      (tempestweb- │
│                                                                offline /   │
│                                                                mutations)  │
│                                                                            │
│  online / Background Sync / replay()  ──drains FIFO──►  fetch              │
│                                                          header:           │
│                                                          idempotency-key   │
└─────────────────────────────────────────────────────────────┬────────────┘
                                                               │  HTTPS
                                                               ▼
┌──────────────── Backend (FastAPI + tempest-fastapi-sdk) ───────────────────┐
│                                                                            │
│  IdempotencyMiddleware  ──(method, path, key)──►  store (Memory | Redis)   │
│       │ 1st time                      │ retry / replay → cached response   │
│       ▼                               ▼                                    │
│  router  ──►  BaseRepository.add()  ──►  Postgres / SQLite                 │
│               (id, created_at, updated_at automatic)                       │
│                                                                            │
│  pull:  GET /api/notes?since=<ts>  ──►  repo.list({"updated_at__gt": ts})  │
└────────────────────────────────────────────────────────────────────────────┘
```

The meeting point is the **idempotency key**: the client sends it in a header, and
the SDK's `IdempotencyMiddleware` uses it to cache the response by
`(method, path, key)`. A repeated replay returns the **cached response** — zero
duplicate rows in the database.

!!! note "A separate backend, on purpose"
    The backend is its **own FastAPI service** (the same one you'd already have
    with the SDK). It doesn't need to know the client is a tempestweb app — it
    receives a normal `POST`/`PUT` with an idempotency header. This holds across
    all three tempestweb execution modes (WASM, server, transpile).

---

## Part A — Enqueue mutations in the tempestweb app

The `native.offline` capability is the real client API. You enqueue a mutation
instead of hitting the network directly:

```python
from tempestweb import native


async def save_note(text: str) -> None:
    """Queue a note creation (survives being offline)."""
    await native.offline.enqueue("POST", "/api/notes", {"text": text})
```

The full signature:

```python
await native.offline.enqueue(
    method,                 # "POST" | "PUT" | "PATCH" | "DELETE"
    url,                    # your backend endpoint
    body=None,              # JSON-able body
    *,
    idempotency_key=None,   # auto-generated when omitted
    owner=None,             # optional scope (e.g. per user)
)
```

It returns a `Mutation` (`id`, `owner`, `idempotency_key`, `method`, `url`,
`attempts`, `status`). You can also **inspect** and **drain** the queue:

| Call | Does | Returns |
|---|---|---|
| `native.offline.enqueue(...)` | Queue a durable mutation. | `Mutation` |
| `native.offline.pending(owner=None)` | List pending ones, oldest first. | `list[Mutation]` |
| `native.offline.size(owner=None)` | Count the pending ones. | `int` |
| `native.offline.replay(owner=None)` | Drain the queue **now** (FIFO, stops at 1st failure). | `ReplayResult(sent, remaining)` |

### The full app

A minimal "activity log": typing and pressing **Queue** writes to the queue; the
counter comes from `size()`; **Sync** triggers the replay (which the runtime also
does on its own when the network returns). This is
[`examples/offline-queue/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/offline-queue/app.py):

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent
from tempestweb import native


@dataclass
class QueueState:
    """State for the offline-queue demo."""

    draft: str = ""
    queued: int = 0
    status: str = ""
    log: list[str] = field(default_factory=list)


def make_state() -> QueueState:
    """Initial state."""
    return QueueState()


def view(app: App[QueueState]) -> Widget:
    """Input + pending count + replay control."""

    def on_draft(event: TextChangeEvent) -> None:
        value = event.value
        app.set_state(lambda s: setattr(s, "draft", value))

    async def queue_note() -> None:
        text = app.state.draft
        await native.offline.enqueue("POST", "/api/notes", {"text": text})  # (1)!
        size = await native.offline.size()

        def _update(s: QueueState) -> None:
            s.queued = size
            s.draft = ""
            s.log = [*s.log, text]
            s.status = f"queued: {text}"

        app.set_state(_update)

    async def sync_now() -> None:
        result = await native.offline.replay()  # (2)!

        def _update(s: QueueState) -> None:
            s.queued = result.remaining
            s.status = f"sent {result.sent}, {result.remaining} left"

        app.set_state(_update)

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Pending: {app.state.queued}", key="pending"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Input(
                        value=app.state.draft,
                        placeholder="a note to sync",
                        on_change=on_draft,
                        key="draft",
                    ),
                    Button(label="Queue", on_click=queue_note, key="queue"),
                    Button(label="Sync", on_click=sync_now, key="replay"),
                ],
            ),
            Text(content=app.state.status, key="status"),
        ],
    )
```

1.  Queues instead of `fetch`-ing. Works **with no network** — the write goes to
    IndexedDB.
2.  Drains the queue now. The runtime **also** does this on its own when the
    network returns (`online` event + Background Sync), so this button is
    optional.

!!! tip "The idempotency key is automatic"
    You don't have to generate the key: when you omit `idempotency_key`, the queue
    generates a stable one and sends it in the `idempotency-key` header on every
    replay. That key is what the backend uses to avoid applying the same write
    twice.

---

## Part B — The sync endpoint on the backend with the SDK

On the far side, a FastAPI service built with `tempest-fastapi-sdk`. Three pieces:
the **model**, the **schemas** and the **endpoint** — plus the
`IdempotencyMiddleware` that makes replay safe.

```bash
uv add "tempest-fastapi-sdk[cache]"   # [cache] only if you'll use the Redis store
```

### The model and the schemas

The SDK's `BaseModel` already ships `id` (UUID), `is_active`, `created_at` and
`updated_at` — the last **auto-refreshed** on every `UPDATE`, which is exactly
what delta-sync (Part E) needs.

```python
from sqlalchemy.orm import Mapped, mapped_column
from tempest_fastapi_sdk import BaseModel, BaseResponseSchema, BaseSchema


class NoteModel(BaseModel):
    """A persisted note."""

    __tablename__ = "notes"

    text: Mapped[str] = mapped_column()


class NoteCreateSchema(BaseSchema):
    """Note creation body (what the client queues)."""

    text: str


class NoteResponseSchema(BaseResponseSchema):
    """Note response — inherits id/is_active/created_at/updated_at."""

    text: str
```

!!! info "`BaseRepository` with no subclass"
    For plain CRUD you **instantiate `BaseRepository` directly**:
    `BaseRepository(session, model=NoteModel)`. It exposes `add()`, `list()`,
    `get_by_id()`, `update()`, `delete()` and more. Only subclass it when you need
    custom queries.

### The FastAPI app

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from tempest_fastapi_sdk import (
    AsyncDatabaseManager,
    BaseRepository,
    IdempotencyMiddleware,
    MemoryIdempotencyStore,
    register_exception_handlers,
)

db = AsyncDatabaseManager("sqlite+aiosqlite:///./notes.db")
app = FastAPI(title="notes-backend")

# Dedup replays: a repeated POST with the same Idempotency-Key returns the cached
# response — no duplicate row.
app.add_middleware(
    IdempotencyMiddleware,
    store=MemoryIdempotencyStore(),   # swap for RedisIdempotencyStore on multi-replica
    ttl_seconds=24 * 3600,
)
register_exception_handlers(app)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """One async session per request."""
    async for session in db.session_dependency():
        yield session


@app.on_event("startup")
async def _startup() -> None:
    """Create the tables on boot (use migrations in production)."""
    await db.create_tables()


@app.post("/api/notes", response_model=NoteResponseSchema, status_code=201)
async def create_note(
    data: NoteCreateSchema,
    session: AsyncSession = Depends(get_session),
) -> NoteResponseSchema:
    """Persist a note. Idempotent via the Idempotency-Key header."""
    repo = BaseRepository(session, model=NoteModel)
    note = await repo.add(NoteModel(text=data.text))
    return NoteResponseSchema.model_validate(note)
```

!!! success "How idempotency connects end to end"
    The `native.offline` replay sends the `idempotency-key` header; the
    `IdempotencyMiddleware` reads `Idempotency-Key` — and HTTP headers are
    **case-insensitive**, so the two match with no work on your side. The
    middleware only acts on `POST`/`PUT`/`PATCH`/`DELETE` and **only** when the
    header is present; requests without a key pass straight through.

---

## Part C — Replay and confirmation when back online

Replay is the **client runtime's responsibility** — the SDK imposes no sync
protocol. tempestweb drains the queue on three triggers:

- **The `online` event.** As soon as the browser reports connectivity, the queue
  drains (tab open).
- **Background Sync.** Where the browser supports it (Chromium), the service
  worker drains the queue **even with the tab closed**.
- **Explicit.** Your app calls `await native.offline.replay()` whenever you want
  (e.g. a "Sync" button or when a screen opens).

Replay is **FIFO and stops at the first failure** — if a mutation fails it stays
pending (with `attempts` incremented) and the following ones do **not** jump
ahead, preserving order. The `ReplayResult` tells you the outcome:

```python
from tempestweb import native


async def sync_and_report() -> str:
    """Drain the queue and return a human-readable status line."""
    result = await native.offline.replay()
    if result.remaining == 0:
        return f"all synced ({result.sent} sent)"
    return f"sent {result.sent}, {result.remaining} still pending"
```

!!! warning "Replay doesn't return the created resource to the app"
    `replay()` returns only **counts** (`sent` / `remaining`), not the server's
    response bodies. So the app doesn't get back the `id`/`created_at` of a note
    created by a queued mutation. If you need that data on the client, **re-read**
    it from the server with a pull (Part E) after the replay — the canonical
    offline-first pattern (write optimistically, reconcile by re-reading).

---

## Part D — Idempotency and conflict

### Idempotency (solved)

The `IdempotencyMiddleware` caches the response by `(method, path, key)`. A replay
with the same key returns the **same** result — never inserts twice. It's the
Stripe/AWS/GitHub pattern, and it's what makes replay safe by construction.

!!! danger "Pick the right store in production"
    `MemoryIdempotencyStore` is **per-process** — on multi-replica one replica
    can't see the key cached by another, and replay can duplicate. With more than
    one replica, use `RedisIdempotencyStore`:

    ```python
    from redis.asyncio import Redis
    from tempest_fastapi_sdk import IdempotencyMiddleware, RedisIdempotencyStore

    app.add_middleware(
        IdempotencyMiddleware,
        store=RedisIdempotencyStore(Redis.from_url("redis://localhost:6379/0")),
        ttl_seconds=24 * 3600,
    )
    ```

### Conflict (your call)

Idempotency solves **duplicate replay**, not **content conflict** (two clients
editing the same row). tempestweb's queue default is **last-write-wins**: the last
write to arrive wins. For most apps (notes, logs, forms) that's enough.

If you need **version-based** resolution (rejecting a write based on a stale
version), that's an **application** decision — neither tempestweb nor the SDK
imposes a protocol. A common pattern is to version the row and refuse stale
writes:

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


@app.put("/api/notes/{note_id}", response_model=NoteResponseSchema)
async def update_note(
    note_id: str,
    data: NoteUpdateSchema,             # includes a `version: int` field
    session: AsyncSession = Depends(get_session),
) -> NoteResponseSchema:
    """Update a note, rejecting writes based on a stale version."""
    repo = BaseRepository(session, model=NoteModel)
    note = await repo.get_by_id(note_id)              # 404 if missing
    if data.version < note.version:                    # conflict → the client re-reads
        raise HTTPException(status_code=409, detail="stale version")
    note.text = data.text
    note.version = data.version + 1
    return NoteResponseSchema.model_validate(await repo.update(note))
```

!!! note "Honesty about the boundary"
    The snippet above is **application code**, not a framework API — the `version`
    field is yours. tempestweb delivers the mutation idempotently; **what the
    server does with a conflict is up to you** (last-write-wins, version, per-field
    merge, CRDT…).

---

## Part E — Pull: bringing server changes back to the app

The queue handles the **push**. For the **pull** (the server has new data the app
hasn't seen yet), the pattern is **delta-sync**: keep a *watermark* (the largest
`updated_at` you've seen) and ask only for what changed since then.

`BaseRepository` supports the `updated_at__gt` filter for exactly this:

```python
from datetime import datetime

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession


@app.get("/api/notes", response_model=list[NoteResponseSchema])
async def list_notes(
    since: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[NoteResponseSchema]:
    """List the notes changed since `since` (delta-sync)."""
    repo = BaseRepository(session, model=NoteModel)
    filters = {"updated_at__gt": since} if since else None
    notes = await repo.list(filters=filters, order_by=NoteModel.updated_at)
    return [NoteResponseSchema.model_validate(n) for n in notes]
```

On the client, you read the delta with `native.http` (not the queue — reads don't
need a durable queue) and advance the watermark:

```python
from tempestweb import native


async def pull_since(watermark: str | None) -> tuple[list[dict], str | None]:
    """Fetch notes changed since `watermark`; return (notes, new_watermark)."""
    url = "/api/notes" + (f"?since={watermark}" if watermark else "")
    response = await native.http.request("GET", url)
    if not response.ok:
        return [], watermark
    notes = response.json_body or []
    newest = max((n["updated_at"] for n in notes), default=watermark)
    return notes, newest
```

!!! info "Honest gap: the pull is an app pattern, not a ready-made API"
    tempestweb has **no** "read queue" and no built-in pull mechanism — the
    `native.offline` queue is **write-only**. The delta-sync above is a pattern you
    assemble with `native.http` (client) + the `updated_at__gt` filter (SDK).
    Storing the watermark locally is up to you (e.g. `native.storage`).

---

## Recap

- **Push is handled by the queue.** `native.offline.enqueue(...)` writes locally;
  the runtime drains FIFO when the network returns (`online` + Background Sync) or
  via `replay()`. Each mutation carries an **idempotency key**.
- **The backend is FastAPI + the SDK.** `BaseRepository.add()` persists; the
  `IdempotencyMiddleware` (header `Idempotency-Key`, case-insensitive) dedups
  replays by `(method, path, key)` — zero duplicate rows.
- **Conflict is your call.** The default is last-write-wins; version/merge is
  application code — the framework imposes no protocol.
- **Pull is manual delta-sync.** `native.http` + the repository's `updated_at__gt`
  filter; the queue does **not** read, and replay returns only counts (re-read the
  resource if you need the `id`/timestamps).

Ready to ship the backend? See [Deploy to production](deploy.md) and
[Security (Mode B)](security.md). 🚀
