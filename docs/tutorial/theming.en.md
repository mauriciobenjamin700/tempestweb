# Theming (Material 3)

Your widgets are good-looking from the start. A bare `Button` becomes a **Material
3 filled button** — pill shape, primary fill, a state layer on hover, elevation. A
bare `Input` becomes an **outlined field** with an animated focus. You write **no**
CSS for any of it. ✨

This is the **always-on base theme** that landed in 0.6.0: a small Material 3
stylesheet (`client/theme.js`) injected **once**, at mount, that gives every app
sensible typography, spacing and accented controls — even one you never styled. And
when you want to break out of the defaults, the widget's inline `Style` **always
wins**.

!!! note "Where the style comes from (tempest-core ≥ 0.8.1)"
    Each `Button`/`Input`'s **resting look** — fill, border, shape and color — now
    comes from **tempest-core's variant system**, resolved inline by the widget
    itself. `client/theme.js` handles only what inline style **cannot** express:
    the hover/focus/press state layer (`::before`), the focus ring and the font
    family. The `filled_button`/`tonal_button`/… helpers are an MD3-named façade
    over the core variants. You still get the Material 3 look with **zero** CSS.

## The minimum: rely on the base theme

There is nothing to configure. Write the app normally; the base theme installs
itself.

```python
from dataclasses import dataclass

from tempest_core import App, Button, Column, Input, Text, Widget


@dataclass
class State:
    name: str = ""


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    def set_name(event) -> None:
        app.set_state(lambda s: setattr(s, "name", event.value))

    return Column(
        children=[
            Text(content="What's your name?"),
            Input(value=app.state.name, on_change=set_name, key="name"),
            Button(label=f"Hello, {app.state.name or 'world'}!", key="hello"),
        ],
    )
```

Run it in all three modes — it looks identical:

```bash
tempestweb dev --mode wasm       # Python in the browser (Pyodide)
tempestweb dev --mode server     # Python on the server (FastAPI + WebSocket)
tempestweb dev --mode transpile  # app transcribed to native JS (static bundle)
```

What you just got for free:

- **Typography** — the `Roboto`/`system-ui` family instead of the browser's Times
  New Roman, on `Text`, `Button` and `Input`.
- **Button** — a filled pill in the primary color, a translucent state layer on
  hover/focus/press, and animated elevation.
- **Field** — a rounded outlined `Input` whose border thickens and recolors to the
  primary tone on focus.
- **Checkbox** — a box sized and accented with the primary color.

!!! info "Why a stylesheet and not inline `Style`?"
    Inline CSS cannot express `:hover`, `:focus-visible`, `:active` or `:disabled`
    — the very states that make a control feel modern. Those live in the base
    sheet, keyed off the `data-tw-type` attribute the DOM renderer stamps on every
    element.

## Overriding the theme: inline `Style` wins

The base sheet is a **floor, not a cage**. Because it uses no `!important` and a
widget's `Style` becomes an inline `style=""` on the element, your declarations beat
the cascade. The interaction states (hover/focus) keep working on top.

```python
from tempest_core import Button, Style
from tempest_core.style import Color

# The pill, the typography and the state layer stay — only the color changes.
Button(
    label="Buy now",
    style=Style(background=Color.from_hex("#0b57d0")),
    key="buy",
)
```

!!! tip "Global rebrand via tokens"
    The theme tokens are CSS custom properties on `:root` (`--tw-primary`,
    `--tw-surface`, `--tw-outline`, …). To re-theme the whole UI without touching a
    single widget, override them from your own `<style>` on the host page:

    ```css
    :root { --tw-primary: #0b57d0; }
    ```

## Elevation with `Style(shadow=...)`

In 0.6.0, a `Shadow` on a widget's `Style` becomes a **real CSS `box-shadow`** on
the web — the same elevation the native renderers (Qt/Compose) draw. The mapping is
direct: `offset_x offset_y blur color`.

```python
from tempest_core import Column, Text, Widget
from tempest_core.style import Color, Edge, Shadow, Style


def card(content: str) -> Widget:
    return Column(
        children=[Text(content=content)],
        style=Style(
            background=Color.from_hex("#ffffff"),
            radius=12.0,
            padding=Edge.all(16.0),
            shadow=Shadow(
                color=Color(r=0, g=0, b=0, a=0.3),
                blur=3.0,
                offset_x=0.0,
                offset_y=1.0,
            ),
        ),
        key="card",
    )
```

