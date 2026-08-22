"""``on_scan`` and ``on_frame`` reach their handlers (issue #77, item 1).

The last two inert handlers the core declared. A ``QrScanner`` and a
``CameraPreview`` rendered as empty boxes — no stream, nothing to decode or
sample — so neither could ever fire. These pin the Python halves: the wire types
resolve the handlers and coerce to the typed events.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from tempest_core import App, Column, Text, Widget
from tempest_core.widgets.events import CameraFrameEvent, QrScanEvent
from tempest_core.widgets.media import CameraPreview, QrScanner
from tempestweb.runtime import AppSession, WasmRuntime
from tempestweb.transports import WasmTransport
from tempestweb.transports.base import Event, Patch, TransportClosedError

#: A one-pixel JPEG, as the client sends it: base64 with no data: prefix.
PIXEL: str = "QUJD"


@dataclass
class _State:
    """State for the camera views.

    Attributes:
        scanned: Codes read, in order.
        frames: One entry per frame received, as ``width x height``.
    """

    scanned: list[str] = field(default_factory=list)
    frames: list[str] = field(default_factory=list)


def _scanner_view(app: App[_State]) -> Widget:
    """Render a scanner that records every code it reads.

    Args:
        app: The application handle.

    Returns:
        The widget tree.
    """

    def scanned(event: QrScanEvent) -> None:
        app.set_state(lambda state: state.scanned.append(event.data))

    return QrScanner(key="scanner", on_scan=scanned)


def _preview_view(app: App[_State]) -> Widget:
    """Render a preview that records the size of each frame.

    Args:
        app: The application handle.

    Returns:
        The widget tree.
    """

    def framed(event: CameraFrameEvent) -> None:
        app.state.frames.append(f"{event.width}x{event.height}")

    return CameraPreview(
        key="preview", facing="front", frame_interval_ms=200, on_frame=framed
    )


class _StubTransport:
    """The narrowest ``PatchTransport`` a session needs to dispatch one event.

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
        """Ignore the native-result sink the session registers.

        Args:
            handler: The sink the session registers.
        """

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 — test double
        """Ignore the native-event sink the session registers.

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


def _scan(key: str, data: str) -> Event:
    """Build the wire event a decoded code produces.

    Args:
        key: The scanner's widget key.
        data: The decoded payload.

    Returns:
        The wire event.
    """
    return {"type": "scan", "key": key, "payload": {"data": data, "format": "qr_code"}}


def _frame(key: str, width: int, height: int) -> Event:
    """Build the wire event a sampled camera frame produces.

    Args:
        key: The preview's widget key.
        width: The frame's width in pixels.
        height: The frame's height in pixels.

    Returns:
        The wire event.
    """
    return {
        "type": "frame",
        "key": key,
        "payload": {"width": width, "height": height, "data": PIXEL, "rotation": 0},
    }


@pytest.mark.asyncio
async def test_mode_b_scan_reaches_the_handler() -> None:
    """A decoded code runs ``on_scan`` with the payload the reader scanned."""
    state = _State()
    session: AppSession[_State] = AppSession(
        lambda: state, _scanner_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_scan("scanner", "https://example.test/a"))
    await asyncio.sleep(0)

    assert state.scanned == ["https://example.test/a"]
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_scan_reaches_the_handler() -> None:
    """Mode A resolves ``on_scan`` off its own registry."""
    state = _State()
    runtime: WasmRuntime[_State] = WasmRuntime(
        state, _scanner_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_scan("scanner", "ticket-42"))
    await asyncio.sleep(0)

    assert state.scanned == ["ticket-42"]


@pytest.mark.asyncio
async def test_scan_payload_coerces_to_the_typed_event() -> None:
    """The handler reads ``event.data`` / ``event.format``, typed."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def scanned(event: QrScanEvent) -> None:
            seen.append(event)

        return QrScanner(key="scanner", on_scan=scanned)

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_scan("scanner", "abc"))

    assert len(seen) == 1
    assert isinstance(seen[0], QrScanEvent)
    assert seen[0].data == "abc"
    assert seen[0].format == "qr_code"


@pytest.mark.asyncio
async def test_mode_b_frames_reach_the_handler() -> None:
    """Each sampled frame runs ``on_frame`` with its dimensions."""
    state = _State()
    session: AppSession[_State] = AppSession(
        lambda: state, _preview_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_frame("preview", 640, 480))
    await session.dispatch(_frame("preview", 320, 240))
    await asyncio.sleep(0)

    assert state.frames == ["640x480", "320x240"]
    await session.close()


@pytest.mark.asyncio
async def test_frame_payload_coerces_to_the_typed_event() -> None:
    """The handler receives a ``CameraFrameEvent``, bytes included."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def framed(event: CameraFrameEvent) -> None:
            seen.append(event)

        return CameraPreview(key="preview", on_frame=framed)

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_frame("preview", 1280, 720))

    assert len(seen) == 1
    assert isinstance(seen[0], CameraFrameEvent)
    assert seen[0].width == 1280
    assert seen[0].data == PIXEL
    assert seen[0].rotation == 0


@pytest.mark.asyncio
async def test_a_camera_widget_with_no_handler_ignores_the_event() -> None:
    """A preview or scanner that declares nothing must not raise on an event."""
    session: AppSession[_State] = AppSession(
        lambda: _State(),
        lambda app: Column(key="root", children=[Text(content="x", key="t")]),
        _StubTransport(),
    )
    await session.start()

    await session.dispatch(_scan("t", "anything"))
    await session.dispatch(_frame("t", 1, 1))
    await session.close()
