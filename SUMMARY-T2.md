# SUMMARY — Track T2 (Mode B: server)

Branch: `feat/mode-server`. Scope delivered: phases **B0–B2** + **B5 (SSE)**.

## What was built

### Python — `tempestweb/transports/`

- **`base.py`** — the single A/B seam. `PatchTransport` Protocol now covers the
  full duplex + native-proxy surface: `send_patches`, `send_native_call`,
  `recv_event` (user events only), `on_native_result` (sink for replies),
  `close`. Added envelope encoders `encode_patches` / `encode_event` /
  `encode_native_call` / `encode_native_result` and the `Envelope` /
  `EnvelopeKind` / `NativeCall` / `NativeResult` aliases. Importable without
  starlette (the shared seam stays dependency-light); only the WS/SSE impls
  pull FastAPI.
- **`websocket.py`** — `WebSocketTransport` over a Starlette WebSocket. A single
  inbound demux task reads each JSON envelope and routes `event` to an asyncio
  queue (drained by `recv_event`) vs `native_result` to the registered handler.
  Send maps disconnects to `TransportClosedError`; `close()` cancels the pump.
- **`sse.py`** — `SSETransport` (B5). Outbound `patches`/`native_call` envelopes
  get a monotonic id, are buffered (bounded ring) for replay, and stream out of
  `stream(last_event_id=...)` as SSE `id:`/`data:` blocks; a named `ping`
  heartbeat fires whenever the queue idles past `ping_interval`. Inbound
  `event`/`native_result` envelopes are pushed in via `feed_inbound` (called by
  the POST endpoint). `Last-Event-ID` reconnect replays only missed ticks.

### Python — `tempestweb/runtime/session.py`

- `AppSession` (present from the prior run) now wires the native-call proxy:
  `native_call(capability, args)` is an awaitable keyed by `call_id`, resolved
  by `on_native_result`; `close()` fails any in-flight calls. Tightened patch
  typing (`CorePatch` vs wire `Patch`).

### Python — `tempestweb/runtime/serialize.py` (bug fix)

- Critical fix: `patch_to_wire` previously did a blanket
  `patch.model_dump(mode="json")`, which raised `PydanticSerializationError`
  because the IR carries live handler callables in `Update.set_props` and in
  `Insert`/`Replace` nodes. The exception was swallowed inside the spawned send
  task, so no patch ever reached the client and the WS loop hung. Now each patch
  kind is built explicitly, stripping handlers to `null` via `node_to_wire` /
  `_json_safe` per the contract. Wire shapes verified against the goldens.

### Python — `tempestweb/server/`

- **`app.py`** — `TempestWebServer` + `create_app(state_factory, view)`. Routes:
  `GET /ws` (WebSocket), `GET /sse?session=<id>` (StreamingResponse from the
  transport stream), `POST /sse/{session_id}` (feeds inbound envelopes; 404 for
  unknown session). A per-id registry keeps SSE sessions for POST routing and
  reconnect. Each connection gets its own `AppSession` from `state_factory`, so
  state is fully isolated.

### Client — `client/` (pure JS, no TS, no build)

- **`transport-ws.js`** — `createWebSocketTransport(url, {onNativeCall, WebSocketImpl})`.
  Implements the `Transport` interface (`onPatches`/`sendEvent`/`close`), buffers
  patch batches delivered before `onPatches` attaches, answers `native_call`
  with `native_result`.
- **`transport-sse.js`** — `createSSETransport({session, onNativeCall, ...})`.
  EventSource patch stream + HTTP POST upstream; ignores `ping`; reconnection
  rides the browser's `Last-Event-ID`. `EventSourceImpl`/`fetchImpl` injectable.

## Tests (all green)

- **`tests/unit/test_server_ws.py`** (3) — connect -> initial patches -> click ->
  Update patch; two connections keep independent state; unknown key ignored.
- **`tests/unit/test_server_sse.py`** (4) — same patch stream over SSE +
  `feed_inbound`; `id:` framing + `ping` heartbeat; `Last-Event-ID` replay; two
  independent sessions; POST to unknown session -> 404.
- **`tests/unit/test_server_native.py`** (2) — native_call round-trip (success
  value + typed `NativeCallError`).
- **`tests/client/transport-ws.test.js`** (5) + **`transport-sse.test.js`** (4) —
  jsdom + injected fakes; patch delivery, late-attach buffering, event framing,
  native_call success/failure, ping ignore.

Verification gate `pytest tests/unit/test_server*.py -q` -> 9 passed.
Full suite: 13 pytest passed, 10 JS tests passed. `ruff` + `ruff format --check`
+ `mypy --strict` all clean.

## What is stubbed / not done in this track

- Client orchestrator (`client/tempestweb.js` `mount()`) and the DOM renderer
  (`client/dom.js`, `client/events.js`) are W1's track — still stubbed here. The
  transports satisfy the `Transport` interface those will consume, but no live
  DOM apply path exists in this branch.
- Mode A (`transport-wasm.js`) untouched — out of scope.
- DOM patch application is exercised only through the wire shapes (fixtures),
  not by mutating a real document, since the renderer is W1's.

## Needs manual verification (no automated browser here)

- A real browser end-to-end: serve `create_app(...)` with uvicorn, point a page
  at `/ws` (or `/sse`) and confirm the counter mounts and increments. The Python
  side is fully covered by the Starlette TestClient WS path and the SSE
  transport/stream tests; the browser leg (real `WebSocket`/`EventSource`,
  `Last-Event-ID` auto-reconnect) is only fakable in jsdom and should be
  eyeballed once W1's renderer + `mount()` land.
- `ping` heartbeat keep-alive across a proxy/load balancer (interval tuning).

## Suggested merge order

1. W1 (DOM renderer + `mount()`) — unblocks the real browser path that consumes
   these transports.
2. T2 (this branch) — server + transports; merges cleanly on top, no overlap
   with W1 files (only `client/transport-ws.js` / `transport-sse.js`, which W1
   leaves stubbed).
3. Mode A / WASM track afterwards.

No new env vars, no scripts, no migrations. New runtime deps already declared
under the `server` extra (`fastapi`, `uvicorn[standard]`, `websockets`) and the
`dev` extra (`httpx` for the test client).
