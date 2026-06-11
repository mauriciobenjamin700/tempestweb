"""Animation demo — proves implicit CSS transitions (E.4).

A box carries a ``Style`` with a ``Transition``; clicking "toggle" changes its
width and background. Because the style declares a transition, the leaf renderer
emits a CSS ``transition`` shorthand, so the browser tweens the change instead of
snapping. The same ``view`` runs in both modes.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Container, Style, Text, Widget
from tempest_core.style import Color, Curve, Edge, Transition


@dataclass
class AnimState:
    """State for the animation demo."""

    wide: bool = False


def make_state() -> AnimState:
    """Build the initial state.

    Returns:
        A fresh :class:`AnimState`.
    """
    return AnimState()


def view(app: App[AnimState]) -> Widget:
    """Render a box that animates its width/color on toggle.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def toggle() -> None:
        app.set_state(lambda s: setattr(s, "wide", not s.wide))

    wide = app.state.wide
    box = Container(
        key="box",
        style=Style(
            width=240.0 if wide else 100.0,
            height=48.0,
            background=Color.from_hex("#3366ff" if wide else "#cccccc"),
            transition=Transition(duration_ms=300, curve=Curve.EASE_IN_OUT),
        ),
        children=[],
    )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Wide: {wide}", key="state"),
            box,
            Button(label="toggle", on_click=toggle, key="toggle"),
        ],
    )
