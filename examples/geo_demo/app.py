"""Geolocation demo — a native capability running in-process in Mode A.

Clicking "locate" calls the native :func:`tempestweb.native.get_position`, which
sends a ``geolocation.get`` native_call. In Mode A the bootstrap's in-process FFI
bridge resolves it against the browser's Geolocation API with no network hop; in
Mode B it is proxied to the client over the transport. Same ``view`` either way.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Style, Text, Widget
from tempest_core.style import Edge

from tempestweb.native import get_position


@dataclass
class GeoState:
    """State for the geolocation demo."""

    status: str = "idle"
    coords: str = ""


def make_state() -> GeoState:
    """Build the initial state.

    Returns:
        A fresh :class:`GeoState`.
    """
    return GeoState()


def view(app: App[GeoState]) -> Widget:
    """Render a button that fetches and shows the device position.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    async def locate() -> None:
        app.set_state(lambda s: setattr(s, "status", "locating…"))
        try:
            position = await get_position()
        except Exception as error:  # noqa: BLE001 - surface any capability failure
            message = str(error)

            def fail(state: GeoState) -> None:
                state.status = f"error: {message}"

            app.set_state(fail)
            return

        coords = f"{position.latitude:.3f}, {position.longitude:.3f}"

        def done(state: GeoState) -> None:
            state.status = "located"
            state.coords = coords

        app.set_state(done)

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Status: {app.state.status}", key="status"),
            Text(content=app.state.coords, key="coords"),
            Button(label="locate", on_click=locate, key="locate"),
        ],
    )
