# Changelog

All notable changes to **tempestweb** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project adheres to semantic
versioning.

## [0.3.0] — 2026-06-13

### Added

- **`native.install` capability** — the PWA install flow in Python:
  `install.state()` → `InstallState(can_install, installed)` and
  `install.prompt()` → `"accepted" | "dismissed" | "unavailable"`. Wraps the soft
  controller in `client/pwa/install-prompt.js` (now copied into the wasm
  artifact) via `client/native/install.js`.

## [0.2.0] — 2026-06-13

Real-app capabilities, driven by building a full on-device vision PWA (FAMACHApp)
entirely on tempestweb. Backward compatible — existing apps build unchanged.

### Added

- **`native.onnx` capability** — run ONNX models in the browser via
  **onnxruntime-web**. `onnx.load(model_url) → OnnxModel` and
  `onnx.run(session_id, feeds) → {name: Tensor}`, bridged over the same
  `native_call` seam (`client/native/onnx.js`, wasm execution provider forced).
  numpy-free: tensors cross as base64 + shape + dtype. Unlocks in-browser
  inference even though `onnxruntime` has no Pyodide wheel.
- **`native.file` capability** — `file.save(name, bytes, mime)` shares
  (Web Share API) or downloads a generated blob; `file.pick(accept)` opens a file
  input and returns the chosen file as `PickedFile` (bytes the FilePicker widget's
  uri-only event can't carry). `client/native/file.js`.
- **`[wasm]` project config** (`tempestweb.toml`): `packages` (extra Pyodide
  packages to `loadPackage`, e.g. numpy/pillow), `modules` (project Python
  packages bundled next to `app.py`), `assets` (static files copied verbatim +
  precached, e.g. `.onnx` models), `scripts` (`<script>` tags injected before the
  bootstrap, e.g. onnxruntime-web). Threaded through `tempestweb build`.

### Fixed

- `load_app` now puts the project root on `sys.path`, so a multi-module project's
  `app.py` can import the sibling packages it ships (previously failed the build's
  render check with `ModuleNotFoundError`).

## [0.1.0] — 2026-06-11

First public release. Build web apps in typed Python — one declarative tree, a
pure-JS DOM renderer, two execution modes (WASM in the browser via Pyodide, or a
FastAPI server over WebSocket/SSE).

### Added

- **Two execution modes, one `view()`.** Mode A (WASM/Pyodide) runs Python in the
  browser; Mode B (server) runs it on FastAPI over WebSocket + SSE. The app never
  names a transport.
- **`tempestweb` CLI** — `new` (scaffold), `dev` (watch + reload), `build`
  (`--mode wasm|server`), `run`. The wasm build emits a static bundle (Pyodide +
  the `tempest_core`/`tempestweb` payload + `app.py`); the server build emits a
  FastAPI host.
- **Pure-JS client** (no TypeScript, no framework, no build step): DOM patcher,
  `Style`→CSS, delegated events, the three transports (wasm/ws/sse).
- **Trilho E parity** (live in Mode A): URL routing (deep links + back/forward +
  pushState), virtualized lists with a proportional scrollbar, overlays
  (dialogs/sheets), CSS transitions, pointer gestures (tap/swipe/long-press),
  real form controls (Input/Checkbox/Image), and a11y (semantics→ARIA) / i18n /
  theme.
- **Native capabilities** wired in both modes (geolocation, clipboard, http,
  share, camera, audio, storage, notifications) — in-process FFI in Mode A,
  proxied over the transport in Mode B.
- **PWA layer**: installable manifest + icons + a service worker with an injected
  app-shell precache (offline second load).
- **Observability**: telemetry, logger, error boundary, feature flags, auth —
  adapter pattern.
- **`tempestweb.components`**: ready-to-use validated fields (EmailField,
  PasswordField, PhoneField, CPFField, CNPJField, AddressField, TextField) and
  forms (LoginForm, SignupForm).
- **Bilingual docs** (PT-BR + EN) built with MkDocs Material.

### Depends on

- [`tempest-core`](https://pypi.org/project/tempest-core/) `>=0.1.0` — the
  renderer-agnostic UI engine (IR/reconciler/state/style/widgets).

### Known follow-ups

- Mode B `view→URL` (pushState) needs a server→client nav envelope (Mode A is
  bidirectional today).
- WebPush tab-closed delivery and real camera/geo need on-device verification.
