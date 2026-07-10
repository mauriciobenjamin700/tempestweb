# Changelog

All notable changes to **tempestweb** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project adheres to semantic
versioning.

## [0.10.0] — 2026-07-09

### Added

- **Mode C — transpile (experimental, spike C0).** A third execution mode
  alongside **A (WASM)** and **B (server)**: the typed-Python *app layer* is
  transcribed to **native JavaScript** — zero Python runtime in the browser,
  static hosting, great first-paint/SEO. The "TypeScript story" for Python. It
  reuses the whole shared JS renderer (`client/dom.js`, `style.js`, `events.js`):
  only the app layer is compiled.
  - **Compiler** (`tempestweb.transpile`) — an `ast`-based codegen for a small,
    typed Python subset (`@dataclass` state, `view()`, handler closures,
    `setattr` mutations, f-strings, keyword-only widget calls). Out-of-subset
    constructs raise `TranspileError` with a `file:line` diagnostic.
  - **Native JS runtime** (`client/transpile/`) — `diff.js` (a faithful port of
    the core reconciler, locked against a core-derived golden covering all five
    patch kinds), `widgets.js` (IR builders), `runtime.js` (`State`/`App` + the
    render loop). A generated `counter.gen.js` runs the canonical counter.
  - Verified live in the browser (Playwright): the counter renders and updates
    with **granular Update patches** (no root re-render), zero Python at runtime.
  - **Experimental / spike.** Widget style fidelity (MD3 defaults), a
    `tempestweb build --mode transpile` CLI target, and a wider subset are the
    next phases (C1–C5). See `docs/modo-c-transpile.md`. The public API may
    change; not yet recommended for production apps.

### Changed

- **Pinned `tempest-core>=0.11.0`** (was `>=0.9.0`). The conformance goldens are
  regenerated from the new core; no wire-shape change beyond what 0.9.0 already
  carried (`Widget.tag` / `Widget.attrs`).

## [0.9.0] — 2026-07-04

### Added

- **Static SSR — a new leaf renderer (`tempestweb.html`).** The same typed widget
  tree that drives the interactive DOM client now renders to a **static HTML
  string** on the server, reusing `tempest_core.build()` — the "one tree, N
  renderers" thesis, with HTML as a render target alongside the DOM-JS client.
  - `render_to_html(widget) -> str` renders a widget tree to an HTML fragment.
  - `render_document(widget, *, title, lang="pt-BR", head="", htmx=False,
    css_reset=True) -> str` wraps a tree in a full `<!doctype html>` document
    (charset + viewport meta, escaped `<title>`, optional CSS reset, optional htmx
    script tag).
  - `style_to_css(style, widget_type=None) -> str` is a faithful Python port of
    the client's `client/style.js` (`styleToCss`) — **byte-identical** CSS output
    (same field order, enum maps, and JavaScript-style number formatting) so a
    server-rendered page and the DOM client agree with no hydration drift.
  - `escape_text` / `escape_attr` are the HTML-escaping choke points; every text
    node and attribute value passes through them, and the `attrs` escape hatch
    rejects invalid attribute names (`^[a-zA-Z][a-zA-Z0-9:_-]*$`) as an
    attribute-injection guard.
- **`tag` / `attrs` honoring.** The renderer reads the new (`tempest-core` 0.9.0)
  base `Widget.tag` (semantic HTML tag override) and `Widget.attrs` (arbitrary
  HTML attributes — `hx-*`, `id`, `class`, `data-*`, `aria-*`) so a typed tree can
  emit semantic, htmx-ready markup (`Container(tag="nav", attrs={...})`).

### Changed

- **Pinned `tempest-core>=0.9.0`** (was `>=0.8.2`) for the base `Widget.tag` /
  `Widget.attrs` fields the HTML renderer consumes.
