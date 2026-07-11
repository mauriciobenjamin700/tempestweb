# Native capabilities

**Capabilities** (`native/`) are Web API adapters exposed as **typed Python
awaitables**. You write `await geolocation.get()` and receive a typed `Position`
— without touching JavaScript. 📡

!!! info "Track N — the native surface"
    This layer is the roadmap's **Track N** (phases N0–N4, detailed in the
    [design plan](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md)).
    The capabilities work across the **three** execution modes — each resolves its
    backend based on the `--mode`.

## One Python API, three paths

The central principle: **the Python API is always the same**; the `--mode` chooses
how the call reaches the Web API, not your code.

=== "Mode A — direct"

    The call goes **directly to the Web API** via `pyodide.ffi`, inside the
    browser. No network.

    ```python
    pos = await geolocation.get()   # calls navigator.geolocation in the browser
    ```

=== "Mode B — proxy"

    The call is **proxied via a round-trip**: the server emits a native request
    over the transport (WS/SSE), the client runs the Web API and returns the typed
    result.

    ```python
    pos = await geolocation.get()   # SAME line; triggers native_call/native_result
    ```

=== "Mode C — transcribed"

    The `async` call is **transcribed to JS** and runs in-process against the same
    browser glue — no Python, no network.

    ```python
    pos = await geolocation.get()   # SAME line; becomes a native JS call
    ```

