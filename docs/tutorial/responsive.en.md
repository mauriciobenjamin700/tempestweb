# Responsive layout

The browser owns the viewport; your `view` owns the tree. They meet at
`app.media`: a snapshot of the viewport that the client reports on mount and on
every resize, orientation change, or system theme change.

Because the `view` runs again on every change, **an `if` is already
responsiveness**. There is no media query to write and no CSS to maintain. 🚀

## The viewport snapshot

`app.media` is a `MediaQueryData` with six fields:

| Field | What it is |
| --- | --- |
| `width` · `height` | viewport size in CSS px |
| `device_pixel_ratio` | screen density (1 on a plain monitor, 2–3 on a phone) |
| `orientation` | `"portrait"` or `"landscape"` |
| `platform_dark_mode` | whether the OS asks for a dark theme |
| `text_scale_factor` | the user's text scaling (1.0 in a browser) |

```python
from tempest_core import App, Column, Row, Style, Text, Widget

BREAKPOINT = 700.0


def view(app: App[None]) -> Widget:
    """Render a row on a wide viewport and a column on a narrow one."""
    cards: list[Widget] = [
        Text(content="Requests", key="a"),
        Text(content="Errors", key="b"),
    ]
    if app.media.width >= BREAKPOINT:
        return Row(key="cards", style=Style(gap=12.0), children=cards)
    return Column(key="cards", style=Style(gap=12.0), children=cards)
```

Open it on a monitor and narrow the window: the tree switches from `Row` to
`Column`, and the reconciler turns that into the minimal patch sequence — the
cards are re-parented, not rebuilt.

!!! tip "Pick the breakpoint from the content, not from a device"
    `700.0` above is not "phone"; it is "below this the three cards get too
    narrow". A named module constant compared against `media.width` is all the
    infrastructure you need.

## Viewport-height frames

`Style` has no `100vh`. When something has to fill the screen — the classic case
being a `Scaffold(scroll=True)`, whose `app_bar` and `bottom_bar` only stay put
when the column around them is bounded — the bound comes from `media.height`:

```python
from tempest_core import Style
from tempest_core.presets import Scaffold


def view(app: App[None]) -> Widget:
    """Render a scaffold bounded by the viewport, so its bars do not scroll away."""
    return Scaffold(
        key="screen",
        style=Style(height=app.media.height),
        scroll=True,
        app_bar=...,
        bottom_bar=...,
        body=...,
    )
```

!!! warning "Without `media`, that becomes a 4000px page"
    With no height the column grows with its content, the `ScrollView` never
    scrolls, and the action bar ends up at the bottom of the document — far from
    the user's thumb. That was exactly the symptom Mode B had before `app.media`
    was kept current there (issue #74).

## System theme

`platform_dark_mode` arrives in the same snapshot, so an app can follow the OS
preference without writing any CSS:

```python
from tempest_core import Theme, ThemeMode


def view(app: App[None]) -> Widget:
    """Pick the palette the OS asked for."""
    mode = ThemeMode.DARK if app.media.platform_dark_mode else ThemeMode.LIGHT
    theme = Theme.from_seed(seed=..., mode=mode)
    ...
```

## How it reaches you

??? info "Technical details: the `media` event"
    `client/media.js` reads the viewport and sends
    `{"type": "media", "key": "", "payload": {...}}` on mount and on every
    `resize` or `prefers-color-scheme` change. The shared `mount()` installs it,
    so all three modes report.

    On the other side the event is handled **before** handler resolution (like
    `navigate`): in Mode C by the JS runtime, and in Modes A and B by
    `apply_media`, which validates the payload into a `MediaQueryData` and calls
    `App._update_media` — the very method the core's docstring always promised a
    renderer would call.

    The key is empty on purpose: `media` is an app event, not a widget's. An
    absent field keeps its default and a malformed payload is ignored, because a
    strange resize must not take down the event loop.

## Recap

* `app.media` is the viewport snapshot, refreshed on mount and on every resize —
  identical in all three modes.
* Responsive layout is an `if` in the `view`; no media queries, no CSS.
* `media.height` is the only height bound available to a frame that must fit the
  screen.
* `platform_dark_mode` lets the app follow the system theme.

The complete example, which prints the live snapshot and switches layout at the
breakpoint, lives in
[`examples/responsive_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/responsive_demo/app.py):

```bash
tempestweb run --mode server --path examples/responsive_demo
```
