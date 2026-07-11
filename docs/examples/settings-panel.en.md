# Settings Panel — Selection Controls in Action 🚀

Build a complete settings panel with **Switch**, **Checkbox**, **Slider**, **RadioGroup**, and **SegmentedControl** — and see how to bind all of them cleanly to a single typed state dataclass.

---

## What you'll build

A settings panel split into four sections, plus a live summary card:

| Section | Widgets | Controls |
|---|---|---|
| **Notifications** | Switch + Checkbox | Push notifications, e-mail alerts, sounds |
| **Appearance** | SegmentedControl + Slider | Theme (System/Light/Dark), font size, quality |
| **Audio & Storage** | Slider + Switch | Playback volume, auto-save drafts |
| **Language** | RadioGroup | Interface language |
| **Live summary** | Card (read-only) | Real-time reflection of all the values above |

Every interaction — dragging a slider, checking a box, picking a segment — **immediately updates** the summary card, making two-way binding concretely visible.

!!! note "Note — why a live summary?"
    The summary card is not decoration. It proves that each control genuinely modifies the shared state. If you click a control and the summary does not change, there is a bug. It is the fastest smoke test possible.

---

## Prerequisites

```bash
pip install tempestweb
```

Recommended reading before continuing:

- [Basic tutorial](../tutorial/index.md) — `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how the update cycle works
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

```bash
mkdir -p examples/settings-panel
touch examples/settings-panel/app.py
```

---

## Step 1 — Defining option constants

Before the state, define the option lists for the selection controls. Keeping them as constants at the top of the file avoids duplication and makes future adjustments easy.

```python
from __future__ import annotations

_THEME_OPTIONS: list[str] = ["System", "Light", "Dark"]
_LANGUAGE_OPTIONS: list[str] = ["English", "Português", "Español", "Français"]
_QUALITY_OPTIONS: list[str] = ["Low", "Medium", "High", "Ultra"]
```

!!! tip "Tip — index as state, not the string"
    The state stores the **index** (`theme_index: int = 0`), not the string `"System"`. This keeps the serialized state compact and language-independent. To display the label, use `_THEME_OPTIONS[state.theme_index]` at render time.

---

## Step 2 — Modelling the state

With the options defined, model exactly what needs to persist between renders:

```python
from dataclasses import dataclass


@dataclass
class SettingsState:
    """All mutable settings controlled by the panel.

    Attributes:
        notifications_enabled: Master switch for push notifications.
        email_alerts: Whether to send e-mail alerts on events.
        sound_enabled: Whether in-app sounds are active.
        auto_save: Whether drafts are saved automatically.
        theme_index: Index into ``_THEME_OPTIONS`` (0=System, 1=Light, 2=Dark).
        language_index: Index into ``_LANGUAGE_OPTIONS``.
        volume: Playback volume in ``[0, 100]``.
        font_size: Preferred font size in ``[10, 30]`` logical points.
        quality_index: Index into ``_QUALITY_OPTIONS`` (stream/render quality).
    """

    notifications_enabled: bool = True
    email_alerts: bool = False
    sound_enabled: bool = True
    auto_save: bool = True
    theme_index: int = 0
    language_index: int = 0
    volume: float = 70.0
    font_size: float = 16.0
    quality_index: int = 2


def make_state() -> SettingsState:
    """Build the initial settings state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults.
    """
    return SettingsState()
```

`make_state` is the function tempestweb calls to initialize the app. It must exist with that exact name in the module.

---

## Step 3 — Event types

Two event types arrive from input controls. Import them from `tempest_core.widgets.events`:

```python
from tempest_core.widgets.events import SlideEvent, ToggleEvent
```

| Type | Used by | Relevant field |
|---|---|---|
| `ToggleEvent` | `Switch`, `Checkbox` | `.checked: bool` |
| `SlideEvent` | `Slider` | `.value: float` |

`RadioGroup` and `SegmentedControl` deliver the index (`int`) directly to the callback — no event wrapper.

---

## Step 4 — Notifications section

The first section uses `Switch` for the master control and two `Checkbox` widgets for sub-options. The UI is organised in a `_notifications_card` function that takes `app` and returns a `Card`:

```python
from tempest_core import App, Style, Widget
from tempest_core.components import AppBar, Card, Divider, Scaffold
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import Checkbox, Column, Row, Switch, Text
from tempest_core.widgets.events import ToggleEvent


