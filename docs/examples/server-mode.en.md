# Mode B end to end — FastAPI + WebSocket Server 🚀

Discover how the **same** `view()` that runs in the browser (Mode A / Pyodide) can be served from a FastAPI server over WebSocket — without changing a single line of application code.

---

## What you will learn

In this tutorial you will:

- 🧩 Understand the difference between **Mode A** (Python in the browser) and **Mode B** (Python on the server)
- 🔌 Use `tempestweb.server.create_app` to wrap any `view` in a FastAPI application
- 🧪 Test the server with `fastapi.testclient.TestClient` — no network ports needed
- 🚀 Start the real server with `uvicorn.run`
- 🔍 Understand the fix for a pre-existing serialization bug in `_json_safe` that caused errors when using styled widgets (`Style`, `Edge`)

!!! note "Prerequisite: the Counter example"
    This tutorial uses `make_state` and `view` from `examples/counter/app.py`.
    Read [the basic tutorial](../tutorial/index.md) first if you haven't done that yet.

---

## Why two modes?

tempestweb has a central premise: **application code does not know about the transport**. The `view` function only knows it receives an `App` and returns a `Widget`. Who decides *where* Python runs and *how* patches reach the browser is the **transport layer**.

```
┌──────────────────────────────────────┐
│  view(app) → Widget                  │  ← identical in both modes
├──────────────────────────────────────┤
│  PatchTransport  (single seam)       │
├─────────────────┬────────────────────┤
│  Mode A (WASM)  │  Mode B (server)   │
│  WasmTransport  │  WebSocket / SSE   │
└─────────────────┴────────────────────┘
```

| | Mode A | Mode B |
|---|---|---|
| Where Python runs | In the browser (Pyodide) | On the server (FastAPI) |
| Transport | `pyodide.ffi` in-process | WebSocket / SSE+POST |
| Interaction latency | Zero (no network) | Server round-trip |
| SEO / first paint | Limited | Better (server can pre-render) |
| Shared state | Impossible across tabs | Possible (sessions in same process) |

!!! tip "Golden rule"
    Choose the mode on the CLI: `tempestweb dev --mode wasm` (static) or `tempestweb run --mode server` (server) — or at deploy time. `app.py` never changes.

---

## Prerequisites

```bash
pip install tempestweb
```

Expected structure:

```
examples/
├── counter/
│   └── app.py          # make_state + view (our app)
└── server-mode/
    └── serve.py        # Mode B entry-point
```

---

## Step 1 — The counter app (unchanged)

This is `examples/counter/app.py`. Copy it exactly as is — it runs in **both modes** without any modification:

