"""Dispatch pacing and background work in a Mode B session (issue #62).

A session reads one event, awaits its handler, then reads the next. That keeps a
widget's events in order, and it also means a slow handler holds the whole
connection. These tests pin both halves of the answer: ``spawn`` for handing work
out of a handler, and the opt-in concurrent dispatch for apps that want handlers
to overlap.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from tempest_core import App, Button, Color, Column, Input, Theme, ThemeMode, Widget
from tempestweb.runtime import AppSession, NoSessionError, spawn
from tempestweb.runtime.background import install_spawner, uninstall_spawner
from tempestweb.transports.base import Event, Patch, TransportClosedError


@dataclass
class _State:
    """State for the pacing tests."""

    log: list[str] = field(default_factory=list)


class _ScriptedTransport:
    """A transport that replays canned events, then reports the client left.

    Attributes:
        sent: Every patch batch the session pushed, in order.
    """

    def __init__(self, events: list[Event], *, hold_open: bool = False) -> None:
        """Initialize the transport.

        Args:
            events: The events to hand to the session, in order.
            hold_open: When ``True``, block once the script is exhausted until
                :meth:`disconnect` is called, instead of reporting the client
                left immediately. Tests that assert on background work need this:
                the session cancels its tasks on close, so a run that ends the
                moment the last event is dispatched would cancel the very work
                under test.
        """
        self._events: list[Event] = list(events)
        self._hold: asyncio.Event | None = asyncio.Event() if hold_open else None
        self.sent: list[list[Patch]] = []
        self.closed: bool = False

    def disconnect(self) -> None:
        """Release a held-open transport, so the session's run loop can finish."""
        if self._hold is not None:
            self._hold.set()

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

    async def recv_event(self) -> Event:
        """Return the next scripted event.

        Returns:
            The next event.

        Raises:
            TransportClosedError: Once the script is exhausted.
        """
        if not self._events:
            if self._hold is not None:
                await self._hold.wait()
            raise TransportClosedError("script exhausted")
        return self._events.pop(0)

    def send_native_call(self, envelope: dict[str, Any]) -> None:
        """Ignore native calls for these tests.

        Args:
            envelope: The native_call envelope.
        """

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 - test double
        """Ignore native results.

        Args:
            handler: The sink the session registers.
        """

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 - test double
        """Ignore native events.

        Args:
            handler: The sink the session registers.
        """

    async def close(self) -> None:
        """Mark the transport closed."""
        self.closed = True


def _click(key: str) -> Event:
    """Build a click event for a widget key.

    Args:
        key: The widget key.

    Returns:
        The wire event.
    """
    return {"type": "click", "key": key, "payload": {}}


@pytest.mark.asyncio
async def test_serial_dispatch_holds_the_connection() -> None:
    """The default: a slow handler delays every later event.

    Pinned deliberately — it is the behaviour the other two features exist to
    work around, and changing it silently would be worse than the freeze.
    """
    gate = asyncio.Event()

    def view(app: App[_State]) -> Widget:
        async def slow() -> None:
            app.state.log.append("slow:start")
            await gate.wait()
            app.state.log.append("slow:end")

        def quick() -> None:
            app.state.log.append("quick")

        return Column(
            key="root",
            children=[
                Button(label="s", on_click=slow, key="slow"),
                Button(label="q", on_click=quick, key="quick"),
            ],
        )

    state = _State()
    transport = _ScriptedTransport([_click("slow"), _click("quick")])
    session: AppSession[_State] = AppSession(lambda: state, view, transport)
    run = asyncio.ensure_future(session.run())

    for _ in range(6):
        await asyncio.sleep(0)
    assert state.log == ["slow:start"], "the quick handler must be stuck behind it"

    gate.set()
    await run
    assert state.log == ["slow:start", "slow:end", "quick"]


@pytest.mark.asyncio
async def test_concurrent_dispatch_lets_other_widgets_through() -> None:
    """With the opt-in, a slow handler no longer blocks another widget's."""
    gate = asyncio.Event()

    def view(app: App[_State]) -> Widget:
        async def slow() -> None:
            app.state.log.append("slow:start")
            await gate.wait()
            app.state.log.append("slow:end")

        def quick() -> None:
            app.state.log.append("quick")

        return Column(
            key="root",
            children=[
                Button(label="s", on_click=slow, key="slow"),
                Button(label="q", on_click=quick, key="quick"),
            ],
        )

    state = _State()
    transport = _ScriptedTransport([_click("slow"), _click("quick")], hold_open=True)
    session: AppSession[_State] = AppSession(
        lambda: state, view, transport, concurrent_dispatch=True
    )
    run = asyncio.ensure_future(session.run())

    await asyncio.sleep(0.05)
    assert "quick" in state.log, "the second widget ran while the first was parked"
    assert "slow:end" not in state.log

    gate.set()
    await asyncio.sleep(0.05)
    transport.disconnect()
    await run
    assert "slow:end" in state.log


@pytest.mark.asyncio
async def test_concurrent_dispatch_keeps_one_widget_in_order() -> None:
    """Two quick edits of the same field must not apply out of order.

    This is what the per-key lock buys: overlap across widgets, arrival order
    within one. The first edit deliberately takes longer than the second, so
    without the lock the newer value would land first and the stale one would be
    the value that sticks.
    """
    applied: list[str] = []

    def view(app: App[_State]) -> Widget:
        async def edit(event: Any) -> None:  # noqa: ANN401 - the core's event model
            value = str(getattr(event, "value", ""))
            await asyncio.sleep(0.02 if value == "first" else 0.0)
            applied.append(value)

        return Column(
            key="root",
            children=[Input(value="", on_change=edit, key="field")],
        )

    events: list[Event] = [
        {"type": "change", "key": "field", "payload": {"value": "first"}},
        {"type": "change", "key": "field", "payload": {"value": "second"}},
    ]
    transport = _ScriptedTransport(events, hold_open=True)
    session: AppSession[_State] = AppSession(
        lambda: _State(), view, transport, concurrent_dispatch=True
    )
    run = asyncio.ensure_future(session.run())

    await asyncio.sleep(0.1)
    transport.disconnect()
    await run

    assert applied == ["first", "second"]