def _notifications_card(app: App[SettingsState]) -> Widget:
    """Render the Notifications section with Switch and Checkbox controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the notification preference controls.
    """
    state: SettingsState = app.state

    def on_notifications_toggle(event: ToggleEvent) -> None:
        """Toggle master notification switch."""
        app.set_state(lambda s: setattr(s, "notifications_enabled", event.checked))

    def on_email_toggle(event: ToggleEvent) -> None:
        """Toggle e-mail alert preference."""
        app.set_state(lambda s: setattr(s, "email_alerts", event.checked))

    def on_sound_toggle(event: ToggleEvent) -> None:
        """Toggle in-app sound preference."""
        app.set_state(lambda s: setattr(s, "sound_enabled", event.checked))

    return Card(
        key="notifications-card",
        children=[
            Text(
                content="Notifications",
                key="notif-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="notif-divider"),
            Row(
                key="notif-master-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Enable notifications",
                        key="notif-master-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.notifications_enabled,
                        on_change=on_notifications_toggle,
                        key="notif-switch",
                    ),
                ],
            ),
            Checkbox(
                label="Send e-mail alerts",
                checked=state.email_alerts,
                on_change=on_email_toggle,
                key="email-checkbox",
            ),
            Checkbox(
                label="Play sounds",
                checked=state.sound_enabled,
                on_change=on_sound_toggle,
                key="sound-checkbox",
            ),
        ],
    )
```

!!! info "Note — `Switch` in a `Row` with `grow=1.0`"
    The `Text` with `grow=1.0` takes all available space in the row, pushing the `Switch` to the right — the classic settings-row pattern seen in iOS and Android. The `gap=12.0` on the `Row` adds horizontal spacing between the two.

---

## Step 5 — Appearance section

This section introduces `SegmentedControl` (for theme and quality) and `Slider` (for font size):

```python
from tempest_core.components import SegmentedControl
from tempest_core.widgets import Slider
from tempest_core.widgets.events import SlideEvent


def _appearance_card(app: App[SettingsState]) -> Widget:
    """Render the Appearance section with SegmentedControl and Slider controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the theme, font-size and quality controls.
    """
    state: SettingsState = app.state

    def on_theme_select(index: int) -> None:
        """Select a colour theme."""
        app.set_state(lambda s: setattr(s, "theme_index", index))

    def on_quality_select(index: int) -> None:
        """Select the render/stream quality level."""
        app.set_state(lambda s: setattr(s, "quality_index", index))

    def on_font_size_change(event: SlideEvent) -> None:
        """Adjust the preferred font size."""
        app.set_state(lambda s: setattr(s, "font_size", round(event.value, 1)))

    return Card(
        key="appearance-card",
        children=[
            Text(
                content="Appearance",
                key="appearance-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="appearance-divider"),
            Text(
                content="Theme",
                key="theme-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_THEME_OPTIONS,
                selected=state.theme_index,
                on_select=on_theme_select,
                key="theme-segments",
            ),
            Text(
                content=f"Font size: {state.font_size:.0f} pt",
                key="font-size-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.font_size,
                min_value=10.0,
                max_value=30.0,
                step=1.0,
                on_change=on_font_size_change,
                key="font-slider",
            ),
            Text(
                content="Render quality",
                key="quality-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_QUALITY_OPTIONS,
                selected=state.quality_index,
                on_select=on_quality_select,
                key="quality-segments",
            ),
        ],
    )
```

!!! tip "Tip — dynamic label above the Slider"
    The `Text` before the `Slider` uses `f"Font size: {state.font_size:.0f} pt"`. Each slider movement changes the state → `view` is called again → the label updates. No local variable or manual `ref` needed: the state *is* the source of truth.

---

## Step 6 — Audio & Storage section

Volume via `Slider` and auto-save via `Switch`, following the same patterns:

```python
def _audio_card(app: App[SettingsState]) -> Widget:
    """Render the Audio section with a volume Slider and auto-save Switch.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the audio and save controls.
    """
    state: SettingsState = app.state

    def on_volume_change(event: SlideEvent) -> None:
        """Adjust playback volume."""
        app.set_state(lambda s: setattr(s, "volume", round(event.value)))

    def on_auto_save_toggle(event: ToggleEvent) -> None:
        """Toggle auto-save preference."""
        app.set_state(lambda s: setattr(s, "auto_save", event.checked))

    return Card(
        key="audio-card",
        children=[
            Text(
                content="Audio & Storage",
                key="audio-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="audio-divider"),
            Text(
                content=f"Volume: {state.volume:.0f}%",
                key="volume-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.volume,
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                on_change=on_volume_change,
                key="volume-slider",
            ),
            Row(
                key="auto-save-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Auto-save drafts",
                        key="auto-save-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.auto_save,
                        on_change=on_auto_save_toggle,
                        key="auto-save-switch",
                    ),
                ],
            ),
        ],
    )
