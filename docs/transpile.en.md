# Mode C — transpile (Python → native JavaScript) 🧪

Modes A (WASM) and B (server) keep **Python alive** at runtime — in the browser
(Pyodide) or on the server. **Mode C** is different: a compiler transcribes the
**app layer** of your typed Python into **native JavaScript**. Zero Python
runtime, static hosting, great first paint and SEO. It's the "TypeScript story"
for Python. 🚀

!!! warning "Experimental (spike)"
    Mode C is under construction. It already runs counter-style apps — state,
    `view()`, handlers, styled Button/Input — but the API may change and the
    accepted Python subset is still narrow. For rich screens today, use Modes
    A/B; come back to Mode C as it matures.

## Why it exists

| | Mode A (WASM) | Mode B (server) | **Mode C (transpile)** |
|---|---|---|---|
| Python runtime | browser (~6 MB Pyodide) | live server | **none** |
| First paint / SEO | poor | good | **great** |
| Hosting | static | server + WS/client | **static** |
| Scale cost | zero server | stateful per client | **zero server** |

The trick: the JS client (`dom.js`, `style.js`, `events.js`) is already native and
shared by all three modes. Mode C **does not transpile all of Python** — only the
app layer; the whole renderer stays the same JS.

## Your first build

Take the counter app (the same one that runs in Modes A/B, unchanged):

```python
from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    value: int = 0


def make_state() -> CounterState:
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

Generate the static bundle:

```bash
tempestweb build --mode transpile --path examples/counter
```

This writes a **fully static** `dist/transpile/` directory — no Python:

```text
dist/transpile/
├── index.html                     # mounts the app via mountApp
└── client/
    ├── tempestweb.js dom.js style.js events.js …   # the shared client
    └── transpile/
        ├── app.gen.js             # your app.py transcribed to native JS
        ├── runtime.js widgets.js diff.js
        └── widget-styles.gen.js   # MD3 styles resolved from the core
```

Serve it with any static host (or locally):

```bash
tempestweb run --mode transpile --path examples/counter
```

While developing, use the **livereload** loop — edit `app.py` and the browser
reloads with the recompiled bundle:

```bash
tempestweb dev --mode transpile --path examples/counter
```

!!! check "What happened"
    Your `view()` became `app.gen.js` — native JavaScript. The runtime holds the
    state, runs `view()`, **diffs** in JS and applies **granular patches** to the
    DOM. No Python is downloaded or executed in the browser.

## What the compiler emits

The `app.py` above becomes, in essence:

```javascript
import { State } from "./runtime.js";
import { Button, Column, Edge, Row, Style, Text } from "./widgets.js";

export class CounterState extends State {
  constructor() {
    super();
    this.value = 0;
  }
}

export function makeState() {
  return new CounterState();
}

export function view(app) {
  const increment = () => {
    app.setState((s) => {
      s.value = (s.value + 1);
    });
  };
  // …
  return Column({
    style: Style({ gap: 8.0, padding: Edge.all(16) }),
    children: [
      Text({ content: `Count: ${app.state.value}`, key: "label" }),
      // …
    ],
  });
}
```

!!! note "Naming conventions"
    The compiler translates the API to idiomatic JS: `make_state` → `makeState`,
    `set_state` → `setState`, `on_click` → `onClick`, `color_scheme` →
    `colorScheme`. `setattr(s, "x", v)` becomes `s.x = v`; f-strings become
    template literals.

## State with methods

You are not limited to `setattr` lambdas. A `@dataclass` with methods transpiles
to a JS class — `self` becomes `this`:

```python
@dataclass
class Counter:
    value: int = 0

    def increment(self) -> None:
        self.value += 1


def view(app: App[Counter]) -> Widget:
    def inc() -> None:
        app.set_state(lambda s: s.increment())

    return Button(label="+", on_click=inc, key="inc")
```

## Reactive form fields

`Input` resolves its Material 3 style and wires `on_change`. Binding is two-way:
typing fires the handler, which updates the state and re-renders.

```python
from tempest_core import App, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Input


@dataclass
class FormState:
    name: str = ""


