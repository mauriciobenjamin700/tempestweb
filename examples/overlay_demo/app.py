"""Overlay demo — proves the floating overlay layer renders (E.3).

Clicking "open" pushes a :class:`Dialog` onto the app's overlay layer; the dialog
floats above the screen tree. Its "close" button dismisses it by id. The same
``view`` runs in both modes — overlays are part of the scene the reconciler diffs,
so the client renders them into a separate overlay host above the tree.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.overlays import Dialog


@dataclass
class OverlayState:
    """State for the overlay demo."""

    dialog_id: str | None = None
    opened: int = 0


def make_state() -> OverlayState:
    """Build the initial state.

    Returns:
        A fresh :class:`OverlayState`.
    """
    return OverlayState()


def view(app: App[OverlayState]) -> Widget:
    """Render the overlay demo: a button that opens a dismissable dialog.

    Args:
        app: The application handle exposing ``state``, ``set_state`` and the
            imperative overlay API (``show_dialog`` / ``dismiss``).

    Returns:
        The widget tree for the current state.
    """

    def close() -> None:
        """Dismiss the open dialog, if any."""
        if app.state.dialog_id is not None:
            app.dismiss(app.state.dialog_id)
            app.set_state(lambda s: setattr(s, "dialog_id", None))

    def open_dialog() -> None:
        """Push a dialog onto the overlay layer and remember its id."""
        dialog = Dialog(
            title="Hello",
            children=[
                Text(content="I am a floating dialog.", key="dialog-body"),
                Button(label="close", on_click=close, key="dialog-close"),
            ],
            on_dismiss=lambda _event: close(),
        )
        overlay_id = app.show_dialog(dialog, barrier=True)

        def _record(state: OverlayState) -> None:
            state.dialog_id = overlay_id
            state.opened += 1

        app.set_state(_record)

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Opened: {app.state.opened}", key="opened"),
            Button(label="open", on_click=open_dialog, key="open"),
        ],
    )
