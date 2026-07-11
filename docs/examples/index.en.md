# Example Gallery 🎨

Welcome to the **tempestweb** gallery! 🚀 Here you'll find complete, ready-to-run
apps, each focused on **one concept** — state, forms, lists, navigation, theming,
i18n, canvas, native capabilities, and much more.

!!! tip "Three modes, one codebase"
    Every example is a typed-Python `view(app) -> Widget` module. The **same**
    `app.py` runs without changing a single line:

    - **Mode A (WASM/Pyodide)** — Python straight in the browser.
    - **Mode B (server)** — Python on a FastAPI server + a thin WebSocket client.
    - **Mode C (transpile)** — the app transcribed to native JS, a static bundle.

    The view tree never names a transport. You write the logic once and pick the
    mode at serve time.

!!! info "The mode badges"
    Each line carries a badge: **[A/B]** runs in the interactive modes (WASM and
    server); **[A/B/C]** **also** runs transpiled to native JS. Most examples use
    ready-made components or the Python event shape (`event.value`), so they live in
    **A/B**. Mode C runs the **pure-widget** subset — the showcase is the
    [Mode C tour](transpile-tour.md).

!!! note "How to read each page"
    Every page follows the tutorial pattern: what you'll build → the complete code
    → a piece-by-piece explanation → a **Recap** at the end. Start with the
    [**Counter**](../tutorial/index.md) and the [**To-do list**](todo.md) if you're
    new here.

---

## Fundamentals

The building blocks — the starting point for everyone.

- [**Counter**](../tutorial/index.md) — the reactive "hello world": state + handler + patch. **[A/B/C]**
- [**To-do list**](todo.md) — a controlled `Input`, a virtualized `LazyColumn`, and a per-item `Checkbox`. **[A/B]**
- [**Form**](form.md) — `Form` + `FormField` + typed validators that mirror errors back onto state. **[A/B]**
- [**Async fetch**](fetch.md) — an `idle → loading → loaded/error` transition via an `async` handler. **[A/B]**

---

## State and data

Manage time, conversions, tables, and charts fully deterministically.

- [**Stopwatch**](stopwatch.md) — Start/Stop/Lap/Reset with time stored as integer tenths-of-a-second. **[A/B]**
- [**Temperature converter**](temperature-converter.md) — two controlled fields (Celsius/Fahrenheit) kept in sync via two-way binding. **[A/B]**
- [**Data table**](data-table.md) — live search + per-column sort toggle (ASC/DESC), driven from state. **[A/B]**
- [**Data grid**](data-grid.md) — a dense grid with typed columns and per-cell formatting. **[A/B]**
- [**Charts dashboard**](charts-dashboard.md) — metric cards + charts drawn from state. **[A/B]**

---

## Forms and flows

From simple validation to a multi-step wizard.

- [**Login form**](login-form.md) — `EmailInput`/`PasswordInput`, three-layer validation, and an error `Banner`. **[A/B]**
- [**Signup wizard**](signup-wizard.md) — three steps (Account/Profile/Review) with validators gating "Next". **[A/B]**
- [**Brazilian registration**](br-cadastro.md) — PF/PJ with CPF/CNPJ/phone/address masks and real-time BR validators. **[A/B]**
- [**Quiz with score**](quiz-app.md) — 5 questions with `RadioGroup`, a `ProgressBar`, and a final results screen. **[A/B]**

---

## Ready-made components (core)

The high-level components of `tempest_core` — shells, cards, and feedback out of the box.

- [**Core app shell**](core-app-shell.md) — `Scaffold` + `AppBar` + `NavBar` assembled in a few lines. **[A/B]**
- [**Tabbed settings**](core-tabbed-settings.md) — a `TabView` with preference sections. **[A/B]**
- [**Feedback & status**](core-feedback.md) — `Banner`, `Badge`, `EmptyState`, and `Spinner` in their states. **[A/B]**
- [**Profile cards**](core-profile-cards.md) — `Card` + `Avatar` + `Chip` composing a profile grid. **[A/B]**

---

## Layout and navigation

App shells, tabs, drawers, and routes.

- [**Tabbed profile**](tabs-profile.md) — `TabView` + `RouteChangeEvent` with three sections and a `Switch`. **[A/B]**
- [**Dashboard app shell**](dashboard-shell.md) — `Scaffold` + `AppBar` + `Sidebar` + `NavBar` with swappable sections. **[A/B]**
- [**Drawer navigation & routing**](router-drawer.md) — a sliding `RouteDrawer`, 2-level route push/pop, and a `Breadcrumb`. **[A/B]**
- [**Onboarding carousel**](onboarding-carousel.md) — `PageView` with `PageChangeEvent`, a dot indicator, and a completion screen. **[A/B]**

---

## Lists, media, and input

Virtualized lists, galleries, chat, search, and drag-and-drop.

- [**Image gallery**](image-gallery.md) — a virtualized 12-photo `LazyGrid` + a `Dialog` lightbox. **[A/B]**
- [**Chat UI**](chat-ui.md) — a virtualized `LazyColumn`, a two-way `Input`, and a Send `Button`. **[A/B]**
- [**Search with autocomplete**](search-autocomplete.md) — live filtering via `Autocomplete` + a `Chip` category filter. **[A/B]**
- [**Kanban board**](kanban-board.md) — three columns with `Draggable` cards and `DragTarget`s to move/delete. **[A/B]**

