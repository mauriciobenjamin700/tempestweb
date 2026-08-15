# Icons (Material + Lucide)

Your app needs a menu glyph, a lock in the password field, a back arrow?
tempestweb ships **two vendored icon sets** — **Lucide** (the default, inherited
from the core) and **Material Symbols (Outlined)** — drawn client-side as
**inline SVG**. No icon font, no network, no CDN: it works **offline** and inside
a PWA. 🎯

You pick the set in one obvious call, in **typed Python**:

```python
from tempestweb.icons import material_icon, lucide_icon, MaterialIcons, Icons

material_icon(MaterialIcons.HOME)   # Material Symbols "home"
lucide_icon(Icons.MAIL)             # Lucide "mail"
```

## The minimum: one icon on screen

An `Icon` is a widget like any other. Drop it in a `Column`/`Row` and you're done:

```python
from dataclasses import dataclass

from tempest_core import App, Column, Row, Text, Widget

from tempestweb.icons import MaterialIcons, material_icon


@dataclass
class State:
    pass


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    return Row(
        children=[
            material_icon(MaterialIcons.HOME),
            Text(content="Home"),
        ],
    )
```

Run it in all three modes — the drawing is identical:

```bash
tempestweb dev --mode wasm       # Python in the browser (Pyodide)
tempestweb dev --mode server     # Python on the server (FastAPI + WebSocket)
tempestweb dev --mode transpile  # app transcribed to native JS (static bundle)
```

!!! info "Why two sets?"
    **Lucide** is the core's default set (`tempest_core.icons.Icons`) — clean,
    "feather"-style strokes. **Material Symbols** pairs with the **always-on
    Material 3 base theme** (see [Theming](theming.md)). Use whichever matches
    your app; you can mix both on the same screen.

## Picking an icon with autocomplete

`MaterialIcons` and `Icons` are `StrEnum`s — each member **is** its string. So you
get editor autocomplete without losing the freedom to pass a raw string:

```python
from tempestweb.icons import MaterialIcons, material_icon

material_icon(MaterialIcons.SETTINGS)   # with autocomplete
material_icon("settings")               # raw string — identical
```

!!! tip "Any name in the set works"
    The enum lists the **most common** icons (HOME, SEARCH, CLOSE, MENU…), but any
    valid Material Symbols name works as a raw string **as long as the glyph is
    vendored on the client** (`client/icons/material.js`). For a glyph outside the
    set, see [Custom icon](#custom-icon-raw-svg) below.

## Size and color

`size` is the icon's edge in logical pixels. Omit it to let the icon **scale with
the surrounding font**. Color comes from `Style.color` — the glyph is drawn in
`currentColor`:

```python
from tempest_core import Style
from tempest_core.style import Color

from tempestweb.icons import MaterialIcons, material_icon

# A 20px icon tinted red
material_icon(
    MaterialIcons.FAVORITE,
    size=20.0,
    style=Style(color=Color(r=220, g=40, b=40)),
)

# No size → follows the container's font size
material_icon(MaterialIcons.STAR)
```

## Icons inside fields

The ready-made fields (see [Ready-made components](components.md)) accept icons in
their slots by **raw name** — and an unprefixed name stays **Lucide**, for
compatibility with the core's `Icon`:

```python
from tempestweb.components import EmailField, PasswordField

EmailField(value="", on_change=..., leading_icon="mail")     # Lucide
PasswordField(value="", on_change=..., leading_icon="lock")  # Lucide
```

!!! note "The name grammar"
    Under the hood, the set is encoded as a **prefix** on the `Icon` name:
    `"material:home"`, `"lucide:mail"`. The `material_icon`/`lucide_icon` helpers
    add the prefix for you. An **unprefixed** name (`"mail"`) resolves to Lucide —
    which is why the field slots only ask for the bare name.

## Custom icon (raw SVG) { #custom-icon-raw-svg }

Need a glyph that is **not** vendored? Two ways out.

**1. `custom_icon` — ship the path over the wire, register nothing.** The SVG `d`
rides in the icon name itself, so the client needs no prior registration. It's
drawn **stroked** on a `0 0 24 24` grid in `currentColor` (the Lucide convention):

```python
from tempestweb.icons import custom_icon

# A hand-drawn "bolt" on the 24x24 grid
custom_icon("M13 2 L4 14 H12 L11 22 L20 10 H13 Z", size=24.0)
```

**2. Register on both sides — for a reused glyph.** Register in Python
(`register_icon`) **and** on the client (`registerIcon` in
`client/icons/index.js`), then pass the bare name:

```python
from tempest_core import Icon

from tempestweb.icons import register_icon

register_icon("rocket", "M13 2 L4 14 H12 L11 22 L20 10 H13 Z")
Icon(name="rocket")
```

```javascript
import { registerIcon } from "./icons/index.js";

registerIcon("rocket", "M13 2 L4 14 H12 L11 22 L20 10 H13 Z");
```

!!! tip "When to use which"
    `custom_icon` is great for a **single, one-off glyph** (no client change). The
    both-sides registration is worth it when the **same** glyph shows up in many
    places — the path travels once (in the vendored JS) instead of in every patch.

## Offline and PWA

Because everything is inline SVG from path data vendored in
`client/icons/{lucide,material}.js`, the icons make **no network requests**.
`tempestweb build` bundles those assets into the artifact, so an installed app
(PWA) draws every icon **offline**, with no icon font and no external request.
Nothing to configure. ✅

## Recap

- **Two vendored sets:** `lucide_icon(...)` (default) and `material_icon(...)`
  (pairs with the Material 3 theme).
- `MaterialIcons`/`Icons` are `StrEnum`s → autocomplete + raw string.
- `size` scales the icon (omit to follow the font); `Style.color` tints it.
- Field slots take a **bare name** (= Lucide).
- Glyph outside the set: `custom_icon(path)` (one-off) or `register_icon` +
  `registerIcon` (reused).
- It's all **inline SVG** — no network, **offline/PWA safe**.
