# Offline queue — durable writes that survive being offline 📥

**Modes: A/B** — uses components and the Python event shape (`event.value`).

A tiny "activity log": typing a note and pressing **Queue** appends a mutation to
the **durable offline queue** (`native.offline.enqueue`) instead of hitting the
network directly — so it works with **no connectivity**. **Replay** drains the
queue in FIFO order. 🚀

!!! note "Why a queue instead of a direct POST?"
    In a real app, a `POST /api/log` fails when the user is offline. With
    `native.offline`, the write is **persisted locally** and re-sent later — the
    runtime also drains the queue **automatically** when connectivity returns. The
    server dedups on the idempotency key, so a replay never double-applies the same
    mutation.

---

## What this example shows

- **`native.offline.enqueue(method, url, body)`** — persists a mutation to the
  durable queue instead of making the network request now.
- **`native.offline.size()`** — returns how many mutations are pending.
- **`native.offline.replay()`** — drains the queue and returns a `ReplayResult`
  with `sent` and `remaining`.
- **Bridge-free initial render** — the first mount only *reads* state, so
  `build(view(app))` is green with no native bridge installed; the `async` handlers
  are the ones that call the capability.

---

## Running ▶

```bash
tempestweb run --mode wasm     examples/offline-queue   # Python in the browser (Pyodide)
tempestweb run --mode server   examples/offline-queue   # Python on the server (FastAPI + WS)
```

The **same** `view` runs unchanged in both modes — it reads `event.value` off the
`TextChangeEvent` (the Python event shape).

---

## The code

```python
"""Offline queue — durable writes that survive being offline (native.offline)."""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent
from tempestweb import native


@dataclass
class QueueState:
    """State for the offline-queue demo.

    Attributes:
        draft: The text currently typed into the input.
        queued: The number of pending mutations (from the last refresh).
        status: A short human-readable status line.
        log: The notes queued so far, in order.
    """

    draft: str = ""
    queued: int = 0
    status: str = ""
    log: list[str] = field(default_factory=list)


def make_state() -> QueueState:
    """Build the initial state.

    Returns:
        A fresh :class:`QueueState`.
    """
    return QueueState()


def view(app: App[QueueState]) -> Widget:
    """Render the input, the pending count, and the replay control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_draft(event: TextChangeEvent) -> None:
        value = event.value
        app.set_state(lambda s: setattr(s, "draft", value))

    async def queue_note() -> None:
        text = app.state.draft
        await native.offline.enqueue("POST", "/api/log", {"text": text})
        size = await native.offline.size()

        def _update(s: QueueState) -> None:
            s.queued = size
            s.draft = ""
            s.log = [*s.log, text]
            s.status = f"queued: {text}"

        app.set_state(_update)

    async def replay() -> None:
        result = await native.offline.replay()

        def _update(s: QueueState) -> None:
            s.queued = result.remaining
            s.status = f"replayed {result.sent}, {result.remaining} left"

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
                    Button(label="Replay", on_click=replay, key="replay"),
                ],
            ),
            Text(content=app.state.status, key="status"),
            Column(
                style=Style(gap=2.0),
                children=[
                    Text(content=f"• {entry}", key=f"log-{i}")
                    for i, entry in enumerate(app.state.log)
                ],
            ),
        ],
    )
```

---

## Piece by piece

### Enqueue instead of send

```python
async def queue_note() -> None:
    text = app.state.draft
    await native.offline.enqueue("POST", "/api/log", {"text": text})
    size = await native.offline.size()
    ...
```

`queue_note` is an `async` handler. It does **not** POST — it *enqueues* the
mutation (`method`, `url`, `body`) and then reads the queue size. Because the write
is durable, it survives a page refresh or going offline.

### Drain the queue

```python
async def replay() -> None:
    result = await native.offline.replay()
    # result.sent → sent ; result.remaining → still pending
```

`replay()` tries to send everything in FIFO order and returns a `ReplayResult`. In
production the runtime calls this on its own when connectivity returns — the button
just makes the flow explicit and testable.

!!! tip "The initial mount is bridge-free"
    The first render only reads `app.state` — no native call. That is why
    `build(view(app))` works **with no bridge installed**, and tests drive the
    `async` handlers through a scripted bridge.

!!! info "Server-side idempotency"
    Each mutation carries an idempotency key. If a replay re-sends something the
    server already processed, it dedups — so flaky reconnects never apply the same
    write twice.

---

## Recap

In this example you saw:

- ✅ **`native.offline.enqueue`** to make writes durable and offline-tolerant
- ✅ **`native.offline.size`** to expose the pending count
- ✅ **`native.offline.replay`** returning `ReplayResult(sent, remaining)`
- ✅ A **bridge-free** initial mount with `async` handlers that call the capability
- ✅ The pattern running unchanged in **Modes A/B**

---

## Next steps

- 💡 See [PWA & offline](../pwa.md) for the full offline + WebPush story
- 💡 The [Mode C tour](transpile-tour.md) also uses `native.offline` in a static bundle
- 💡 Read [native capabilities](../capabilities.md) for the whole `tempestweb.native` module