```

---

## Step 7 — Language section

`RadioGroup` is the right choice for single selection when all items should be visible at once:

```python
from tempest_core.components import RadioGroup


def _language_card(app: App[SettingsState]) -> Widget:
    """Render the Language section with a RadioGroup control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the language radio group.
    """
    state: SettingsState = app.state

    def on_language_select(index: int) -> None:
        """Select the preferred interface language."""
        app.set_state(lambda s: setattr(s, "language_index", index))

    return Card(
        key="language-card",
        children=[
            Text(
                content="Language",
                key="language-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="language-divider"),
            RadioGroup(
                options=_LANGUAGE_OPTIONS,
                selected=state.language_index,
                on_select=on_language_select,
                key="language-radio",
            ),
        ],
    )
```

!!! info "Note — `RadioGroup` vs. `SegmentedControl`"
    Use `RadioGroup` when there are more than 3-4 options or when labels are long — it stacks options vertically. Use `SegmentedControl` for 2-4 short options that fit on a single horizontal line.

---

## Step 8 — The live summary card

This function takes the `state` directly (without the full `app`) because it does not need to register any handlers — it is read-only:

```python
def _summary_card(state: SettingsState) -> Widget:
    """Render a live summary of all current settings.

    This card re-renders on every state change and shows all selected values
    so the user can verify that every control is truly bound to the state.

    Args:
        state: The current snapshot of :class:`SettingsState`.

    Returns:
        A ``Card`` listing all current setting values.
    """
    theme_name: str = _THEME_OPTIONS[state.theme_index]
    language_name: str = _LANGUAGE_OPTIONS[state.language_index]
    quality_name: str = _QUALITY_OPTIONS[state.quality_index]
    notif_text: str = "on" if state.notifications_enabled else "off"
    email_text: str = "yes" if state.email_alerts else "no"
    sound_text: str = "on" if state.sound_enabled else "off"
    save_text: str = "on" if state.auto_save else "off"

    lines: list[Widget] = [
        Text(
            content="Live summary",
            key="summary-heading",
            style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="summary-divider"),
        Text(
            content=f"Notifications: {notif_text}  |  E-mail alerts: {email_text}",
            key="summary-notif",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Sound: {sound_text}  |  Auto-save: {save_text}",
            key="summary-sound",
            style=Style(font_size=13.0),
        ),
        Text(
            content=(
                f"Theme: {theme_name}  |  Font: {state.font_size:.0f} pt"
                f"  |  Quality: {quality_name}"
            ),
            key="summary-appearance",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Volume: {state.volume:.0f}%  |  Language: {language_name}",
            key="summary-audio",
            style=Style(font_size=13.0),
        ),
    ]

    return Card(key="summary-card", children=lines)
```

---

## Step 9 — Assembling everything in `view`

The `view` function is tempestweb's entry point. It calls each section builder and organises them in a `Scaffold` with an `AppBar`:

```python
def view(app: App[SettingsState]) -> Widget:
    """Render the full settings panel from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    return Scaffold(
        key="settings-scaffold",
        app_bar=AppBar(title="Settings", key="settings-appbar"),
        body=Column(
            key="settings-body",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _notifications_card(app),
                _appearance_card(app),
                _audio_card(app),
                _language_card(app),
                _summary_card(app.state),
            ],
        ),
    )
```

!!! tip "Tip — `_summary_card(app.state)` vs. `_summary_card(app)`"
    Passing `app.state` (instead of the full `app`) to the summary card communicates clearly that it is **read-only**. Any reader instantly knows that function registers no handlers. It is a design convention, not a technical constraint.

---

## The complete app ✅

Here is the complete `examples/settings-panel/app.py`, ready to copy:

```python
"""Settings panel — demonstrates selection controls bound to a settings dataclass.

Every control (Switch, Checkbox, Slider, RadioGroup, SegmentedControl) is wired
to a dedicated field in :class:`SettingsState`.  Any change immediately re-renders
a live summary card at the bottom that reflects the current state — so the demo
makes the two-way binding visible.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AppBar,
    Card,
    Divider,
    RadioGroup,
    Scaffold,
    SegmentedControl,
)
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import (
    Checkbox,
    Column,
    Row,
    Slider,
    Switch,
    Text,
)
from tempest_core.widgets.events import SlideEvent, ToggleEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_THEME_OPTIONS: list[str] = ["System", "Light", "Dark"]
_LANGUAGE_OPTIONS: list[str] = ["English", "Português", "Español", "Français"]
_QUALITY_OPTIONS: list[str] = ["Low", "Medium", "High", "Ultra"]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SettingsState:
    """All mutable settings controlled by the panel.

    Attributes:
        notifications_enabled: Master switch for push notifications.
        email_alerts: Whether to send e-mail alerts on events.
        sound_enabled: Whether in-app sounds are active.
        auto_save: Whether drafts are saved automatically.
        theme_index: Index into ``_THEME_OPTIONS`` (0=System, 1=Light, 2=Dark).
        language_index: Index into ``_LANGUAGE_OPTIONS``.
        volume: Playback volume in ``[0, 100]``.
        font_size: Preferred font size in ``[10, 30]`` logical points.
        quality_index: Index into ``_QUALITY_OPTIONS`` (stream/render quality).
    """

    notifications_enabled: bool = True
    email_alerts: bool = False
    sound_enabled: bool = True
    auto_save: bool = True
    theme_index: int = 0
    language_index: int = 0
    volume: float = 70.0
    font_size: float = 16.0
    quality_index: int = 2


