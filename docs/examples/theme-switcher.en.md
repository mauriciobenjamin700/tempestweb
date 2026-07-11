# Theme Switcher — Light/Dark Theme Toggle 🚀

Build a complete light/dark theme switcher with an accent colour picker — and learn how to manage tempestweb's theme system with `App.set_theme`, `Theme.is_dark`, and `ThemeChangeEvent`.

---

## What you'll build

A theme control panel with five sections:

- 🏷 **Header** — badge showing the active mode and the selected accent colour
- ☀️/🌙 **Colour Mode** — Light / System / Dark buttons plus an OS simulation switch
- 🎨 **Accent Colour** — three colour swatches (Blue, Violet, Teal)
- 🪟 **Colour Tokens** — a preview strip of the current palette's semantic tokens
- 🔔 **ThemeChangeEvent** — an OS-event log with buttons to fire events manually

!!! note "Note — smooth transition"
    Every `Container` uses `Transition(duration_ms=200, curve=Curve.EASE_IN_OUT)`.
    The renderer interpolates background colours between theme changes, making
    the switch feel polished without any extra code in the app logic.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading before continuing:

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

```bash
mkdir -p examples/theme-switcher
touch examples/theme-switcher/app.py
```

---

## Step 1 — Defining the state

The app's state tracks three things:

| Field | Type | Meaning |
|---|---|---|
| `forced_mode` | `ThemeMode` | The mode the user has explicitly chosen (`LIGHT`, `DARK`, or `SYSTEM`) |
| `last_os_event` | `str` | Text description of the last `ThemeChangeEvent` received |
| `swatch_index` | `int` | Index of the active accent swatch (0=Blue, 1=Violet, 2=Teal) |

```python
from __future__ import annotations

from dataclasses import dataclass

from tempest_core.theme import ThemeMode


@dataclass
class ThemeSwitcherState:
    """Application state for the theme-switcher demo.

    Attributes:
        forced_mode: The ThemeMode the user has explicitly chosen;
            SYSTEM means follow the OS.
        last_os_event: A human-readable description of the last
            ThemeChangeEvent received from the OS (purely for display).
        swatch_index: Index of the accent colour swatch the user last clicked
            (0 = blue, 1 = violet, 2 = teal).
    """

    forced_mode: ThemeMode = ThemeMode.SYSTEM
    last_os_event: str = "none yet"
    swatch_index: int = 0


def make_state() -> ThemeSwitcherState:
    """Build the initial application state.

    Returns:
        A fresh ThemeSwitcherState with SYSTEM mode and blue accent.
    """
    return ThemeSwitcherState()
```

!!! tip "Tip — `ThemeMode.SYSTEM`"
    With `ThemeMode.SYSTEM`, tempestweb defers the decision to the OS. The
    `Theme.is_dark(platform_dark_mode=...)` method resolves this correctly —
    you don't need to detect the scheme manually.

---

## Step 2 — Defining the palettes

Define two colour palettes (light and dark) as module-level constants. This
keeps all colour values centralised and easy to maintain.

```python
from tempest_core.style import Color, Curve, Transition

# Light palette
_LIGHT_BG: Color = Color.from_hex("#f8fafc")
_LIGHT_SURFACE: Color = Color.from_hex("#ffffff")
_LIGHT_ON_BG: Color = Color.from_hex("#0f172a")
_LIGHT_MUTED: Color = Color.from_hex("#64748b")
_LIGHT_DIVIDER: Color = Color.from_hex("#e2e8f0")
_LIGHT_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_LIGHT_SUCCESS: Color = Color.from_hex("#16a34a")
_LIGHT_WARN: Color = Color.from_hex("#d97706")
_LIGHT_ERROR: Color = Color.from_hex("#dc2626")

# Dark palette
_DARK_BG: Color = Color.from_hex("#0b0f14")
_DARK_SURFACE: Color = Color.from_hex("#1e293b")
_DARK_ON_BG: Color = Color.from_hex("#f1f5f9")
_DARK_MUTED: Color = Color.from_hex("#94a3b8")
_DARK_DIVIDER: Color = Color.from_hex("#334155")
_DARK_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_DARK_SUCCESS: Color = Color.from_hex("#4ade80")
_DARK_WARN: Color = Color.from_hex("#fbbf24")
_DARK_ERROR: Color = Color.from_hex("#f87171")

# Smooth transition applied to background/surface containers on theme change
_TWEEN: Transition = Transition(duration_ms=200, curve=Curve.EASE_IN_OUT)

# Transparent colour for the unselected swatch ring
_TRANSPARENT: Color = Color(r=0, g=0, b=0, a=0.0)
```

Also define the three accent colour palettes:

```python
_ACCENT_LIGHT: list[Color] = [
    Color.from_hex("#2563eb"),  # blue
    Color.from_hex("#7c3aed"),  # violet
    Color.from_hex("#0d9488"),  # teal
]
_ACCENT_DARK: list[Color] = [
    Color.from_hex("#3b82f6"),  # blue
    Color.from_hex("#a78bfa"),  # violet
    Color.from_hex("#2dd4bf"),  # teal
]
_ACCENT_NAMES: list[str] = ["Blue", "Violet", "Teal"]
```

