"""A list's declared handlers fire from the wire events the client now emits.

``LazyColumn`` and friends declare ``on_end_reached`` (and, on the scrollable
ones plus ``RefreshControl``, ``on_refresh``), and both resolve through the plain
``on_<type>`` fallback — no entry in ``EVENT_TYPE_TO_HANDLER_PROPS`` is needed.
Nothing exercised that path before ``client/lists.js`` started emitting the
events, so these pin it in both runtimes: Mode A (``WasmRuntime``) and Mode B
(``AppSession``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tempest_core import (
    App,
    Column,
    Container,
    EndReachedEvent,
    LazyColumn,
    RefreshControl,
    RefreshEvent,
    Text,
    Widget,
)
from tempestweb.runtime import AppSession, WasmRuntime
from tempestweb.transports import WasmTransport
from tempestweb.transports.base import Event, Patch, TransportClosedError

PAGE: int = 20


@dataclass
class _ListState:
    """State for a list that grows as its end is reached."""

    loaded: int = PAGE
    events: list[str] = field(default_factory=list)


def _view(app: App[_ListState]) -> Widget:
    """Render a virtualized list that loads another page at its end.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def row(index: int) -> Widget:
        return Container(key=str(index), child=Text(content=f"Item {index}"))

    def load_more(event: EndReachedEvent) -> None:
        app.state.events.append("end_reached")
        app.set_state(lambda s: setattr(s, "loaded", s.loaded + PAGE))

    return LazyColumn(
        key="rows",
        item_count=app.state.loaded,
        item_builder=row,
        window_size=PAGE,
        on_end_reached=load_more,
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


def _end_reached(key: str) -> Event:
    """Build the wire event the client sends when a list nears its end.

    Args:
        key: The list's widget key.

    Returns:
        The wire event.
    """
    return {"type": "end_reached", "key": key, "payload": {}}


@pytest.mark.asyncio
async def test_mode_b_end_reached_loads_the_next_page() -> None:
    """In Mode B an ``end_reached`` event runs ``on_end_reached`` and rebuilds."""
    state = _ListState()
    transport = _StubTransport()
    session: AppSession[_ListState] = AppSession(lambda: state, _view, transport)
    await session.start()
    assert transport.sent, "the initial scene must have been pushed"

    await session.dispatch(_end_reached("rows"))

    assert state.events == ["end_reached"]
    assert state.loaded == 2 * PAGE
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_end_reached_loads_the_next_page() -> None:
    """In Mode A the same event resolves ``on_end_reached`` on the registry."""
    state = _ListState()
    runtime: WasmRuntime[_ListState] = WasmRuntime(
        state, _view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_end_reached("rows"))

    assert state.events == ["end_reached"]
    assert state.loaded == 2 * PAGE


@pytest.mark.asyncio
async def test_end_reached_payload_coerces_to_the_typed_event() -> None:
    """The handler receives an ``EndReachedEvent``, not the raw payload dict."""
    seen: list[object] = []

    def view(app: App[_ListState]) -> Widget:
        def reached(event: EndReachedEvent) -> None:
            seen.append(event)

        return LazyColumn(
            key="rows",
            item_count=1,
            item_builder=lambda index: Text(content=str(index), key=str(index)),
            on_end_reached=reached,
        )

    runtime: WasmRuntime[_ListState] = WasmRuntime(
        _ListState(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_end_reached("rows"))

    assert len(seen) == 1
    assert isinstance(seen[0], EndReachedEvent)


def _refresh(key: str) -> Event:
    """Build the wire event the client sends when a pull-to-refresh completes.

    Args:
        key: The widget key that was pulled.

    Returns:
        The wire event.
    """
    return {"type": "refresh", "key": key, "payload": {}}


def _refresh_view(app: App[_ListState]) -> Widget:
    """Render a list plus a standalone control, both wired to on_refresh.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def reload(event: RefreshEvent) -> None:
        app.state.events.append("refresh")
        app.set_state(lambda s: setattr(s, "loaded", PAGE))

    def reload_control(event: RefreshEvent) -> None:
        app.state.events.append("control")

    return Column(
        key="root",
        children=[
            RefreshControl(key="pull", on_refresh=reload_control),
            LazyColumn(
                key="rows",
                item_count=app.state.loaded,
                item_builder=lambda index: Container(
                    key=str(index), child=Text(content=str(index))
                ),
                on_refresh=reload,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_mode_b_refresh_runs_the_list_handler() -> None:
    """A pull on the list itself runs its ``on_refresh``."""
    state = _ListState(loaded=5 * PAGE)
    session: AppSession[_ListState] = AppSession(
        lambda: state, _refresh_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_refresh("rows"))

    assert state.events == ["refresh"]
    assert state.loaded == PAGE
    await session.close()


@pytest.mark.asyncio
async def test_mode_b_refresh_runs_a_standalone_control() -> None:
    """A pull on a standalone ``RefreshControl`` runs its own handler."""
    state = _ListState()
    session: AppSession[_ListState] = AppSession(
        lambda: state, _refresh_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_refresh("pull"))

    assert state.events == ["control"]
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_refresh_runs_the_list_handler() -> None:
    """Mode A resolves ``refresh`` the same way, off the handler registry."""
    state = _ListState(loaded=5 * PAGE)
    runtime: WasmRuntime[_ListState] = WasmRuntime(
        state, _refresh_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_refresh("rows"))

    assert state.events == ["refresh"]
    assert state.loaded == PAGE


@pytest.mark.asyncio
async def test_refresh_payload_coerces_to_the_typed_event() -> None:
    """The handler receives a ``RefreshEvent``, not the raw payload dict."""
    seen: list[object] = []

    def view(app: App[_ListState]) -> Widget:
        def reload(event: RefreshEvent) -> None:
            seen.append(event)

        return RefreshControl(key="pull", on_refresh=reload)

    runtime: WasmRuntime[_ListState] = WasmRuntime(
        _ListState(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_refresh("pull"))

    assert len(seen) == 1
    assert isinstance(seen[0], RefreshEvent)
