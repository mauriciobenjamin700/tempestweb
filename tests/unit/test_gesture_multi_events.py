"""Multi-pointer gestures reach their handlers, in both Python-side runtimes.

``on_pan``, ``on_scale``, ``on_double_tap`` and ``on_interaction`` were declared
by the core and inert: the client tracked one pointer and only ever classified
tap / swipe / long press. These pin the Python halves — that each wire type
resolves the right handler and coerces to the right typed event.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from tempest_core import (
    App,
    GestureDetector,
    InteractiveViewer,
    PanEvent,
    PanHandler,
    ScaleEvent,
    ScaleHandler,
    TapEvent,
    Text,
    Widget,
)
from tempestweb.runtime import AppSession, WasmRuntime
from tempestweb.transports import WasmTransport
from tempestweb.transports.base import Event, Patch, TransportClosedError


@dataclass
class _State:
    """State for the gesture views.

    Attributes:
        offset: Accumulated pan deltas, as ``(x, y)``.
        zoom: The last reported scale.
        log: One entry per handler call.
    """

    offset: tuple[float, float] = (0.0, 0.0)
    zoom: float = 1.0
    log: list[str] = field(default_factory=list)


def _pan_view(app: App[_State]) -> Widget:
    """Render a pan surface that accumulates the drag.

    Args:
        app: The application handle.

    Returns:
        The widget tree.
    """

    def panned(event: PanEvent) -> None:
        def mutate(state: _State) -> None:
            state.offset = (state.offset[0] + event.dx, state.offset[1] + event.dy)
            state.log.append(f"pan:{event.dx:.0f},{event.dy:.0f}")

        app.set_state(mutate)

    return PanHandler(key="pad", on_pan=panned, child=Text(content="drag"))


def _scale_view(app: App[_State]) -> Widget:
    """Render a pinch surface that records the scale and its double tap.

    Args:
        app: The application handle.

    Returns:
        The widget tree.
    """

    def scaled(event: ScaleEvent) -> None:
        app.set_state(lambda state: setattr(state, "zoom", event.scale))

    def doubled(event: TapEvent) -> None:
        app.state.log.append("double_tap")

    return ScaleHandler(
        key="photo",
        on_scale=scaled,
        on_double_tap=doubled,
        child=Text(content="pinch"),
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


def _wire(kind: str, key: str, payload: dict[str, Any]) -> Event:
    """Build a wire event of `kind` for `key`.

    Args:
        kind: The wire event type.
        key: The target widget's key.
        payload: The event payload.

    Returns:
        The wire event.
    """
    return {"type": kind, "key": key, "payload": payload}


@pytest.mark.asyncio
async def test_mode_b_pan_accumulates() -> None:
    """Each pan step runs ``on_pan`` and the app accumulates the drag."""
    state = _State()
    session: AppSession[_State] = AppSession(lambda: state, _pan_view, _StubTransport())
    await session.start()

    for dx, dy in ((10, 0), (5, -3)):
        await session.dispatch(
            _wire("pan", "pad", {"dx": dx, "dy": dy, "vx": dx * 60, "vy": dy * 60})
        )
        await asyncio.sleep(0)

    assert state.offset == (15.0, -3.0)
    assert state.log == ["pan:10,0", "pan:5,-3"]
    await session.close()


@pytest.mark.asyncio
async def test_pan_payload_coerces_to_a_typed_event() -> None:
    """The handler reads ``event.dx`` / ``event.vx``, not a raw dict."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def panned(event: PanEvent) -> None:
            seen.append(event)

        return PanHandler(key="pad", on_pan=panned, child=Text(content="x"))

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(
        _wire("pan", "pad", {"dx": 12.5, "dy": -4.0, "vx": 750.0, "vy": -240.0})
    )

    assert len(seen) == 1
    assert isinstance(seen[0], PanEvent)
    assert seen[0].dx == 12.5
    assert seen[0].vy == -240.0


@pytest.mark.asyncio
async def test_mode_b_scale_and_double_tap_on_the_same_widget() -> None:
    """A pinch surface routes both of its handlers, by wire type."""
    state = _State()
    session: AppSession[_State] = AppSession(
        lambda: state, _scale_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(
        _wire(
            "scale",
            "photo",
            {"scale": 2.0, "focus_x": 200.0, "focus_y": 100.0, "rotation": 0.0},
        )
    )
    await session.dispatch(_wire("double_tap", "photo", {"x": 31.0, "y": 30.0}))
    await asyncio.sleep(0)

    assert state.zoom == 2.0
    assert state.log == ["double_tap"]
    await session.close()


@pytest.mark.asyncio
async def test_scale_payload_coerces_to_a_typed_event() -> None:
    """The handler reads ``event.scale`` and the focus point."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def scaled(event: ScaleEvent) -> None:
            seen.append(event)

        return ScaleHandler(key="photo", on_scale=scaled, child=Text(content="x"))

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(
        _wire(
            "scale",
            "photo",
            {"scale": 1.5, "focus_x": 10.0, "focus_y": 20.0, "rotation": 90.0},
        )
    )

    assert len(seen) == 1
    assert isinstance(seen[0], ScaleEvent)
    assert seen[0].scale == 1.5
    assert seen[0].rotation == 90.0


@pytest.mark.asyncio
async def test_double_tap_on_a_gesture_detector() -> None:
    """A GestureDetector's double tap is its own handler, not its tap's."""
    calls: list[str] = []

    def view(app: App[_State]) -> Widget:
        def tapped(event: TapEvent) -> None:
            calls.append("tap")

        def doubled(event: TapEvent) -> None:
            calls.append("double")

        return GestureDetector(
            key="card",
            on_tap=tapped,
            on_double_tap=doubled,
            child=Text(content="x"),
        )

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_wire("tap", "card", {"x": 1.0, "y": 2.0}))
    await runtime.dispatch_event(_wire("double_tap", "card", {"x": 1.0, "y": 2.0}))

    assert calls == ["tap", "double"]


@pytest.mark.asyncio
async def test_interaction_reaches_the_viewer() -> None:
    """``on_interaction`` receives a ScaleEvent, for pan and for pinch alike."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def interacted(event: ScaleEvent) -> None:
            seen.append(event)

        return InteractiveViewer(
            key="map", on_interaction=interacted, child=Text(content="x")
        )

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    # One pointer: the scale holds at 1 and the focus is where the finger is.
    await runtime.dispatch_event(
        _wire(
            "interaction",
            "map",
            {"scale": 1.0, "focus_x": 140.0, "focus_y": 130.0, "rotation": 0.0},
        )
    )
    # Two pointers: same handler, same event type, a real scale.
    await runtime.dispatch_event(
        _wire(
            "interaction",
            "map",
            {"scale": 2.0, "focus_x": 240.0, "focus_y": 130.0, "rotation": 0.0},
        )
    )

    assert [event.scale for event in seen] == [1.0, 2.0]
    assert all(isinstance(event, ScaleEvent) for event in seen)


@pytest.mark.asyncio
async def test_a_surface_with_no_handler_ignores_the_gesture() -> None:
    """A widget that declares none of these must not raise on one."""
    session: AppSession[_State] = AppSession(
        lambda: _State(),
        lambda app: Text(content="plain", key="t"),
        _StubTransport(),
    )
    await session.start()

    await session.dispatch(
        _wire("pan", "t", {"dx": 1.0, "dy": 1.0, "vx": 0.0, "vy": 0.0})
    )
    await session.dispatch(_wire("scale", "t", {"scale": 2.0}))
    await session.close()
