"""``App.media`` in Modes A and B (issue #74).

``MediaQueryData``'s docstring promises the renderer keeps it current, and the
client had reported the viewport since Mode C — but nothing in this package ever
called ``App._update_media``, so a server-side app ran forever on the default
snapshot (``width`` and ``height`` both ``0.0``). A responsive ``view`` had no
width to branch on, and ``Scaffold(scroll=True)`` had no height to bound its
frame with, because ``Style`` has no ``100vh``.

These pin the Python half: the wire payload becomes a ``MediaQueryData``, a
malformed one is refused instead of poisoning the context, and a ``media`` event
dispatched through a real session reaches ``app.media`` and rebuilds the view.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempest_core import App, Text
from tempestweb.runtime import AppSession
from tempestweb.runtime.events import apply_media
from tempestweb.transports.base import Event, Patch, TransportClosedError


@dataclass
class _State:
    """State for the media tests."""

    value: int = 0


def _app() -> App[_State]:
    """Build an app whose view reads the viewport width.

    Returns:
        App[_State]: An app rendering the width it was last told about.
    """
    return App(
        state=_State(),
        view=lambda app: Text(content=f"w={app.media.width:.0f}", key="w"),
        apply_patches=lambda patches: None,
    )


class _ScriptedTransport:
    """A transport that replays canned events, then reports the client left.

    Yields to the loop a few times before closing. ``_update_media`` requests a
    *coalesced* rebuild rather than rendering inline, so a transport that raised
    the moment its script ran out would cut the run before the rebuild it asked
    for ever flushed — the context would be right and no patch would prove it.
    """

    def __init__(self, events: list[Event]) -> None:
        """Initialize the transport.

        Args:
            events: The events to hand to the session, in order.
        """
        self._events: list[Event] = list(events)
        self.sent: list[list[Patch]] = []

    async def send_patches(self, patches: list[Patch]) -> None:
        """Record a patch batch.

        Args:
            patches: The batch the session produced.
        """
        self.sent.append(patches)

    async def send_navigate(self, path: str) -> None:
        """Ignore navigation for these tests.

        Args:
            path: The new path.
        """

    async def send_theme(self, mode: str) -> None:
        """Mark the theme mode — unused by this harness.

        Args:
            mode: The resolved theme mode (ignored).
        """
        return None

    async def recv_event(self) -> Event:
        """Return the next scripted event.

        Returns:
            Event: The next event.

        Raises:
            TransportClosedError: Once the script is exhausted.
        """
        if not self._events:
            for _ in range(4):
                await asyncio.sleep(0)
            raise TransportClosedError("script exhausted")
        return self._events.pop(0)

    def send_native_call(self, envelope: dict[str, Any]) -> None:
        """Ignore native calls for these tests.

        Args:
            envelope: The outbound envelope.
        """

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 - test double
        """Ignore the native result sink.

        Args:
            handler: The sink the session would register.
        """

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 - test double
        """Ignore the native event sink.

        Args:
            handler: The sink the session would register.
        """

    async def close(self) -> None:
        """Close the transport."""


def test_the_default_snapshot_is_the_zero_viewport() -> None:
    """The starting point the issue describes: no width to branch on."""
    app = _app()

    assert app.media.width == 0.0
    assert app.media.height == 0.0


def test_a_payload_becomes_the_media_context() -> None:
    """The whole point: what the browser reported is what the view reads."""
    app = _app()

    apply_media(
        app,
        {
            "width": 390,
            "height": 844,
            "device_pixel_ratio": 3,
            "platform_dark_mode": True,
            "orientation": "portrait",
        },
    )

    assert app.media.width == 390.0
    assert app.media.height == 844.0
    assert app.media.device_pixel_ratio == 3.0
    assert app.media.platform_dark_mode is True
    assert app.media.orientation == "portrait"


def test_a_partial_payload_keeps_the_other_defaults() -> None:
    """A client reporting only what it knows must not blank the rest."""
    app = _app()

    apply_media(app, {"width": 1280, "height": 800})

    assert app.media.width == 1280.0
    assert app.media.text_scale_factor == 1.0
    assert app.media.orientation == "portrait"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "1280x800",
        {"width": "1280"},
        {"height": None, "width": True},
        {"platform_dark_mode": "yes"},
        {"orientation": 90},
    ],
    ids=[
        "none",
        "string",
        "width-as-string",
        "width-as-bool",
        "dark-as-string",
        "orientation-as-int",
    ],
)
def test_a_malformed_payload_leaves_the_context_alone(payload: Any) -> None:
    """A half-applied snapshot is worse than none: the view would branch on it."""
    app = _app()
    apply_media(app, {"width": 1024, "height": 768})

    apply_media(app, payload)

    assert app.media.width == 1024.0
    assert app.media.height == 768.0


def test_a_media_event_reaches_the_view_through_a_session() -> None:
    """End to end in Mode B: the wire event re-renders the tree.

    The session is what the issue reported as missing the branch, so this is the
    test that fails without it — the width never leaves the payload.
    """
    transport = _ScriptedTransport(
        [
            {
                "type": "media",
                "key": "",
                "payload": {"width": 1280, "height": 800, "orientation": "landscape"},
            }
        ]
    )
    session: AppSession[_State] = AppSession(
        lambda: _State(),
        lambda app: Text(content=f"w={app.media.width:.0f}", key="w"),
        transport,
    )

    asyncio.run(session.run())

    assert session.app is not None
    assert session.app.media.width == 1280.0
    assert session.app.media.orientation == "landscape"
    rendered = [patch for batch in transport.sent for patch in batch]
    assert any("w=1280" in repr(patch) for patch in rendered), rendered