```python
"""Counter — the canonical tempestweb example.

This exact ``view`` runs unchanged in both modes:

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state.

    Returns:
        A fresh :class:`CounterState`.
    """
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

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

!!! info "Why `Style(gap=8.0, padding=Edge.all(16))`?"
    `Style` and `Edge` are instances of `pydantic.BaseModel`. When the server serializes the initial patches to JSON, these objects must be converted to plain dicts — that is exactly what `_json_safe` does (see Step 5).

---

## Step 2 — Creating the server with `create_app`

Create `examples/server-mode/serve.py`:

```python
"""Mode B server entry-point — the counter example running on the server.

This module demonstrates how the *exact same* ``view`` function that runs inside
the browser (Mode A / Pyodide) can be served from a FastAPI host over WebSocket
and SSE without any change to the application code.

Usage::

    # Start the server (development):
    python examples/server-mode/serve.py

    # Then open the thin JS client in your browser at http://127.0.0.1:8000.
    # WebSocket endpoint: ws://127.0.0.1:8000/ws
    # SSE endpoints:      GET  http://127.0.0.1:8000/sse?session=<id>
    #                     POST http://127.0.0.1:8000/sse/<id>

The ``app`` symbol is importable by uvicorn / ASGI runners::

    uvicorn examples.server_mode.serve:app
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from examples.counter.app import make_state, view
from tempestweb.server import create_app

# ---------------------------------------------------------------------------
# Module-level ASGI app — importable by any ASGI runner.
# ---------------------------------------------------------------------------

app: FastAPI = create_app(
    make_state,
    view,
    title="tempestweb — Mode B counter demo",
)


def run() -> None:
    """Launch the Mode B demo server programmatically.

    Binds to ``127.0.0.1:8000`` (internal-only; change to ``0.0.0.0`` when a
    separate origin needs to reach this host).
    """
    uvicorn.run(
        "examples.server_mode.serve:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
```

That is all. Two key lines:

```python hl_lines="2 3"
app: FastAPI = create_app(
    make_state,   # (1) state factory — called once per connection
    view,         # (2) the view function — the same as Mode A
    title="tempestweb — Mode B counter demo",
)
```

---

## Step 3 — What `create_app` does under the hood

`create_app` is a factory that mounts a `FastAPI` with three routes:

| Route | Protocol | Direction | Purpose |
|---|---|---|---|
| `GET /ws` | WebSocket | bidirectional | Main transport (B1) |
| `GET /sse?session=<id>` | SSE | server→client | Patch stream (B5) |
| `POST /sse/{session_id}` | HTTP | client→server | Event delivery for SSE |

Each WebSocket connection gets its own `AppSession` — state is completely isolated between clients:

```
Connection A                  Connection B
   │                             │
   ├── AppSession(state_factory) ├── AppSession(state_factory)
   │       CounterState(value=0) │       CounterState(value=0)
   │                             │
   │   click "+": value=1        │   value still 0
   │                             │
```

!!! check "Isolation guaranteed"
    `state_factory` is called **per connection**, never once globally. Two users opening the app at the same time start with independent counters.

---

## Step 4 — The wire format

All communication between Python and the JS client uses **JSON envelopes** with a `kind` field:

```json
// Server → client: patch batch after a click
{
  "kind": "patches",
  "data": [
    {
      "path": ["children", 0],
      "set_props": { "content": "Count: 1" },
      "unset_props": []
    }
  ]
}
```

```json
// Client → server: click event on the "+" button
{
  "kind": "event",
  "data": { "type": "click", "key": "inc" }
}
```

!!! note "The JS client is the same in both modes"
    The client in `client/` never knows whether Python is in the browser or on the server. It only sends events and applies patches to the DOM — the transport is completely transparent to it.

---

## Step 5 — The fixed bug: `_json_safe` and Pydantic objects

### What was the problem

The counter `view` uses `Style` and `Edge` — both are `pydantic.BaseModel` instances. When the server tried to serialize the initial patches to JSON, these objects were not recognized as serializable and caused an error:

```
TypeError: Object of type Style is not JSON serializable
```

### The fix in `tempestweb/runtime/serialize.py`

The `_json_safe` function was fixed to handle `BaseModel` before the generic fallback:

```python
from pydantic import BaseModel

def _json_safe(value: Any) -> Any:
    """Replace non-JSON-able prop values (handlers, Pydantic models) recursively.

    The IR carries live handler callables in ``props``; this strips them to
    ``None`` so the result is JSON-serializable.  Pydantic
    :class:`~pydantic.BaseModel` instances (e.g.
    :class:`~tempest_core.style.Style`,
    :class:`~tempest_core.style.Edge`) are lowered via
    ``model_dump(mode="json")`` which resolves colors, edges, enums and other
    structured style values to plain JSON-safe scalars before the recursive walk.

    Args:
        value: Any prop value drawn from a node's ``props``.

    Returns:
        A JSON-able value: callables become ``None``; Pydantic models are dumped
        to dicts; dicts and lists are walked recursively; everything else is
        returned unchanged.
    """
    if callable(value):
        return None
    if isinstance(value, BaseModel):          # ← fix: was missing before
        return _json_safe(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
```

!!! warning "Order matters"
    The `isinstance(value, BaseModel)` check must come **after** the `callable` check and **before** the `dict` check — because `model_dump(mode="json")` returns a `dict`, which is then recursively processed by the next branch.

### Why `mode="json"`?

`model_dump()` without `mode="json"` can return Python types that are still not serializable (e.g. `Enum`, `Color` with internal integer fields). `mode="json"` ensures everything comes out as primitive scalars.

---

## Step 6 — Running the server

### Quick development via CLI

```bash
# Mode A — Python in the browser (Pyodide / WASM)
tempestweb dev --mode wasm --path examples/counter

# Mode B — Python on the server (FastAPI + WebSocket)
tempestweb run --mode server --path examples/counter
```

!!! tip "Same command, different mode"
    Switch between `--mode wasm` and `--mode server` to see the same app running on both architectures. The browser URL and UI are identical.

### Server directly with `serve.py`

```bash
python examples/server-mode/serve.py
```

This calls `uvicorn.run` programmatically — no subprocess, no `os.system`. The server starts at `http://127.0.0.1:8000`.

### Via uvicorn directly

```bash
uvicorn "examples.server_mode.serve:app" --host 127.0.0.1 --port 8000
```

!!! note "Why `127.0.0.1` and not `0.0.0.0`?"
    Internal services use `127.0.0.1` by default. Change to `0.0.0.0` only when a client from a different origin (e.g. a frontend dev server) needs to reach this host.

---

## Step 7 — Testing with `TestClient`

Starlette's `fastapi.testclient.TestClient` allows testing the WebSocket server **in-process**, without opening any network ports. Tests are deterministic and run in the same `pytest` loop.

```python
"""Mode B end-to-end — the counter example served over WebSocket.

