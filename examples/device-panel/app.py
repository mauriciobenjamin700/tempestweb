"""Device panel — Tier-1 web-platform capabilities in one screen.

The same ``view`` runs unchanged in both interactive modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

A small control panel wiring several of the new ``native`` capabilities to
buttons: buzz the device (``vibration``), keep the screen awake
(``wakelock``), go fullscreen (``fullscreen``), and read the connection and
storage-quota state (``network`` / ``quota``). Each is a typed Python awaitable
that resolves the same way in Mode A (in-process) and Mode B (proxied to the
browser and back) — the app code never knows the difference.

The initial mount only reads state, so ``build(view(app))`` is green with no
native bridge installed; the async handlers call the capabilities, and the test
drives them through a scripted bridge.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Text
from tempestweb import native


@dataclass
class PanelState:
    """State for the device panel.

    Attributes:
        status: A short human-readable line describing the last action.
        awake: Whether a screen wake lock is currently held.
        network: The last connection summary read from ``network.state``.
    """

    status: str = "ready"
    awake: bool = False
    network: str = ""


def make_state() -> PanelState:
    """Build the initial state.

    Returns:
        A fresh :class:`PanelState`.
    """
    return PanelState()


def view(app: App[PanelState]) -> Widget:
    """Render the panel and wire each button to a native capability.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    async def buzz() -> None:
        await native.vibration.vibrate([100, 50, 100])
        app.set_state(lambda s: setattr(s, "status", "buzzed"))

    async def toggle_awake() -> None:
        if app.state.awake:
            app.set_state(lambda s: setattr(s, "status", "screen released"))
            app.set_state(lambda s: setattr(s, "awake", False))
        else:
            await native.wakelock.request()
            app.set_state(lambda s: setattr(s, "status", "screen kept awake"))
            app.set_state(lambda s: setattr(s, "awake", True))

    async def go_fullscreen() -> None:
        active = await native.fullscreen.enter()
        app.set_state(lambda s: setattr(s, "status", f"fullscreen={active}"))

    async def read_network() -> None:
        state = await native.network.state()
        summary = f"{state.effective_type} · online={state.online}"
        app.set_state(lambda s: setattr(s, "network", summary))
        app.set_state(lambda s: setattr(s, "status", "network read"))

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Status: {app.state.status}", key="status"),
            Text(content=f"Network: {app.state.network or '—'}", key="network"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Button(label="Buzz", on_click=buzz, key="buzz"),
                    Button(label="Keep awake", on_click=toggle_awake, key="awake"),
                    Button(label="Fullscreen", on_click=go_fullscreen, key="fs"),
                    Button(label="Network", on_click=read_network, key="net"),
                ],
            ),
        ],
    )
