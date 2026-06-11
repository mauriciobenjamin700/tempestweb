# Wire contract

The **wire contract** is the agreement between **Python** (the reconciler, from
the core) and the **JS client** (which mutates the DOM). It is the **same** across
all three transports — `pyodide.ffi` (Mode A), WebSocket and SSE (Mode B). Only
the envelope changes; never the data shape. 🤝

!!! info "This page is the didactic summary"
    The canonical document, pinned by golden fixtures **derived from the real
    core**, lives next to the code:
    [`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    Any agent working on the client or transports programs against it and the
    fixtures. Here we give the overview; the link has every field.

## The four crossings

Typing "leaks" across the wire at four points — analogous to FastAPI's
request/response:

<div class="grid cards" markdown>

-   __1. IR → client__

    ---

    The serialized `Node` tree and the patch list from the `diff`.

-   __2. Event → handler__

    ---

    The click/input payload that goes up and is validated (Pydantic) before
    entering Python.

-   __3. Style → CSS__

    ---

    The typed `Style` object that the client translates to CSS.

-   __4. Native call__

    ---

    Web APIs exposed as typed awaitables (`native_call`/`native_result`).

</div>

## 1. Node — the serialized IR

Every node in the tree has the same shape:

```json
{
  "type": "Column",
  "key": "label",
  "props": { "style": null },
  "children": []
}
```

- `type` — the widget name (`Column`, `Row`, `Text`, `Button`, `Container`, …).
- `key` — stable reconciliation key (may be `null`).
- `props` — widget props, including `"style"` (a `Style` object or `null`).
- `children` — the list of child `Node`s.

!!! warning "Handlers do not cross as functions"
    The core serializes a **reference**; the event comes back with the widget's
    `key`. The Python side resolves which handler to call — the client never runs
    app logic.

## 2. The 5 patches

The reconciler runs `diff(old, new)` and emits a list. `path` addresses the
target node by indices (`[]` = root, `[0]` = first child).

| Type | Told apart by | Semantics |
|---|---|---|
| **Update** | `set_props` | Apply props and remove `unset_props`. |
| **Insert** | `node` + `index` | Insert a child at the position. |
| **Remove** | only `index` | Remove the child at the position. |
| **Reorder** | `order` | Reorder the children. |
| **Replace** | `node` without `index` | Replace the whole node. |

## 3. Style

`props.style` is a `Style` object (or `null`). `Color` is `{r,g,b,a}` (r/g/b
0–255, a 0–1) → CSS `rgba(...)`. `Edge` is `{top,right,bottom,left}` in px.

```json
{
  "direction": "column",
  "gap": 8.0,
  "padding": { "top": 16, "right": 16, "bottom": 16, "left": 16 },
  "background": { "r": 255, "g": 255, "b": 255, "a": 1.0 },
  "color": { "r": 17, "g": 17, "b": 17, "a": 1.0 },
  "width": 320.0
}
```

!!! note "Style → CSS is almost identity"
    `Style` was designed by copying the CSS vocabulary, so the translation is
    direct and lives in the client (`client/style.js`) — a single translator for
    both modes.

## 4. Event (client → Python)

```json
{ "type": "click", "key": "inc", "payload": {} }
```

The Python side resolves the `key` → the node's handler in the current tree,
validates the `payload` with Pydantic and invokes the handler (sync or `async`).

## Per-transport framing

The Node/Patch/Event shape **does not change** across transports; only the
envelope does:

=== "WASM (Mode A)"

    In-process function call via `pyodide.ffi`. Python passes the patch list
    directly to the client; events come back via callback. No network, no
    envelope.

=== "WebSocket (Mode B)"

    Each WS message is JSON with a `kind`:

    ```json
    { "kind": "patches", "data": [ /* Patch... */ ] }   // server → client
    { "kind": "event",   "data": { /* Event */ } }       // client → server
    ```

=== "SSE (Mode B, B5)"

    The server responds with `text/event-stream`. Each tick is an SSE event whose
    `data:` is the JSON of the **same** patch list. Events go up via HTTP POST
    (body = `Event`). Reconnect uses `Last-Event-ID`.

## The native call (Mode B — proxy)

The **4th crossing**. In Mode A a `native/` capability calls the Web API directly
in the browser. In Mode B it is **proxied** via a round-trip:

```json
// server → client: native capability request
{ "kind": "native_call", "call_id": "c1", "capability": "geolocation.get", "args": {} }

// client → server: typed result (or error)
{ "kind": "native_result", "call_id": "c1", "ok": true,  "value": { "lat": -23.5, "lon": -46.6 } }
{ "kind": "native_result", "call_id": "c1", "ok": false, "error": "PermissionDenied" }
```

- `call_id` correlates request ↔ result (multiple calls can be in flight).
- `capability` is the stable name (`geolocation.get`, `clipboard.read`, …).
- The Python side exposes this as a **typed awaitable** — see
  [Capabilities](capabilities.md).

!!! tip "The Python API is identical in both modes"
    In Mode A the same `await geolocation.get()` resolves in-process; in Mode B it
    triggers the `native_call`/`native_result` round-trip. Only the path changes —
    that is why the typed signature lives in the contract, not the transport.

## Recap

- The contract is the **same** across all three transports; only the envelope
  differs.
- Four crossings: **IR → client**, **Event → handler**, **Style → CSS**, **native
  call**.
- The shapes are pinned by golden fixtures derived from the real core.

For each field, read the canonical
[`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
To see the contract in action, take the [Tutorial](tutorial/index.md). 🚀