def view(app: App[FormState]) -> Widget:
    def on_name(event) -> None:
        app.set_state(lambda s: setattr(s, "name", event.payload["value"]))

    return Column(
        style=Style(gap=12.0, padding=Edge.all(24)),
        children=[
            Text(content=f"Hello, {app.state.name or 'stranger'}!", key="greet"),
            Input(value=app.state.name, placeholder="Your name", on_change=on_name, key="name"),
        ],
    )
```

Type in the field and the greeting updates live — no server, no Python. ✨

## Native capabilities (requests, storage, cookies…)

The same typed `native` API from Modes A/B works in Mode C — `async` calls are
transcribed to in-process JS calls into the shared browser glue (`fetch`,
IndexedDB/localStorage, `document.cookie`). No Python, no network.

```python
from tempestweb import native


@dataclass
class DataState:
    body: str = ""


def view(app: App[DataState]) -> Widget:
    async def fetch_it() -> None:
        res = await native.http.request("GET", "/api/items")
        await native.storage.put("last", res.body)
        await native.cookies.set("seen", "1")
        app.set_state(lambda s: setattr(s, "body", res.body))

    return Button(label="fetch", on_click=fetch_it, key="go")
```

!!! tip "`async` handlers"
    A handler may be `async def` and use `await`. The re-render happens when
    `set_state` runs (after the `await`), so the UI reflects the result as soon as
    the capability resolves. Capabilities available in Mode C: `http`, `storage`
    (IndexedDB/localStorage), `clipboard`, `geolocation`, `cookies`, `share`,
    `audio`, `file`, `notifications` (incl. WebPush `subscribe`/`unsubscribe`),
    `install` (PWA install prompt), `offline` (durable mutation queue).

!!! tip "Install the PWA (`native.install`)"
    `await native.install.state()` reports `{can_install, installed}`; after a
    user gesture, `await native.install.prompt()` fires the native install prompt
    and resolves with `"accepted"`, `"dismissed"` or `"unavailable"`. The
    controller already suppresses the browser's cold mini-infobar, so you show an
    "Install" button at the right moment.

!!! tip "Push (`native.notifications`)"
    `await native.notifications.push_state()` reports `{supported, permission}`
    **without** prompting — use it to decide whether to show the button. `await
    native.notifications.request_permission()` asks for permission; `await
    native.notifications.subscribe(vapid_public_key)` runs the browser WebPush
    flow and returns the **subscription JSON** — you send it to your own backend
    (via `native.http`, or queued with `native.offline`). `unsubscribe()`
    cancels. The framework decides neither your endpoint schema nor the push
    server: it just hands you the raw subscription.

!!! tip "Offline queue (`native.offline`)"
    Writes made offline survive: `await native.offline.enqueue("POST", url,
    body)` records a durable mutation in IndexedDB (with an idempotency key) and
    replay happens in FIFO order when connectivity returns — via the `online`
    event, via Background Sync (tab closed) or explicitly with `await
    native.offline.replay()`. Inspect with `native.offline.size()` and
    `native.offline.pending()`. The server dedups on the idempotency key, so a
    replay never double-applies.

!!! tip "Field validators"
    `from tempest_core.validators import validate_email, validate_cpf,
    validate_cnpj, validate_phone` runs **client-side** in Mode C, with the same
    algorithm and PT-BR messages as the core (a faithful port, locked by a
    fixture). Pairs with `Input` + state for validated, server-free forms.

## Navigation (routes + URL)

Mode C speaks the same navigation as Modes A/B: `app.push(Route(...))`,
`app.pop()`, `app.replace(...)`, `app.nav.top` — synced with the browser URL
(deep links + back/forward) automatically.

```python
from tempest_core import App, Button, Column, Route, Text, Widget


def view(app: App[MyState]) -> Widget:
    def open_product() -> None:
        app.push(Route(name="/products/42"))

    route = app.nav.top
    return Column(children=[
        Text(content=f"route: {route.name}", key="r"),
        Button(label="open product", on_click=open_product, key="p"),
        Button(label="back", on_click=lambda e: app.pop(), key="b"),
    ])
