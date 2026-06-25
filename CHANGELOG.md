# Changelog

All notable changes to **tempestweb** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project adheres to semantic
versioning.

## [Unreleased]

### Changed

- **Bumped tempest-core to `>=0.8.1`** and **delegated Material 3 styling to the
  core's native variant system.** The core now resolves each `Button`/`Input`
  variant's resting MD3 style inline (fill, border, shape, color), so tempestweb
  no longer reimplements it. The button helpers (`filled_button`, `tonal_button`,
  `outlined_button`, `text_button`, `elevated_button`) are now a thin MD3-named
  façade over the core variants; `client/theme.js` keeps only what inline Style
  cannot express (the `::before` state layer, focus ring, disabled state, surface
  fill and type ramp) and dropped the duplicated resting rules.
- **Behavior:** outlined/text buttons now paint the core's opaque surface fill
  (was transparent), and the `Input` focus indicator is the inset box-shadow ring
  (the core's inline border outranks a stylesheet `:focus` rule). Apps still get
  the MD3 look with zero CSS.

## [0.6.0] — 2026-06-13

### Added

- **Always-on Material 3 base stylesheet.** The web client now ships a small
  always-on MD3 base theme (`client/theme.js`), keyed off `data-tw-type`, so
  apps get sensible typography, spacing and accented controls out of the box —
  no per-widget styling required. Inline widget `Style` still overrides it.
- **`Style.shadow` renders as `box-shadow` on the web.** Elevation set on a
  widget's `Style` now emits a real CSS `box-shadow`, matching the native
  renderers.
- **MD3 field and button variants.** The pre-built components (`fields`,
  `buttons`) gained light Material 3 variants (filled/outlined/text buttons,
  themed text fields) so forms look finished without hand-styling.

### Fixed

- **Checkbox MD3 theming targets the nested input.** Following the Checkbox
  `<label><input>` structure (0.5.3), the base theme sizes/accents the nested
  `[data-tw-type="Checkbox"] > input` rather than the keyed `<label>` wrapper,
  so the box is styled without shrinking the whole caption row.

## [0.5.3] — 2026-06-13

### Fixed

- **`Checkbox` now renders its label as visible text on the web.** The DOM
  renderer mapped `Checkbox` to a bare `<input type=checkbox>` and put its
  `label` on `aria-label` only, so labelled checkboxes (todo items, settings
  toggles) showed as empty boxes. A `Checkbox` now renders as a `<label>`
  wrapping the real `<input>` plus a caption text node: the box and its caption
  lay out as one tidy row (the wrapper also gives the input its accessible name
  natively). The `<label>` is the keyed, path-addressed element; the nested
  input carries `checked` and fires `change`, which bubbles to the label for
  event delegation. An explicit widget `Style` still wins.

### Examples

- **Fixed three examples that passed `children=` to `Container`.** `Container`
  holds a single `child`, not a `children` list (that is `Column`/`Row`/`Stack`).
  Pydantic silently dropped the unknown kwarg, so the container rendered empty:
  `list_demo` lost its row text (1000-item list showed blank rows), `gesture_demo`
  lost its "swipe or tap me" hint, and `anim_demo` carried a no-op `children=[]`.

## [0.5.2] — 2026-06-13

### Changed

- **Friendly error when the `[server]` extra is missing for Mode A serving.**
  `tempestweb dev` and `tempestweb run --mode wasm` lazy-import the dev server
  (Starlette + uvicorn, shipped under the `[server]` extra). On an install
  without it the import surfaced a raw `ModuleNotFoundError`. Both commands now
  raise a `DevError`/`RunError` with an actionable hint
  (`uv add 'tempestweb[server]'`), printed cleanly by the CLI. The built wasm
  artifact still never embeds a server — this only affects local serving.

## [0.5.1] — 2026-06-13

### Fixed

- **`Row`/`Column` are now flex containers on the web by default.** The web
  renderer only emitted `display: flex` when a style set an explicit `direction`,
  so a `Row`/`Column` with just `gap`/`justify`/`align` rendered as a plain block
  and those properties were silently inert (children only flowed horizontally by
  accident when they were inline-block, e.g. buttons). `styleToCss` now takes the
  widget type and defaults `display: flex` + `flex-direction` (`row`/`column`,
  also `LazyRow`/`LazyColumn`) from it; an explicit `style.direction` still
  overrides the natural axis. This matches the widget docstrings and the native
  (Qt/Compose) behaviour. Non-flex types (`Container`, `Stack`) are unchanged.

## [0.5.0] — 2026-06-13

### Added

- **`tempestweb sync` command** — auto-fills `[wasm].modules` from the project's
  installed pure-Python dependencies. Reads `[project.dependencies]` from
  `pyproject.toml`, keeps the names that are installed **and** pure-Python
  (no `.so`/`.pyd`/`.dylib`), and writes their import names into `[wasm].modules`,
  preserving existing entries. Native packages (numpy, pillow) and the framework
  (`tempestweb`, `pydantic`, …) are skipped, as is anything already under
  `[wasm].packages`. Idempotent; `--dry-run` previews without writing. Pairs with
  the 0.4.0 site-packages resolution so a dependency you `uv add` reaches the wasm
  bundle with **zero manual bookkeeping**. Uses `tomlkit` (added to the `[cli]`
  extra) for a comment-preserving round-trip edit of `tempestweb.toml`.

## [0.4.0] — 2026-06-13

### Added

- **`[wasm].modules` resolves from the installed environment** — each entry is now
  resolved in two steps: a vendored copy beside `app.py`
  (`<project>/<module>/`) still wins, but when none exists the module is pulled
  straight from the project's `.venv` `site-packages` via `importlib`. A
  dependency you `uv add` no longer has to be cloned and committed at the repo
  root to make it into the wasm bundle — just list it in `modules`. A name that is
  neither vendored nor importable fails the build with a clear message.
  Backward compatible: existing vendored layouts build unchanged. A stale project
  directory holding only `__pycache__` (real source deleted, bytecode lingering)
  no longer shadows the installed package and silently bundles nothing — it falls
  through to the installed copy.

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
