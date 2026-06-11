# SUMMARY — Track T4 (`feat/native-web`): Trilho N capability adapters

## What was built

Trilho N complete: every native Web capability is a **typed Python awaitable**
with **two backends behind one seam** — Mode A (in-process Pyodide FFI) and Mode B
(proxied `native_call`/`native_result` round-trip per `docs/contract.md`). The
identical application code runs in both modes; only the installed `NativeBridge`
differs.

### Python — `tempestweb/native/`

- **`dispatch.py`** — the seam. `NativeBridge` protocol (single async `call`),
  `native_call` envelope builder, `send_native_call` (fresh `call_id`, unwraps
  `value`/raises `NativeError`), `resolve_native_result`, `install/uninstall/
  current_bridge`. Realigned to the contract's `native_call`/`native_result` /
  `call_id` / dotted-`capability` wire shape.
- **`bridges.py`** — `FFIBridge` (Mode A, awaits a JS promise in-process) and
  `ProxyBridge` (Mode B, `call_id -> Future` registry, injected `send_frame`,
  `resolve()` + `close()`).
- **N0 `http.py`** — `request` (conservative retry + capped exponential backoff;
  retries only idempotent methods or any method with an `idempotency_key`, sent as
  `Idempotency-Key` on every attempt), `generate_idempotency_key`, `upload`
  (progress callback), `poll` (predicate + interval). Policy is pure Python; the
  one round-trip is the `http.request` capability. Base of the T9/P2 offline
  replay.
- **N1 `audio.py`** — `play` (per-channel, autoplay-blocked -> graceful
  `PlayResult`, not an error) / `stop`.
- **N2 `share.py`** — `share` + `is_share_supported`; `unsupported`/`cancelled`
  are normal `ShareOutcome`s, never raised.
- **N3 `geolocation.py` / `clipboard.py` / `storage.py`** — `geolocation.get` ->
  `Position`; `clipboard.read`/`write`; `storage.put/get/list_keys/remove`
  (layered over the owner-scoped IndexedDB store, `localStorage` fallback).
  tempestroid-style aliases (`get_text`, `read_file`, ...) kept.
- **N4 `camera.py`** — `capture` -> typed `Photo` (base64 + `to_bytes()`).
- **`notifications.py`** — `notify` / `request_permission` (typed
  `NotificationPermission`).
- **`__init__.py`** — exports both capability namespaces
  (`native.http.request`, `native.audio.play`, ...) and flat symbols, with a
  current `__all__`.

### Client — `client/native/` (pure JS, no build, JSDoc)

- **`index.js`** — capability router: `HANDLERS` map, `dispatch(envelope, deps)`
  (never throws — failures become `{ok:false,error}`), `CapabilityError`,
  `installNativeBridge` (exposes `window.__tempestweb_native__` for Mode A). Web
  APIs reached through an injectable `deps` object -> fully testable under jsdom.
- One module per capability: `http.js`, `audio.js`, `share.js`, `geolocation.js`,
  `clipboard.js`, `storage.js`, `camera.js`, `notifications.js`.

### Tests

- `tests/unit/test_native_dispatch.py` — seam + both bridges (9 cases).
- `tests/unit/test_native_http.py` — retry, network-error retry, POST-no-retry,
  idempotency-key reuse, upload progress, poll satisfied/exhausted (13 cases).
- `tests/unit/test_native_capabilities.py` — every capability's envelope/args/
  typed return (13 cases).
- `tests/client/native.test.js` — router + each JS handler under jsdom/mocks
  (23 cases).

## Test status

    .venv/bin/pytest tests/unit/test_native*.py -q   ->  35 passed
    node --test tests/client/native.test.js          ->  23 passed
    ruff check tempestweb + ruff format --check       ->  clean
    mypy tempestweb (--strict)                         ->  Success, no issues

## What is stubbed / cross-track

- `storage` IndexedDB backend is **T9/P2** (`client/offline/store.js`); the glue
  injects it via `deps.store`, with a tested `localStorage` fallback meanwhile.
- `ProxyBridge` transport wiring (`send_frame` + inbound `native_result` ->
  `resolve`) is wired by **T2** server/transport; integration is a per-session
  `install_bridge(ProxyBridge(...))` + result routing.
- `FFIBridge` Pyodide `dispatch` is wired by the **T3** Mode A runtime; tested here
  with a fake callable.

## Needs manual verification (no real browser here)

See `NOTES-T4.md` section "Manual verification required": live upload progress,
audio autoplay gating, Web Share sheet, geolocation/clipboard permission prompts,
camera `getUserMedia`, and a Mode B end-to-end `native_call` over a live WS once
T2 wires the bridge.

## Suggested merge order

Per `docs/agents/MANIFEST.md`: T1 -> T2/T3 -> **T4** -> T9 -> others. T4 depends on
nothing at runtime (it programs against the contract and stubs the bridge), so it
can merge right after T2/T3 land. On merge:
1. T2 session: `install_bridge(ProxyBridge(transport.send))`; route `native_result`
   frames to `bridge.resolve`.
2. T3 bootstrap: `installNativeBridge(window, deps)` and install `FFIBridge` with
   the Pyodide-proxied `window.__tempestweb_native__`.
3. T9: inject the owner-scoped IndexedDB store as `deps.store`.