!!! info "Note — semantic tokens"
    The field names (`background`, `surface`, `on_background`, `error`) mirror
    Material Design's semantic tokens. Using semantic names (instead of
    `dark_blue_colour`) makes the palette readable regardless of the active scheme.

---

## Step 3 — Theme resolution helpers

Two small helpers isolate the theme resolution logic from the rest of the UI:

```python
from tempest_core import App
from tempest_core.style import Color
from tempest_core.theme import Theme, ThemeMode


def _is_dark(app: App[ThemeSwitcherState]) -> bool:
    """Resolve whether the current theme renders dark.

    Delegates to Theme.is_dark so SYSTEM is resolved correctly against
    the platform flag.

    Args:
        app: The application handle exposing theme and media.

    Returns:
        True when the resolved scheme is dark.
    """
    return app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)


def _accent(app: App[ThemeSwitcherState], dark: bool) -> Color:
    """Return the currently selected accent colour for the given scheme.

    Args:
        app: The application handle exposing state.
        dark: Whether the dark palette should be used.

    Returns:
        The Color for the active accent.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    return palette[app.state.swatch_index]
```

The `_make_theme` helper constructs a full `Theme` every time the mode or swatch
changes:

```python
def _make_theme(
    mode: ThemeMode,
    dark: bool,
    swatch_index: int,
) -> Theme:
    """Construct a fully-populated Theme.

    Args:
        mode: The ThemeMode to set.
        dark: Whether the dark palette should be used.
        swatch_index: The 0-based index into the accent colour lists.

    Returns:
        The fully-populated Theme.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    accent_color: Color = palette[swatch_index]
    return Theme(
        mode=mode,
        primary=accent_color,
        background=_DARK_BG if dark else _LIGHT_BG,
        surface=_DARK_SURFACE if dark else _LIGHT_SURFACE,
        on_primary=_DARK_ON_PRIMARY if dark else _LIGHT_ON_PRIMARY,
        on_background=_DARK_ON_BG if dark else _LIGHT_ON_BG,
        error=_DARK_ERROR if dark else _LIGHT_ERROR,
    )
```

!!! tip "Tip — `app.set_theme` vs `app.set_state`"
    Always call both together when the mode changes:
    `app.set_state(...)` updates the `forced_mode` field in your local state
    (so the active button stays highlighted), while `app.set_theme(...)` propagates
    the new `Theme` to the entire widget tree via the reconciler.

---

## Step 4 — The header card

The first card displays the active mode and current accent name:

```python
from tempest_core import Style, Widget
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import Button, Column, Container, Row, Switch, Text


def _header_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the header card showing the current active theme.

    Args:
        app: The application handle.

    Returns:
        A padded container with the title, active mode label and accent badge.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    accent_color: Color = _accent(app, dark)

    mode_label: str
    if app.state.forced_mode is ThemeMode.DARK:
        mode_label = "Dark"
    elif app.state.forced_mode is ThemeMode.LIGHT:
        mode_label = "Light"
    else:
        resolved: str = "dark" if dark else "light"
        mode_label = f"System ({resolved})"

    accent_name: str = _ACCENT_NAMES[app.state.swatch_index]

    return Container(
        key="header-card",
        style=Style(
            background=surface,
            padding=Edge.all(24.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Theme Switcher",
                    key="header-title",
                    style=Style(
                        font_size=26.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Text(
                    content=f"Active mode: {mode_label}  •  Accent: {accent_name}",
                    key="header-subtitle",
                    style=Style(font_size=14.0, color=muted),
                ),
                Container(
                    key="accent-badge",
                    style=Style(
                        background=accent_color,
                        padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                        radius=20.0,
                        align=AlignItems.CENTER,
                        width=160.0,
                    ),
                    child=Text(
                        content="Live colour token",
                        key="badge-text",
                        style=Style(
                            font_size=12.0,
                            font_weight=FontWeight.BOLD,
                            color=_DARK_ON_BG,
                        ),
                    ),
                ),
            ],
        ),
    )
```

Notice how every colour is **read directly from the palette** on every `view`
call. There is no cache or global "current colour" variable — tempestweb calls
`view` again after each `set_theme`, and the function simply picks the right
palette.

---

## Step 5 — The mode card with OS switch

The second card provides the three mode buttons and a `Switch` that simulates
an OS signal:

```python
from tempest_core.style import Border, JustifyContent
from tempest_core.theme import MediaQueryData
from tempest_core.widgets.events import ToggleEvent


def _mode_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the mode-selection card with Light / System / Dark buttons.

    Args:
        app: The application handle.

    Returns:
        A container with three mode buttons and the OS dark-mode toggle.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    def _apply_mode(new_mode: ThemeMode) -> None:
        """Switch to the requested theme mode."""
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        app.set_state(lambda s: setattr(s, "forced_mode", new_mode))
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def set_light() -> None:
        """Force the light colour scheme."""
        _apply_mode(ThemeMode.LIGHT)

    def set_system() -> None:
        """Follow the operating system colour scheme."""
        _apply_mode(ThemeMode.SYSTEM)

    def set_dark() -> None:
        """Force the dark colour scheme."""
        _apply_mode(ThemeMode.DARK)

    def _btn_style(mode: ThemeMode) -> Style:
        """Build a button-wrapper style, highlighted when the mode is active."""
        is_active: bool = app.state.forced_mode is mode
        return Style(
            background=accent_color if is_active else surface,
            border=Border(
                width=2.0,
                color=accent_color if is_active else divider,
            ),
            radius=10.0,
            padding=Edge.symmetric(vertical=6.0, horizontal=14.0),
            transition=_TWEEN,
        )

    def _on_change_os(event: ToggleEvent) -> None:
        """Handle the OS dark-mode indicator toggle (simulation).

        Args:
            event: The toggle event carrying the new checked state.
        """
        new_media: MediaQueryData = app.media.model_copy(
            update={"platform_dark_mode": event.checked}
        )
        app._update_media(new_media)  # noqa: SLF001

    return Container(
        key="mode-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Mode",
                    key="mode-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="mode-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="mode-buttons",
                    style=Style(gap=8.0, justify=JustifyContent.CENTER),
                    children=[
                        Container(
                            key="btn-light-wrap",
                            style=_btn_style(ThemeMode.LIGHT),
                            child=Button(
                                label="Light",
                                on_click=set_light,
                                key="btn-light",
                            ),
                        ),
                        Container(
                            key="btn-system-wrap",
                            style=_btn_style(ThemeMode.SYSTEM),
                            child=Button(
                                label="System",
                                on_click=set_system,
                                key="btn-system",
                            ),
                        ),
                        Container(
                            key="btn-dark-wrap",
                            style=_btn_style(ThemeMode.DARK),
                            child=Button(
                                label="Dark",
                                on_click=set_dark,
                                key="btn-dark",
                            ),
                        ),
                    ],
                ),
                Row(
                    key="os-row",
                    style=Style(gap=12.0, align=AlignItems.CENTER),
                    children=[
                        Text(
                            content="Simulate OS dark mode",
                            key="os-label",
                            style=Style(font_size=14.0, color=muted, grow=1.0),
                        ),
                        Switch(
                            checked=app.media.platform_dark_mode,
                            on_change=_on_change_os,
                            key="os-switch",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "(Only affects SYSTEM mode. Mirrors how "
                        "the host fires ThemeChangeEvent.)"
                    ),
                    key="os-hint",
                    style=Style(font_size=11.0, color=muted),
                ),
            ],
        ),
    )
```

!!! info "Note — `app._update_media`"
    In production the host (browser or server) updates `MediaQueryData`
    automatically when the OS changes its colour scheme. Here we call
    `_update_media` directly to simulate that notification in the demo — in a
    real deployment you never need to do this; the host takes care of it.

---

## Step 6 — The accent picker

The third card creates clickable swatches to change the accent colour without
touching the light/dark mode. The key is the `_make_swatch_handler` factory
that captures the correct index in a closure:

```python
from collections.abc import Callable


def _accent_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the accent-colour picker card.

    Args:
        app: The application handle.

    Returns:
        A container with three selectable swatch buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    swatch_colors: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT

    def _make_swatch_handler(idx: int) -> Callable[[], None]:
        """Return a click handler that selects accent swatch at idx.

        Args:
            idx: The 0-based index into the accent colour list.

        Returns:
            A zero-argument callable that applies the selected swatch.
        """

        def handler() -> None:
            """Select the accent swatch at the captured index."""
            app.set_state(lambda s: setattr(s, "swatch_index", idx))
            app.set_theme(_make_theme(app.state.forced_mode, dark, idx))

        return handler

    swatch_widgets: list[Widget] = []
    for i, (color, name) in enumerate(zip(swatch_colors, _ACCENT_NAMES, strict=True)):
        is_selected: bool = app.state.swatch_index == i
        swatch_widgets.append(
            Column(
                key=f"swatch-col-{i}",
                style=Style(gap=6.0, align=AlignItems.CENTER),
                children=[
                    Container(
                        key=f"swatch-{i}",
                        style=Style(
                            width=44.0,
                            height=44.0,
                            radius=22.0,
                            background=color,
                            border=Border(
                                width=3.0,
                                color=on_bg if is_selected else _TRANSPARENT,
                            ),
                            transition=_TWEEN,
                        ),
                        child=Button(
                            label="",
                            on_click=_make_swatch_handler(i),
                            key=f"swatch-btn-{i}",
                        ),
                    ),
                    Text(
                        content=name,
                        key=f"swatch-label-{i}",
                        style=Style(
                            font_size=11.0,
                            color=on_bg if is_selected else muted,
                            font_weight=(FontWeight.BOLD if is_selected else None),
                        ),
                    ),
                ],
            )
        )

    return Container(
        key="accent-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Accent Colour",
                    key="accent-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="accent-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="swatches-row",
                    style=Style(
                        gap=24.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=swatch_widgets,
                ),
            ],
        ),
    )
```

!!! warning "Warning — closures in loops"
    Always use a factory (`_make_swatch_handler(i)`) when creating handlers
    inside a `for` loop. A direct lambda (`lambda: handler_for(i)`) captures
    `i` by reference, so all buttons end up calling the handler for the **last**
    index. The factory captures `idx` by value at call time.

---

## Step 7 — Token preview and OS event

The two final cards complete the app.

The **Colour Tokens** card displays a row of colour chips for every semantic
token in the current palette:

