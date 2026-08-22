"""Gesture demo — every pointer gesture the core declares, in one screen.

Three surfaces, because the core has three kinds of gesture widget and they
recognize different things from the same pointers:

* a :class:`GestureDetector` reports ``on_tap``, ``on_double_tap``,
  ``on_long_press`` and ``on_swipe`` — the discrete gestures;
* a :class:`PanHandler` reports ``on_pan`` continuously while a pointer drags,
  with deltas and velocity, which is what moves something under the finger;
* an :class:`InteractiveViewer` reports ``on_interaction``: one pointer pans it,
  two pinch it, and both arrive as a scale plus a focus point.

The client recognizes all of them from pointer events and routes typed events to
the handlers, so the same ``view`` runs in every mode::

    tempestweb run --mode server --path examples/gesture_demo
    tempestweb run --mode wasm --path examples/gesture_demo
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Container, Style, Text, Widget
from tempest_core.style import Color, Edge
from tempest_core.widgets.events import PanEvent, ScaleEvent, SwipeEvent, TapEvent
from tempest_core.widgets.gestures import (
    GestureDetector,
    InteractiveViewer,
    PanHandler,
)


@dataclass
class GestureState:
    """State for the gesture demo.

    Attributes:
        last: The last discrete gesture the pad recognized.
        offset_x: How far the pan surface has been dragged, horizontally.
        offset_y: How far the pan surface has been dragged, vertically.
        zoom: The viewer's current scale, from the last pinch.
        focus: Where the viewer's last interaction was centred.
    """

    last: str = "none"
    offset_x: float = 0.0
    offset_y: float = 0.0
    zoom: float = 1.0
    focus: str = "—"


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

    def on_double_tap(_event: TapEvent) -> None:
        app.set_state(lambda s: setattr(s, "last", "double tap"))

    def on_pan(event: PanEvent) -> None:
        """Accumulate a drag, which is what a pan is for.

        Args:
            event: The pan step, carrying this frame's deltas and velocity.
        """

        def mutate(state: GestureState) -> None:
            state.offset_x += event.dx
            state.offset_y += event.dy

        app.set_state(mutate)

    def on_interaction(event: ScaleEvent) -> None:
        """Record a pan-or-zoom on the viewer.

        Args:
            event: The interaction, carrying the scale and its focus point.
        """

        def mutate(state: GestureState) -> None:
            state.zoom = event.scale
            state.focus = f"{event.focus_x:.0f}, {event.focus_y:.0f}"

        app.set_state(mutate)

    pad = GestureDetector(
        key="pad",
        on_swipe=on_swipe,
        on_tap=on_tap,
        on_double_tap=on_double_tap,
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

    pan_surface = PanHandler(
        key="pan",
        on_pan=on_pan,
        child=Container(
            key="pan-box",
            style=Style(
                width=240.0,
                height=100.0,
                background=Color.from_hex("#d7f5dd"),
                padding=Edge.all(16),
            ),
            child=Text(content="drag me", key="pan-hint"),
        ),
    )

    viewer = InteractiveViewer(
        key="viewer",
        on_interaction=on_interaction,
        child=Container(
            key="viewer-box",
            style=Style(
                width=240.0,
                height=100.0,
                background=Color.from_hex("#ffe8cc"),
                padding=Edge.all(16),
            ),
            child=Text(content="drag or pinch me", key="viewer-hint"),
        ),
    )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Last: {app.state.last}", key="last"),
            pad,
            Text(
                content=(
                    f"Pan offset: {app.state.offset_x:.0f}, {app.state.offset_y:.0f}"
                ),
                key="offset",
            ),
            pan_surface,
            Text(
                content=f"Zoom: {app.state.zoom:.2f} · focus {app.state.focus}",
                key="zoom",
            ),
            viewer,
        ],
    )
