"""Router demo — proves URL-driven navigation (E.1).

``view`` renders a different screen depending on ``app.nav.top`` — the route on
top of the navigation stack. The client reports the document path on load and on
browser back/forward, and the runtime resets the nav stack to that path
(``routes_from_path``), so the URL drives which screen shows. The same ``view``
runs in both modes.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.navigation import Route
from tempest_core.style import Edge


@dataclass
class RouterState:
    """State for the router demo (the screen comes from app.nav, not state)."""


def make_state() -> RouterState:
    """Build the initial state.

    Returns:
        A fresh :class:`RouterState`.
    """
    return RouterState()


def view(app: App[RouterState]) -> Widget:
    """Render the screen for the current top route.

    Args:
        app: The application handle; ``app.nav.top.name`` is the active route.

    Returns:
        The widget tree for the active route.
    """
    route = app.nav.top.name
    if route == "/details":
        screen = Text(content="Details screen", key="screen")
    elif route == "/about":
        screen = Text(content="About screen", key="screen")
    else:
        screen = Text(content="Home screen", key="screen")

    def go(path: str) -> None:
        app.push(Route(name=path))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Route: {route}", key="route"),
            screen,
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(
                        label="Details",
                        on_click=lambda: go("/details"),
                        key="nav-details",
                    ),
                    Button(
                        label="About", on_click=lambda: go("/about"), key="nav-about"
                    ),
                ],
            ),
        ],
    )