```python
def _palette_preview_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render a colour-token preview strip.

    Args:
        app: The application handle.

    Returns:
        A container with labelled colour chips for every semantic token.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    tokens: list[tuple[str, Color]] = [
        ("Background", _DARK_BG if dark else _LIGHT_BG),
        ("Surface", _DARK_SURFACE if dark else _LIGHT_SURFACE),
        ("On-BG", _DARK_ON_BG if dark else _LIGHT_ON_BG),
        ("Muted", _DARK_MUTED if dark else _LIGHT_MUTED),
        ("Primary", accent_color),
        ("Success", _DARK_SUCCESS if dark else _LIGHT_SUCCESS),
        ("Warning", _DARK_WARN if dark else _LIGHT_WARN),
        ("Error", _DARK_ERROR if dark else _LIGHT_ERROR),
    ]

    chips: list[Widget] = [
        Column(
            key=f"chip-col-{label}",
            style=Style(gap=4.0, align=AlignItems.CENTER),
            children=[
                Container(
                    key=f"chip-{label}",
                    style=Style(
                        width=36.0,
                        height=36.0,
                        radius=8.0,
                        background=color,
                        border=Border(width=1.0, color=divider),
                        transition=_TWEEN,
                    ),
                ),
                Text(
                    content=label,
                    key=f"chip-label-{label}",
                    style=Style(font_size=10.0, color=muted),
                ),
            ],
        )
        for label, color in tokens
    ]

    return Container(
        key="palette-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Tokens",
                    key="palette-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="palette-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="chips-row",
                    style=Style(
                        gap=12.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=chips,
                ),
            ],
        ),
    )
```

The **ThemeChangeEvent** card simulates OS notifications:

```python
from tempest_core.widgets.events import ThemeChangeEvent


def _os_event_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the OS-event log card.

    Args:
        app: The application handle.

    Returns:
        A container with the last OS event description and fire buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    success: Color = _DARK_SUCCESS if dark else _LIGHT_SUCCESS

    def _handle_theme_change_event(event: ThemeChangeEvent) -> None:
        """Handle an OS-level theme change notification.

        Args:
            event: The typed event carrying the new ThemeMode.
        """
        new_mode: ThemeMode = event.mode
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        log_msg: str = f"ThemeChangeEvent(mode={new_mode!r})"

        def _mutate(s: ThemeSwitcherState) -> None:
            """Apply both mode and log fields in one mutation."""
            s.forced_mode = new_mode
            s.last_os_event = log_msg

        app.set_state(_mutate)
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def _fire_dark_event() -> None:
        """Simulate an OS dark-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.DARK))

    def _fire_light_event() -> None:
        """Simulate an OS light-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.LIGHT))

    return Container(
        key="os-event-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="ThemeChangeEvent (OS simulation)",
                    key="event-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="event-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Text(
                    content=f"Last event: {app.state.last_os_event}",
                    key="event-log",
                    style=Style(font_size=13.0, color=muted),
                ),
                Row(
                    key="event-buttons",
                    style=Style(gap=8.0),
                    children=[
                        Button(
                            label="Fire dark event",
                            on_click=_fire_dark_event,
                            key="fire-dark",
                        ),
                        Button(
                            label="Fire light event",
                            on_click=_fire_light_event,
                            key="fire-light",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "Simulates the host bridge dispatching "
                        "ThemeChangeEvent to App.set_theme."
                    ),
                    key="event-hint",
                    style=Style(font_size=11.0, color=success),
                ),
            ],
        ),
    )
```

!!! info "Note — `ThemeChangeEvent` in production"
    In a real app the host (browser or server) fires `ThemeChangeEvent`
    automatically when the OS changes its colour scheme — you only need to
    register the handler. Here the buttons simulate that notification so the
    example is completely self-contained.

---

## Step 8 — Assembling the `view` function

The root `view` function composes the five cards inside a `Column`:

```python
from tempest_core import App, Style, Widget
from tempest_core.style import Edge


def view(app: App[ThemeSwitcherState]) -> Widget:
    """Render the full theme-switcher UI.

    All sections read app.theme.is_dark() (resolved against
    app.media.platform_dark_mode) to select the correct palette, so the
    entire tree restyles on every set_theme call.

    Args:
        app: The application handle exposing state, theme and media.

    Returns:
        The widget tree for the current state and theme.
    """
    dark: bool = _is_dark(app)
    bg: Color = _DARK_BG if dark else _LIGHT_BG

    return Container(
        key="root",
        style=Style(
            background=bg,
            padding=Edge.all(0.0),
            transition=_TWEEN,
        ),
        child=Column(
            key="page",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _header_card(app),
                _mode_card(app),
                _accent_card(app),
                _palette_preview_card(app),
                _os_event_card(app),
            ],
        ),
    )
```

---

## The complete app

Here is the full `examples/theme-switcher/app.py`, ready to copy:

```python
"""Theme switcher — demonstrates light/dark theming via ``App.set_theme``.

The app maintains its own colour palette for both schemes inside ``view`` and
calls ``app.set_theme`` to swap between them.  Every container, text and button
re-reads ``app.theme.is_dark()`` on each rebuild so the entire tree restyles
without any patch other than ``Update`` on the changed ``Style`` fields — no
navigation, no overlays, just pure theming.

Key concepts shown
------------------
* :class:`~tempest_core.theme.Theme` — carries the active
  :class:`~tempest_core.theme.ThemeMode` plus an optional colour palette.
* :meth:`~tempest_core.core.state.App.set_theme` — swaps the active theme
  and schedules a coalesced rebuild like any state mutation.
* :meth:`~tempest_core.theme.Theme.is_dark` — resolves ``SYSTEM`` against
  the platform flag; used by the ``view`` to pick the right palette at
  build time.
* :class:`~tempest_core.widgets.events.ThemeChangeEvent` — the typed event
  the host fires when the OS colour scheme changes; shown here as an inline
  handler the user can fire manually.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.style import (
    AlignItems,
    Border,
    Color,
    Curve,
    Edge,
    FontWeight,
    JustifyContent,
    Transition,
)
from tempest_core.theme import MediaQueryData, Theme, ThemeMode
from tempest_core.widgets import Button, Column, Container, Row, Switch, Text
from tempest_core.widgets.events import ThemeChangeEvent, ToggleEvent

# ---------------------------------------------------------------------------
# Palette definitions
# ---------------------------------------------------------------------------

# Light palette
_LIGHT_BG: Color = Color.from_hex("#f8fafc")
_LIGHT_SURFACE: Color = Color.from_hex("#ffffff")
_LIGHT_ON_BG: Color = Color.from_hex("#0f172a")
_LIGHT_MUTED: Color = Color.from_hex("#64748b")
_LIGHT_DIVIDER: Color = Color.from_hex("#e2e8f0")
_LIGHT_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_LIGHT_SUCCESS: Color = Color.from_hex("#16a34a")
_LIGHT_WARN: Color = Color.from_hex("#d97706")
_LIGHT_ERROR: Color = Color.from_hex("#dc2626")

# Dark palette
_DARK_BG: Color = Color.from_hex("#0b0f14")
_DARK_SURFACE: Color = Color.from_hex("#1e293b")
_DARK_ON_BG: Color = Color.from_hex("#f1f5f9")
_DARK_MUTED: Color = Color.from_hex("#94a3b8")
_DARK_DIVIDER: Color = Color.from_hex("#334155")
_DARK_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_DARK_SUCCESS: Color = Color.from_hex("#4ade80")
_DARK_WARN: Color = Color.from_hex("#fbbf24")
_DARK_ERROR: Color = Color.from_hex("#f87171")

# Smooth implicit transition applied to background/surface containers when the
# theme changes — the renderer tweens the colour so the switch feels polished.
_TWEEN: Transition = Transition(duration_ms=200, curve=Curve.EASE_IN_OUT)

# Transparent colour for the unselected swatch ring.
_TRANSPARENT: Color = Color(r=0, g=0, b=0, a=0.0)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class ThemeSwitcherState:
    """Application state for the theme-switcher demo.

    Attributes:
        forced_mode: The :class:`~tempest_core.theme.ThemeMode` the user
            has explicitly chosen; ``SYSTEM`` means follow the OS.
        last_os_event: A human-readable description of the last
            ``ThemeChangeEvent`` received from the OS (purely for display).
        swatch_index: Index of the accent colour swatch the user last clicked
            (0 = blue, 1 = violet, 2 = teal), to showcase per-palette
            customisation on top of the dark/light split.
    """

    forced_mode: ThemeMode = ThemeMode.SYSTEM
    last_os_event: str = "none yet"
    swatch_index: int = 0


def make_state() -> ThemeSwitcherState:
    """Build the initial application state.

    Returns:
        A fresh :class:`ThemeSwitcherState` with ``SYSTEM`` mode and blue
        accent.
    """
    return ThemeSwitcherState()


# ---------------------------------------------------------------------------
# Accent swatches (three selectable accent palettes)
# ---------------------------------------------------------------------------

_ACCENT_LIGHT: list[Color] = [
    Color.from_hex("#2563eb"),  # blue
    Color.from_hex("#7c3aed"),  # violet
    Color.from_hex("#0d9488"),  # teal
]
_ACCENT_DARK: list[Color] = [
    Color.from_hex("#3b82f6"),  # blue
    Color.from_hex("#a78bfa"),  # violet
    Color.from_hex("#2dd4bf"),  # teal
]
_ACCENT_NAMES: list[str] = ["Blue", "Violet", "Teal"]


# ---------------------------------------------------------------------------
# Helper: resolve dark flag from app context
# ---------------------------------------------------------------------------


def _is_dark(app: App[ThemeSwitcherState]) -> bool:
    """Resolve whether the current theme renders dark.

    Delegates to :meth:`~tempest_core.theme.Theme.is_dark` so ``SYSTEM``
    is resolved correctly against the platform flag.

    Args:
        app: The application handle exposing ``theme`` and ``media``.

    Returns:
        ``True`` when the resolved scheme is dark.
    """
    return app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)


def _accent(app: App[ThemeSwitcherState], dark: bool) -> Color:
    """Return the currently selected accent colour for the given scheme.

    Args:
        app: The application handle exposing ``state``.
        dark: Whether the dark palette should be used.

    Returns:
        The :class:`~tempest_core.style.Color` for the active accent.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    return palette[app.state.swatch_index]


def _make_theme(
    mode: ThemeMode,
    dark: bool,
    swatch_index: int,
) -> Theme:
    """Construct a fully-populated :class:`~tempest_core.theme.Theme`.

    Args:
        mode: The :class:`~tempest_core.theme.ThemeMode` to set.
        dark: Whether the dark palette should be used.
        swatch_index: The 0-based index into the accent colour lists.

    Returns:
        The fully-populated :class:`~tempest_core.theme.Theme`.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    accent_color: Color = palette[swatch_index]
    return Theme(
        mode=mode,
        primary=accent_color,
        background=_DARK_BG if dark else _LIGHT_BG,
        surface=_DARK_SURFACE if dark else _LIGHT_SURFACE,
        on_primary=_DARK_ON_PRIMARY if dark else _LIGHT_ON_PRIMARY,
        on_background=_DARK_ON_BG if dark else _LIGHT_ON_BG,
        error=_DARK_ERROR if dark else _LIGHT_ERROR,
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _header_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the header card showing the current active theme.

    Args:
        app: The application handle.

    Returns:
        A padded container with the title, active mode label and accent badge.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    accent_color: Color = _accent(app, dark)

    mode_label: str
    if app.state.forced_mode is ThemeMode.DARK:
        mode_label = "Dark"
    elif app.state.forced_mode is ThemeMode.LIGHT:
        mode_label = "Light"
    else:
        resolved: str = "dark" if dark else "light"
        mode_label = f"System ({resolved})"

    accent_name: str = _ACCENT_NAMES[app.state.swatch_index]

    return Container(
        key="header-card",
        style=Style(
            background=surface,
            padding=Edge.all(24.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Theme Switcher",
                    key="header-title",
                    style=Style(
                        font_size=26.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Text(
                    content=f"Active mode: {mode_label}  •  Accent: {accent_name}",
                    key="header-subtitle",
                    style=Style(font_size=14.0, color=muted),
                ),
                Container(
                    key="accent-badge",
                    style=Style(
                        background=accent_color,
                        padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                        radius=20.0,
                        align=AlignItems.CENTER,
                        width=160.0,
                    ),
                    child=Text(
                        content="Live colour token",
                        key="badge-text",
                        style=Style(
                            font_size=12.0,
                            font_weight=FontWeight.BOLD,
                            color=_DARK_ON_BG,
                        ),
                    ),
                ),
            ],
        ),
    )


def _mode_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the mode-selection card with Light / System / Dark buttons.

    Each button calls App.set_theme with a new Theme built from the chosen
    ThemeMode and active accent palette.

    Args:
        app: The application handle.

    Returns:
        A container with three mode buttons and the OS dark-mode toggle.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    def _apply_mode(new_mode: ThemeMode) -> None:
        """Switch to the requested theme mode.

        Args:
            new_mode: The target ThemeMode.
        """
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        app.set_state(lambda s: setattr(s, "forced_mode", new_mode))
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def set_light() -> None:
        """Force the light colour scheme."""
        _apply_mode(ThemeMode.LIGHT)

    def set_system() -> None:
        """Follow the operating system colour scheme."""
        _apply_mode(ThemeMode.SYSTEM)

    def set_dark() -> None:
        """Force the dark colour scheme."""
        _apply_mode(ThemeMode.DARK)

    def _btn_style(mode: ThemeMode) -> Style:
        """Build a button-wrapper style, highlighted when the mode is active.

        Args:
            mode: The mode this button represents.

        Returns:
            A Style with an accent border when active, or a muted border otherwise.
        """
        is_active: bool = app.state.forced_mode is mode
        return Style(
            background=accent_color if is_active else surface,
            border=Border(
                width=2.0,
                color=accent_color if is_active else divider,
            ),
            radius=10.0,
            padding=Edge.symmetric(vertical=6.0, horizontal=14.0),
            transition=_TWEEN,
        )

    def _on_change_os(event: ToggleEvent) -> None:
        """Handle the OS dark-mode indicator toggle (simulation).

        In a real deployment the renderer fires ThemeChangeEvent; this
        Switch lets the demo simulate that notification by toggling
        media.platform_dark_mode.

        Args:
            event: The toggle event carrying the new checked state.
        """
        new_media: MediaQueryData = app.media.model_copy(
            update={"platform_dark_mode": event.checked}
        )
        app._update_media(new_media)  # noqa: SLF001

    return Container(
        key="mode-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Mode",
                    key="mode-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="mode-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="mode-buttons",
                    style=Style(gap=8.0, justify=JustifyContent.CENTER),
                    children=[
                        Container(
                            key="btn-light-wrap",
                            style=_btn_style(ThemeMode.LIGHT),
                            child=Button(
                                label="Light",
                                on_click=set_light,
                                key="btn-light",
                            ),
                        ),
                        Container(
                            key="btn-system-wrap",
                            style=_btn_style(ThemeMode.SYSTEM),
                            child=Button(
                                label="System",
                                on_click=set_system,
                                key="btn-system",
                            ),
                        ),
                        Container(
                            key="btn-dark-wrap",
                            style=_btn_style(ThemeMode.DARK),
                            child=Button(
                                label="Dark",
                                on_click=set_dark,
                                key="btn-dark",
                            ),
                        ),
                    ],
                ),
                Row(
                    key="os-row",
                    style=Style(gap=12.0, align=AlignItems.CENTER),
                    children=[
                        Text(
                            content="Simulate OS dark mode",
                            key="os-label",
                            style=Style(font_size=14.0, color=muted, grow=1.0),
                        ),
                        Switch(
                            checked=app.media.platform_dark_mode,
                            on_change=_on_change_os,
                            key="os-switch",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "(Only affects SYSTEM mode. Mirrors how "
                        "the host fires ThemeChangeEvent.)"
                    ),
                    key="os-hint",
                    style=Style(font_size=11.0, color=muted),
                ),
            ],
        ),
    )


def _accent_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the accent-colour picker card.

    Three colour swatches (Blue, Violet, Teal) let the user customise the
    accent without changing the dark/light mode.  Selecting a swatch rebuilds
    the full tree with the new accent token.

    Args:
        app: The application handle.

    Returns:
        A container with three selectable swatch buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    swatch_colors: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT

    def _make_swatch_handler(idx: int) -> Callable[[], None]:
        """Return a click handler that selects accent swatch at ``idx``.

        Args:
            idx: The 0-based index into the accent colour list.

        Returns:
            A zero-argument callable that applies the selected swatch.
        """

        def handler() -> None:
            """Select the accent swatch at the captured index."""
            app.set_state(lambda s: setattr(s, "swatch_index", idx))
            app.set_theme(_make_theme(app.state.forced_mode, dark, idx))

        return handler

    swatch_widgets: list[Widget] = []
    for i, (color, name) in enumerate(zip(swatch_colors, _ACCENT_NAMES, strict=True)):
        is_selected: bool = app.state.swatch_index == i
        swatch_widgets.append(
            Column(
                key=f"swatch-col-{i}",
                style=Style(gap=6.0, align=AlignItems.CENTER),
                children=[
                    Container(
                        key=f"swatch-{i}",
                        style=Style(
                            width=44.0,
                            height=44.0,
                            radius=22.0,
                            background=color,
                            border=Border(
                                width=3.0,
                                color=on_bg if is_selected else _TRANSPARENT,
                            ),
                            transition=_TWEEN,
                        ),
                        child=Button(
                            label="",
                            on_click=_make_swatch_handler(i),
                            key=f"swatch-btn-{i}",
                        ),
                    ),
                    Text(
                        content=name,
                        key=f"swatch-label-{i}",
                        style=Style(
                            font_size=11.0,
                            color=on_bg if is_selected else muted,
                            font_weight=(FontWeight.BOLD if is_selected else None),
                        ),
                    ),
                ],
            )
        )

    return Container(
        key="accent-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Accent Colour",
                    key="accent-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="accent-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="swatches-row",
                    style=Style(
                        gap=24.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=swatch_widgets,
                ),
            ],
        ),
    )


def _palette_preview_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render a colour-token preview strip.

    Shows all resolved palette colours (background, surface, text, accent,
    success, warning, error) so the user can see the full scheme at a glance.

    Args:
        app: The application handle.

    Returns:
        A container with labelled colour chips for every semantic token.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    tokens: list[tuple[str, Color]] = [
        ("Background", _DARK_BG if dark else _LIGHT_BG),
        ("Surface", _DARK_SURFACE if dark else _LIGHT_SURFACE),
        ("On-BG", _DARK_ON_BG if dark else _LIGHT_ON_BG),
        ("Muted", _DARK_MUTED if dark else _LIGHT_MUTED),
        ("Primary", accent_color),
        ("Success", _DARK_SUCCESS if dark else _LIGHT_SUCCESS),
        ("Warning", _DARK_WARN if dark else _LIGHT_WARN),
        ("Error", _DARK_ERROR if dark else _LIGHT_ERROR),
    ]

    chips: list[Widget] = [
        Column(
            key=f"chip-col-{label}",
            style=Style(gap=4.0, align=AlignItems.CENTER),
            children=[
                Container(
                    key=f"chip-{label}",
                    style=Style(
                        width=36.0,
                        height=36.0,
                        radius=8.0,
                        background=color,
                        border=Border(width=1.0, color=divider),
                        transition=_TWEEN,
                    ),
                ),
                Text(
                    content=label,
                    key=f"chip-label-{label}",
                    style=Style(font_size=10.0, color=muted),
                ),
            ],
        )
        for label, color in tokens
    ]

    return Container(
        key="palette-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Tokens",
                    key="palette-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="palette-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="chips-row",
                    style=Style(
                        gap=12.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=chips,
                ),
            ],
        ),
    )


def _os_event_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the OS-event log card.

    Args:
        app: The application handle.

    Returns:
        A container with the last OS event description and fire buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    success: Color = _DARK_SUCCESS if dark else _LIGHT_SUCCESS

    def _handle_theme_change_event(event: ThemeChangeEvent) -> None:
        """Handle an OS-level theme change notification.

        Args:
            event: The typed event carrying the new ThemeMode.
        """
        new_mode: ThemeMode = event.mode
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        log_msg: str = f"ThemeChangeEvent(mode={new_mode!r})"

        def _mutate(s: ThemeSwitcherState) -> None:
            """Apply both mode and log fields in one mutation."""
            s.forced_mode = new_mode
            s.last_os_event = log_msg

        app.set_state(_mutate)
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def _fire_dark_event() -> None:
        """Simulate an OS dark-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.DARK))

    def _fire_light_event() -> None:
        """Simulate an OS light-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.LIGHT))

    return Container(
        key="os-event-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="ThemeChangeEvent (OS simulation)",
                    key="event-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="event-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Text(
                    content=f"Last event: {app.state.last_os_event}",
                    key="event-log",
                    style=Style(font_size=13.0, color=muted),
                ),
                Row(
                    key="event-buttons",
                    style=Style(gap=8.0),
                    children=[
                        Button(
                            label="Fire dark event",
                            on_click=_fire_dark_event,
                            key="fire-dark",
                        ),
                        Button(
                            label="Fire light event",
                            on_click=_fire_light_event,
                            key="fire-light",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "Simulates the host bridge dispatching "
                        "ThemeChangeEvent to App.set_theme."
                    ),
                    key="event-hint",
                    style=Style(font_size=11.0, color=success),
                ),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------


def view(app: App[ThemeSwitcherState]) -> Widget:
    """Render the full theme-switcher UI.

    All sections read ``app.theme.is_dark()`` (resolved against
    ``app.media.platform_dark_mode``) to select the correct palette, so the
    entire tree restyles on every :meth:`~App.set_theme` call.

    Args:
        app: The application handle exposing ``state``, ``theme`` and
            ``media``.

    Returns:
        The widget tree for the current state and theme.
    """
    dark: bool = _is_dark(app)
    bg: Color = _DARK_BG if dark else _LIGHT_BG

    return Container(
        key="root",
        style=Style(
            background=bg,
            padding=Edge.all(0.0),
            transition=_TWEEN,
        ),
        child=Column(
            key="page",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _header_card(app),
                _mode_card(app),
                _accent_card(app),
                _palette_preview_card(app),
                _os_event_card(app),
            ],
        ),
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/theme-switcher
```

