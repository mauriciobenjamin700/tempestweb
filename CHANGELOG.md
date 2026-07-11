# Changelog

All notable changes to **tempestweb** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project adheres to semantic
versioning.

## [0.45.0] — 2026-07-11

### Added

- **Benchmarks (Track S — S9, partial).** `benchmarks/bench_reconcile.py` times
  the `build → diff` hot path (ops/s, µs/op) and confirms minimal patching (a
  single-row change yields 2 patches). A CI regression gate remains a follow-up.
- **Stability & support docs (Track S — S10, S11).** New `docs/stability.md`
  (PT+EN): the pre-1.0 public-surface + deprecation policy, a browser support
  matrix (A/B/C), the accessibility baseline, and the **Mode C subset contract**
  — the stable, fail-loud in/out list (S11), with components staying an open
  decision.

## [0.44.0] — 2026-07-11

### Added

- **Server metrics (Track S — S8, partial).** `create_app(..., metrics=True)`
  mounts `GET /metrics` in Prometheus text format: `tempestweb_sessions_live`
  (gauge), `tempestweb_sessions_opened_total` /
  `tempestweb_connections_rejected_total` (counters), and
  `tempestweb_sessions_max` when a cap is configured. Disabled by default.
  (OpenTelemetry tracing + patch-latency/throughput remain follow-ups.)

## [0.43.0] — 2026-07-11

### Added

- **Deploy & ops (Track S — S4 partial, S5, S7 partial).**
  - **S4** `GET /health` — unauthenticated liveness/readiness probe returning
    `{status, sessions, ready}`; `ready` flips to `false` at `max_connections`
    for load-balancer draining. Horizontal-scale guidance (sticky sessions).
  - **S5** `examples/deploy/` — a production `Dockerfile` (with `HEALTHCHECK`),
    `docker-compose.yml` (app + nginx/TLS) and `nginx.conf` (WebSocket upgrade,
    long streaming timeouts, `ip_hash` stickiness). New `docs/deploy.md` (PT+EN).
  - **S7** root `SECURITY.md` (private reporting + security model) and a
    `pip-audit` job in CI.

## [0.42.0] — 2026-07-11

### Added

- **Mode B limits & security headers (Track S — S2 partial, S6).** `SecurityConfig`
  gains:
  - **S2** `max_connections` — cap on concurrent WS+SSE sessions (a connection
    over the cap is refused: WS `1013` / SSE `503`), and `max_message_bytes` —
    an SSE `POST` body over the limit returns `413`. (Idle-session timeout, a WS
    message cap and per-IP rate limiting remain follow-ups.)
  - **S6** `security_headers` (adds `X-Content-Type-Options: nosniff`,
    `Referrer-Policy`, `X-Frame-Options: DENY`), `hsts`
    (`Strict-Transport-Security`), and `content_security_policy` — applied to
    every HTTP response by a middleware.
- **XSS audit (S6):** confirmed the JS client is safe by construction — zero
  `innerHTML`/HTML-injection sinks anywhere in `client/`; the DOM patcher only
  uses `textContent` + `setAttribute`. Documented in `docs/security.md`.

## [0.41.0] — 2026-07-11

### Added

- **Mode B server security (Track S — S0/S1/S3).** `create_app(...)` gains an
  opt-in `security=SecurityConfig(...)`:
  - **S0 auth gate** — an `authenticate` predicate (sync or async) runs on every
    WebSocket upgrade and SSE request *before* a session is created; a falsy
    return or a raised error rejects the connection (WS close `1008` / HTTP
    `401`). Builders: `token_authenticator(secret)` (shared secret, constant-time,
    empty = disabled) and `jwt_authenticator(key, ...)`.
  - **S1 origin allowlist** — `allowed_origins` installs `CORSMiddleware` for the
    HTTP/SSE surface *and* hard-checks the `Origin` header on the WS upgrade
    (which browser CORS does not guard); `["*"]` allows any origin.
  - **S3 server-side JWT** — `verify_jwt(token, key, ...)` validates signature +
    expiry (needs the `[auth]` extra / PyJWT; degrades to a clean rejection when
    absent), distinct from the client-side `decode_jwt`.

  The host stays fully open when no `SecurityConfig` is passed (dev). New
  `docs/security.md` (PT+EN) documents the surface.

