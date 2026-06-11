"""a11y + i18n + theme demo (E.7).

Shows the three cross-cutting concerns reaching the DOM: the greeting is
localized with the core's ``translate`` (toggle the language), the button carries
``Semantics`` (mapped to ARIA) and is ``focusable`` (mapped to ``tabindex``), and
the greeting's color comes from a typed ``Style`` (the theme layer). The same
``view`` runs in both modes.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Locale, Style, Text, Widget, translate
from tempest_core.style import Color, Edge
from tempest_core.widgets import Semantics

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {"greeting": "Hello"},
    "pt": {"greeting": "Olá"},
}


@dataclass
class A11yState:
    """State for the a11y/i18n demo."""

    lang: str = "en"


def make_state() -> A11yState:
    """Build the initial state.

    Returns:
        A fresh :class:`A11yState`.
    """
    return A11yState()


def view(app: App[A11yState]) -> Widget:
    """Render a localized greeting and an accessible language toggle.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """
    locale = Locale(language=app.state.lang)

    def toggle() -> None:
        app.set_state(lambda s: setattr(s, "lang", "pt" if s.lang == "en" else "en"))

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(
                content=translate("greeting", locale, TRANSLATIONS),
                key="greeting",
                style=Style(color=Color.from_hex("#3366ff")),
            ),
            Button(
                label="lang",
                on_click=toggle,
                key="lang",
                semantics=Semantics(label="Toggle language", role="button"),
                focusable=True,
            ),
        ],
    )
