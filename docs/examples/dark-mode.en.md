# Dark Mode — The Theme Reaches the Widget 🌙

A small app with **Card**, **Badge**, **Input**, **Button** and **Alert**, each
resolving its colour from the theme you pass — plus two buttons that swap the
theme at runtime.

---

## What you will build

A screen where **every styled widget gets `theme=app.theme`**. Clicking "Dark"
calls `app.set_theme(...)`, the tree is rebuilt, and each widget re-resolves its
own palette.

!!! tip "It is one line, and it is the line that matters"
    ```python
    Button(label="Save", theme=app.theme, on_click=save)
    ```
    Without the `theme=`, the widget resolves the light palette — even with the
    app in dark mode. The theme is not ambient: it is a field on the widget.

---

## Prerequisites

```bash
pip install tempestweb
```

Recommended reading: [Theming (Material 3)](../tutorial/theming.md), especially
the **Dark mode: pass the theme to the widget** section.

---

## The state and the theme swap

```python
from dataclasses import dataclass

from tempest_core import App, Theme, ThemeMode


@dataclass
class DarkModeState:
    """What the screen holds.

    Attributes:
        dark: Whether the reader asked for the dark theme.
        draft: The text typed into the sample field.
    """

    dark: bool = False
    draft: str = ""


def make_state() -> DarkModeState:
    """Build the initial state: light, with an empty field."""
    return DarkModeState()


def choose(app: App[DarkModeState], dark: bool = False) -> None:
    """Swap the app's theme, which re-resolves every widget below.

    Args:
        app: The application handle.
        dark: Whether to switch to the dark theme.
    """
    app.set_state(lambda state: setattr(state, "dark", dark))
    app.set_theme(Theme(mode=ThemeMode.DARK if dark else ThemeMode.LIGHT))
```

---

## The tree

Every **styled** widget takes the theme; `Row`, `Column` and `Text` do not,
because the core gives them no such field — their colour is inherited from the
box around them.

```python
from tempest_core import Alert, Badge, Button, Card, Column, Input, Row, Style, Text, Widget


def view(app: App[DarkModeState]) -> Widget:
    """Draw the sample tree, each widget resolving from ``app.theme``."""
    theme = app.theme
    return Column(
        key="dark-body",
        children=[
            Row(
                key="mode-row",
                children=[
                    Text(content="Dark mode", key="mode-label"),
                    Button(key="mode-light", label="Light", theme=theme,
                           variant="outline" if app.state.dark else "solid",
                           on_click=lambda: choose(app, False)),
                    Button(key="mode-dark", label="Dark", theme=theme,
                           variant="solid" if app.state.dark else "outline",
                           on_click=lambda: choose(app, True)),
                ],
            ),
            Card(
                key="sample-card",
                theme=theme,
                children=[
                    Badge(key="sample-badge", label="new", theme=theme),
                    Input(key="sample-input", value=app.state.draft, theme=theme,
                          placeholder="Type here", on_change=lambda e: None),
                    Button(key="sample-button", label="Save", theme=theme,
                           on_click=lambda: None),
                ],
            ),
            Alert(key="sample-alert", theme=theme,
                  title="Every colour above came from the theme"),
        ],
    )
```

---

## Running it

```bash
tempestweb run --mode server --path examples/dark-mode --port 8000
tempestweb run --mode wasm   --path examples/dark-mode --port 8000
tempestweb build --mode transpile --path examples/dark-mode
```

Measured in Modes B and C, with the **same** computed values in both — the ones
the core resolves:

| widget | light | dark |
| --- | --- | --- |
| `Button` | `rgb(88, 71, 133)` | `rgb(199, 193, 215)` |
| `Card` | `rgb(252, 252, 252)` | `rgb(25, 25, 26)` |
| `Alert` | `rgb(219, 226, 240)` | `rgb(29, 59, 124)` |

!!! warning "What is still light"
    An `Input`'s background and the page background come from the **base sheet**,
    whose `--tw-*` tokens have no mode axis — so in a dark app the field shows up
    white. Tracked in
    [#148](https://github.com/mauriciobenjamin700/tempestweb/issues/148).

---

## Recap

* The theme is a **field on the widget**, not ambient: `theme=app.theme` on every
  styled widget.
* `app.set_theme(...)` rebuilds the tree and each widget re-resolves.
* A layout widget (`Row`/`Column`/`Text`) has no `theme` — passing one raises.
* Mode C carries both modes in the generated table since 0.99.0; before that,
  every transpiled widget rendered light.
