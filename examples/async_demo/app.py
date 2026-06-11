"""Async demo — proves an ``async`` handler with ``await`` updates the UI (A2).

The same ``view`` runs in both modes. The ``load`` handler is ``async``: it sets a
"loading…" status, ``await``s a timer, then commits the result. Because the
runtime awaits the handler on the browser's event loop (Mode A) / the server's
(Mode B), the tab never freezes — the "loading…" frame paints immediately and the
"done" frame follows after the await.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tempestweb._core import App, Button, Column, Style, Text, Widget
from tempestweb._core.style import Edge


@dataclass
class AsyncState:
    """State for the async demo."""

    status: str = "idle"
    loads: int = 0


def make_state() -> AsyncState:
    """Build the initial state.

    Returns:
        A fresh :class:`AsyncState`.
    """
    return AsyncState()


def view(app: App[AsyncState]) -> Widget:
    """Render the async demo UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def _finish(s: AsyncState) -> None:
        """Commit the completed load."""
        s.status = "done"
        s.loads += 1

    async def load() -> None:
        """Set a pending status, await a timer, then commit the result."""
        app.set_state(lambda s: setattr(s, "status", "loading…"))
        await asyncio.sleep(0.4)
        app.set_state(_finish)

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Status: {app.state.status}", key="status"),
            Text(content=f"Loads: {app.state.loads}", key="loads"),
            Button(label="load", on_click=load, key="load"),
        ],
    )