def make_state() -> SettingsState:
    """Build the initial settings state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults.
    """
    return SettingsState()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _notifications_card(app: App[SettingsState]) -> Widget:
    """Render the Notifications section with Switch and Checkbox controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the notification preference controls.
    """
    state: SettingsState = app.state

    def on_notifications_toggle(event: ToggleEvent) -> None:
        """Toggle master notification switch."""
        app.set_state(lambda s: setattr(s, "notifications_enabled", event.checked))

    def on_email_toggle(event: ToggleEvent) -> None:
        """Toggle e-mail alert preference."""
        app.set_state(lambda s: setattr(s, "email_alerts", event.checked))

    def on_sound_toggle(event: ToggleEvent) -> None:
        """Toggle in-app sound preference."""
        app.set_state(lambda s: setattr(s, "sound_enabled", event.checked))

    return Card(
        key="notifications-card",
        children=[
            Text(
                content="Notifications",
                key="notif-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="notif-divider"),
            Row(
                key="notif-master-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Enable notifications",
                        key="notif-master-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.notifications_enabled,
                        on_change=on_notifications_toggle,
                        key="notif-switch",
                    ),
                ],
            ),
            Checkbox(
                label="Send e-mail alerts",
                checked=state.email_alerts,
                on_change=on_email_toggle,
                key="email-checkbox",
            ),
            Checkbox(
                label="Play sounds",
                checked=state.sound_enabled,
                on_change=on_sound_toggle,
                key="sound-checkbox",
            ),
        ],
    )


