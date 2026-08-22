"""Overlay demo — the floating overlay layer, and the rest of the modal contract.

Clicking "open" pushes a :class:`Dialog` onto the app's overlay layer; the dialog
floats above the screen tree. Its "close" button dismisses it by id. The same
``view`` runs in both modes — overlays are part of the scene the reconciler diffs,
so the client renders them into a separate overlay host above the tree.

"actions" opens an :class:`ActionSheet` whose items carry icons, which is what
makes this demo cover the two halves a modal needs beyond painting: the icons a
``MenuItem`` declares are drawn, and while either overlay is open the keyboard
belongs to it — focus moves in, Tab stays inside, and closing hands focus back to
the button that opened it.

The icon names show both registries: a bare name is a Lucide glyph and
``material:`` picks the Material one, so an app can mix them per item.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.events import MenuSelectEvent
from tempest_core.widgets.overlays import ActionSheet, Dialog, MenuItem


@dataclass
class OverlayState:
    """State for the overlay demo."""

    dialog_id: str | None = None
    sheet_id: str | None = None
    opened: int = 0
    chosen: str = "—"


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

    def close_sheet() -> None:
        """Dismiss the open action sheet, if any."""
        if app.state.sheet_id is not None:
            app.dismiss(app.state.sheet_id)
            app.set_state(lambda s: setattr(s, "sheet_id", None))

    def chose(event: MenuSelectEvent) -> None:
        """Record the chosen action and close the sheet.

        Args:
            event: The selection, carrying the item's value and label.
        """
        app.set_state(lambda s: setattr(s, "chosen", event.label))
        close_sheet()

    def open_actions() -> None:
        """Push an action sheet whose items carry icons."""
        sheet = ActionSheet(
            title="Row actions",
            items=[
                MenuItem(label="Edit", value="edit", icon="material:edit"),
                MenuItem(label="Duplicate", value="duplicate", icon="plus"),
                MenuItem(label="Delete", value="delete", icon="trash"),
            ],
            on_select=chose,
        )
        overlay_id = app.show_sheet(sheet, barrier=True)
        app.set_state(lambda s: setattr(s, "sheet_id", overlay_id))

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
            Text(content=f"Chosen: {app.state.chosen}", key="chosen"),
            Button(label="open", on_click=open_dialog, key="open"),
            Button(label="actions", on_click=open_actions, key="actions"),
        ],
    )