```

!!! info "URL ↔ stack"
    `app.push`/`pop` push/pop the URL (`pushState`); a deep link or the browser
    back button reset the stack from the path (`routes_from_path`) — identical to
    Modes A/B. **Path/query params:** the route `name` carries the full path
    (including `?query`), as the core models it; read segments via
    `app.nav.stack`. A typed-param router is a core-level evolution.

## Localization (i18n)

The core's `translate` / `t` + `Locale` work in Mode C: look a key up in the
`{language: {key: template}}` table by the locale's language and interpolate
`{name}` — same semantics and fallbacks as the core (missing key/language → the
key itself).

```python
from tempest_core import App, Locale, Text, Widget, t

MESSAGES = {
    "pt": {"greet": "Olá, {name}!"},
    "en": {"greet": "Hello, {name}!"},
}


def view(app: App[MyState]) -> Widget:
    loc = Locale(language=app.state.lang)
    return Text(content=t("greet", locale=loc, translations=MESSAGES, name="Ana"), key="g")
```

Flip `app.state.lang` in a handler and the UI re-renders in the new language —
verified live (Playwright, PT → EN). The `MESSAGES` table is a **module constant**
(now supported in the subset).

## Theme + responsiveness

Mode C exposes `app.theme` and `app.media` like Modes A/B.
`app.theme.is_dark()` resolves light/dark (`DARK`/`LIGHT` absolute; `SYSTEM`
follows the OS); `app.media` carries `width`/`height`/`platform_dark_mode`/
`orientation`, synced with the browser (matchMedia + resize) so the UI
**re-renders responsively**.

```python
from tempest_core import App, Column, Text, Theme, ThemeMode, Widget


def view(app: App[MyState]) -> Widget:
    dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    wide = app.media.width >= 600.0

    def toggle() -> None:
        app.set_theme(Theme(mode=ThemeMode.LIGHT if dark else ThemeMode.DARK))

    return Column(children=[
        Text(content=("dark" if dark else "light"), key="s"),
        Text(content=("wide" if wide else "narrow"), key="l"),
    ])
```

!!! check "Adaptive responsiveness"
    Resize the window or change the OS `prefers-color-scheme` and `view`
    re-renders — verified in the browser (400px→narrow, 900px→wide; theme toggle
    light↔dark). The core breakpoints (`Breakpoints`: sm/md/lg/xl) are available
    too.

## Animation (transitions)

Animate declaratively: give a widget's `Style` a `Transition` and the **browser**
tweens it when a styled field changes (width, color, opacity) — no Python
runtime, no frame driver.

```python
from tempest_core import App, Container, Style, Widget
from tempest_core.style import Color, Curve, Transition


def view(app: App[MyState]) -> Widget:
    w = 320.0 if app.state.big else 120.0
    return Container(key="box", style=Style(
        width=w,
        background=Color(r=103, g=80, b=164, a=1.0),
        transition=Transition(duration_ms=400, curve=Curve.EASE_IN_OUT),
    ))
```

!!! check "Verified"
    Flipping `app.state.big` in a handler animates the width 120→320px over 400ms
    (Playwright confirmed the CSS transition is applied). Curves: `linear`,
    `ease`, `ease-in`, `ease-out`, `ease-in-out`, `bounce`, `elastic`.

### Imperative animation (AnimationController)

For frame-driven control, use `AnimationController` + `Tween` — the runtime drives
the controllers on a `requestAnimationFrame` loop, computing the value each frame
and re-rendering.

```python
from tempest_core.animation import AnimationController, Tween
from tempest_core.style import Curve


def make_state() -> S:
    s = S()
    s.anim = AnimationController(0.6, curve=Curve.EASE_OUT)
    return s


def view(app: App[S]) -> Widget:
    w = Tween(begin=100.0, end=340.0).at(app.state.anim.value)

    def go() -> None:
        app.state.anim.forward()
        app.register_animation(app.state.anim)

    return Container(key="box", style=Style(width=w))
