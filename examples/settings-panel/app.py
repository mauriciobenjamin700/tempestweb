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

from tempestweb._core.style import AlignItems, Edge, FontWeight
from tempestweb._core.widgets.events import SlideEvent, ToggleEvent

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import (
    AppBar,
    Card,
    Divider,
    RadioGroup,
    Scaffold,
    SegmentedControl,
)
from tempestweb._core.widgets import (
    Checkbox,
    Column,
    Row,
    Slider,
    Switch,
    Text,
)

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
        """Toggle master notification switch.

        Args:
            event: The toggle event carrying the new checked state.
        """
        app.set_state(lambda s: setattr(s, "notifications_enabled", event.checked))

    def on_email_toggle(event: ToggleEvent) -> None:
        """Toggle e-mail alert preference.

        Args:
            event: The toggle event carrying the new checked state.
        """
        app.set_state(lambda s: setattr(s, "email_alerts", event.checked))

    def on_sound_toggle(event: ToggleEvent) -> None:
        """Toggle in-app sound preference.

        Args:
            event: The toggle event carrying the new checked state.
        """
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
        """Select a colour theme.

        Args:
            index: The segment index corresponding to the chosen theme.
        """
        app.set_state(lambda s: setattr(s, "theme_index", index))

    def on_quality_select(index: int) -> None:
        """Select the render/stream quality level.

        Args:
            index: The segment index corresponding to the chosen quality.
        """
        app.set_state(lambda s: setattr(s, "quality_index", index))

    def on_font_size_change(event: SlideEvent) -> None:
        """Adjust the preferred font size.

        Args:
            event: The slide event carrying the new float value.
        """
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
        """Adjust playback volume.

        Args:
            event: The slide event carrying the new volume in ``[0, 100]``.
        """
        app.set_state(lambda s: setattr(s, "volume", round(event.value)))

    def on_auto_save_toggle(event: ToggleEvent) -> None:
        """Toggle auto-save preference.

        Args:
            event: The toggle event carrying the new checked state.
        """
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
        """Select the preferred interface language.

        Args:
            index: The radio option index corresponding to the chosen language.
        """
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


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[SettingsState]) -> Widget:
    """Render the full settings panel from the current state.

    Sections are laid out vertically:

    1. **Notifications** — :class:`~tempestweb._core.widgets.inputs.Switch` +
       :class:`~tempestweb._core.widgets.inputs.Checkbox` controls.
    2. **Appearance** — :class:`~tempestweb._core.components.SegmentedControl` for
       theme and quality, :class:`~tempestweb._core.widgets.inputs.Slider` for
       font size.
    3. **Audio & Storage** — :class:`~tempestweb._core.widgets.inputs.Slider` for
       volume, :class:`~tempestweb._core.widgets.inputs.Switch` for auto-save.
    4. **Language** — :class:`~tempestweb._core.components.RadioGroup` single-choice.
    5. **Live summary** — re-renders every time any control changes state.

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
