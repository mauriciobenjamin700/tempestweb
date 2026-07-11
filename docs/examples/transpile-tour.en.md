# Mode C tour — one app transpiled to native JS 🧭

**Modes: A/B/C** — this is the showcase example for **Mode C (transpile)**.

A single app that exercises the heart of the core — **state + methods**,
**navigation** (routes/URL), **i18n**, **theme + responsiveness**, a **validated
form** and an **animated box** (`AnimationController`) — running with **zero Python
in the browser**: the whole app is transcribed to native JavaScript. 🚀

!!! success "The same `view`, all three modes"
    This example is the Mode C showcase, but the **same** `view` runs unchanged in
    Modes A (WASM) and B (server). You write the logic once; the compiler decides
    whether it becomes native JS (C) or stays live Python (A/B). See the full guide
    in [Mode C — transpile](../transpile.md).

---

## What this example shows

- **Typed state with methods** — `TourState.set_email` validates and stores the email.
- **Route-based navigation** — `app.push(Route(...))` / `app.pop()` swap between the
  home screen and the form; the compiler transcribes the navigation stack.
- **i18n** — `t()` resolves strings from a translations dict, and the **lang** button
  switches languages live.
- **Theme + responsiveness** — `app.theme.is_dark(...)` and `app.media.width` derive
  the color scheme and layout (`wide`/`narrow`) from the environment.
- **Validated form** — the core's `validate_email` runs as native validation.
- **Animation** — an `AnimationController` + `Tween` interpolate a `Container`'s
  width, registered via `app.register_animation`.
- **Native capabilities in Mode C** — `native.install.prompt()` (PWA install) and
  `native.offline.enqueue/size` (durable queue) work in the static bundle too.

---

## Running ▶

```bash
# Static build (Mode C) — emits the native JS bundle:
tempestweb build --mode transpile --path examples/transpile-tour

# Dev with livereload (Mode C):
tempestweb dev --mode transpile --path examples/transpile-tour
```

!!! tip "Run it in Modes A/B too"
    ```bash
    tempestweb dev --mode wasm   --path examples/transpile-tour   # Python in the browser
    tempestweb dev --mode server --path examples/transpile-tour   # Python on the server
    ```
    Not a single line of `app.py` changes between modes.

---

## The code