This test suite proves that the *exact same* ``make_state``/``view`` from
``examples/counter/app.py`` works unchanged when mounted on a FastAPI server
(Mode B).  It mirrors :mod:`tests.unit.test_server_ws` but uses the real
counter module instead of a local re-definition, demonstrating the "one view,
both modes" property of tempestweb.

The Starlette :class:`~fastapi.testclient.TestClient` drives the WebSocket
transport in-process, so no network port is opened and the suite is fully
deterministic.

Tests
-----
- :func:`test_initial_mount_receives_counter_zero` — the very first envelope
  after connecting contains the initial label ``"Count: 0"``.
- :func:`test_click_increments_counter` — sending a ``click`` event on key
  ``"inc"`` yields an Update patch that sets the label to ``"Count: 1"``.
- :func:`test_multiple_clicks_accumulate` — two successive clicks bring the
  label to ``"Count: 2"`` (stateful accumulation, not reset).
- :func:`test_decrement_via_dec_button` — clicking ``"dec"`` after three
  increments rolls the counter back to ``"Count: 2"``.
- :func:`test_two_connections_independent_state` — two simultaneous WebSocket
  connections own their own state; clicks on one do not leak to the other.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from examples.counter.app import make_state, view
from tempestweb.server import create_app

# ---------------------------------------------------------------------------
# Helpers (no dependencies — pure dict traversal)
# ---------------------------------------------------------------------------


def _find_label_content(node: dict[str, Any]) -> str | None:
    """Recursively find the ``label`` node's ``content`` prop in a wire tree.

    Args:
        node: A wire-format IR node (``{type, key, props, children}``).

    Returns:
        The ``content`` string if found, otherwise ``None``.
    """
    if node.get("key") == "label":
        content: Any = node["props"].get("content")
        return str(content) if content is not None else None
    for child in node.get("children", []):
        found = _find_label_content(child)
        if found is not None:
            return found
    return None


