"""Gesture demo — proves pointer gestures reach Python handlers (E.5).

A :class:`GestureDetector` wraps a pad; swiping it fires ``on_swipe`` with a
direction and tapping fires ``on_tap``. The client recognizes the gesture from
pointer events and routes a typed event to the handler. The same ``view`` runs in
both modes.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Container, Style, Text, Widget
from tempest_core.style import Color, Edge
from tempest_core.widgets.events import SwipeEvent, TapEvent
from tempest_core.widgets.gestures import GestureDetector


@dataclass
class GestureState:
    """State for the gesture demo."""

    last: str = "none"


def make_state() -> GestureState:
    """Build the initial state.

    Returns:
        A fresh :class:`GestureState`.
    """
    return GestureState()


def view(app: App[GestureState]) -> Widget:
    """Render a gesture pad that reports the last recognized gesture.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def on_swipe(event: SwipeEvent) -> None:
        app.set_state(lambda s: setattr(s, "last", f"swipe {event.direction}"))

    def on_tap(_event: TapEvent) -> None:
        app.set_state(lambda s: setattr(s, "last", "tap"))

    pad = GestureDetector(
        key="pad",
        on_swipe=on_swipe,
        on_tap=on_tap,
        child=Container(
            key="pad-box",
            style=Style(
                width=240.0,
                height=120.0,
                background=Color.from_hex("#dde3ff"),
                padding=Edge.all(16),
            ),
            child=Text(content="swipe or tap me", key="hint"),
        ),
    )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Last: {app.state.last}", key="last"),
            pad,
        ],
    )