This emits `box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.3)`. A `Shadow` with no explicit
`color` falls back to a neutral translucent black, so an elevation still reads even
without picking a tint.

!!! note "The same MD3 elevation levels"
    The base sheet defines `--tw-elevation-1` and `--tw-elevation-2` (umbra +
    penumbra) and applies them to the filled button on hover/press. When you want a
    card or button with its own elevation, use `Style(shadow=...)` — the numbers
    above (`blur=3, offset_y=1`) are exactly the resting shadow of
    `elevated_button`.

## Material 3 button variants

You don't have to remember which colors compose a _tonal_ or _outlined_ button.
`tempestweb.components` ships all five MD3 variants as one-line helpers:

```python
from tempest_core import App, Row, Widget
from tempestweb.components import (
    elevated_button,
    filled_button,
    outlined_button,
    text_button,
    tonal_button,
)


def view(app: App[State]) -> Widget:
    def save() -> None:
        app.set_state(lambda s: s)

    return Row(
        children=[
            filled_button("Save", on_click=save, key="save"),
            tonal_button("Duplicate", key="dup"),
            elevated_button("Export", key="export"),
            outlined_button("Edit", key="edit"),
            text_button("Cancel", key="cancel"),
        ],
    )
```

| Helper | Emphasis | How it's built |
|---|---|---|
| `filled_button` | High (default) | A bare button — the base theme gives the full filled look |
| `tonal_button` | Medium | A _secondary container_ fill + on-container text, flat |
| `elevated_button` | Medium | A light surface + primary text + a resting shadow |
| `outlined_button` | Medium | An outline + primary label, transparent fill |
| `text_button` | Low | Just the primary label, no fill or outline |

!!! info "How the variants tell themselves apart from filled"
    `filled_button` is a `Button` with **no** inline `Style`, so the base theme
    supplies everything. The other variants get a small `Style` (background / color
    / border / shadow). Setting an inline `background` is also the signal the base
    sheet uses to **opt a variant out** of the filled button's automatic
    elevation — that's why tonal/outlined/text stay flat while `elevated_button`
    carries its own shadow.

## Themed fields

The tempestweb-native fields — `TextField`, `EmailField`, `PasswordField` — use a
bare `Input` with **no** inline `Style` on purpose, precisely so the base sheet
renders them as light, outlined fields consistent with the rest of the UI. A muted
label sits above and a red error line appears when you pass `error`.

```python
from tempest_core import App, Column, Widget
from tempestweb.components import EmailField, PasswordField, validate_email


def view(app: App[State]) -> Widget:
    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    def set_password(value: str) -> None:
        app.set_state(lambda s: setattr(s, "password", value))

    return Column(
        children=[
            EmailField(
                value=app.state.email,
                on_change=set_email,
                error=validate_email(app.state.email) or "",
                key="email",
            ),
            PasswordField(
                value=app.state.password,
                on_change=set_password,
                key="password",
            ),
        ],
    )
```

!!! tip "More on fields and forms"
    The fields and the ready-made forms (`LoginForm`, `SignupForm`, the BR fields)
    have their own page in [Ready-made components](components.md). Here the focus is
    only on how the theme makes them look finished without styling anything.

## Recap

- The **Material 3 base theme is always on** — typography, spacing and accented
  controls come ready, with no per-widget styling.
- The **widget's inline `Style` always wins** over the base sheet (no `!important`);
  the hover/focus states keep working on top.
- Re-theme the whole UI by overriding the `--tw-*` tokens from a `<style>` on the
  page.
- `Style(shadow=...)` becomes a **CSS `box-shadow`** on the web, matching the native
  renderers.
- `filled_button` / `tonal_button` / `elevated_button` / `outlined_button` /
  `text_button` are the five MD3 variants, one line each.
- `TextField` / `EmailField` / `PasswordField` inherit the outlined field from the
  theme.
- Everything renders the same in Mode A (WASM) and Mode B (server).