## [0.40.0] — 2026-07-11

### Changed

- **Docs: three execution modes, front and center.** The landing page, the
  "running modes" tutorial and the transpile guide were reframed from two modes
  to three (A WASM · B server · C transpile/native-JS) in the tiangolo style —
  a three-card grid with a "which mode?" decision note, an updated
  "how it works" diagram including the Mode C transpile path, and Mode C
  positioned as a first-class guide in the nav. The README (PyPI front page) now
  presents all three modes consistently (diagram + capabilities + a Mode C
  scaffold pointer) and an accurate, non-stale status. No code changes — the
  package is unchanged; this release ships the corrected README/docs.

## [0.39.0] — 2026-07-11

### Added

- **`tempestweb new --template pwa`** — scaffold an installable, offline Mode C
  PWA in one command. The template pre-configures `tempestweb.toml` with
  `mode = "transpile"` + a `[pwa]` manifest block, and ships an `app.py` with a
  counter and an **Install** button (`native.install`). The default template
  (a two-mode counter) is unchanged; `render_files`/`scaffold_project`/
  `create_project` gain a `template` argument, and an unknown template fails
  loud (`UnknownTemplateError`). Verified: the scaffolded project renders
  through the real core and builds into a full PWA (manifest + service worker +
  transpiled install button).

## [0.38.0] — 2026-07-11

### Added

- **Stdlib method mapping in the transpiler.** Common Python methods now map to
  their JS idioms: string/list renames (`.upper()` → `.toUpperCase()`,
  `.lower`, `.strip`/`.lstrip`/`.rstrip`, `.startswith`/`.endswith`, `.append()`
  → `.push()`), dict views (`.items()` → `Object.entries(d)`, `.keys()`,
  `.values()`), and `sep.join(it)` → `it.join(sep)`. Methods on runtime/facade
  objects (`app.replace(route)`, `native.storage.get(...)`, `ctrl.forward()`)
  pass through unchanged — the map deliberately omits `.replace` and `.get` to
  avoid clashing with them (use subscript `d[k]` for a dict lookup).

## [0.37.0] — 2026-07-11

### Added

- **Wider expression + statement subset in the transpiler:**
  - **Sequence unpacking** — `a, b = pair` (array destructuring), `for k, v in
    items:` and comprehension tuple targets (`[f(k, v) for k, v in items]`).
  - **`enumerate(it)`** → `it.map((v, i) => [i, v])` and **`zip(a, b)`** → paired
    arrays, so tuple-target iteration works idiomatically.
  - **Operators `**` (power) and `//` (floor division → `Math.floor(a / b)`).**
  - **Slices** — `x[a:b]` / `x[a:]` / `x[:b]` → `x.slice(...)` (a step is
    rejected).
  - **`assert cond[, msg]`** → `if (!(cond)) throw` an `AssertionError`.
  - **Chained assignment** `a = b = x`.

  (Chained comparison `a < b < c` was already supported.)

## [0.36.0] — 2026-07-11

### Added

- **`raise` in the transpiler.** `raise Exc("msg")` / `raise Exc` throw an
  `Error` whose `message` is the first argument and whose `name` is the
  exception class — so it round-trips with the multiple-`except` dispatch
  (`except Exc` matches on `err.name`). A bare `raise` inside an `except`
  re-throws the caught error. `raise … from …` and a bare `raise` outside an
  `except` fail loud. This completes the raise/try/except loop in Mode C.

## [0.35.0] — 2026-07-11

### Added

- **Dataclass inheritance in the transpiler.** `@dataclass class B(A):` emits
  `class B extends A` (the base must be another `@dataclass` in the module);
  `super()` chains the base constructor, then the subclass's field defaults are
  assigned (overriding an inherited default when they clash). Multiple bases or
  an unknown base fail loud.
