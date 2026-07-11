# 2. State and handlers

On the [previous page](view.md) we drew the tree. Now we'll make the buttons
**change the state** — and see how tempestweb turns that change into a new tree
automatically.

## State is a dataclass

The counter holds a single integer:

```python
from dataclasses import dataclass


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state."""
    return CounterState()
```

`make_state()` is the factory for the initial state. The runtime calls it once
when mounting the app.

!!! note "Why a factory?"
    In Mode B (server), **each connection has its own isolated state**. The
    factory guarantees that each session starts with a fresh `CounterState`,
    without sharing references between clients.

## Handlers change state via `set_state`

A handler **never** mutates `app.state` directly. It calls `app.set_state`,
passing a function that applies the change:

```python
def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""

    def increment() -> None:  # (1)!
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                children=[
                    Button(label="-", on_click=decrement, key="dec"),  # (2)!
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

1. The handler is a normal function (or `async def`). It describes the **state
   transition**, it does not touch the DOM.
2. `on_click=increment` wires the click event to the handler. The `key="inc"` is
   what the event carries back so Python can resolve the handler.

!!! warning "Never mutate the DOM in a handler"
    You do not write `document.getElementById(...)`. You change the **state**; the
    reconciler computes the diff and the client applies the patches. That is the
    golden rule — and it holds identically in all three modes.

## The cycle: event → state → rebuild → patches

When the user clicks `+`:

```text
1. Client captures the click on Button key="inc"
2. Client sends the event → { "type": "click", "key": "inc", "payload": {} }
3. Python resolves key="inc" → handler increment
4. increment calls app.set_state → value goes from 0 to 1
5. The runtime runs view() again → new tree
6. diff(old tree, new tree) → [ Update on Text "label" ]
7. Client applies the patch → the text becomes "Count: 1"
```

!!! info "Coalescing"
    If a handler calls `set_state` several times in the same tick, the core
    **coalesces** everything into a single `diff`. The transport receives **one
    patch list per tick** — the client applies the whole list before the next
    frame. You never see intermediate states flickering.

## Handlers can be `async`

The runtime runs on an asyncio event loop, so handlers can be `async def` —
useful to fetch data before updating the state:

```python
async def load_total() -> None:
    """Fetch a total from a typed native HTTP wrapper, then update state."""
    total = await app.native.http.get_json("/api/total")  # typed awaitable
    app.set_state(lambda s: setattr(s, "value", total["count"]))
```

!!! tip "Async-first absorbs Mode B latency"
    In Mode B there is one network round-trip per interaction. The async-first
    rule (handler → state → coalesced rebuild) absorbs that naturally — the same
    code works locally (Mode A) and remotely (Mode B).

## Recap

- State is a `dataclass`; `make_state()` builds the initial one (isolated per
  session).
- Handlers call `app.set_state(fn)` — they **never** touch the DOM.
- The cycle is **event → state → rebuild → diff → patches**.
- Multiple `set_state` in the same tick **coalesce** into a single diff.
- Handlers can be `async`.

But what exactly does the `diff` emit? Let's look at the
[patches on the wire](patches.md). 🚀
