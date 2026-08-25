"""``on_reorder`` and ``on_page_change`` fire from the events the client now sends.

Both were declared by the core and inert in every mode: a `ReorderableList`
rendered rows nobody could pick up, and a `PageView` rendered a plain box with no
pages to swipe. Once the client reports `reorder` and `page_change`, the handlers
resolve through the plain ``on_<type>`` fallback — these pin that, in both
Python-side runtimes, and check the payload arrives as the typed event.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from tempest_core import (
    App,
    Column,
    PageChangeEvent,
    PageView,
    ReorderableList,
    ReorderEvent,
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
        tasks: The rows, in the order the reader left them.
        page: The visible page of the carousel.
        log: One entry per handler call, for ordering assertions.
    """

    tasks: list[str] = field(default_factory=lambda: ["a", "b", "c"])
    page: int = 0
    log: list[str] = field(default_factory=list)


def _sortable_view(app: App[_State]) -> Widget:
    """Render a reorderable list that moves a row when one is dropped.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current order.
    """

    def moved(event: ReorderEvent) -> None:
        def mutate(state: _State) -> None:
            task = state.tasks.pop(event.from_index)
            state.tasks.insert(event.to_index, task)
            state.log.append(f"{event.from_index}->{event.to_index}")

        app.set_state(mutate)

    return ReorderableList(
        key="tasks",
        children=[Text(content=task, key=task) for task in app.state.tasks],
        on_reorder=moved,
    )


def _carousel_view(app: App[_State]) -> Widget:
    """Render a carousel that follows the page the reader swiped to.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current page.
    """

    def changed(event: PageChangeEvent) -> None:
        app.state.log.append(f"{event.previous}->{event.page}")
        app.set_state(lambda state: setattr(state, "page", event.page))

    return PageView(
        key="tour",
        page=app.state.page,
        children=[Text(content=f"Page {index}", key=f"p{index}") for index in range(3)],
        on_page_change=changed,
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


def _reorder(key: str, from_index: int, to_index: int) -> Event:
    """Build the wire event a drag between two rows produces.

    Args:
        key: The list's widget key.
        from_index: Where the row came from.
        to_index: Where it was dropped.

    Returns:
        The wire event.
    """
    return {
        "type": "reorder",
        "key": key,
        "payload": {"from_index": from_index, "to_index": to_index},
    }


def _page_change(key: str, page: int, previous: int) -> Event:
    """Build the wire event a swipe to another page produces.

    Args:
        key: The carousel's widget key.
        page: The page the scroll landed on.
        previous: The page it came from.

    Returns:
        The wire event.
    """
    return {
        "type": "page_change",
        "key": key,
        "payload": {"page": page, "previous": previous},
    }


@pytest.mark.asyncio
async def test_mode_b_reorder_moves_the_row() -> None:
    """In Mode B a ``reorder`` event runs ``on_reorder`` and rebuilds the list."""
    state = _State()
    session: AppSession[_State] = AppSession(
        lambda: state, _sortable_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_reorder("tasks", 0, 2))
    await asyncio.sleep(0)

    assert state.tasks == ["b", "c", "a"]
    assert state.log == ["0->2"]
    scene = session.app.current_tree if session.app is not None else None
    assert scene is not None
    assert [child.props["content"] for child in scene.root.children] == ["b", "c", "a"]
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_reorder_moves_the_row() -> None:
    """Mode A resolves the same handler off its registry."""
    state = _State()
    runtime: WasmRuntime[_State] = WasmRuntime(
        state, _sortable_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_reorder("tasks", 2, 0))
    await asyncio.sleep(0)

    assert state.tasks == ["c", "a", "b"]


@pytest.mark.asyncio
async def test_reorder_payload_coerces_to_the_typed_event() -> None:
    """The handler reads ``event.from_index``, not ``payload["from_index"]``."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def moved(event: ReorderEvent) -> None:
            seen.append(event)

        return ReorderableList(key="tasks", children=[], on_reorder=moved)

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_reorder("tasks", 1, 0))

    assert len(seen) == 1
    assert isinstance(seen[0], ReorderEvent)
    assert seen[0].from_index == 1
    assert seen[0].to_index == 0


@pytest.mark.asyncio
async def test_mode_b_page_change_follows_the_swipe() -> None:
    """In Mode B a ``page_change`` event runs ``on_page_change``."""
    state = _State()
    session: AppSession[_State] = AppSession(
        lambda: state, _carousel_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_page_change("tour", 2, 0))
    await asyncio.sleep(0)

    assert state.page == 2
    assert state.log == ["0->2"]
    scene = session.app.current_tree if session.app is not None else None
    assert scene is not None
    assert scene.root.props["page"] == 2
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_page_change_follows_the_swipe() -> None:
    """Mode A routes the same event through the same handler."""
    state = _State()
    runtime: WasmRuntime[_State] = WasmRuntime(
        state, _carousel_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_page_change("tour", 1, 0))
    await asyncio.sleep(0)

    assert runtime.app.state.page == 1


@pytest.mark.asyncio
async def test_page_change_payload_coerces_to_the_typed_event() -> None:
    """The handler receives a ``PageChangeEvent`` with both indices."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def changed(event: PageChangeEvent) -> None:
            seen.append(event)

        return PageView(key="tour", page=0, children=[], on_page_change=changed)

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_page_change("tour", 2, 1))

    assert len(seen) == 1
    assert isinstance(seen[0], PageChangeEvent)
    assert seen[0].page == 2
    assert seen[0].previous == 1


@pytest.mark.asyncio
async def test_an_unhandled_gesture_is_ignored() -> None:
    """A list with no handler must not raise when the client reports a drag."""
    session: AppSession[_State] = AppSession(
        lambda: _State(),
        lambda app: Column(key="root", children=[Text(content="x", key="t")]),
        _StubTransport(),
    )
    await session.start()

    await session.dispatch(_reorder("root", 0, 1))
    await session.dispatch(_page_change("root", 1, 0))
    await session.close()
