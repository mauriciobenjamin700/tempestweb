"""Async fetch view — exercises an ``async`` handler driving the UI.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates async-first handlers: pressing *Load* runs an ``async`` handler
that flips the view into a loading state (rendering a
:class:`~tempest_core.widgets.Spinner`), awaits an I/O-bound fetch, then
calls :meth:`App.set_state` again with the result — idle → loading → loaded/error.
The ``fetch`` callable is injected so the example is deterministic under test
(the real app would pass ``native.http.request``); the view never blocks the
event loop.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    LazyColumn,
    Spinner,
    Text,
)

#: A coroutine that resolves to the fetched rows. Injected into the view so the
#: example stays deterministic under test; in a real app this wraps
#: ``native.http.request``.
Fetcher = Callable[[], Awaitable[list[str]]]


class Phase(StrEnum):
    """The lifecycle phase of the async fetch.

    Attributes:
        IDLE: Nothing has been requested yet.
        LOADING: A fetch is in flight (the spinner is shown).
        LOADED: The fetch resolved and rows are available.
        ERROR: The fetch raised; an error message is shown.
    """

    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


async def _default_fetch() -> list[str]:
    """Return a fixed list of rows, standing in for a network call.

    Returns:
        A small list of sample rows.
    """
    return ["alpha", "beta", "gamma"]


@dataclass
class FetchState:
    """State for the async fetch app.

    Attributes:
        phase: The current lifecycle phase.
        rows: The rows fetched on success.
        error: The error message shown on failure.
        fetch: The injected coroutine that performs the fetch.
    """

    phase: Phase = Phase.IDLE
    rows: list[str] = field(default_factory=list)
    error: str = ""
    fetch: Fetcher = _default_fetch


def make_state() -> FetchState:
    """Build the initial, idle fetch state.

    Returns:
        A fresh :class:`FetchState`.
    """
    return FetchState()


def view(app: App[FetchState]) -> Widget:
    """Render the fetch UI from the current lifecycle phase.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    async def load() -> None:
        app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))
        try:
            rows = await app.state.fetch()
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            # Bind the message before the except block clears ``exc`` so the
            # closure below captures a live value.
            message = str(exc)

            def on_error(s: FetchState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        def on_success(s: FetchState) -> None:
            s.phase = Phase.LOADED
            s.rows = rows

        app.set_state(on_success)

    children: list[Widget] = [
        Text(content="Async fetch", key="title"),
        Button(label="Load", on_click=load, key="load"),
    ]

    if app.state.phase is Phase.LOADING:
        children.append(Spinner(key="spinner"))
    elif app.state.phase is Phase.ERROR:
        children.append(Text(content=f"Error: {app.state.error}", key="error"))
    elif app.state.phase is Phase.LOADED:
        rows = app.state.rows
        children.append(
            LazyColumn(
                item_count=len(rows),
                item_builder=lambda i: Text(content=rows[i]),
                key="rows",
            )
        )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=children,
    )
