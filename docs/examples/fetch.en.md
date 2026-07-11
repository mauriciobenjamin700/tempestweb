# Async fetch — `idle → loading → loaded/error` ⏳

**Modes: A/B** — uses core widgets and an `async` handler (the fetcher is injected).

The canonical async-I/O pattern in tempestweb: pressing **Load** fires an `async`
handler that flips the phase to `loading` (rendering a `Spinner`), awaits an
I/O-bound fetch, then re-renders with the result. Without freezing the UI. 🚀

!!! note "The fetcher is injected"
    The `fetch` callable is a **state field** with a default. That keeps the
    example deterministic under test (inject a fake coroutine); in a real app you
    would pass `native.http.request`. The `view` never blocks the event loop.

---

## What this example shows

- **`async` handler** — `load()` `await`s an injected fetcher without freezing the UI.
- **Phase machine** — a `StrEnum` `Phase` (`idle`/`loading`/`loaded`/`error`)
  drives what the `view` renders.
- **`Spinner`** while loading; a **`LazyColumn`** of rows once loaded.
- **Error handling** — any exception from the `await` transitions to `error`.

---

## Running ▶

```bash
tempestweb run --mode wasm     examples/fetch   # Python in the browser (Pyodide)
tempestweb run --mode server   examples/fetch   # Python on the server (FastAPI + WS)
```

---

## The code

```python
"""Async fetch view — exercises an ``async`` handler driving the UI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    LazyColumn,
    Spinner,
    Text,
)

#: A coroutine that resolves to the fetched rows. Injected into the view so the
#: example stays deterministic under test; in a real app this wraps
#: ``native.http.request``.
Fetcher = Callable[[], Awaitable[list[str]]]


class Phase(StrEnum):
    """The lifecycle phase of the async fetch.

    Attributes:
        IDLE: Nothing has been requested yet.
        LOADING: A fetch is in flight (the spinner is shown).
        LOADED: The fetch resolved and rows are available.
        ERROR: The fetch raised; an error message is shown.
    """

    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


async def _default_fetch() -> list[str]:
    """Return a fixed list of rows, standing in for a network call.

    Returns:
        A small list of sample rows.
    """
    return ["alpha", "beta", "gamma"]


@dataclass
class FetchState:
    """State for the async fetch app.

    Attributes:
        phase: The current lifecycle phase.
        rows: The rows fetched on success.
        error: The error message shown on failure.
        fetch: The injected coroutine that performs the fetch.
    """

    phase: Phase = Phase.IDLE
    rows: list[str] = field(default_factory=list)
    error: str = ""
    fetch: Fetcher = _default_fetch


def make_state() -> FetchState:
    """Build the initial, idle fetch state.

    Returns:
        A fresh :class:`FetchState`.
    """
    return FetchState()


def view(app: App[FetchState]) -> Widget:
    """Render the fetch UI from the current lifecycle phase.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    async def load() -> None:
        app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))
        try:
            rows = await app.state.fetch()
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            # Bind the message before the except block clears ``exc`` so the
            # closure below captures a live value.
            message = str(exc)

            def on_error(s: FetchState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        def on_success(s: FetchState) -> None:
            s.phase = Phase.LOADED
            s.rows = rows

        app.set_state(on_success)

    children: list[Widget] = [
        Text(content="Async fetch", key="title"),
        Button(label="Load", on_click=load, key="load"),
    ]

    if app.state.phase is Phase.LOADING:
        children.append(Spinner(key="spinner"))
    elif app.state.phase is Phase.ERROR:
        children.append(Text(content=f"Error: {app.state.error}", key="error"))
    elif app.state.phase is Phase.LOADED:
        rows = app.state.rows
        children.append(
            LazyColumn(
                item_count=len(rows),
                item_builder=lambda i: Text(content=rows[i]),
                key="rows",
            )
        )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=children,
    )
```

---

## Piece by piece

### `set_state` before and after the `await`

```python
async def load() -> None:
    app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))  # (1) immediate re-render
    rows = await app.state.fetch()                               # (2) I/O
    app.set_state(on_success)                                    # (3) final re-render
```

The `set_state(LOADING)` call happens **before** the `await` — so the `Spinner`
paints right away. Only then does the `await` resolve and the phase become
`loaded`. In between, the UI never freezes: the runtime awaits the handler on the
browser's event loop (Mode A) or the server's (Mode B).

### The phase drives the tree

```python
if app.state.phase is Phase.LOADING:
    children.append(Spinner(key="spinner"))
elif app.state.phase is Phase.ERROR:
    children.append(Text(content=f"Error: {app.state.error}", key="error"))
elif app.state.phase is Phase.LOADED:
    children.append(LazyColumn(...))
```

Building a `children` list and appending per phase is an idiomatic pattern for
conditional rendering.

!!! warning "Capture the message before leaving the `except`"
    ```python
    except Exception as exc:
        message = str(exc)   # ← capture here
        def on_error(s): s.error = message
    ```
    In Python, `exc` is cleared at the end of the `except` block. Binding `message`
    beforehand ensures the `on_error` closure captures a live value.

---

## Recap

In this example you saw:

- ✅ An **`async` handler** that `await`s without freezing the UI
- ✅ The **`idle → loading → loaded/error`** phase machine driving the `view`
- ✅ **`set_state` before and after the `await`** to paint `loading` immediately
- ✅ An **injected fetcher** that makes the example deterministic under test
- ✅ The pattern running unchanged in **Modes A/B**

---

## Next steps

- 💡 The [Weather (HTTP + geolocation)](weather-native.md) chains **two** native capabilities with this same pattern
- 💡 Back to the [To-do list](todo.md) for another use of `LazyColumn`
- 💡 Read [native capabilities](../capabilities.md) to swap `_default_fetch` for `native.http.request`
