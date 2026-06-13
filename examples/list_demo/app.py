"""Virtualized list demo — proves windowed rendering + scroll sliding (E.2).

A :class:`LazyColumn` declares 1000 items but materializes only a small window;
the client renders that window into a scrollable viewport, pads it so the
scrollbar reflects all 1000 items, and reports the visible window as it scrolls so
the runtime slides it. The same ``view`` runs in both modes.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Container, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.lists import LazyColumn

ITEM_COUNT = 1000


@dataclass
class ListState:
    """State for the virtualized list demo."""


def make_state() -> ListState:
    """Build the initial state.

    Returns:
        A fresh :class:`ListState`.
    """
    return ListState()


def view(app: App[ListState]) -> Widget:
    """Render a 1000-item virtualized list inside a bounded viewport.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def build_row(index: int) -> Widget:
        # A block-level row (Container) so rows stack vertically in the viewport.
        return Container(
            key=str(index),
            style=Style(padding=Edge.all(8)),
            child=Text(content=f"Item {index}", key=f"t{index}"),
        )

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"{ITEM_COUNT} items, windowed", key="title"),
            LazyColumn(
                key="rows",
                item_count=ITEM_COUNT,
                # Render more than fits the viewport so there is a scroll buffer
                # above and below the visible rows before the window must slide.
                window_size=60,
                item_builder=build_row,
                style=Style(height=300.0),
            ),
        ],
    )