- **`with … as x`.** Transpiled via the context-manager protocol —
  `x = cm.__enter__()` then a `try/finally` whose `finally` calls
  `cm.__exit__(null, null, null)` (faithful for managers exposing those methods,
  e.g. a transpiled dataclass; `async with` awaits both). The `as` target is
  hoisted to a function-scoped `let`, mirroring Python's leak. A single context
  manager; `as` must bind a plain name.
- **Multiple `except` clauses.** A lone `except` still catches everything (type
  informational); multiple clauses dispatch by exception class name
  (`err.name === "ValueError"`, `["A","B"].includes(err.name)`), with a trailing
  broad/`Exception` clause as the `else` — or `throw` to re-raise when none
  matches (Python's selective semantics, preserved for A/B/C parity). Matching is
  by class **name**; a JS/browser error only matches when the names coincide.

### Fixed

- **Dataclass construction with field arguments.** A transpiled dataclass
  constructor now takes an options object and applies overrides
  (`Doubler(n=5)` → `new Doubler({ n: 5 })` sets `n = 5`), falling back to the
  field default when a key is absent — previously the constructor ignored all
  arguments and always used the defaults (a silent divergence from Python).

## [0.34.0] — 2026-07-11

### Added

- **Control-flow statements in the transpiler:** `while` loops, `break` /
  `continue`, and `try` / `except` / `finally` (a single `except`, binding the
  error to its name or `_err`). `while/else`, `try/else` and multiple `except`
  clauses still fail loud with a located `TranspileError`.

### Fixed

- **`const` vs `let` correctness.** The hoisting analysis now emits `let` for any
  name that is augmented (`+=`), re-bound, or assigned inside a block — only a
  name bound exactly once at the top level stays `const`. This fixes a latent JS
  bug where a `for`/`while` counter (`total = 0; total += x`) emitted
  `const total = 0` followed by `total += x` (assignment to a constant → a
  runtime `TypeError`).

## [0.33.0] — 2026-07-11

### Added

- **WebPush end-to-end (server path).** The last piece to make push work end to
  end:
  - `tempestweb.server.generate_vapid_keys() -> VapidKeys` — a P-256 VAPID
    keypair (base64url); requires the `[webpush]` extra.
  - `tempestweb vapid` CLI — prints a fresh keypair (`--env` prints
    `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` export lines).
  - `tempestweb.server.webpush_router(service, *, owner, prefix)` — a mountable
    FastAPI router exposing `GET /webpush/vapid-public-key`, `POST
    /webpush/subscribe`, `POST /webpush/unsubscribe`, `POST /webpush/send`.
  - `examples/webpush-server/server.py` — a runnable demo: VAPID (env or
    ephemeral dev keypair) + the router + a page and minimal push service worker.
    `uv run uvicorn server:app --app-dir examples/webpush-server`.

  With the client already able to `native.notifications.subscribe(public_key)`
  and POST the subscription, the full loop closes: subscribe → store → send →
  notification. The server path (keygen, router, send with a mocked sender) is
  unit-tested; the browser subscribe/permission + real push delivery are device/
  gesture dependent (manual). Verified live (Playwright): the demo page loads,
  the service worker registers + activates, `PushManager` is available and the
  VAPID public key is served.

## [0.32.0] — 2026-07-10

### Added

- **`native.notifications.push_state()`** — reports WebPush `{supported,
  permission}` WITHOUT prompting, so an app can decide whether to show an
  "enable notifications" button before the gesture-gated `subscribe`. New
  dispatch handler + Python `PushState` model, marked `mode_c`; JS + Python
  tested.
- **Offline-queue demo in `examples/transpile-tour`** — a visible "queue" button
  enqueues a mutation via `native.offline` and shows the live pending count.
  Verified live (Playwright): three clicks drive `queued=3` through real
  IndexedDB, entirely from the transpiled UI.

## [0.31.0] — 2026-07-10

### Added

- **WebPush subscribe/unsubscribe in Mode C (`native.notifications`).** The push
  subscription flow (already in the dispatch registry and Python surface) is now
  exposed on the Mode C facade and marked `mode_c`:
  `await native.notifications.subscribe(vapid_public_key)` runs the browser
  WebPush flow (permission + `pushManager.subscribe`) and returns the raw
  subscription JSON to POST to your own backend (e.g. via `native.http` or queued
  with `native.offline`); `unsubscribe()` cancels it. The framework owns neither
  the endpoint schema nor the push server — it hands back the raw subscription.
  The dispatch handler is already unit-tested; the contract conformance test
  enforces the facade coupling. Verified live (Playwright): in the built app the
  flow reaches `pushManager` (support detected, permission readable) — the
  grant/subscribe step is gesture + push-service dependent and left to manual
  verification. This closes the Mode C PWA capability set (install, offline
  queue, update prompt, push).

## [0.30.0] — 2026-07-10

### Added

- **"New version available" update prompt (Mode C PWA).** When a new service
  worker is deployed, the shell now surfaces an unobtrusive banner ("new version
  available → Reload"); confirming activates the waiting worker (skipWaiting) and
  reloads the page once. New pure-JS `client/pwa/update-prompt.js`
  (`createUpdateBanner` / `showUpdatePrompt`, idempotent, injectable document +
  skipWaiting) wired into the transpile shell via `registerServiceWorker`'s
  `onUpdate`. Lives in the shell (not the app view), so it needs no core App
  change and works without the app cooperating. Verified live (Playwright): in
  the built app the banner renders and its button invokes skipWaiting on the
  waiting registration. jsdom-tested (5 cases).

## [0.29.0] — 2026-07-10

### Added

- **Offline mutation queue in Mode C (`native.offline`).** A new native
  capability exposing the durable, replay-on-reconnect queue (the tested
  `client/offline/{store,sync}.js` over IndexedDB) end to end:
  `await native.offline.enqueue(method, url, body)` records a mutation with an
  idempotency key; `pending()` / `size()` inspect it; `replay()` drains it in
  FIFO order (also wired to the `online` event and Background Sync). The Python
  awaitable surface (`tempestweb.native.offline` — `enqueue`/`pending`/`size`/
  `replay`, `Mutation`/`ReplayResult` models) and the JS dispatch handlers
  (`offline.*`) are marked `mode_c`, and the offline client modules now ship in
  the wasm and transpile artifacts (and join the service-worker precache).
  Verified live (Playwright): in the built app, `enqueue` writes to real
  IndexedDB (FIFO, idempotency key), `size`/`pending` reflect the queue, and
  `replay` performs real `fetch` round-trips, preserving the queue on failure.

## [0.28.0] — 2026-07-10

### Added

- **PWA install prompt in Mode C (`native.install`).** The install capability
  (already present in the dispatch registry and Python surface) is now exposed on
  the Mode C native facade and marked `mode_c`: `await native.install.state()`
  returns `{can_install, installed}` and `await native.install.prompt()` fires the
  browser's stashed `beforeinstallprompt` after a user gesture, resolving to
  `"accepted"` / `"dismissed"` / `"unavailable"`. `examples/transpile-tour` gains
  an "install" button. Verified live (Playwright): the facade round-trips
  end-to-end in the browser (`install.state()` → `{can_install:false,
  installed:false}`; `beforeinstallprompt` captured and `prompt()` fired — the
  accept/dismiss step is gesture-dependent and not automatable).

## [0.27.0] — 2026-07-10

### Added

- **Mode C is a first-class PWA — installable and offline out of the box.**
  `tempestweb build --mode transpile` now emits the full PWA layer alongside the
  static bundle: `manifest.webmanifest`, a cache-first app-shell service worker
  (`sw.js`) whose precache covers the *entire* bundle (index, shared client,
  `client/transpile/*` incl. the generated `app.gen.js`, native tree, icons), its
  registration (`register.js`), and the icon set. The generated `index.html`
  links the manifest, sets `theme-color`/apple-touch-icon and registers the
  worker. Because Mode C is a zero-Python static bundle, it is the ideal PWA
  target. Verified live (Playwright): with the HTTP server killed, reloading the
  built tour still renders and navigates — the app runs fully offline.
- **`[pwa]` config section.** `tempestweb.toml` gains a `[pwa]` table to
  customize the generated manifest — `name`, `short_name`, `description`,
  `theme_color`, `background_color`, `display` (`standalone`/`fullscreen`/
  `minimal-ui`), `orientation`, `lang`, `categories`. All optional; names fall
  back to the project name. The `theme_color` is mirrored into the shell's
  `theme-color` meta. `examples/transpile-tour` now ships a `[pwa]` block.

### Changed

- The wasm (Mode A) `theme-color` meta now follows the `[pwa].theme_color`
  instead of a hard-coded value.

## [0.26.0] — 2026-07-10

### Added

- **More builtins in the transpiler.** `round(x[, n])`, `min`/`max` (variadic or
  over one iterable), `sum(it)`, and `range(...)` — the last materialized to a
  JS array so a comprehension's `.map`/`.filter` chain has something to iterate
  (JS has no lazy range). This closes a correctness gap: comprehensions over
  `range(...)` now actually run in the browser.
- **Richer f-string number formatting.** Beyond `.Nf`: thousands grouping
  (`{x:,}` → `toLocaleString`), grouped fixed-point (`{x:,.2f}`), percent
  (`{x:.1%}`) and integer (`{x:d}`, `{x:,d}`). Unsupported specs (alignment,
  sign, hex/bin, dynamic `{x:.{n}f}`, `!a`) still fail loud with a located
  `TranspileError`.

  Verified live (Playwright): a built app renders `total=1,234,567.89`,
  `ratio=12.6%`, and a `range(1, 5)` comprehension `squares=1,4,9,16 sum=30`,
  zero Python in the browser.

## [0.25.0] — 2026-07-10

### Added

- **Wider transpiler expression subset.** Mode C now transcribes more everyday
  Python:
  - `set` literals → `new Set([...])`; `tuple` literals → JS arrays (JS has no
    tuple type — immutability is not enforced).
  - dict comprehensions (`{k: v for x in it if c}`) →
    `Object.fromEntries(it.filter(...).map((x) => [k, v]))`.
  - f-string formatting: `{x:.2f}` → `(x).toFixed(2)`, `{x!s}` → `String(x)`,
    `{x!r}` → `JSON.stringify(x)`.

  Out-of-subset format specs (alignment `{x:>5}`, dynamic `{x:.{n}f}`, the `!a`
  conversion) and multi-loop/destructured comprehensions still fail loud with a
  located `TranspileError`. Verified live (Playwright): a built app renders
  `pi=3.14` and a dict-comp-derived `squares=9` with zero Python in the browser.

## [0.24.0] — 2026-07-10

### Added

- **Canonical Mode C tour example (`examples/transpile-tour`).** One app that
  exercises the whole app-layer surface at once — state with methods, navigation
  (routes + URL), i18n, theme + responsiveness, a validated form (native
  `validate_email`) and an imperative animation (`AnimationController`/`Tween`).
  Verified live (Playwright): navigation, form validation ("E-mail inválido"),
  theme/lang toggles and the animated box all work with zero Python in the
  browser. Documented as "O tour completo" in the transpile guide (PT + EN).

### Fixed

- **Function-scope hoisting in the transpiler.** A name assigned inside an
  `if`/`for` block (e.g. `body = Column(...)` in a branch) was emitted as a
  block-scoped `const` and became invisible to the rest of the function —
  a runtime `ReferenceError` in JS. Such names now hoist to a single
  function-top `let`; top-level-only names keep their `const`.
- **Fail-loud on out-of-subset constructs.** Variadic/keyword-only parameters,
  function decorators, non-dataclass class decorators and f-string format-specs
  were silently mis-transpiled. Each now raises a located `TranspileError`
  (`file:line`), matching the `mypy --strict` spirit. `field(default=…)` and
  `field(default_factory=list/dict/set)` are now honored.

## [0.23.0] — 2026-07-10

### Added

- **Imperative animation in Mode C (`AnimationController`/`Tween`/`Spring`).**
  Frame-driven animation now works in the transpile mode: `AnimationController`
  drives a normalized value (eased ramp or damped spring) on a
  `requestAnimationFrame` loop the runtime owns, and `Tween` maps it to a float/
  Color/Edge for a `Style`. `client/transpile/animation.js` is a faithful port of
  `tempest_core.animation` (curve math + ramp/spring integration + lerps); the App
  gains `register_animation`/`unregister_animation`/`has_animations`. Verified live
  (Playwright): a box animates width 100→340 over an ease-out ramp and settles.
  **This closes 100% of `tempest_core` coverage in Mode C.**

## [0.22.0] — 2026-07-10

### Added

- **Animation in Mode C (declarative transitions) — core coverage closed.** Give
  a widget's `Style` a `Transition` and the browser tweens it when a styled field
  changes (width/color/opacity) — no Python runtime, no frame driver.
  `client/transpile/motion.js` ports `tempest_core.style`'s `Transition` + `Curve`
  (linear/ease/ease-in/out/in-out/bounce/elastic); `Color` joins the Style-value
  helpers. Verified live (Playwright): a box animates width 120→320px over a
  400ms CSS transition. This closes `tempest_core` coverage in Mode C — widgets,
  layout components, native (10 capabilities), validators, navigation, i18n,
  theme + responsiveness, and animation. The imperative, frame-driven
  `AnimationController` remains the one advanced piece (declarative transitions
  cover the canonical case).

## [0.21.0] — 2026-07-10

### Added

- **Theme + responsiveness in Mode C.** The transpile mode exposes `app.theme`
  and `app.media` like Modes A/B: `app.theme.is_dark()` resolves light/dark
  (`SYSTEM` follows the OS), and `app.media` (width/height/platform_dark_mode/
  orientation) is kept in sync with the browser via matchMedia + resize, so the
  view re-renders responsively. `app.set_theme(Theme(...))` swaps the theme.
  `client/transpile/theme.js` ports `tempest_core.theme` (ThemeMode/Theme/
  MediaQueryData/Breakpoints); `client/transpile/media.js` reports the viewport.
  Verified live (Playwright): a resize flips narrow↔wide and a toggle flips
  light↔dark.

## [0.20.0] — 2026-07-10

### Added

- **i18n in Mode C (`translate`/`t` + `Locale`).** The core's localization works
  in the transpile mode: look a key up in a `{language: {key: template}}` table by
  the locale's language and interpolate `{name}`, mirroring `tempest_core.i18n`
  (including the miss/fallback rules). `client/transpile/i18n.js` ports it; the
  transpiler routes `from tempest_core import translate, t, Locale` to it.
  Verified live (Playwright): a language toggle flips PT → EN reactively.
- **Module-level constants in the subset.** A top-level `NAME = {...}` (e.g. a
  translations table) now transpiles to a `const`, so apps can define shared data
  outside `view`.

## [0.19.0] — 2026-07-10

### Added

- **Navigation in Mode C (routes + URL sync).** The transpile mode now speaks the
  core navigation API — `app.push(Route(...))`, `app.pop()`, `app.replace(...)`,
  `app.reset(...)`, and `app.nav.top` — synced with the browser URL. A push/pop
  `pushState`-s the new path; a deep link or back/forward resets the stack from
  the path (`routesFromPath`), so the same `view()` runs under Modes A/B/C.
  `client/transpile/nav.js` ports `tempest_core.navigation` (Route kept at strict
  parity, since the transpile build validates through the real core).
- **Transpiler: common builtins.** `len` → `.length`, and `str`/`int`/`float`/
  `bool`/`abs` map to their JS idioms; keyword-only class calls (e.g.
  `Route(name=...)`) emit `new`.

## [0.18.0] — 2026-07-10

### Added

- **More Mode C native capabilities.** `share`, `audio`, `file`, and
  `notifications` (notify + request_permission) join the Mode C facade, alongside
  http/storage/clipboard/geolocation/cookies. All route to the shared
  `client/native` glue; the capability contract marks them `mode_c` and the
  conformance test enforces the facade matches that subset.
- **`tempest_core.validators` in Mode C.** `client/transpile/validators.js` is a
  faithful port of the core's BR field validators (`validate_cpf`/`cnpj`/`email`/
  `phone`) — same algorithms and PT-BR messages. The transpiler routes
  `from tempest_core.validators import ...` to it, so a transpiled form validates
  client-side with no Python. Parity is locked by a core-derived fixture.

## [0.17.0] — 2026-07-10

### Added

- **Native-capability contract (single source of truth).**
  `tempestweb.native.contract` pins the set of native capabilities and which are
  exposed in Mode C. Conformance tests assert the three surfaces agree — the
  Python awaitables, the JS `HANDLERS` (`client/native/index.js`), and the Mode C
  facade (`client/transpile/native.js`) — so a capability added to one surface
  but not the others fails CI. It is the extraction candidate for a shared
  contract `tempestroid` (mobile) could mirror.

## [0.16.0] — 2026-07-10

### Added

- **Mode C `storage` is IndexedDB-backed.** The transpile-mode `storage`
  capability now persists over IndexedDB via a minimal async KV
  (`client/native/idb-kv.js`) injected as `deps.store`, falling back to
  localStorage only when IndexedDB is unavailable. Verified live (Playwright):
  values land in the `tempestweb/kv` object store, not localStorage.

## [0.15.0] — 2026-07-10

### Added

- **Native capabilities in Mode C (via the typed Python interface).** The same
  `tempestweb.native` API used by Modes A/B now works in the transpile mode:
  `http`/requests, `storage` (IndexedDB/localStorage), `clipboard`,
  `geolocation`, and the new `cookies`. A transpiled `await native.http.request(
  ...)` becomes an in-process JS call to the shared browser glue
  (`client/native/*.js`) through the `dispatch` registry — no Python, no bridge,
  no network. The `client/transpile/native.js` facade mirrors the Python API;
  `from tempestweb import native` is routed to it by the transpiler. Verified live
  (Playwright): a transpiled app round-trips a cookie and a storage value.
- **`async`/`await` in the transpile subset.** `async def` handlers and `await`
  expressions transpile (methods and nested defs too); the runtime tolerates an
  async handler (re-render on `set_state` after the await). Also added: dict
  literals → JS objects, and mixed positional+keyword calls → a trailing options
  object (e.g. `native.http.request("GET", url, json=body)`).
- **`cookies` native capability (all modes).** A new typed awaitable
  (`native.cookies.get/set/remove/all`) over `document.cookie`, served by
  `client/native/cookies.js` in every mode. Non-HttpOnly cookies only.

## [0.14.0] — 2026-07-10

### Added

- **Mode C — `tempestweb dev --mode transpile` (watch + livereload).** The dev
  loop now serves the transpile mode with browser livereload, completing the CLI
  story (`build` / `run` / `dev`) for Mode C. It builds the static bundle, serves
  it over the dev HTTP app, and rebuilds on every watched change before reloading
  the tab; a failing rebuild (syntax error or out-of-subset construct) is reported
  and skipped so the last good bundle keeps serving. Both static modes (wasm,
  transpile) share the devserver; Mode B still uses `run --mode server`.

## [0.13.0] — 2026-07-10

### Added

- **Mode C — the ergonomic layout components `HStack` / `VStack`.** The
  `tempest_core.components` layer is Python composition (each expands to a
  primitive widget tree at `build()` time), so it is not auto-portable to a
  Python-free runtime — except the pure layout aliases, which expand to a plain
  `Row` / `Column`. `HStack`/`VStack` are now available in Mode C
  (`client/transpile/components.js`): a `gap` as a spacing token (`"md"`,
  resolved via the core-derived `spacing.gen.js`) or a raw px, plus direct
  `align`/`justify`. Parity with the core is locked by a core-derived fixture
  (order-agnostic) and byte-match golden tests.

### Note

- The rest of `tempest_core.components` (Card, DataTable, Tabs, charts, form
  inputs) stays out of Mode C: their composition is data/loop-driven Python that
  a zero-Python runtime cannot reproduce without compiling the core's own
  composition source. Use Modes A/B for those, or compose from primitives.

## [0.12.0] — 2026-07-10

### Added

- **Mode C — every `tempest_core` widget is ported (experimental).** All ~64
  buildable core widgets now have native-JS IR builders, **generated by
  introspecting the real core** (`client/transpile/widgets.gen.js` +
  `tests/conformance/_transpile_widgets.py`) — no hand-written per-widget code.
  Layout (`Column`, `Row`, `Container`, `Stack`, `Wrap`, `ScrollView`,
  `SafeArea`, `Spacer`), display (`Text`, `Icon`, `Image`, `Svg`, `Spinner`,
  `Skeleton`, `ProgressBar`), input (`Button`, `Input`, `TextArea`, `Switch`,
  `Checkbox`, `Slider`, `RangeSlider`, `Dropdown`, `DatePicker`, `PinInput`, …),
  overlays (`Dialog`, `BottomSheet`, `Popover`, `Toast`, `Tooltip`), and gestures
  (`GestureDetector`, `Draggable`, `PanHandler`, …). Each builder writes the
  core's wire prop shape with real defaults; required props have no default.
- **Mode C — Material 3 styling for every styled widget.** The introspected
  style table now covers all 14 styled widgets across the axes each accepts
  (variant/field_variant × size × color_scheme, normalized with `"_"`), resolved
  the same way as the core.
- **Mode C — per-widget event binding.** Handlers are stashed in a non-wire
  `__handlers` map and bound to the DOM event the renderer emits for that widget:
  `on_click` → click; `on_change`/`on_toggle` → `input`/`change` on native form
  controls (`Input`/`Checkbox`) and → click on div-rendered toggles like
  `Switch`. Verified live (Playwright) with a multi-widget gallery.
- **Golden coverage.** Byte-match tests lock both generated modules
  (`widgets.gen.js`, `widget-styles.gen.js`) against the live core; a JS smoke
  test builds every widget. The Mode C tutorial (PT + EN) documents the full set.

### Note

- `tempest_core.components` (compositions like Card/DataTable/Tabs, layered above
  the widgets) and exotic events the client does not yet emit remain out of scope.

## [0.11.0] — 2026-07-09

### Added

- **Mode C — `tempestweb build --mode transpile` (experimental).** The transpile
  mode is now a real CLI target: `build --mode transpile <path>` (and
  `run --mode transpile`, which static-hosts the bundle like wasm) transcribes
  the project's `app.py` to `client/transpile/app.gen.js` and emits a **fully
  static** artifact — an `index.html` that mounts via `mountApp`, the shared JS
  client, and the native runtime (diff/widgets/runtime). Zero Python at runtime,
  servable by any CDN. An out-of-subset app fails with a clear `BuildError`.
- **Mode C — Button & Input Material 3 style fidelity.** A build-time generator
  introspects the real `tempest_core`, resolving each Button (variant × size ×
  color_scheme) and Input (field_variant × size × color_scheme) style into a
  native JS data module (`widget-styles.gen.js`); the widget builders look it up
  and merge an explicit `style` on top. Transpiled buttons/fields now render with
  their MD3 look — parity with Modes A/B, verified live (Playwright). A golden
  test byte-matches the table against the core. (`state_styles` hover/pressed is
  N/A: the IR carries no interaction state.)
- **Mode C — `Input` with reactive two-way binding.** The native runtime
  dispatches handlers by `"eventType:key"`, so `input`/`change` events reach an
  `Input`'s `on_change`; the shared `dom.js` renders the `<input>`. Typing drives
  `on_change → set_state → re-render` end-to-end with no Python — verified in the
  browser with a live `Hello, {name}!` form.
- **Mode C — wider Python subset.** The transpiler now handles arithmetic
  (`* / %`), comparisons, boolean/unary operators, ternary expressions, list
  comprehensions (`→ .filter().map()`), `in`/`not in`, subscript, expression
  lambdas, `if`/`elif`/`else`, `for … in`, assignment/`+=`, and **dataclass
  methods** (`self → this`). New `Container` widget (layout + `tag`/`attrs`
  escape hatch).
- **Bilingual Mode C tutorial docs.** A tiangolo-style page (PT-BR default +
  EN-US) in the docs nav, covering the first build, generated output, state
  methods, reactive forms, and the supported subset.

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
