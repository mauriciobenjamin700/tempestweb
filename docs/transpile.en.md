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
    `audio`, `file`, `notifications`.

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

## The supported subset

Mode C accepts a **typed subset** of Python — enough for the app layer. A
construct outside it becomes a clear **compile error** (`file:line`), in the
spirit of `mypy --strict`.

!!! info "In the subset today"
    - **Expressions:** arithmetic (`+ - * / %`), comparison (`== != < <= > >=`),
      boolean (`and`/`or`), unary (`not`/`-`), ternary (`a if c else b`), list
      comprehensions (`[e for x in it if c]`), `in`/`not in`, indexing,
      f-strings, expression lambdas.
    - **Statements:** `if`/`elif`/`else`, `for … in`, assignment, `+=` and
      friends, `return`.
    - **Structures:** a state `@dataclass` (fields + methods), `make_state()`,
      `view()` with handler closures.
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
    dict/set/tuple and f-strings with a format spec.

## Recap

- **Mode C** transcribes the Python app layer to **native JS** — zero Python
  runtime, a static bundle, great first paint/SEO.
- `tempestweb build --mode transpile` produces a directory servable by any CDN;
  `run --mode transpile` serves it locally.
- The same `view()` from Modes A/B runs here — state, handlers, styled
  `Button`/`Input`, reactive binding.
- It's **experimental**: narrow subset, API subject to change. Design details in
  [`docs/modo-c-transpile.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/modo-c-transpile.md).