def _label_update(patches: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the Update patch whose ``set_props`` contains ``content``.

    The reconciler may emit additional patches (e.g. re-serialised handler
    props) alongside the label update.  This isolates the one we care about.

    Args:
        patches: The ``data`` list from a ``patches`` envelope.

    Returns:
        The first Update patch that carries a ``content`` key in ``set_props``.

    Raises:
        AssertionError: If no such patch is present.
    """
    for patch in patches:
        if "content" in patch.get("set_props", {}):
            return patch
    raise AssertionError(f"no label content update in {patches}")


# ---------------------------------------------------------------------------
# Fixtures / app instance
# ---------------------------------------------------------------------------
# Each test creates its own TestClient so sessions do not bleed across tests.


def _client() -> TestClient:
    """Build a fresh TestClient wrapping a Mode B counter app.

    Returns:
        A configured :class:`~fastapi.testclient.TestClient`.
    """
    return TestClient(create_app(make_state, view, title="test-counter"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_mount_receives_counter_zero() -> None:
    """Connecting receives one ``patches`` envelope with the initial counter label."""
    with _client().websocket_connect("/ws") as ws:
        initial = ws.receive_json()

    assert initial["kind"] == "patches", f"unexpected kind: {initial['kind']}"
    root = initial["data"][0]
    assert root["path"] == [], "initial patch must target the root (empty path)"
    assert _find_label_content(root["node"]) == "Count: 0"


def test_click_increments_counter() -> None:
    """A single ``click`` on ``"inc"`` drives the counter from 0 → 1."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})

        update = ws.receive_json()

    assert update["kind"] == "patches"
    patch = _label_update(update["data"])
    assert patch["set_props"] == {"content": "Count: 1"}
    # The path is non-empty because it is an Update, not a full Replace.
    assert patch["path"] != []


def test_multiple_clicks_accumulate() -> None:
    """Two successive increments accumulate: 0 → 1 → 2."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        first = ws.receive_json()

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        second = ws.receive_json()

    assert _label_update(first["data"])["set_props"] == {"content": "Count: 1"}
    assert _label_update(second["data"])["set_props"] == {"content": "Count: 2"}


def test_decrement_via_dec_button() -> None:
    """Clicking ``"dec"`` after three increments rolls the counter back to 2."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        for _ in range(3):
            ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
            ws.receive_json()  # consume each update

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "dec"}})
        update = ws.receive_json()

    assert _label_update(update["data"])["set_props"] == {"content": "Count: 2"}


