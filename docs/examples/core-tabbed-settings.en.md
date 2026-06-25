# Tabbed settings — state-driven selection 🚀

In this example you'll build a **tabbed settings panel** using the core's
selection components: `Tabs`, `SegmentedControl`, `RadioGroup` and `Chip` — all
driven by integer indices in state and `on_select` handlers.

---

## What you'll build

- 🗂️ A **Tabs** widget switching between "Appearance" and "Notifications".
- 🎚️ A **SegmentedControl** to pick the theme (Light / Dark / Auto).
- 🔘 A **RadioGroup** for the notification frequency.
- 🏷️ A **Chip** reflecting the current choice.

---

## Prerequisites

```bash
pip install tempestweb
```

!!! tip "Tip"
    If you're not yet familiar with the state → view → patches cycle, read the
    [introductory tutorial](../tutorial/index.md).

---

## Step 1 — Options and state

The options are module constants; the state keeps only **integer indices**
pointing at the active choice of each control.

```python
from __future__ import annotations

from dataclasses import dataclass

TAB_LABELS: list[str] = ["Appearance", "Notifications"]
THEME_OPTIONS: list[str] = ["Light", "Dark", "Auto"]
FREQUENCY_OPTIONS: list[str] = ["Off", "Daily", "Weekly", "Realtime"]


@dataclass
class SettingsState:
    """State for the tabbed settings panel.

    Attributes:
        active_tab: Index into :data:`TAB_LABELS` of the open tab.
        theme: Index into :data:`THEME_OPTIONS` of the chosen theme.
        frequency: Index into :data:`FREQUENCY_OPTIONS` of the chosen cadence.
    """

    active_tab: int = 0
    theme: int = 2
    frequency: int = 1


def make_state() -> SettingsState:
    """Build the initial state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults selected.
    """
    return SettingsState()
```

!!! note "Note — indices, not strings"
    Storing `theme: int = 2` (instead of `"Auto"`) keeps the state small and
    decoupled from the labels. `SegmentedControl`, `RadioGroup` and `Tabs` all
    speak in indices via `selected`/`active` and `on_select`.

---

## Step 2 — The handlers

Each selection control hands the chosen index to a dedicated handler:

```python
def select_tab(index: int) -> None:
    """Switch the active tab."""
    app.set_state(lambda s: setattr(s, "active_tab", index))

def select_theme(index: int) -> None:
    """Pick a theme from the segmented control."""
    app.set_state(lambda s: setattr(s, "theme", index))

def select_frequency(index: int) -> None:
    """Pick a notification cadence from the radio group."""
    app.set_state(lambda s: setattr(s, "frequency", index))
```

---

## Step 3 — The conditional panel

Depending on the active tab, we build a different `Card`. Note how each control
takes `selected` (the current index) + `on_select` (the handler), and the `Chip`
reflects the choice with `selected=True`.

```python
from tempest_core import Row, Style, Text
from tempestweb.components import Card, Chip, RadioGroup, SegmentedControl

if state.active_tab == 0:
    panel: Widget = Card(
        key="appearance-card",
        children=[
            Text(content="Theme", key="theme-title"),
            SegmentedControl(
                key="theme-segmented",
                options=THEME_OPTIONS,
                selected=state.theme,
                on_select=select_theme,
            ),
            Row(
                style=Style(gap=4.0),
                children=[
                    Chip(
                        key="theme-chip",
                        label=f"Theme: {THEME_OPTIONS[state.theme]}",
                        selected=True,
                    ),
                ],
            ),
        ],
    )
else:
    panel = Card(
        key="notifications-card",
        children=[
            Text(content="Notification frequency", key="frequency-title"),
            RadioGroup(
                key="frequency-radio",
                options=FREQUENCY_OPTIONS,
                selected=state.frequency,
                on_select=select_frequency,
            ),
            Row(
                style=Style(gap=4.0),
                children=[
                    Chip(
                        key="frequency-chip",
                        label=f"Notify: {FREQUENCY_OPTIONS[state.frequency]}",
                        selected=True,
                    ),
                ],
            ),
        ],
    )
```

---

## Step 4 — The root tree

The `Tabs` sits at the top (`active` + `on_select`), followed by the active tab's
panel.

```python
from tempest_core import Column, Style, Text
from tempest_core.style import Edge
from tempestweb.components import Tabs

return Column(
    style=Style(gap=12.0, padding=Edge.all(16)),
    children=[
        Text(content="Settings", key="heading"),
        Tabs(
            key="settings-tabs",
            tabs=TAB_LABELS,
            active=state.active_tab,
            on_select=select_tab,
        ),
        panel,
    ],
)
```

