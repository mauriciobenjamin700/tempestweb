# Architecture

tempestweb is tempestroid's **renderer-agnostic** reconciler with a **third leaf
renderer** (DOM) and **two patch transports** (Pyodide FFI and WebSocket/SSE).
This page gives the didactic overview; the canonical document, kept next to the
code, is
[`docs/arquitetura.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/arquitetura.md)
(in PT-BR).

## The central idea

```text
            typed Python (view + state)         ← identical in both modes
                        │
                        ▼
        core: IR (Pydantic) ──diff──► patches    ← reused from tempestroid
                        │
              ┌─────────┴──────────┐
        Mode A: transport     Mode B: transport
        Pyodide FFI           WebSocket / SSE
        (in the browser)      (server → client)
              └─────────┬──────────┘
                        ▼
        JS client (pure): apply patches to the DOM
        + Style → CSS translator + event capture       ← same code in both modes
```

The **reconciler** (Python) and the **JS client** are the same in both modes. The
only thing that changes is the **transport layer**.

## The four layers

| Layer | What it does | Where it lives |
|---|---|---|
| **Core** | IR, diff/patch, state, style, widgets | `tempestweb/_core/` (vendored from tempestroid) |
| **Leaf renderer** | Applies patches to the DOM, translates `Style → CSS`, captures events | `client/` — plain JavaScript |
| **Transport** | Carries patches Python→JS and events JS→Python | `tempestweb/transports/{wasm,websocket}.py` + `client/transport-*.js` |
| **Runtime / host** | Hosts the Python | Pyodide in the browser (A) · FastAPI (B) |

The divergence between the two modes is **locked into the transport layer**.
Everything above (the Python app) and everything below (the JS client that
mutates the DOM) is shared.

!!! info "Why the renderer is the same in both modes"
    Patches are **plain serialized data**. The JS client only knows how to
    consume a patch and mutate the DOM — it does not care where the patch came
    from. In Mode A the patch arrives via an in-process function call
    (`pyodide.ffi`); in Mode B it arrives via a WebSocket message. The patch
    bytes are the same. That is why `client/dom.js` and `client/style.js` are
    written once and serve both.

## The transport seam

The transport interface abstracts the difference between modes. On the client:

```js
// client/transport.js — the shared contract
// onPatches(callback): register who receives patch lists
// sendEvent(event):    send an event (click/input) back to Python
```

And on the Python side:

```python
from typing import Protocol


class PatchTransport(Protocol):
    """Carries patches Python→client and events client→Python."""

    async def send_patches(self, patches: list[dict]) -> None: ...

    async def recv_event(self) -> dict: ...
```

`transports/wasm.py` implements this over `pyodide.ffi`;
`transports/websocket.py` over a WebSocket connection. Switching modes is
swapping the implementation — the user's `view()` does not change.

## Style → CSS: the easy target

In tempestroid, `Style → Compose` is the hard part, because the vocabularies
diverge. On the web there is no divergence: the core's `Style` **was designed by
copying CSS** (flexbox, box model, typography). The `Style → CSS` translator is
nearly the identity and lives in the JS client — **a single translator** for both
modes, so A and B can never disagree on style translation.

## Where typing "leaks" (the contract)

Analogous to FastAPI's request/response, Pydantic validates three crossings at
the Python↔client boundary:

1. **IR → client** — the serialized tree/patches.
2. **Events → handlers** — click/input payloads validated before entering Python.
3. **Native calls** — typed wrappers over Web APIs, exposed as awaitables.

The **schema is the same** in both modes; only the transport medium differs.

??? note "Golden rule of execution (detail)"
    Python runs on an **asyncio event loop**.

    - **Mode A:** Pyodide integrates asyncio into the browser's event loop. There
      is no separate UI thread — heavy Python work **freezes the tab**, so
      handlers should be async/light.
    - **Mode B:** each WebSocket connection has its asyncio session on the server.
      Patches go out over the connection, events come in over it; state lives on
      the server, isolated per client.

## A ↔ B conformance

Because the renderer and the style translator are single, the divergence risk is
not translation, it is **transport**: A and B must not produce different DOM for
the same `view()`. The conformance suite locks this with golden snapshots, in CI
— the web analogue of tempestroid's Qt-vs-Compose.

## Recap

- Four layers: **core**, **leaf renderer**, **transport**, **host**.
- Everything above and below the transport is **shared**; only the transport
  changes between modes.
- The real risk is **transport**, not translation — hence the conformance suite.

To dive into full detail, read
[`docs/arquitetura.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/arquitetura.md)
and the [design plan](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
To see all of this in practice, head to the [Tutorial](tutorial/index.md). 🚀