def _appearance_card(app: App[SettingsState]) -> Widget:
    """Render the Appearance section with SegmentedControl and Slider controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the theme, font-size and quality controls.
    """
    state: SettingsState = app.state

    def on_theme_select(index: int) -> None:
        """Select a colour theme."""
        app.set_state(lambda s: setattr(s, "theme_index", index))

    def on_quality_select(index: int) -> None:
        """Select the render/stream quality level."""
        app.set_state(lambda s: setattr(s, "quality_index", index))

    def on_font_size_change(event: SlideEvent) -> None:
        """Adjust the preferred font size."""
        app.set_state(lambda s: setattr(s, "font_size", round(event.value, 1)))

    return Card(
        key="appearance-card",
        children=[
            Text(
                content="Appearance",
                key="appearance-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="appearance-divider"),
            Text(
                content="Theme",
                key="theme-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_THEME_OPTIONS,
                selected=state.theme_index,
                on_select=on_theme_select,
                key="theme-segments",
            ),
            Text(
                content=f"Font size: {state.font_size:.0f} pt",
                key="font-size-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.font_size,
                min_value=10.0,
                max_value=30.0,
                step=1.0,
                on_change=on_font_size_change,
                key="font-slider",
            ),
            Text(
                content="Render quality",
                key="quality-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_QUALITY_OPTIONS,
                selected=state.quality_index,
                on_select=on_quality_select,
                key="quality-segments",
            ),
        ],
    )


def _audio_card(app: App[SettingsState]) -> Widget:
    """Render the Audio section with a volume Slider and auto-save Switch.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the audio and save controls.
    """
    state: SettingsState = app.state

    def on_volume_change(event: SlideEvent) -> None:
        """Adjust playback volume."""
        app.set_state(lambda s: setattr(s, "volume", round(event.value)))

    def on_auto_save_toggle(event: ToggleEvent) -> None:
        """Toggle auto-save preference."""
        app.set_state(lambda s: setattr(s, "auto_save", event.checked))

    return Card(
        key="audio-card",
        children=[
            Text(
                content="Audio & Storage",
                key="audio-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="audio-divider"),
            Text(
                content=f"Volume: {state.volume:.0f}%",
                key="volume-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.volume,
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                on_change=on_volume_change,
                key="volume-slider",
            ),
            Row(
                key="auto-save-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Auto-save drafts",
                        key="auto-save-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.auto_save,
                        on_change=on_auto_save_toggle,
                        key="auto-save-switch",
                    ),
                ],
            ),
        ],
    )