@pytest.mark.asyncio
async def test_concurrent_dispatch_survives_a_raising_handler() -> None:
    """One failing handler must not take the session down with it."""

    def view(app: App[_State]) -> Widget:
        def boom() -> None:
            raise RuntimeError("handler exploded")

        def quick() -> None:
            app.state.log.append("quick")

        return Column(
            key="root",
            children=[
                Button(label="b", on_click=boom, key="boom"),
                Button(label="q", on_click=quick, key="quick"),
            ],
        )

    state = _State()
    transport = _ScriptedTransport([_click("boom"), _click("quick")], hold_open=True)
    session: AppSession[_State] = AppSession(
        lambda: state, view, transport, concurrent_dispatch=True
    )
    run = asyncio.ensure_future(session.run())

    await asyncio.sleep(0.05)
    transport.disconnect()
    await run

    assert state.log == ["quick"]


@pytest.mark.asyncio
async def test_spawn_runs_work_outside_the_handler() -> None:
    """The handler returns immediately; the spawned work lands later."""
    done = asyncio.Event()

    def view(app: App[_State]) -> Widget:
        def upload() -> None:
            async def work() -> None:
                await asyncio.sleep(0)
                app.state.log.append("work:done")
                done.set()

            app.state.log.append("handler:returned")
            spawn(work())

        def quick() -> None:
            app.state.log.append("quick")

        return Column(
            key="root",
            children=[
                Button(label="u", on_click=upload, key="upload"),
                Button(label="q", on_click=quick, key="quick"),
            ],
        )

    state = _State()
    transport = _ScriptedTransport([_click("upload"), _click("quick")], hold_open=True)
    session: AppSession[_State] = AppSession(lambda: state, view, transport)
    run = asyncio.ensure_future(session.run())

    await asyncio.wait_for(done.wait(), timeout=1.0)
    transport.disconnect()
    await run

    assert state.log.index("quick") < state.log.index("work:done")


@pytest.mark.asyncio
async def test_spawned_work_is_cancelled_with_the_session() -> None:
    """Background work must not outlive the connection that started it."""
    started = asyncio.Event()
    finished = False

    async def forever() -> None:
        nonlocal finished
        started.set()
        await asyncio.sleep(10)
        finished = True

    def view(app: App[_State]) -> Widget:
        def go() -> None:
            spawn(forever())

        return Column(key="root", children=[Button(label="g", on_click=go, key="go")])

    transport = _ScriptedTransport([_click("go")], hold_open=True)
    session: AppSession[_State] = AppSession(lambda: _State(), view, transport)
    run = asyncio.ensure_future(session.run())

    await asyncio.wait_for(started.wait(), timeout=1.0)
    transport.disconnect()
    await run
    await asyncio.sleep(0)

    assert finished is False, "close() must cancel background work"


@pytest.mark.asyncio
async def test_spawn_outside_a_session_raises_a_useful_error() -> None:
    """Off-session, spawn says so instead of silently dropping the work."""
    uninstall_spawner()

    async def work() -> None:
        return None

    with pytest.raises(NoSessionError, match="running tempestweb session"):
        spawn(work())


@pytest.mark.asyncio
async def test_installed_spawner_is_used() -> None:
    """install_spawner is the seam the runtimes plug their task tracker into."""
    seen: list[str] = []

    async def work() -> None:
        seen.append("ran")

    def spawner(coro: Any) -> None:  # noqa: ANN401 - a coroutine of any result
        seen.append("scheduled")
        asyncio.ensure_future(coro)

    install_spawner(spawner)
    try:
        spawn(work())
        await asyncio.sleep(0)
    finally:
        uninstall_spawner()

    assert seen == ["scheduled", "ran"]


def _bare_view(app: App[_State]) -> Widget:
    """Render the smallest tree a session can start with.

    Args:
        app (App[_State]): The session's application handle.

    Returns:
        Widget: A column with nothing in it.
    """
    return Column(children=[])


class TestTheThemeTheSessionBuildsWith:
    """A rebranded page still needs the tree to know the palette.

    Components resolve their colors in **Python** — a filled button carries
    its fill as an inline style — so overriding the CSS custom properties
    rebrands what the base stylesheet paints and leaves every component
    baseline-purple. The session is where the palette reaches the tree.
    """

    async def test_the_session_hands_its_theme_to_the_app(self) -> None:
        theme = Theme.from_seed(Color(r=39, g=58, b=79), mode=ThemeMode.LIGHT)
        session: AppSession[_State] = AppSession(
            _State,
            _bare_view,
            _ScriptedTransport([]),
            theme=theme,
        )

        await session.start()

        assert session.app is not None
        assert session.app.theme is theme

    async def test_a_session_without_a_theme_invents_nothing(self) -> None:
        session: AppSession[_State] = AppSession(
            _State,
            _bare_view,
            _ScriptedTransport([]),
        )

        await session.start()

        assert session.app is not None
        assert session.app.theme.tokens.schemes.light.primary != Color(
            r=72,
            g=100,
            b=132,
        )