def test_two_connections_independent_state() -> None:
    """Two simultaneous WebSocket connections own fully isolated state.

    Connection A is clicked twice; connection B is never clicked and then
    clicked once.  B must yield ``Count: 1``, not ``Count: 3``.
    """
    client = _client()
    with (
        client.websocket_connect("/ws") as ws_a,
        client.websocket_connect("/ws") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        # Drive A up to 2.
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_a1 = ws_a.receive_json()
        update_a2 = ws_a.receive_json()
        assert _label_update(update_a1["data"])["set_props"] == {"content": "Count: 1"}
        assert _label_update(update_a2["data"])["set_props"] == {"content": "Count: 2"}

        # B was never touched: its first click must yield Count: 1, not Count: 3.
        ws_b.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_b = ws_b.receive_json()
        assert _label_update(update_b["data"])["set_props"] == {"content": "Count: 1"}
```

### Explaining each test

#### `test_initial_mount_receives_counter_zero`

```python
with _client().websocket_connect("/ws") as ws:
    initial = ws.receive_json()

assert initial["kind"] == "patches"
root = initial["data"][0]
assert root["path"] == []                           # root patch (Replace)
assert _find_label_content(root["node"]) == "Count: 0"
```

On connect, the server immediately sends a `patches` envelope containing a `Replace` patch at the root path (`path == []`). This patch carries the entire widget tree. We inspect it recursively until we find the node with `key="label"` and verify that `content` is `"Count: 0"`.

#### `test_click_increments_counter`

```python
ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
update = ws.receive_json()

patch = _label_update(update["data"])
assert patch["set_props"] == {"content": "Count: 1"}
assert patch["path"] != []   # Update, not Replace — path is not empty
```

The client sends a click event. The server resolves the `increment` handler, calls `set_state`, the reconciler computes the diff, and emits an `Update` patch with only `{"content": "Count: 1"}` in `set_props` — only what changed.

!!! tip "Update vs. Replace"
    A `Replace` (path `[]`) remounts the entire tree. An `Update` (non-empty path) only touches the props that changed on that specific node. The reconciler always picks the minimum — which is why clicking `+` produces only an `Update` on the text node, not a full `Replace`.

#### `test_multiple_clicks_accumulate`

Two successive clicks on the same connection produce `"Count: 1"` and `"Count: 2"`. This confirms state **accumulates** — each `AppSession` preserves state between events.

#### `test_decrement_via_dec_button`

Three increments followed by one decrement must produce `"Count: 2"`. This verifies both the `dec` button and the correctness of accumulated state.

#### `test_two_connections_independent_state`

```python
client = _client()
with (
    client.websocket_connect("/ws") as ws_a,
    client.websocket_connect("/ws") as ws_b,
):
    ...
    # B was never clicked; its first click must yield Count: 1, not Count: 3
    assert _label_update(update_b["data"])["set_props"] == {"content": "Count: 1"}
```

This is the most important test: two simultaneous clients on the **same** server have completely isolated state. Clicking on `ws_a` does not affect `ws_b`.

---

## Automated verification ✅

Run the full check suite:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests (includes the 5 tests from this tutorial)
pytest -q
```

!!! check "Expected result"
    ```
    tests/unit/test_example_server_mode.py .....   5 passed
    ```
    All 5 tests green — initial mount, single click, accumulation, decrement, and cross-connection isolation.

---

## How it works under the hood

### The full Mode B cycle

```
Browser                       Python Server
   │                               │
   │──── WS connect ──────────────▶│
   │                               │  AppSession created
   │                               │  state_factory() → CounterState(value=0)
   │                               │  view(app) → Widget tree
   │                               │  reconciler → initial patch
   │◀─── {"kind":"patches"} ───────│
   │                               │
   │  user clicks "+"              │
   │──── {"kind":"event",          │
   │      "data":{"type":"click",  │
   │              "key":"inc"}} ──▶│
   │                               │  resolve_handler("inc", "click")
   │                               │  → increment()
   │                               │  app.set_state(...)
   │                               │  view(app) → new tree
   │                               │  diff → Update patch
   │◀─── {"kind":"patches"} ───────│
   │  DOM updated                  │
```

### `AppSession` — the per-connection session

`AppSession` is the heart of Mode B. It:

1. Builds an isolated `App` with `state_factory()` and `view`
2. Sends the initial patches via `transport.send_patches`
3. Loops: receive event → `dispatch` → resolve handler → `set_state` → patches back
4. On disconnect, cancels all pending send tasks (structured concurrency)

### `WebSocketTransport` — the channel

`WebSocketTransport` is a concrete `PatchTransport`. It runs an internal **demux** (asyncio task) that reads envelopes from the socket and routes them:

- `kind == "event"` → internal queue (drained by `recv_event`)
- `kind == "native_result"` → registered handler (for native API proxying)

This keeps the session loop clean: it only sees user events, never protocol envelopes.

---

## Recap

In this tutorial you learned:

- ✅ The difference between Mode A (WASM) and Mode B (server) — and that `view` is identical in both
- ✅ How to use `create_app(make_state, view)` to wrap any app in a FastAPI server
- ✅ That `state_factory` is called **per connection**, guaranteeing full isolation between clients
- ✅ The wire envelope format (`kind: patches / event`) that travels over WebSocket
- ✅ How to test the server with `TestClient` without opening network ports
- ✅ Why `_json_safe` must handle `pydantic.BaseModel` before serializing to JSON
- ✅ The difference between a `Replace` patch (initial mount, path `[]`) and an `Update` (diff, non-empty path)

---

## Next steps

- 💡 Explore the [SSE transport](../tutorial/modes.md) — the WebSocket alternative for environments with HTTP proxies
- 💡 Add [WebPush](../pwa.md) for push notifications in Mode B
- 💡 Read `docs/contract.md` for the complete format of all 5 patch types
- 💡 See `tests/unit/test_server_ws.py` for lower-level tests of the WebSocket transport in isolation