def _language_card(app: App[SettingsState]) -> Widget:
    """Render the Language section with a RadioGroup control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the language radio group.
    """
    state: SettingsState = app.state

    def on_language_select(index: int) -> None:
        """Select the preferred interface language."""
        app.set_state(lambda s: setattr(s, "language_index", index))

    return Card(
        key="language-card",
        children=[
            Text(
                content="Language",
                key="language-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="language-divider"),
            RadioGroup(
                options=_LANGUAGE_OPTIONS,
                selected=state.language_index,
                on_select=on_language_select,
                key="language-radio",
            ),
        ],
    )


def _summary_card(state: SettingsState) -> Widget:
    """Render a live summary of all current settings.

    Args:
        state: The current snapshot of :class:`SettingsState`.

    Returns:
        A ``Card`` listing all current setting values.
    """
    theme_name: str = _THEME_OPTIONS[state.theme_index]
    language_name: str = _LANGUAGE_OPTIONS[state.language_index]
    quality_name: str = _QUALITY_OPTIONS[state.quality_index]
    notif_text: str = "on" if state.notifications_enabled else "off"
    email_text: str = "yes" if state.email_alerts else "no"
    sound_text: str = "on" if state.sound_enabled else "off"
    save_text: str = "on" if state.auto_save else "off"

    lines: list[Widget] = [
        Text(
            content="Live summary",
            key="summary-heading",
            style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="summary-divider"),
        Text(
            content=f"Notifications: {notif_text}  |  E-mail alerts: {email_text}",
            key="summary-notif",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Sound: {sound_text}  |  Auto-save: {save_text}",
            key="summary-sound",
            style=Style(font_size=13.0),
        ),
        Text(
            content=(
                f"Theme: {theme_name}  |  Font: {state.font_size:.0f} pt"
                f"  |  Quality: {quality_name}"
            ),
            key="summary-appearance",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Volume: {state.volume:.0f}%  |  Language: {language_name}",
            key="summary-audio",
            style=Style(font_size=13.0),
        ),
    ]

    return Card(key="summary-card", children=lines)


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[SettingsState]) -> Widget:
    """Render the full settings panel from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    return Scaffold(
        key="settings-scaffold",
        app_bar=AppBar(title="Settings", key="settings-appbar"),
        body=Column(
            key="settings-body",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _notifications_card(app),
                _appearance_card(app),
                _audio_card(app),
                _language_card(app),
                _summary_card(app.state),
            ],
        ),
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/settings-panel/app.py
```

Python runs **inside the browser** via Pyodide. No server required — open the URL printed in the terminal.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/settings-panel/app.py
```

Python runs on the server; the browser receives JSON patches over WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode, confirm that:

    1. `AppBar` shows the title **Settings** at the top
    2. Four cards appear: Notifications, Appearance, Audio & Storage, Language
    3. Toggling the master notifications `Switch` updates the `notifications` field in the summary card
    4. Moving the volume slider changes the **"Volume: XX%"** label above it and the corresponding field in the summary
    5. Clicking a segment on the theme `SegmentedControl` changes the `Theme` field in the summary
    6. Selecting a language in the `RadioGroup` changes the `Language` field in the summary

---

## Automated verification ✅

```bash
# Lint
ruff check .

# Format
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All four must pass green. The example is written to be `mypy --strict` clean — every variable, parameter, and return value is annotated explicitly.

---

## How it works under the hood

### The update cycle

```
User interacts with a control
          │
          ▼
handler (e.g. on_volume_change)
          │
          ▼
app.set_state(lambda mutator)
          │
          ▼
tempestweb applies the mutator → new state
          │
          ▼
view(app) called again → new widget tree
          │
          ▼
reconciler computes diff (minimal patches)
          │
          ▼
DOM updated — only what changed
```

### Why split into section builders?

`view` could build everything inline, but it would be over 200 lines. Splitting into `_notifications_card`, `_appearance_card`, and so on brings two benefits:

1. **Readability:** each function fits on one screen — immediate purpose, no scrolling.
2. **Testability:** each builder takes `App[SettingsState]` and returns `Widget` — you can test them in isolation by injecting an `app` with a fixed state.

### State as index, not as string

Storing `theme_index: int` instead of `theme: str` has an important consequence: the same serialized state works with option lists in any language. If you want to localize theme labels, just swap `_THEME_OPTIONS` — the state itself does not change.

---

## Recap

In this tutorial you learned:

- ✅ Model **multiple control types** (bool, int, float) in a single typed dataclass
- ✅ Use `Switch` and `Checkbox` with `ToggleEvent.checked`
- ✅ Use `Slider` with `SlideEvent.value` and explicit rounding
- ✅ Use `SegmentedControl` and `RadioGroup` with an integer index as state
- ✅ Organise the UI into **independent, testable section builders**
- ✅ Build a **live summary card** as proof of two-way binding
- ✅ Use `Scaffold` + `AppBar` as the standard page structure

---

## Next steps

- 💡 Explore [Tabs Profile](./tabs-profile.en.md) to see `Switch` and `Checkbox` inside a tabbed panel
- 💡 See [Stopwatch](./stopwatch.en.md) to learn temporal state management with `asyncio`
- 💡 Read [Managing state](../tutorial/state.md) for a complete treatment of the `set_state` cycle
- 💡 Add persistence: serialize `SettingsState` to `localStorage` in Mode A via `pyodide.ffi`, or to a REST endpoint in Mode B