!!! check "The contract is the same"
    In Modes A and B the `native_call`/`native_result` envelope is in the
    [wire contract](wire-contract.md#the-native-call-mode-b-proxy). In Mode C there
    is no envelope — the call is transcribed — but the **typed signature is
    identical**. You write one line; the mode decides the mechanism.

## The capabilities

| Capability | Python API | Mirrors (React SDK) |
|---|---|---|
| `http` (N0) | `await http.request(...)`, `upload`, `poll`, `idempotency_key` | `createApiClient`/`retry` |
| `audio` (N1) | `await audio.play(src, volume=...)`, `audio.stop()` | `playAudio`/`useAudio` |
| `share` (N2) | `await share(title=..., url=...)` → `ShareResult` | `share`/`isShareSupported` |
| `geolocation` (N3) | `await geolocation.get()` → `Position` | — |
| `clipboard` (N3) | `await clipboard.read()` / `clipboard.write(text)` | — |
| `storage` (N3) | `put`/`get`/`list` (over IndexedDB) | `createOfflineStore` |
| `camera` (N4) | `await camera.capture()` → bytes/`Blob` | — |

## Example: typed HTTP with retry

`native.http` (N0) is the foundation of offline replay. A request with retry and
an idempotency key:

```python
from tempestweb.native import http
from tempestweb.native.http import RetryOptions


async def submit_order(payload: dict[str, object]) -> dict[str, object]:
    """Submit an order with retry and an idempotency key.

    Args:
        payload: The order body to POST.

    Returns:
        The decoded JSON response.
    """
    key = http.generate_idempotency_key()
    response = await http.request(
        "POST",
        "/api/orders",
        json=payload,
        retry=RetryOptions(attempts=3, backoff=0.5),
        idempotency_key=key,
    )
    return response.json()
```

!!! tip "Idempotency key avoids duplicating effects"
    If retry re-delivers the same request, the `idempotency_key` guarantees the
    server applies the effect **only once**. That is the piece that makes the
    [Track P](pwa.md) offline queue safe.

## Example: geolocation

```python
from tempestweb.native import geolocation


async def center_map(app: object) -> None:
    """Read the device position and update the app state.

    Args:
        app: The running app handle.
    """
    pos = await geolocation.get()   # Position(lat=..., lon=...)
    app.set_state(lambda s: setattr(s, "center", (pos.lat, pos.lon)))
```

!!! warning "Permission is a normal path, not a fatal exception"
    Geolocation, clipboard and camera require **permission** and a **secure
    context** (HTTPS). Treat denial as a normal flow — a typed exception your UI
    presents gracefully, not a crash.

## Camera in Mode B (always on the client)

Camera capture **always happens on the client**, even in Mode B. When you call
`await camera.capture()` "on the server", the round-trip triggers the capture in
the browser and the photo comes back typed (base64 or a blob reference).

```python
from tempestweb.native import camera


async def take_photo() -> bytes:
    """Capture a photo from the device camera.

    Returns:
        The captured image bytes.
    """
    blob = await camera.capture()   # captured on the client; typed in Mode B
    return blob.data
```

!!! note "Compress before uploading"
    In Mode B the photo crosses the network on the round-trip. Compress it on the
    client before returning to keep the payload small.

## ONNX inference in the browser (`native.onnx`)

`onnxruntime` (the CPython C-extension) **has no Pyodide wheel** — Python in the
browser can't run an ONNX graph in-process. The `onnx` capability bridges the gap:
the graph runs in JavaScript via **onnxruntime-web** (the WASM build), driven over
the same `native_call` seam. You do the pre/post-processing in Python (numpy +
pillow, both available in Pyodide) and ship only the raw tensor execution across.

```python
from tempestweb.native import onnx
from tempestweb.native.onnx import Tensor


async def detect(input_b64: str) -> dict[str, Tensor]:
    """Run a YOLO ONNX model loaded same-origin from the artifact."""
    model = await onnx.load("./models/detect.onnx")       # compiles the session (cached in JS)
    feeds = {model.input_name: Tensor(data_base64=input_b64, dims=[1, 3, 640, 640])}
    return await onnx.run(model.session_id, feeds)         # → {name: Tensor}
```

Load `onnxruntime-web` via `[wasm].scripts` and vendor it (and the `.onnx` files)
via `[wasm].assets`, so the service worker precaches everything and inference runs
**offline**. The `wasm` provider is forced (the web build lacks some kernels under
WebGPU). Tensors cross as base64 bytes + shape + dtype — the capability is
numpy-free; the Python side (which has numpy) serializes.

## Save a generated file (`native.file`)

The browser has no synchronous file write. `file.save` delivers a blob built in
Python via `navigator.share({files})` (when the platform accepts it) or an
`<a download>` click (desktop), reporting which path ran.

```python
from tempestweb.native import file


async def export_zip(zip_bytes: bytes) -> None:
    """Share or download a generated ZIP."""
    await file.save("history.zip", zip_bytes, mime_type="application/zip")
```

## PWA install (`native.install`)

Expose the PWA install flow to Python: whether the app is installable (a
`beforeinstallprompt` was captured) or already installed, and fire the prompt
after a real user gesture.

```python
from tempestweb.native import install


async def on_install_tap() -> None:
    """Fire the native install prompt from a button handler."""
    outcome = await install.prompt()   # "accepted" | "dismissed" | "unavailable"


async def maybe_show_install_button() -> bool:
    """Whether to show an Install button."""
    state = await install.state()      # InstallState(can_install, installed)
    return state.can_install and not state.installed
```

`client/native/install.js` wraps the soft controller from
`client/pwa/install-prompt.js` (suppresses the mini-infobar and stashes the event).

## Mode A build extras (`[wasm]`)

Capabilities that need extra Pyodide packages, your own Python modules, static
assets, or a JS library are declared in `tempestweb.toml`:

```toml
[wasm]
packages = ["numpy", "pillow"]                 # loadPackage beyond the core's pydantic
modules  = ["famacha", "ort_vision_sdk"]        # Python packages bundled next to app.py
assets   = ["models/*.onnx", "vendor/ort/*"]    # copied (path preserved) + precached
scripts  = ["./vendor/ort/ort.wasm.min.js"]     # <script> injected before the bootstrap
```

!!! tip "Where each `module` comes from"
    Each name in `modules` is resolved in two steps, in order:

    1. A **vendored copy** next to `app.py` (`<project>/<module>/`), if present —
       the historical behavior, where a copy committed to the repo wins.
    2. An **installed package** in the environment (`importlib`) — when no vendored
       copy exists, the module is pulled straight from your `.venv`'s
       `site-packages`.

    So a dependency you install (`uv add ...`) **need not be cloned and dropped at
    the repo root** to make it into the bundle — just list it in `modules`. A name
    that is neither a vendored copy nor importable fails the build with a clear
    message.

!!! tip "You don't even have to list them: `tempestweb sync`"
    To avoid keeping `modules` up to date by hand, run:

    ```bash
    tempestweb sync            # fills [wasm].modules; --dry-run only previews
    ```

    It reads `[project.dependencies]` from your `pyproject.toml`, keeps the ones
    that are **installed and pure-Python**, and writes their import names into
    `[wasm].modules` — preserving whatever was already there (your app package,
    vendored copies). Packages with native code (numpy, pillow) are **skipped** —
    Pyodide provides them via `[wasm].packages` — as is the framework itself
    (`tempestweb`, `pydantic`). It is idempotent: a second run with no environment
    change writes nothing. Just have the dependencies in your `.venv` and run it. 🚀

## Recap

- Capabilities are Web APIs exposed as **typed Python awaitables**.
- **One API, three paths:** Mode A calls directly, Mode B proxies via a
  round-trip, Mode C transcribes to JS — the typed signature is the same.
- In Modes A/B the envelope is the `native_call`/`native_result` of the
  [wire contract](wire-contract.md).
- Denied permissions are a **normal flow**, handled as a typed exception.

The `storage` capability connects to the offline layer — see
[PWA & offline](pwa.md). 🚀
