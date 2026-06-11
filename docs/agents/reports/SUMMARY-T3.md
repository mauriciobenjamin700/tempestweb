# SUMMARY — Track T3 (Mode A / WASM, Pyodide)

Branch: `feat/mode-wasm`. Scope: Mode A — Python in the browser on Pyodide.
Phases A0 (de-risk), A1 (WASM transport + runtime), A3 (static bootstrap).

## What I built

### Python (mypy `--strict` clean, ruff clean, pytest-covered headless)

- **`tempestweb/transports/wasm.py`** — `WasmTransport`, an in-process
  `PatchTransport` (Protocol from `transports/base.py`). Patches out via a
  `deliver` callable; events in via `push_event` buffered on an `asyncio.Queue`
  that `recv_event` drains; `close()` unblocks a pending `recv_event` and is
  idempotent. **No Pyodide import** — the FFI is a seam owned by the bootstrap.
- **`tempestweb/runtime/wasm.py`** — `WasmRuntime[S]` drives the vendored
  `App`'s coalesced rebuild loop over a transport.
  - `serialize_node` / `serialize_patches` lower the IR to the JSON-able wire
    shape: handler callables are **nulled** (matches `docs/contract.md` and the
    `on_click: null` fixtures), `Style`/`Color`/`Edge` lower via pydantic. The
    tricky bit: `model_dump` recurses into children/embedded-`node`/`set_props`,
    so those are **stripped/sanitized before dumping**, never after.
  - Event routing: resolve `(event.key, "on_" + event.type)` against a handler
    registry refreshed after every build (so a removed node can't fire);
    arity-checked call (bare vs payload arg); async handlers awaited. Unknown
    key/type is ignored (no-op), never an error.
- **`tempestweb/runtime/wasm_main.py`** — `bootstrap()` + `WasmAppHandle`, the
  Python the browser runs. Patches/events cross the FFI as **JSON strings**
  (no Pyodide proxy dicts leak into JS); starts the runtime event loop as a
  background task. Pyodide-free import, so it stays type-checked off-browser.
- `__init__.py` exports updated for both packages.

### Client (JS, jsdom `node --test`, no framework/build)

- **`client/transport-wasm.js`** — `createWasmTransport(bridge)`, the Mode A
  `Transport`. Buffers patch batches arriving before `onPatches()` registers
  (mount race); `sendEvent`->`bridge.pushEvent`; `close()` idempotent.
  Bridge-agnostic → tested with a fake bridge (no Pyodide).

### Bootstrap (live browser — A3)

- **`public/index.html`** — buildless bootstrap: Pyodide `pyodide.mjs` pinned
  `v314.0.0`, `loadPackage(["pydantic"])` from Pyodide's emscripten index (NOT
  PyPI — see NOTES A0), writes the package into the Pyodide FS from
  `public/manifest.json`, imports the app, calls `bootstrap`, wires the
  JSON-string bridge to `createWasmTransport` + `tempestweb.js` `mount`. Console
  fallback when T1's renderer isn't merged.
- **`public/gen_manifest.py`** + **`public/manifest.json`** — the FS file list;
  regenerate when the package file set changes.

## Tests (all green)

- `pytest tests/unit/test_wasm*.py` → **25 passed** (transport 8, runtime 14,
  entrypoint 3). Full suite `pytest -q` → **29 passed**.
- `node --test tests/client/**/*.test.js` → **7 passed** (transport-wasm 6 +
  smoke 1).
- The exact bootstrap Python flow was also run standalone against the real
  `examples/counter/app.py`: namespace-import → `bootstrap` → click → `Count: 1`.

## What is stubbed / depends on others

- **DOM renderer (`client/dom.js`, `client/tempestweb.js`, `client/events.js`)**
  is **Track T1** and currently a stub. The bootstrap imports `tempestweb.js`;
  until T1 lands it console-logs the wire traffic (initial node + patches),
  which still proves A0/A1 at the wire level. The visible counter needs T1.
- `serialize_node` serializes the scene **root**; overlay patches (path prefix
  `"overlay"`) serialize correctly but overlay rendering is a T1 concern.

## Must be verified by hand (browser-only, cannot run in CI here)

Live Pyodide in a real browser — full steps in **NOTES-T3.md** ("Manual
verification"). Short version: `python -m http.server 8000`, open
`/public/index.html`, confirm the console logs the initial node + patch batches
produced in WASM and (with T1) the counter updates with zero network on click.

## Suggested merge order

**T1 (DOM renderer) → T3 (this) → T2 (server).** T3's bootstrap reaches a visible
counter only once T1's `client/tempestweb.js` is merged; the Python/JS transport
contract is independent and already green.

## Verification command (the gate)

    pytest tests/unit/test_wasm*.py -q      # 25 passed
    ruff check tempestweb && ruff format --check tempestweb
    mypy tempestweb                          # clean
    node --test "tests/client/**/*.test.js"  # 7 passed
