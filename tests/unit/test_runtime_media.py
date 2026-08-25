"""``App.media`` follows the browser in every mode (issue #74).

``MediaQueryData``'s docstring always promised that "the renderer keeps it
current via ``App._update_media`` on resize / config change". Nothing in this
package called it: ``media.js`` lived under ``client/transpile/`` and only the
Mode C runtime installed it, so a Mode A or Mode B app ran forever with
``width = height = 0`` — and a ``view`` that branches on the width, or bounds a
``Scaffold`` by the height, silently got the wrong tree.

These pin the Python half: the ``media`` wire event refreshes the snapshot and
requests a rebuild, in both Python-side runtimes, and a malformed report is
ignored instead of taking down the event loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempest_core import App, Button, Column, Row, Text, Widget
from tempestweb.runtime import AppSession, WasmRuntime, apply_media
from tempestweb.transports import WasmTransport
from tempestweb.transports.base import Event, Patch, TransportClosedError

PHONE: dict[str, Any] = {
    "width": 390,
    "height": 844,
    "device_pixel_ratio": 3,
    "platform_dark_mode": True,
    "orientation": "portrait",
}

LAPTOP: dict[str, Any] = {
    "width": 1440,
    "height": 900,
    "device_pixel_ratio": 2,
    "platform_dark_mode": False,
    "orientation": "landscape",
}

#: The width at which the demo view switches from a column to a row.
BREAKPOINT: float = 600.0


@dataclass
class _State:
    """State for the responsive demo view."""

    label: str = "hello"


def _responsive_view(app: App[_State]) -> Widget:
    """Render a column on a narrow viewport and a row on a wide one.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current viewport.
    """
    children: list[Widget] = [
        Text(content=app.state.label, key="a"),
        Text(content=f"{app.media.width:.0f}px", key="b"),
    ]
    if app.media.width >= BREAKPOINT:
        return Row(key="root", children=children)
    return Column(key="root", children=children)


class _StubTransport:
    """The narrowest ``PatchTransport`` these tests need.

    Attributes:
        sent: Every patch batch the session pushed, in order.
    """

    def __init__(self) -> None:
        """Initialize the transport with an empty patch log."""
        self.sent: list[list[Patch]] = []

    async def send_patches(self, patches: list[Patch]) -> None:
        """Record a patch batch.

        Args:
            patches: The batch the session produced.
        """
        self.sent.append(patches)

    async def send_navigate(self, path: str) -> None:
        """Ignore navigation.

        Args:
            path: The new path.
        """

    async def send_theme(self, mode: str) -> None:
        """Mark the theme mode — unused by this harness.

        Args:
            mode: The resolved theme mode (ignored).
        """
        return None

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native calls.

        Args:
            call_id: The correlation id.
            capability: The capability name.
            args: The capability arguments.
        """

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native subscriptions.

        Args:
            sub_id: The subscription id.
            capability: The capability name.
            args: The capability arguments.
        """

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Ignore native unsubscriptions.

        Args:
            sub_id: The subscription id.
        """

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 — test double
        """Ignore the native-result sink.

        Args:
            handler: The sink the session registers.
        """

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 — test double
        """Ignore the native-event sink.

        Args:
            handler: The sink the session registers.
        """

    async def recv_event(self) -> Event:
        """Report no further events.

        Raises:
            TransportClosedError: Always — these tests dispatch directly.
        """
        raise TransportClosedError("no scripted events")

    async def close(self) -> None:
        """Ignore close."""


def _app() -> App[_State]:
    """Build an app around the responsive view, with a no-op patch sink.

    Returns:
        A fresh app whose media snapshot starts at the core's defaults.
    """
    return App(_State(), _responsive_view, lambda _patches: None)


def _media(payload: dict[str, Any]) -> Event:
    """Build the wire event the client reports on mount and on resize.

    Args:
        payload: The viewport snapshot fields.

    Returns:
        The wire event.
    """
    return {"type": "media", "key": "", "payload": payload}


def test_apply_media_updates_the_snapshot() -> None:
    """A well-formed payload lands on ``app.media`` field by field."""
    app: App[_State] = _app()
    apply_media(app, PHONE)

    assert app.media.width == 390
    assert app.media.height == 844
    assert app.media.device_pixel_ratio == 3
    assert app.media.platform_dark_mode is True
    assert app.media.orientation == "portrait"


def test_apply_media_keeps_defaults_for_absent_fields() -> None:
    """No browser reports ``text_scale_factor``, so it keeps its default."""
    app: App[_State] = _app()
    apply_media(app, {"width": 800, "height": 600})

    assert app.media.width == 800
    assert app.media.text_scale_factor == 1.0


def test_apply_media_ignores_a_malformed_report() -> None:
    """A bad payload leaves the snapshot untouched instead of raising."""
    app: App[_State] = _app()
    apply_media(app, PHONE)

    apply_media(app, {"width": "wide"})
    apply_media(app, ["not", "a", "mapping"])
    apply_media(app, None)

    assert app.media.width == 390, "a malformed resize must not clobber the snapshot"


def test_apply_media_ignores_unknown_fields() -> None:
    """A field the core does not declare is dropped, not an error."""
    app: App[_State] = _app()
    apply_media(app, {**PHONE, "colour_gamut": "p3"})

    assert app.media.width == 390


@pytest.mark.asyncio
async def test_mode_b_media_event_reaches_the_view() -> None:
    """In Mode B a ``media`` event rebuilds the tree against the new viewport."""
    transport = _StubTransport()
    session: AppSession[_State] = AppSession(
        lambda: _State(), _responsive_view, transport
    )
    await session.start()
    assert session.app is not None
    assert session.app.media.width == 0.0, "the default before the client reports"

    await session.dispatch(_media(LAPTOP))
    await asyncio.sleep(0)

    assert session.app.media.width == 1440
    scene = session.app.current_tree
    assert scene is not None
    assert scene.root.type == "Row", "a wide viewport must build the wide tree"

    await session.dispatch(_media(PHONE))
    await asyncio.sleep(0)
    scene = session.app.current_tree
    assert scene is not None
    assert scene.root.type == "Column", "and a narrow one the narrow tree"
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_media_event_reaches_the_view() -> None:
    """Mode A routes the same event through the same helper."""
    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), _responsive_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_media(LAPTOP))
    await asyncio.sleep(0)

    assert runtime.app.media.width == 1440
    scene = runtime.app.current_tree
    assert scene is not None
    assert scene.root.type == "Row"


@pytest.mark.asyncio
async def test_media_is_not_mistaken_for_a_widget_event() -> None:
    """``media`` carries an empty key and must never resolve a handler."""
    seen: list[str] = []

    def view(app: App[_State]) -> Widget:
        def clicked() -> None:
            seen.append("click")

        # A Button, because `Text` declares no handler: this test used to hand
        # `on_click` to a Text, which the core dropped in silence, so it passed
        # for the wrong reason — the handler could not have fired either way.
        return Column(
            key="root",
            children=[Button(label="x", key="t", on_click=clicked)],
        )

    session: AppSession[_State] = AppSession(lambda: _State(), view, _StubTransport())
    await session.start()

    await session.dispatch({"type": "media", "key": "t", "payload": LAPTOP})
    await asyncio.sleep(0)

    assert seen == [], "the media branch runs before handler resolution"
    assert session.app is not None
    assert session.app.media.width == 1440
    await session.close()