- **The Mode B wire omits empty `tag` / `attrs`.** Since `tempest-core` 0.9.0 puts
  `tag=None` / `attrs={}` on every node's props, `runtime.serialize.node_to_wire`
  now drops them when falsy. This keeps the WebSocket/SSE payload byte-identical to
  the pre-0.9.0 wire for widgets that do not use them (no per-node bloat) — a
  widget that *does* set them still ships them. The conformance golden
  (`tests/fixtures/conformance_scenarios.json`, derived from `model_dump`) was
  regenerated to reflect the new base fields (purely additive).

## [0.8.1] — 2026-06-27

### Changed

- **`tempest-core` is now the single source of truth.** The whole example
  gallery and the test suite import the renderer-agnostic engine directly as
  `tempest_core` (`from tempest_core import App, Column, Style, …`) instead of
  going through the historical `tempestweb._core` path. Both execution modes were
  re-verified live in the browser (Playwright): the counter renders and updates in
  **Mode B** (FastAPI + WebSocket round-trip) and in **Mode A** (Pyodide,
  in-process, zero-network) with the shim gone.

### Removed

- **The `tempestweb._core` back-compat shim.** The vendored `tempestweb/_core/`
  copy was already extracted into the standalone `tempest-core` package; the shim
  that re-exported it under the old import path (and its `test_core_shim.py`) is
  deleted. The Mode A WASM bundler no longer packs a `_core` part — it ships the
  `tempest_core` package directly. Internal-only change: `_core` was always
  private, so no public API is affected.

## [0.8.0] — 2026-06-25

### Added

- **Two vendored icon sets — Material Symbols (Outlined) + Lucide.** A new
  `tempestweb.icons` façade (`material_icon`, `lucide_icon`, `custom_icon`,
  `register_icon`, `MaterialIcons`/`Icons` enums) builds the core `Icon` widget
  from either set. Both render client-side as **inline SVG** from path data
  vendored in `client/icons/{lucide,material}.js` — no icon font, no network,
  offline/PWA safe. The set is encoded as a `"set:"` prefix on the icon name
  (`"material:home"` / `"lucide:mail"`); a bare name stays Lucide for
  compatibility with the core `Icon` and the field icon slots. `custom_icon`
  ships a one-off SVG path over the wire (no registration); `register_icon` +
  the client `registerIcon` add a reused glyph to both sides.
- **`tempestweb build` bundles the icon assets** into the artifact, so installed
  PWAs draw every icon offline.
- **Docs:** bilingual "Icons (Material + Lucide)" guide (PT-BR + EN-US).

### Changed

- **Bumped tempest-core to `>=0.8.2`.** Picks up the clickable-`Rating` fix
  (stars render as bare glyphs, not filled pills).

### Fixed

- **The `core-profile-cards` example uses an interactive `Rating` again.** The
  0.7.0 display-only workaround is reverted now that tempest-core 0.8.2 renders
  clickable stars as bare glyphs.

## [0.7.0] — 2026-06-25

### Added

- **Canvas rendering on the web.** The DOM renderer now maps a `Canvas` widget to
  a real `<canvas>` and executes its draw-command list
  (`move_to`/`line_to`/`draw_rect`/`stroke`/`fill`/`draw_text`) onto the 2D
  context. Previously any unknown node type fell back to a `<div>`, so the core's
  Canvas-based components (charts, detection overlays, the sketch pad) rendered
  blank — they now draw in both modes.
- **The tempest-core component library, re-exported through
  `tempestweb.components`.** 54 Material 3 components (layout scaffolds, app bars,
  navigation, cards, lists, inputs, feedback, tables and `BarChart`/`LineChart`
  charts) plus the value models/helpers that drive them (`ChartSeries`,
  `TableRow`/`TableCell`, `DetectionBox`, `confidence_scheme`) are now importable
  from `tempestweb.components` — one import home for the native helpers and the
  core set. Each lowers to renderable primitives or a Canvas draw-command list,
  so the whole library works in Mode A and Mode B.

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