---

## Selection and feedback

Controls, disclosure, and feedback states.

- [**Settings panel**](settings-panel.md) — `Switch`, `Checkbox`, `Slider`, `RadioGroup`, and `SegmentedControl` bound to state. **[A/B]**
- [**Rating & review**](rating-review.md) — `Rating` stars + `Chip` tags + a `TextArea` in a validated form. **[A/B]**
- [**FAQ accordion**](faq-accordion.md) — a single-open `Accordion` with a live search filter. **[A/B]**
- [**Notification center**](notification-center.md) — `Banner`, an unread `Badge`, and an `EmptyState` for the empty inbox. **[A/B]**

---

## Theming, i18n, and canvas

Visual customization, internationalization, and drawing.

- [**Theme switcher**](theme-switcher.md) — `Theme`/`ThemeMode` with `App.set_theme`, `Theme.is_dark`, and OS simulation. **[A/B]**
- [**Internationalized greeting**](i18n-greeting.md) — `Locale` + `translate()`/`t()` across English, Portuguese, and Arabic (RTL). **[A/B]**
- [**Sketch pad (canvas)**](sketch-canvas.md) — strokes as draw-command lists (`MoveTo`/`LineTo`), presets, undo, and clear. **[A/B]**

---

## Native capabilities

The native bridge (`tempestweb.native`) exposes geolocation, HTTP, camera,
clipboard, share, and storage — always through injectable callables, so every
example runs deterministically in tests with a `FakeBridge`.

- [**Device panel**](device-panel.md) — four Tier 1 capabilities (`vibration`, `wakelock`, `fullscreen`, `network`) wired to buttons on a single screen. **[A/B]**
- [**Weather (HTTP + geolocation)**](weather-native.md) — a chained `async` handler combining `geolocation.get_position` and `http.request`. **[A/B]**
- [**Copy & share**](clipboard-share.md) — injected `clipboard.write` + `share.share`, driving two `async` handlers. **[A/B]**
- [**Camera capture**](photo-capture.md) — an `IDLE → CAPTURING → CAPTURED/ERROR` lifecycle with `camera.capture` and a data-URI preview. **[A/B]**
- [**Notes on device storage**](file-storage.md) — a notes CRUD over `storage.put/get/list_keys/remove`. **[A/B]**

---

## PWA and offline

Install-as-app, durable writes, and browser push notifications.

- [**PWA install + WebPush**](pwa-webpush.md) — a 7-phase consent flow + a `build_pwa.py` script emitting an installable manifest and icons. **[A/B]**
- [**Offline queue**](offline-queue.md) — durable writes via `native.offline` (enqueue → size → replay) that survive being offline. **[A/B]**
- [**WebPush end-to-end (server)**](webpush-server.md) — real VAPID push subscription + delivery from a FastAPI server. **[B]**

---

## Observability

Telemetry, feature flags, error boundaries, and auth — the blocks that make an
app production-ready.

- [**Feature flags**](feature-flags.md) — `FeatureFlagsProvider` + `InMemoryFeatureFlagsAdapter`: two flags swap widget variants live. **[A/B]**
- [**Error boundary + telemetry**](error-boundary.md) — an `ErrorBoundary` wrapping a boom-togglable child, with `on_error` wired to a `Logger` + `TelemetryProvider`. **[A/B]**
- [**JWT auth gate**](auth-jwt.md) — `AuthStore` + `route_guard`, JWTs decoded offline, and an audit trail via `Logger`. **[A/B]**

---

## Execution modes

The same `view` running on the server or transpiled, without changing a line.

- [**Running Mode B (server)**](server-mode.md) — the counter example running unchanged on a FastAPI WebSocket server via `TestClient`. **[B]**
- [**Mode C tour (transpile)**](transpile-tour.md) — an app with state+methods, navigation, i18n, theme, a form, and animation transcribed to native JS. **[A/B/C]**

---

## Minimal demos

Each isolates **a single capability** in the smallest possible code — great for a
one-sitting read. They have no dedicated page; run any of them with:

```bash
tempestweb dev --path examples/<dir>
```

They all run in **Modes A/B**.

- **`a11y_demo`** — a11y (`Semantics` → ARIA) + i18n (`translate`) + theme color on a single button.
- **`anim_demo`** — implicit CSS transitions: a `Style` with a `Transition` makes the browser tween the change.
- **`async_demo`** — an `async` handler that `await`s a timer and updates the UI without freezing the tab.
- **`geo_demo`** — the native geolocation capability (`native.get_position`) resolved in-process (Mode A) or proxied (Mode B).
- **`gesture_demo`** — a `GestureDetector` routing `on_swipe`/`on_tap` (pointer gestures) to Python handlers.
- **`list_demo`** — a `LazyColumn` declaring 1000 items but materializing only the visible window on scroll.
- **`login_demo`** — the ready-made login screen via the `LoginForm` component, no manual layout.
- **`overlay_demo`** — the floating overlay layer: a `Dialog` above the tree, dismissible by id.
- **`router_demo`** — URL-driven navigation: `view` renders the screen on top of `app.nav`.

---

!!! check "Ready to start?"
    Pick the example closest to what you want to build, copy its `app.py`, and run
    it in whichever modes make sense. They all pass the green gate (build, ruff,
    mypy `--strict`). Happy coding! 💡
