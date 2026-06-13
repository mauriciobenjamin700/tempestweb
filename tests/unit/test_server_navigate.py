"""Mode B view → URL navigation (the reverse of the inbound ``navigate`` event).

When the app navigates imperatively inside a handler (``app.push`` / ``pop`` /
``reset``), the top route changes, so the session emits a ``navigate`` envelope
telling the client to sync its URL via ``history.pushState``. These tests drive
that emission through the real :class:`~tempestweb.transports.sse.SSETransport`
and assert the envelope shape, that no envelope is emitted when the route is
unchanged, and that the initial ``/`` mount does not push a redundant URL.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from tempest_core import App, Button, Column, Text, Widget
from tempest_core.navigation import Route
from tempestweb.runtime.session import AppSession
from tempestweb.transports.sse import SSETransport


@dataclass
class NavState:
    """Trivial state; the screen comes from ``app.nav``, not state."""


def make_state() -> NavState:
    """Build a fresh empty state."""
    return NavState()


def view(app: App[NavState]) -> Widget:
    """Render the top route's name plus buttons that navigate imperatively.

    Args:
        app: The application handle; ``app.nav.top.name`` is the active route.

    Returns:
        The widget tree for the active route.
    """
    return Column(
        children=[
            Text(content=app.nav.top.name, key="route"),
            Button(
                label="Details",
                on_click=lambda: app.push(Route(name="/details")),
                key="go-details",
            ),
            Button(label="Noop", on_click=lambda: None, key="noop"),
        ]
    )


async def _next_envelope(stream: object) -> dict[str, object]:
    """Pull the next non-ping SSE frame and decode its envelope.

    Args:
        stream: The SSE async iterator returned by ``transport.stream()``.

    Returns:
        The decoded JSON envelope of the next data frame.
    """
    while True:
        frame = await asyncio.wait_for(stream.__anext__(), 1.0)  # type: ignore[attr-defined]
        if "data: " in frame and "event: ping" not in frame:
            return json.loads(frame.split("data: ", 1)[1])


async def test_imperative_navigation_emits_navigate_envelope() -> None:
    """A handler calling ``app.push`` makes the session emit a navigate envelope."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[NavState] = AppSession(make_state, view, transport)
    await session.start()

    stream = transport.stream()
    initial = await _next_envelope(stream)
    assert initial["kind"] == "patches"  # initial mount, no navigate yet

    await session.dispatch({"type": "click", "key": "go-details", "payload": {}})

    # The rebuild's patches flush first, then the navigate envelope for the new
    # top route (order: send_patches then _emit_nav_if_changed in _apply_patches).
    patches = await _next_envelope(stream)
    assert patches["kind"] == "patches"
    navigate = await _next_envelope(stream)
    assert navigate == {"kind": "navigate", "path": "/details"}

    await stream.aclose()
    await session.close()


async def test_handler_without_navigation_emits_no_navigate() -> None:
    """A handler that does not navigate emits no navigate envelope."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[NavState] = AppSession(make_state, view, transport)
    await session.start()

    stream = transport.stream()
    await _next_envelope(stream)  # initial mount

    # The noop handler triggers a rebuild (set_state-free, but request_rebuild is
    # not called, so no patches either) — there must be no navigate envelope.
    await session.dispatch({"type": "click", "key": "noop", "payload": {}})
    await session.dispatch({"type": "click", "key": "go-details", "payload": {}})

    # First real envelope after the two clicks is the /details navigation, never a
    # spurious navigate for the unchanged "/" route.
    patches = await _next_envelope(stream)
    assert patches["kind"] == "patches"
    navigate = await _next_envelope(stream)
    assert navigate == {"kind": "navigate", "path": "/details"}

    await stream.aclose()
    await session.close()
