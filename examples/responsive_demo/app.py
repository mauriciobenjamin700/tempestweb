"""Responsive demo — the same view, two layouts, driven by ``app.media``.

The browser owns the viewport; the app reads it from ``app.media``, which the
client keeps current by reporting a snapshot on mount and on every resize. A
``view`` can therefore branch on it: below :data:`BREAKPOINT` the cards stack in
a column with their labels above the values, above it they sit in a row.

The header prints the live snapshot, which is the point of the demo: before the
``media`` event was wired into the Python-side runtimes, a Mode A or Mode B app
read ``0 × 0`` here forever and both layouts were decided by a lie.

Run it and resize the window::

    tempestweb run --mode server --path examples/responsive_demo
    tempestweb run --mode wasm --path examples/responsive_demo
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import (
    App,
    Button,
    Color,
    Column,
    Container,
    Edge,
    Row,
    Style,
    Text,
    Widget,
)

#: Viewport width (px) at which the layout switches from stacked to side by side.
BREAKPOINT = 700.0

#: The cards the demo lays out, as (label, value) pairs.
CARDS: tuple[tuple[str, str], ...] = (
    ("Requests", "1.2M"),
    ("Errors", "0.4%"),
    ("p95", "180ms"),
)


@dataclass
class ResponsiveState:
    """State for the responsive demo.

    Attributes:
        taps: How many times the button was pressed, to prove that state and
            handlers survive a layout switch.
    """

    taps: int = 0


def make_state() -> ResponsiveState:
    """Build the initial state.

    Returns:
        A fresh :class:`ResponsiveState`.
    """
    return ResponsiveState()


def view(app: App[ResponsiveState]) -> Widget:
    """Render the dashboard in the layout the current viewport calls for.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current viewport and state.
    """
    wide = app.media.width >= BREAKPOINT

    def card(label: str, value: str) -> Widget:
        """Build one metric card.

        ``grow`` is the only style that differs between the two layouts: side by
        side the cards share the row, stacked they keep their natural height.

        Args:
            label: The metric's name.
            value: The metric's current value.

        Returns:
            The card widget, keyed by its label.
        """
        return Container(
            key=f"card-{label}",
            style=Style(
                padding=Edge.all(16),
                radius=12.0,
                background=Color(r=234, g=221, b=255),
                grow=1.0 if wide else 0.0,
            ),
            child=Column(
                style=Style(gap=4.0),
                children=[Text(content=label), Text(content=value)],
            ),
        )

    def bump() -> None:
        """Count a button press, to show state surviving a layout switch."""
        app.set_state(lambda state: setattr(state, "taps", state.taps + 1))

    cards = [card(label, value) for label, value in CARDS]
    layout: Widget = (
        Row(key="cards", style=Style(gap=12.0), children=cards)
        if wide
        else Column(key="cards", style=Style(gap=12.0), children=cards)
    )
    media = app.media
    scheme = "dark" if media.platform_dark_mode else "light"
    snapshot = (
        f"{media.width:.0f} × {media.height:.0f} · "
        f"dpr {media.device_pixel_ratio:.1f} · "
        f"{media.orientation} · {scheme}"
    )
    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(
                content=f"Layout: {'row (wide)' if wide else 'column (narrow)'}",
                key="mode",
            ),
            Text(content=snapshot, key="snapshot"),
            Text(content=f"Presses: {app.state.taps}", key="taps"),
            Button(label="Bump", on_click=bump, key="bump"),
            layout,
        ],
    )