```python
"""Mode C tour — one transpiled app exercising the core in native JS."""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import (
    App,
    Button,
    Column,
    Container,
    Locale,
    Route,
    Row,
    Style,
    Text,
    Theme,
    ThemeMode,
    Widget,
    t,
)
from tempest_core.animation import AnimationController, Tween
from tempest_core.style import Color, Curve, Edge
from tempest_core.validators import validate_email
from tempest_core.widgets import Input
from tempestweb import native

MESSAGES = {
    "pt": {"title": "Tour do Modo C", "home": "Início", "form": "Formulário"},
    "en": {"title": "Mode C tour", "home": "Home", "form": "Form"},
}


@dataclass
class TourState:
    """State for the tour."""

    lang: str = "pt"
    email: str = ""
    email_error: str = ""
    install: str = ""
    queued: int = 0
    box: object = field(default=None)

    def set_email(self, value: str) -> None:
        """Store the email and its validation result."""
        self.email = value
        self.email_error = validate_email(value) or "ok"


def make_state() -> TourState:
    """Build the initial state with an animation controller."""
    state = TourState()
    state.box = AnimationController(0.5, curve=Curve.EASE_OUT)
    return state


def view(app: App[TourState]) -> Widget:
    """Render the tour, branching on the current route."""
    loc = Locale(language=app.state.lang)
    dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    wide = app.media.width >= 600.0

    def toggle_lang() -> None:
        app.set_state(lambda s: setattr(s, "lang", "en" if s.lang == "pt" else "pt"))

    def toggle_theme() -> None:
        app.set_theme(Theme(mode=ThemeMode.LIGHT if dark else ThemeMode.DARK))

    def go_form() -> None:
        app.push(Route(name="/form"))

    def go_home() -> None:
        app.pop()

    def on_email(event: object) -> None:
        value = event.payload["value"]
        app.set_state(lambda s: s.set_email(value))

    def grow() -> None:
        app.state.box.forward()
        app.register_animation(app.state.box)

    async def do_install() -> None:
        outcome = await native.install.prompt()
        app.set_state(lambda s: setattr(s, "install", outcome))

    async def queue_write() -> None:
        await native.offline.enqueue("POST", "/api/log", {"n": app.state.queued})
        count = await native.offline.size()
        app.set_state(lambda s: setattr(s, "queued", count))

    header = Row(
        style=Style(gap=8.0),
        children=[
            Text(content=t("title", locale=loc, translations=MESSAGES), key="title"),
            Text(content=("dark" if dark else "light"), key="scheme"),
            Text(content=("wide" if wide else "narrow"), key="layout"),
        ],
    )
    controls = Row(
        style=Style(gap=8.0),
        children=[
            Button(label="lang", on_click=toggle_lang, key="lang"),
            Button(label="theme", on_click=toggle_theme, key="theme"),
        ],
    )

    if app.nav.top.name == "/form":
        body = Column(
            style=Style(gap=10.0),
            children=[
                Text(content=t("form", locale=loc, translations=MESSAGES), key="fh"),
                Input(
                    value=app.state.email,
                    placeholder="email",
                    on_change=on_email,
                    key="email",
                ),
                Text(content=app.state.email_error, key="err"),
                Button(
                    label=t("home", locale=loc, translations=MESSAGES),
                    on_click=go_home,
                    key="back",
                ),
            ],
        )
    else:
        width = Tween(begin=120.0, end=320.0).at(app.state.box.value)
        body = Column(
            style=Style(gap=10.0),
            children=[
                Container(
                    key="box",
                    style=Style(
                        width=width,
                        height=48.0,
                        background=Color(r=103, g=80, b=164, a=1.0),
                        radius=8.0,
                        transition=None,
                    ),
                    children=[],
                ),
                Button(label="grow", on_click=grow, key="grow"),
                Button(label="install", on_click=do_install, key="install"),
                Text(content=app.state.install, key="installout"),
                Button(label="queue", on_click=queue_write, key="queue"),
                Text(content=f"queued={app.state.queued}", key="queuedout"),
                Button(
                    label=t("form", locale=loc, translations=MESSAGES),
                    on_click=go_form,
                    key="toform",
                ),
            ],
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24)),
        children=[header, controls, body],
    )
```

---

## Piece by piece

### State with a method

`TourState` is not just a bag of fields: `set_email` encapsulates the business rule
(store the value **and** revalidate). Mode C transcribes dataclass methods to JS —
which is why the example uses them instead of mutating state inline in the handler.

### Navigation drives the body

```python
if app.nav.top.name == "/form":
    ...   # form screen
else:
    ...   # home screen with the animated box
```

The `view` branches on the **top of the navigation stack**. `go_form` pushes the
`/form` route; `go_home` calls `pop()`. In Mode C this becomes native URL history.

### i18n, theme and responsiveness derived from the environment

```python
loc = Locale(language=app.state.lang)
dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
wide = app.media.width >= 600.0
```

None of this lives in app state — it is all **derived** on every render from
`app.theme`, `app.media` and `app.state.lang`. The **lang** button just flips one
string; everything else recomputes on its own.

### Animation with `AnimationController` + `Tween`

```python
width = Tween(begin=120.0, end=320.0).at(app.state.box.value)
```

`grow()` calls `box.forward()` and registers the controller with
`app.register_animation`. The runtime advances the value every frame and
re-renders; the `Tween` maps `0.0 → 1.0` onto `120px → 320px`.

!!! info "Native capabilities in Mode C"
    `do_install` and `queue_write` are `async` handlers calling
    `native.install.prompt()` and `native.offline.enqueue/size`. Mode C has a
    **complete PWA story** — install, offline and the mutation queue work in the
    static bundle, with no Python server.

---

## Recap

In this example you saw:

- ✅ A **single app** exercising state+methods, navigation, i18n, theme,
  responsiveness, a validated form and animation
- ✅ **Mode C** transcribing all of it to **native JavaScript** — zero Python in
  the browser
- ✅ That the **same `view`** runs unchanged in Modes A/B
- ✅ Native capabilities (PWA install, offline queue) running in the static bundle

---

## Next steps

- 💡 Read [Mode C — transpile](../transpile.md) for the supported subset and build pipeline
- 💡 See [Offline queue](offline-queue.md) for a deep dive on `native.offline`
- 💡 Explore [PWA & offline](../pwa.md) for install and end-to-end WebPush