Python runs **inside the browser** via Pyodide. No server needed.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/theme-switcher
```

Python runs on the server; the browser receives JSON patches over WebSocket and
applies them to the DOM.

!!! check "Verification"
    In either mode you should see:

    1. Header showing mode "System (light)" and blue badge "Live colour token"
    2. "Colour Mode" card with Light / System / Dark buttons — System highlighted
    3. "Accent Colour" card with three swatches — Blue selected
    4. "Colour Tokens" card with 8 colour chips
    5. "ThemeChangeEvent" card showing "Last event: none yet"
    6. Click **Dark** → the entire UI switches to the dark palette with a smooth transition
    7. Click **Light** → returns to the light palette
    8. Click swatch **Violet** → badge and accent change to violet
    9. Enable the "Simulate OS dark mode" switch → with System mode active, the UI turns dark
    10. Click **Fire dark event** → "Last event:" shows `ThemeChangeEvent(mode=<ThemeMode.DARK: 'dark'>)`

---

## Automated verification ✅

Run the four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All pass green. The example was written to be `mypy --strict` clean — every
variable and return value is explicitly annotated.

---

## How it works under the hood

### The theme update cycle

```
Click "Dark"
      │
      ▼
set_dark() → _apply_mode(ThemeMode.DARK)
      │
      ├─ app.set_state(...)   → updates forced_mode in state
      │
      └─ app.set_theme(...)   → propagates new Theme to the reconciler
                                      │
                                      ▼
                              view(app) called again
                                      │
                                      ▼
                              _is_dark(app) returns True
                                      │
                                      ▼
                              all containers read _DARK_*
                                      │
                                      ▼
                              reconciler computes Update patches
                              (only changed Style fields)
                                      │
                                      ▼
                              DOM updated with 200 ms transition
