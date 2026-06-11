# Example Gallery 🎨

Welcome to the **tempestweb** gallery! 🚀 Here you'll find complete, ready-to-run
apps, each focused on **one concept** — state, forms, lists, navigation, theming,
i18n, canvas, and much more.

!!! tip "Two modes, one codebase"
    Every example is a typed-Python `view(app) -> Widget` module. The **same**
    `app.py` runs in both modes without changing a single line:

    - **Mode A (WASM/Pyodide)** — Python straight in the browser.
    - **Mode B (server)** — Python on a FastAPI server + a thin WebSocket client.

    The view tree never names a transport. You write the logic once and pick the
    mode at serve time.

!!! note "How to read each page"
    Every page follows the tutorial pattern: what you'll build → the minimal code
    → a piece-by-piece explanation → a **Recap** at the end. Start with
    [**Counter**](../tutorial/index.md) and the [**To-do list**](#fundamentals)
    if you're new here.

---

## Fundamentals

The building blocks — the starting point for everyone. These four are already
part of the [Tutorial](../tutorial/index.md).

- [**Counter**](../tutorial/index.md) — the reactive "hello world": state + handler + patch.
- [**To-do list**](../tutorial/state.md) — a controlled `Input`, a virtualized list, and per-item checkboxes.
- [**Form**](../tutorial/state.md) — `Form` + `FormField` + validators that mirror errors back onto state.
- [**Async fetch**](../tutorial/state.md) — an `idle → loading → loaded` transition via an `async` handler.

---

## State and data

Manage time, conversions, and tables fully deterministically.

- [**Stopwatch**](stopwatch.md) — Start/Stop/Lap/Reset with time stored as integer tenths-of-a-second (no wall clock).
- [**Temperature converter**](temperature-converter.md) — two controlled fields (Celsius/Fahrenheit) kept in sync via two-way binding.
- [**Data table**](data-table.md) — live search + per-column sort toggle (ASC/DESC), all driven from Python state.

---

## Forms and flows

From simple validation to a multi-step wizard.

- [**Login form**](login-form.md) — `EmailInput`/`PasswordInput`, three-layer validation, and an error `Banner`.
- [**Signup wizard**](signup-wizard.md) — three steps (Account/Profile/Review) with validators gating "Next".
- [**Brazilian registration**](br-cadastro.md) — PF/PJ with CPF/CNPJ/phone/address masks and real-time BR validators.
- [**Quiz with score**](quiz-app.md) — 5 questions with `RadioGroup`, a `ProgressBar`, and a final results screen.

---

## Layout and navigation

App shells, tabs, drawers, and routes.

- [**Tabbed profile**](tabs-profile.md) — `TabView` + `RouteChangeEvent` with three sections and a `Switch` in settings.
- [**Dashboard app shell**](dashboard-shell.md) — `Scaffold` + `AppBar` + `Sidebar` + `NavBar` with four swappable sections.
- [**Drawer navigation & routing**](router-drawer.md) — a sliding `RouteDrawer`, 2-level route push/pop, and a `Breadcrumb`.
- [**Onboarding carousel**](onboarding-carousel.md) — `PageView` with `PageChangeEvent`, a dot indicator, and a completion screen.

---

## Lists, media, and input

Virtualized lists, galleries, chat, search, and drag-and-drop.

- [**Image gallery**](image-gallery.md) — a virtualized 12-photo `LazyGrid` + a `Dialog` lightbox with Prev/Next/Close.
- [**Chat UI**](chat-ui.md) — a virtualized `LazyColumn`, a two-way `Input`, and a Send `Button` with an empty-message warning.
- [**Search with autocomplete**](search-autocomplete.md) — live filtering via `Autocomplete` + a `Chip` category filter.
- [**Kanban board**](kanban-board.md) — three columns with `Draggable` cards and `DragTarget`s to move/delete.

---

## Selection controls and feedback

Controls, disclosure, and feedback states.

- [**Settings panel**](settings-panel.md) — `Switch`, `Checkbox`, `Slider`, `RadioGroup`, and `SegmentedControl` bound to state.
- [**Rating & review**](rating-review.md) — `Rating` stars + `Chip` tags + a `TextArea` in a validated form.
- [**FAQ accordion**](faq-accordion.md) — a single-open `Accordion` with a live search filter.
- [**Notification center**](notification-center.md) — `Banner`, an unread `Badge`, and an `EmptyState` for the empty inbox.

---

## Theming, i18n, and canvas

Visual customization, internationalization, and drawing.

- [**Theme switcher**](theme-switcher.md) — `Theme`/`ThemeMode` with `App.set_theme`, `Theme.is_dark`, and OS simulation via `MediaQueryData`.
- [**Internationalized greeting**](i18n-greeting.md) — `Locale` + `translate()`/`t()` across English, Portuguese, and Arabic (RTL).
- [**Sketch pad (canvas)**](sketch-canvas.md) — strokes as draw-command lists (`MoveTo`/`LineTo`), presets, undo, and clear.

---

!!! check "Ready to start?"
    Pick the example closest to what you want to build, copy its `app.py`, and
    run it in both modes. They all pass the green gate (build, ruff, mypy
    `--strict`). Happy coding! 💡
