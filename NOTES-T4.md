# NOTES — Track T4 (Trilho N: capability adapters)

## The Mode A vs Mode B split (the whole point of the seam)

Every capability in `tempestweb/native/` is **one typed Python awaitable** with
**two backends**. The application code is identical in both modes; only the
installed `NativeBridge` differs. That single seam — `install_bridge(...)` at app
bootstrap — is the entire split.

```
app code:  pos = await native.geolocation.get()
                       │
                       ▼
            send_native_call("geolocation.get", {...})   # tempestweb/native/dispatch.py
                       │
                       ▼
                current_bridge().call(envelope)           # the seam
              ┌────────┴─────────┐
        Mode A│                  │Mode B
   (FFIBridge)│                  │(ProxyBridge)
              ▼                  ▼
  in-process Pyodide FFI   serialize native_call → WS/SSE → client
  window.__tempestweb_     ───────────────────────────────────────►
  native__(envelope)        client/native/index.js runs the Web API
              │             ◄─────────────────────────────────────── native_result
              ▼              ProxyBridge.resolve(call_id, payload)
   client/native/index.js
   runs the Web API in-process
              │
              ▼
        native_result (resolved promise)
```

### Mode A — WASM / Pyodide (in-process)

- Python runs **in the browser** under Pyodide.
- `FFIBridge` (in `bridges.py`) is installed with a JS callable
  (`window.__tempestweb_native__`, set up by `client/native/index.js`'s
  `installNativeBridge`).
- `bridge.call(envelope)` awaits the JS promise **directly** — Python and the Web
  API share the browser's one event loop. **No network, no wire serialization**,
  but the `native_call` / `native_result` *object shape* is still used so the two
  modes are byte-for-byte contract-compatible.

### Mode B — server (proxied round-trip)

- Python runs **on the server**; the browser is a thin client over WebSocket
  (or SSE + POST, T2/B5).
- `ProxyBridge` is installed with a `send_frame` callable wired to the patch
  transport. `bridge.call(envelope)`:
  1. registers a `call_id -> asyncio.Future`,
  2. ships the `native_call` frame down the transport,
  3. suspends on the future.
- The client (`client/native/index.js`) runs the **same** Web API and posts a
  `native_result` frame back up; the transport calls `ProxyBridge.resolve(call_id,
  payload)`, which matches by `call_id` and resolves the future.
- **The Web API always executes in the browser.** Mode B only proxies the call
  there and back over one round-trip.

### Wire format (pinned by `docs/contract.md`)

```json
{ "kind": "native_call",   "call_id": "c1", "capability": "geolocation.get", "args": {} }
{ "kind": "native_result", "call_id": "c1", "ok": true,  "value": { "latitude": -23.5 } }
{ "kind": "native_result", "call_id": "c1", "ok": false, "error": "permission_denied" }
```

Capability names are stable dotted strings. The full registry is
`client/native/index.js::HANDLERS` (and is asserted complete by a JS test):

| Capability | Python | JS handler |
|---|---|---|
| `http.request` / `http.upload` | `native.http.request/upload/poll` | `http.js` |
| `audio.play` / `audio.stop` | `native.audio.play/stop` | `audio.js` |
| `share.is_supported` / `share.share` | `native.share.*` | `share.js` |
| `geolocation.get` | `native.geolocation.get` | `geolocation.js` |
| `clipboard.read` / `clipboard.write` | `native.clipboard.read/write` | `clipboard.js` |
| `storage.put/get/list/remove` | `native.storage.*` | `storage.js` |
| `camera.capture` | `native.camera.capture` | `camera.js` |
| `notifications.notify` / `notifications.request_permission` | `native.notifications.*` | `notifications.js` |

## N0 http — retry / idempotency design

- The **retry / backoff / poll policy is pure Python** (`http.py`), fully tested
  with a fake bridge and an injected `sleep` (no real delays, no browser). The
  single HTTP round-trip is the `http.request` native capability.
- **Conservative retry:** only idempotent methods (`GET/HEAD/PUT/DELETE/OPTIONS`)
  **or** any method carrying an explicit `idempotency_key` are retried. A bare
  `POST` is never retried automatically (matches `docs/plan.md`).
- The `idempotency_key` is sent as the `Idempotency-Key` header **on every
  attempt** (same key), so the server dedupes the effect across retries and
  offline replays. This is the base of the T9/P2 offline replay queue.
- Backoff is capped exponential: `min(base_delay * factor**n, max_delay)`.

## What is stubbed / depends on another track

- **`storage` IndexedDB backend.** `client/native/storage.js` prefers an injected
  owner-scoped store (`deps.store`) with an async `{get,put,remove,keys}`
  interface — that store is **T9/P2** (`client/offline/store.js`). Until it lands,
  the glue falls back to `localStorage` (covered by tests). No change needed here
  on merge; T9 just injects its store into the deps at bootstrap.
- **Transport wiring of `ProxyBridge`.** `ProxyBridge.send_frame` and the inbound
  `native_result` → `resolve()` hop must be wired by the **T2** server session /
  transport (`tempestweb/server`, `transports/`). T2's `transports/base.py`
  already grew `native_call`/`native_result` helpers (per the parallel task list);
  the integration is a one-liner: `install_bridge(ProxyBridge(transport.send))` per
  session, and route inbound `native_result` frames to `bridge.resolve`.
- **`FFIBridge` Pyodide dispatch.** The injected `dispatch` callable is, in a real
  browser, `window.__tempestweb_native__` proxied through `pyodide.ffi`. The
  Mode A runtime (**T3**) wires that at bootstrap. Tested here with a fake async
  callable.

## Manual verification required (no browser in this environment)

The Python policy + JS glue are fully covered by automated tests with mocked Web
APIs. The following need a **real browser/device** and must be checked by hand:

1. **N0 upload progress** — a real multi-MB upload firing `xhr.upload.onprogress`
   ticks (jsdom has no real upload progress). The progress *forwarding* is tested;
   the live tick stream is not.
2. **N1 audio autoplay** — confirm a sound is blocked before the first user gesture
   (`blocked:true`) and plays after a click. CORS/autoplay policy is browser-real.
3. **N2 share** — `navigator.share` opening the OS share sheet on a supported
   mobile browser (requires a user gesture + secure context).
4. **N3 geolocation / clipboard** — real permission prompts and secure-context
   gating.
5. **N4 camera** — `getUserMedia` permission + a real captured frame round-tripping
   in Mode B over WS (watch payload size; compress before upload).
6. **Mode B end-to-end** — once T2 wires `ProxyBridge` into a session, drive one
   `native_call` over a live WS and confirm the `native_result` resolves the
   awaitable.

## Verification commands

```bash
.venv/bin/pytest tests/unit/test_native*.py -q      # 35 passed
node --test tests/client/native.test.js             # 23 passed
.venv/bin/ruff check tempestweb && .venv/bin/mypy tempestweb   # clean
```