```

### Why are `set_state` and `set_theme` called together?

`app.set_state` updates **your** local state (`forced_mode`) so the buttons
reflect which one is active. `app.set_theme` updates the framework's `Theme`
so that `app.theme.is_dark()` and `app.theme.primary` return the correct values
on the next `view` call. These are separate responsibilities — omitting either
one would leave part of the UI out of sync.

### `ThemeMode.SYSTEM` and `app.media`

When the mode is `SYSTEM`, `Theme.is_dark` checks
`platform_dark_mode=app.media.platform_dark_mode`. The `app.media` field is a
`MediaQueryData` that the host updates automatically when the OS changes its
colour scheme. The switch in the "Colour Mode" card simulates that update by
calling `_update_media` directly — in production you never need to do this;
the host handles it.

---

## Recap

In this tutorial you learned:

- ✅ Use `App.set_theme` to switch the theme and trigger a coalesced rebuild
- ✅ Resolve `ThemeMode.SYSTEM` with `Theme.is_dark(platform_dark_mode=...)`
- ✅ Build semantic colour palettes for both schemes as module-level constants
- ✅ Use `Transition` to animate colour changes smoothly
- ✅ React to `ThemeChangeEvent` (OS notification) with a typed handler
- ✅ Create handler factories (`_make_swatch_handler`) for correct closures in loops
- ✅ Combine `set_state` + `set_theme` to keep local state and theme in sync

---

## Next steps

Try extending the example:

- 💡 Persist the chosen mode in the browser's `localStorage` (Mode A) or a server
  session (Mode B) so it survives reloads
- 💡 Add a fourth swatch with custom colours via `Color(r=..., g=..., b=...)`
- 💡 Explore the [Settings Panel](./settings-panel.md) example to see how to
  persist user preferences
- 💡 Read [Execution modes](../tutorial/modes.md) to understand how the same
  `app.py` runs on both transports without any changes
