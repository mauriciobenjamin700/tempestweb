"""Virtualized list demo — windowing, infinite scroll and pull-to-refresh.

A :class:`LazyColumn` declares more items than it materializes: the client
renders only the current window into a scrollable viewport, pads it so the
scrollbar reflects every item, and reports the visible window as it scrolls so
the runtime slides it.

On top of that it wires the two handlers the list declares for its edges:

* ``on_end_reached`` — the client reports ``end_reached`` once the reader crosses
  ``end_reached_threshold`` of the scroll, and the handler loads another page
  (infinite scroll) until the source is exhausted.
* ``on_refresh`` — dragging the list (or the :class:`RefreshControl` above it)
  down from the top reports ``refresh``; the handler flips ``refreshing`` while
  it reloads, which is what draws the spinner and the band at the pull edge.

The same ``view`` runs in every mode::

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (WebSocket)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tempest_core import App, Column, Container, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.events import EndReachedEvent, RefreshEvent
from tempest_core.widgets.lists import LazyColumn, RefreshControl

#: Items added each time the reader reaches the end of the list.
PAGE_SIZE = 25

#: The whole source: infinite scroll stops once every item has been loaded.
TOTAL_ITEMS = 200

#: How long the fake reload takes, so the refreshing state is visible.
RELOAD_SECONDS = 0.6


@dataclass
class ListState:
    """State for the virtualized list demo.

    Attributes:
        loaded: How many items are currently available to the list.
        refreshing: Whether a pull-to-refresh reload is in flight.
        pages: How many pages the reader has loaded by scrolling.
        refreshes: How many reloads have completed.
    """

    loaded: int = PAGE_SIZE
    refreshing: bool = False
    pages: int = 1
    refreshes: int = 0


def make_state() -> ListState:
    """Build the initial state.

    Returns:
        A fresh :class:`ListState` holding the first page.
    """
    return ListState()


def view(app: App[ListState]) -> Widget:
    """Render the list, its pull-to-refresh control and a live status line.

    The list renders a window larger than the viewport, so there is a scroll
    buffer above and below the visible rows before the window has to slide.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def build_row(index: int) -> Widget:
        """Build one row of the list.

        A block-level row (Container) so rows stack vertically in the viewport.

        Args:
            index: The item's absolute index.

        Returns:
            The row widget, keyed by its index.
        """
        return Container(
            key=str(index),
            style=Style(padding=Edge.all(8)),
            child=Text(content=f"Item {index}", key=f"t{index}"),
        )

    def load_more(event: EndReachedEvent) -> None:
        """Load the next page when the reader reaches the end of the list.

        Ignored once every item is loaded — the list keeps reporting
        ``end_reached`` while the reader sits at the bottom, and answering it
        with an unchanged state is what makes that harmless.

        Args:
            event: The end-reached event (it carries no payload).
        """
        if app.state.loaded >= TOTAL_ITEMS:
            return

        def grow(state: ListState) -> None:
            state.loaded = min(TOTAL_ITEMS, state.loaded + PAGE_SIZE)
            state.pages += 1

        app.set_state(grow)

    async def reload(event: RefreshEvent) -> None:
        """Reload the list from the top on a pull-to-refresh.

        The handler is async so ``refreshing`` is actually observable: it renders
        with the spinner running, awaits the (simulated) fetch, then lands the
        fresh first page. A sync handler would flip both halves within one tick
        and the reader would never see the indicator.

        Args:
            event: The refresh event (it carries no payload).
        """
        app.set_state(lambda state: setattr(state, "refreshing", True))
        await asyncio.sleep(RELOAD_SECONDS)

        def done(state: ListState) -> None:
            state.refreshing = False
            state.loaded = PAGE_SIZE
            state.pages = 1
            state.refreshes += 1

        app.set_state(done)

    status = (
        f"{app.state.loaded} of {TOTAL_ITEMS} items · "
        f"{app.state.pages} page(s) scrolled in · "
        f"{app.state.refreshes} reload(s)"
    )
    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(
                content="Scroll to the end to load more; pull down to reload.",
                key="title",
            ),
            Text(content=status, key="status"),
            RefreshControl(
                key="pull", refreshing=app.state.refreshing, on_refresh=reload
            ),
            LazyColumn(
                key="rows",
                item_count=app.state.loaded,
                window_size=30,
                item_builder=build_row,
                refreshing=app.state.refreshing,
                on_end_reached=load_more,
                on_refresh=reload,
                style=Style(height=300.0),
            ),
        ],
    )
