"""Dark mode — the core resolves every widget's colour from the theme you pass.

The idiom this example exists to show is one line long::

    Button(label="Save", theme=app.theme, on_click=save)

A **styled** widget resolves its Material 3 colours from its own ``theme`` field.
Pass ``app.theme`` and the whole tree follows ``app.set_theme(...)``; leave it out
and the widget resolves the light palette, whatever the app's theme says. That is
the core's rule in every mode — and in Mode C it used to be unreachable, because
the generated style tables were baked from the light theme and the builders
refused the kwarg (tempestweb#106).

A layout widget (``Row``, ``Column``, ``Text``) carries no colour of its own, so
the core gives it no ``theme`` field and passing one raises — the colour it shows
is the one it inherits from the styled box around it.

Run unchanged in all three modes::

    tempestweb run --mode server --path examples/dark-mode --port 8000
    tempestweb run --mode wasm   --path examples/dark-mode --port 8000
    tempestweb build --mode transpile --path examples/dark-mode
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import (
    Alert,
    App,
    Badge,
    Button,
    Card,
    Column,
    Edge,
    FontWeight,
    Input,
    Row,
    Style,
    Text,
    TextChangeEvent,
    Theme,
    ThemeMode,
    Widget,
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


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
    """Build the initial state (light, with an empty field).

    Returns:
        A fresh :class:`DarkModeState`.
    """
    return DarkModeState()


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[DarkModeState]) -> Widget:
    """Render the sample tree, every widget resolving from ``app.theme``.

    Args:
        app: The application handle exposing ``state``, ``set_state``, ``theme``
            and ``set_theme``.

    Returns:
        The full widget tree for the current theme.
    """
    theme: Theme = app.theme

    def choose(dark: bool = False) -> None:
        """Swap the app's theme, which re-resolves every widget below.

        Args:
            dark: Whether to switch to the dark theme.
        """
        app.set_state(lambda state: setattr(state, "dark", dark))
        app.set_theme(Theme(mode=ThemeMode.DARK if dark else ThemeMode.LIGHT))

    def edit(event: TextChangeEvent) -> None:
        """Hold what the reader types, so the field is really controlled.

        Args:
            event: The change event carrying the field's value.
        """
        app.set_state(lambda state: setattr(state, "draft", event.value))

    return Column(
        key="dark-body",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Row(
                key="mode-row",
                style=Style(gap=12.0),
                children=[
                    Text(
                        content="Dark mode",
                        key="mode-label",
                        style=Style(font_size=18.0, font_weight=FontWeight.BOLD),
                    ),
                    Button(
                        key="mode-light",
                        label="Light",
                        variant="outline" if app.state.dark else "solid",
                        on_click=lambda: choose(False),
                        theme=theme,
                    ),
                    Button(
                        key="mode-dark",
                        label="Dark",
                        variant="solid" if app.state.dark else "outline",
                        on_click=lambda: choose(True),
                        theme=theme,
                    ),
                ],
            ),
            Card(
                key="sample-card",
                theme=theme,
                children=[
                    Text(
                        content="A card, a badge, a field and a button",
                        key="sample-title",
                        style=Style(font_weight=FontWeight.BOLD),
                    ),
                    Row(
                        key="sample-row",
                        style=Style(gap=8.0),
                        children=[
                            Badge(key="sample-badge", label="new", theme=theme),
                            Badge(
                                key="sample-badge-error",
                                label="late",
                                color_scheme="error",
                                theme=theme,
                            ),
                        ],
                    ),
                    Input(
                        key="sample-input",
                        value=app.state.draft,
                        placeholder="Type here",
                        on_change=edit,
                        theme=theme,
                    ),
                    Button(
                        key="sample-button",
                        label="Save",
                        on_click=lambda: None,
                        theme=theme,
                    ),
                ],
            ),
            Alert(
                key="sample-alert",
                title="Every colour above came from the theme",
                body=f"Draft: {app.state.draft or '(empty)'}",
                theme=theme,
            ),
        ],
    )