```

`forward()`/`reverse()`/`stop()`, eased curves **and springs** (`Spring`) — the
same math as the core. Verified in the browser: the width animates 100→340
(ease-out) and settles. **This closes 100% of tempest-core coverage in Mode C.**

## The complete tour

Everything above — state with methods, navigation, i18n, theme + responsiveness,
a validated form and an imperative animation — lives together in one reference
app, [`examples/transpile-tour`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/transpile-tour/app.py):

```bash
tempestweb build --mode transpile --path examples/transpile-tour
tempestweb dev   --mode transpile --path examples/transpile-tour   # livereload
```

!!! tip "One `view`, every mode"
    The tour's `view()` runs unchanged in Modes A and B. `build` proves it by
    rendering through the real core — an API that only existed in Mode C would
    break the build, so the tour is living proof of portability.

## PWA: installable and offline

You already have a 100% static, Python-free bundle — the **perfect** target for a
PWA. That's why `build --mode transpile` now emits the whole PWA layer **by
itself**: users can **install** your app to their home screen and, after the first
visit, open it **offline**. No extra step, nothing to wire up. 🚀

Just the usual build:

```bash
tempestweb build --mode transpile --path examples/transpile-tour
```

Alongside the app bundle, Mode C now writes the PWA layer next to it:

```text
dist/transpile/
├── index.html               # links the manifest, theme-color, apple-touch-icon
│                            #   and registers the service worker
├── manifest.webmanifest     # install metadata (name, icons, colors)
├── sw.js                    # cache-first service worker (app shell)
├── register.js              # registers sw.js on load
├── icons/                   # the icon set (maskable + apple-touch)
└── client/ …                # the shared client + your app.gen.js
```

`sw.js` **precaches the entire static bundle** — `index.html`, the shared client,
`client/transpile/*` (including your `app.gen.js`), the native tree, the icons and
the manifest. After the first load, the app opens and runs **with no network**.

!!! tip "Real offline ✅"
    This isn't half-baked offline: with the HTTP server **killed**, reloading the
    page still **renders the tour** and navigation keeps working — verified live
    with Playwright (server down, reload, tour intact). Because Mode C is a static,
    Python-free bundle, nothing depends on the server after the first fetch.

### Configuring the manifest with `[pwa]`

Install metadata comes from an optional `[pwa]` section in your `tempestweb.toml`.
Every field is optional — without the section, the build uses sensible defaults
derived from the project name:

```toml
[pwa]
name = "Weather Pro"
short_name = "WPro"
theme_color = "#0a84ff"
display = "standalone"
```

| Field | Type | Default | What it does |
|---|---|---|---|
| `name` | string | project name | Full name shown at install/splash. |
| `short_name` | string | — | Short name for the home-screen icon. |
| `description` | string | — | App description in the install prompt. |
| `theme_color` | string | `"#111111"` | Theme color (browser bar + `<meta name="theme-color">`). |
| `background_color` | string | `"#ffffff"` | Splash-screen background color. |
| `display` | string | `"standalone"` | Display mode: `standalone`, `fullscreen`, or `minimal-ui`. |
| `orientation` | string | — | Preferred orientation (e.g. `portrait`, `landscape`). |
| `lang` | string | `"pt-BR"` | Primary app language. |
| `categories` | list of string | — | App-store categories (e.g. `["productivity"]`). |

!!! warning "Valid `display` value"
    `display` accepts only `"standalone"`, `"fullscreen"`, or `"minimal-ui"`. Any
    other value is a **build error** — it fails early, in the spirit of the rest of
    the Mode C compiler.

!!! note "Automatic in Mode C"
    You don't have to hand-write a service worker, manifest, or registration code:
    `build --mode transpile` generates all of it. The `[pwa]` section only **tunes**
    the install metadata — offline behavior comes for free because the bundle is
    static.

!!! tip "Update prompt"
    When you ship a new version the old service worker keeps serving until the tab
    closes. The shell detects the waiting worker and shows an unobtrusive **"new
    version available → Reload"** banner; on confirm the new worker takes over and
    the page reloads once. Automatic — nothing to write in the app.

## The supported subset

Mode C accepts a **typed subset** of Python — enough for the app layer. A
construct outside it becomes a clear **compile error** (`file:line`), in the
spirit of `mypy --strict`.

!!! info "In the subset today"
    - **Expressions:** arithmetic (`+ - * / %`), comparison (`== != < <= > >=`),
      boolean (`and`/`or`), unary (`not`/`-`), ternary (`a if c else b`), list
      and dict comprehensions (`[e for x in it if c]`, `{k: v for x in it}`),
      `list`/`tuple`/`set`/`dict` literals, `in`/`not in`, indexing, f-strings
      (formats `{x:.2f}`, `{x:,}`, `{x:,.2f}`, `{x:.1%}`, `{x:d}`; conversions
      `{x!s}`, `{x!r}`), expression lambdas.
    - **Builtins:** `len`, `str`/`int`/`float`/`bool`, `abs`, `round(x[, n])`,
      `min`/`max` (variadic or over one iterable), `sum(it)`, `range(...)`
      (materialized to an array).
    - **Statements:** `if`/`elif`/`else`, `for … in`, `while`, `break`/
      `continue`, `try`/`except`/`finally` (a single `except` catches all;
      multiple dispatch by exception class name), `with … as x` (the
      `__enter__`/`__exit__` protocol), assignment, `+=` and friends, `return`.
    - **Structures:** a state `@dataclass` (fields + methods), dataclass
      inheritance (`class B(A)` → `extends`), `make_state()`, `view()` with
      handler closures.
    - **Layout components:** `HStack` / `VStack` (SwiftUI-style ergonomic
      aliases) — `gap` as a token (`"md"`) or px, `align`/`justify` direct.
    - **Widgets:** **all ~64 `tempest_core` widgets** — layout (`Column`, `Row`,
      `Container`, `Stack`, `Wrap`, `ScrollView`, `SafeArea`, `Spacer`), display
      (`Text`, `Icon`, `Image`, `Svg`, `Spinner`, `Skeleton`, `ProgressBar`),
      input (`Button`, `Input`, `TextArea`, `Switch`, `Checkbox`, `Slider`,
      `RangeSlider`, `Dropdown`, `DatePicker`, …), overlays (`Dialog`,
      `BottomSheet`, `Popover`, `Toast`, `Tooltip`), gestures (`GestureDetector`,
      `Draggable`, `PanHandler`, …), and more. The JS builders are **generated**
      by introspecting the core (`widgets.gen.js`), with the resolved MD3 style
      for the 14 styled widgets.

!!! note "Per-widget events"
    Each handler binds to the DOM event the renderer (`dom.js`) emits for that
    widget: `Button.on_click` → click; `Input`/`Checkbox` (native controls) →
    `input`/`change`; a `Switch` (a div) → click. Handlers for widgets whose
    event the client does not yet emit (e.g. `on_scan`, `on_reorder`) are
    registered but inert for now.

!!! warning "Still outside the subset"
    Most of `tempest_core.components` (Card, DataTable, Tabs, charts, form
    inputs …). Unlike the widgets, components are **Python composition** that
    expands to primitives at `build()` time — many from data/loops — so they are
    not auto-portable to a Python-free runtime. The layout aliases `HStack` /
    `VStack` are the exception (they expand to `Row`/`Column`). Also out:
    multi-loop or destructured comprehensions (`for k, v in …`), and f-string
    format specs beyond the supported set (e.g. alignment `{x:>5}`, sign
    `{x:+.2f}`, hex/bin `{x:x}`, dynamic `{x:.{n}f}`, the `!a` conversion).

## Recap

- **Mode C** transcribes the Python app layer to **native JS** — zero Python
  runtime, a static bundle, great first paint/SEO.
- `tempestweb build --mode transpile` produces a directory servable by any CDN;
  `run --mode transpile` serves it locally.
- The same `view()` from Modes A/B runs here — state, handlers, styled
  `Button`/`Input`, reactive binding.
- It's **experimental**: narrow subset, API subject to change. Design details in
  [`docs/modo-c-transpile.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/modo-c-transpile.md).