---

## The complete app

```python
"""Tabbed settings — a tempestweb example for the core's selection components.

This ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It showcases the core's selection and navigation widgets — :class:`Tabs`,
:class:`SegmentedControl`, :class:`RadioGroup`, :class:`Chip` and :class:`Card` —
wired so that every selection is fully state-driven through ``on_select`` /
``on_click`` handlers. The application never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import Card, Chip, RadioGroup, SegmentedControl, Tabs

TAB_LABELS: list[str] = ["Appearance", "Notifications"]
THEME_OPTIONS: list[str] = ["Light", "Dark", "Auto"]
FREQUENCY_OPTIONS: list[str] = ["Off", "Daily", "Weekly", "Realtime"]


@dataclass
class SettingsState:
    """State for the tabbed settings panel.

    Attributes:
        active_tab: Index into :data:`TAB_LABELS` of the open tab.
        theme: Index into :data:`THEME_OPTIONS` of the chosen theme.
        frequency: Index into :data:`FREQUENCY_OPTIONS` of the chosen cadence.
    """

    active_tab: int = 0
    theme: int = 2
    frequency: int = 1


def make_state() -> SettingsState:
    """Build the initial state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults selected.
    """
    return SettingsState()


def view(app: App[SettingsState]) -> Widget:
    """Render the settings UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def select_tab(index: int) -> None:
        """Switch the active tab.

        Args:
            index: Index of the tab to activate.
        """
        app.set_state(lambda s: setattr(s, "active_tab", index))

    def select_theme(index: int) -> None:
        """Pick a theme from the segmented control.

        Args:
            index: Index into :data:`THEME_OPTIONS`.
        """
        app.set_state(lambda s: setattr(s, "theme", index))

    def select_frequency(index: int) -> None:
        """Pick a notification cadence from the radio group.

        Args:
            index: Index into :data:`FREQUENCY_OPTIONS`.
        """
        app.set_state(lambda s: setattr(s, "frequency", index))

    state = app.state

    if state.active_tab == 0:
        panel: Widget = Card(
            key="appearance-card",
            children=[
                Text(content="Theme", key="theme-title"),
                SegmentedControl(
                    key="theme-segmented",
                    options=THEME_OPTIONS,
                    selected=state.theme,
                    on_select=select_theme,
                ),
                Row(
                    style=Style(gap=4.0),
                    children=[
                        Chip(
                            key="theme-chip",
                            label=f"Theme: {THEME_OPTIONS[state.theme]}",
                            selected=True,
                        ),
                    ],
                ),
            ],
        )
    else:
        panel = Card(
            key="notifications-card",
            children=[
                Text(content="Notification frequency", key="frequency-title"),
                RadioGroup(
                    key="frequency-radio",
                    options=FREQUENCY_OPTIONS,
                    selected=state.frequency,
                    on_select=select_frequency,
                ),
                Row(
                    style=Style(gap=4.0),
                    children=[
                        Chip(
                            key="frequency-chip",
                            label=f"Notify: {FREQUENCY_OPTIONS[state.frequency]}",
                            selected=True,
                        ),
                    ],
                ),
            ],
        )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Settings", key="heading"),
            Tabs(
                key="settings-tabs",
                tabs=TAB_LABELS,
                active=state.active_tab,
                on_select=select_tab,
            ),
            panel,
        ],
    )
```

---

## Running the example ▶

=== "Mode A — WASM (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm examples/core-tabbed-settings/app.py
    ```

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/core-tabbed-settings/app.py
    ```

!!! check "Verification"
    On the **Appearance** tab, click "Dark" in the segmented control → the chip
    changes to "Theme: Dark". Click the **Notifications** tab → the frequency
    radio group appears. ✅

---

## Recap

- ✅ Store the selection as **integer indices**, not strings.
- ✅ Use `Tabs`, `SegmentedControl` and `RadioGroup` — all with `on_select(index)`.
- ✅ Reflect the choice in a `Chip` (`selected=True`).
- ✅ Render a conditional panel based on the active tab.
- ✅ Run the same `app.py` in both modes without changing a line.

!!! tip "Next steps"
    - See the [Settings panel](settings-panel.md) for more controls.
    - Combine with [Theme switcher](theme-switcher.md) to actually apply the theme.
