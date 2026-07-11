# 4. Running the modes

!!! abstract "What you'll learn"
    How to run the **same** `app.py` — without changing a line — in all three
    execution modes, and how to pick the right mode for each requirement.

You built the whole counter: [tree](view.md), [state](state.md) and
[patches](patches.md). Now the payoff of tempestweb's central promise: the
**same** `examples/counter/app.py` runs in **Mode A (WASM)**, **Mode B (server)**
and **Mode C (transpile)** — without changing a line. 🎯

## The app does not name a transport

Re-read the complete app. Notice what is **not** there: no `import websocket`,
no `import pyodide`, no mention of "browser" or "server".

```python
"""Counter — the canonical tempestweb example."""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

!!! check "The app is transport-agnostic"
    `view`, `make_state` and the handlers are **100% portable**. The mode choice
    is made by the CLI, outside the app. That is the project's single seam.

## Mode A — Python in the browser (WASM)

In Mode A, your Python runs **inside the tab** via Pyodide. The CLI bundles the
app + the JS client into a static bundle:

=== "Command"

    ```bash
    tempestweb build --mode wasm --path examples/counter
    tempestweb dev   --mode wasm --path examples/counter   # with hot-reload
    ```

=== "What happens"

    1. Pyodide loads the Python interpreter in the browser.
    2. `view()` runs in-process; the `diff` produces patches.
    3. Patches reach the client via **`pyodide.ffi`** — a function call, no
       network.
    4. `client/dom.js` applies the patches to the DOM.

!!! tip "Mode A is fully offline"
    After the initial load, everything runs in the browser — no server. It is the
    natural target for [PWA & offline](../pwa.md). The cost is the WASM bundle
    cold-start (which the Track P service worker solves via precache).

## Mode B — Python on the server (FastAPI)

In Mode B, your Python runs **on the server** and talks to a thin JS client over
WebSocket (or SSE). Like Phoenix LiveView:

=== "Command"

    ```bash
    tempestweb dev --mode server --path examples/counter
    # serves at http://127.0.0.1:8000
    ```

=== "What happens"

    1. FastAPI hosts the app; each connection has its own isolated asyncio
       session.
    2. The user clicks → the client sends `{ "kind": "event", "data": {...} }`.
    3. The server resolves the handler, runs `view()`, computes the `diff`.
    4. The server sends `{ "kind": "patches", "data": [...] }` back.
    5. The **same** `client/dom.js` applies the patches.

!!! info "The JS client is the same in both modes"
    Only the transport implementation differs: `transport-wasm.js` (Mode A) versus
    `transport-ws.js` / `transport-sse.js` (Mode B). The renderer (`client/dom.js`,
    `client/style.js`) is **a single one**.

## Mode C — Python transcribed to JavaScript (transpile)

In Mode C there is no live Python anywhere. A compiler transcribes the **app
layer** (your `view`/`state`/handlers) to **native JavaScript** at build time, and
the result is a 100% static bundle:

=== "Command"

    ```bash
    tempestweb build --mode transpile --path examples/counter   # writes dist/transpile/
    tempestweb dev   --mode transpile --path examples/counter    # with livereload
    ```

=== "What happens"

    1. The compiler reads `app.py` and emits `app.gen.js` — native JS.
    2. In the browser, the runtime holds the state and runs `view()` **in JS**.
    3. The `diff` runs natively in the browser; no transport, no server.
    4. The **same** `client/dom.js` applies the patches to the DOM.

!!! tip "Mode C is the perfect target for PWA and SEO"
    Because the bundle is static and Python-free, first-paint is immediate and the
    `build` already emits the **installable + offline PWA** layer out of the box.
    The [Mode C — transpile](../transpile.md) page dives into the full flow. 🚀

## Side by side

| | Mode A — WASM | Mode B — Server | Mode C — transpile |
|---|---|---|---|
| Where Python runs | In the browser (Pyodide) | On the server (FastAPI) | **Nowhere** (becomes JS) |
| How patches arrive | `pyodide.ffi` (in-process) | WebSocket / SSE (network) | `diff` in JS, in-process |
| State | In the browser | On the server, isolated per connection | In the browser (JS) |
| Offline | Full after load | Partial (read-only cache + queue) | Full (static bundle) |
| Latency per interaction | Zero round-trip | One network round-trip | Zero round-trip |
| SEO / first-paint | Weak (WASM bundle) | Strong (server HTML) | **Great** (static bundle) |

!!! warning "Choose the mode by requirement, not taste"
    Need SEO, fast first-paint, and a static server-free site/PWA? → **Mode C**.
    Need to run sensitive logic or central state on the server? → **Mode B**. Want
    live Python in the browser to prototype? → **Mode A**. The app is the same;
    only `--mode` changes.

## Recap

- The `app.py` **never names a transport** — `view`/`state`/handlers are portable
  across all three modes.
- **Mode A** runs Python in the browser via Pyodide; patches via `pyodide.ffi`.
- **Mode B** runs Python on the server (FastAPI); patches via WebSocket/SSE.
- **Mode C** transcribes the app to native JS; `diff` in-process, static bundle.
- The **JS client and renderer are the same**; only the mode changes.

🎉 You finished the tutorial! You built the counter and understand the wire
contract end to end. To go further, dive into [Mode C — transpile](../transpile.md),
the [PWA & offline](../pwa.md) layer, the [native capabilities](../capabilities.md)
and [observability](../observability.md).
