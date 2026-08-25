"""The ``theme`` envelope: the mode the base stylesheet needs, and nothing more.

What ``tempest_core`` resolves rides along inside each widget's inline style, so a
Card and a Button follow the app's theme on their own. What only the base sheet
paints — the page background, a field's surface, every hover/focus state — is CSS,
and the ``Theme`` never crosses the wire (the core strips it when serializing).
Without the mode, a dark app showed a white field inside a dark card
(tempestweb#148).

These tests pin the three decisions that make the envelope honest:

1. It is sent when the app asks for dark, and again when it comes back to light.
2. The first ``light`` is **not** sent: the sheet's own tokens are the light
   palette, so it would be a frame that says nothing.
3. The mode is resolved the way a **widget** resolves it (``Theme.is_dark()``, no
   platform flag), so the sheet can never disagree with the tree above it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tempest_core import App, Button, Column, Text, Theme, ThemeMode, Widget
from tempestweb.runtime.session import AppSession


class RecordingTransport:
    """A transport that records every envelope the session sends."""

    def __init__(self) -> None:
        """Start with empty logs."""
        self.patches: list[list[dict[str, Any]]] = []
        self.modes: list[str] = []
        self.paths: list[str] = []

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Record one patch batch.

        Args:
            patches: The wire patches for this tick.
        """
        self.patches.append(patches)

    async def send_navigate(self, path: str) -> None:
        """Record a navigation.

        Args:
            path: The new top-route path.
        """
        self.paths.append(path)

    async def send_theme(self, mode: str) -> None:
        """Record a theme mode.

        Args:
            mode: The resolved theme mode.
        """
        self.modes.append(mode)

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native calls — unused here.

        Args:
            call_id: Correlation id.
            capability: Capability name.
            args: Capability arguments.
        """
        return None

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore subscriptions — unused here.

        Args:
            sub_id: Subscription id.
            capability: Capability name.
            args: Capability arguments.
        """
        return None

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Ignore unsubscriptions — unused here.

        Args:
            sub_id: Subscription id.
        """
        return None

    def on_event(self, handler: Any) -> None:  # noqa: ANN401 — test double sink
        """Ignore the event sink.

        Args:
            handler: The sink (unused).
        """
        return None

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 — test double sink
        """Ignore the native-result sink.

        Args:
            handler: The sink (unused).
        """
        return None

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 — test double sink
        """Ignore the native-event sink.

        Args:
            handler: The sink (unused).
        """
        return None

    async def close(self) -> None:
        """Close is a no-op for this double."""
        return None


async def _settle() -> None:
    """Let the session's spawned sends run.

    The session ships every frame as a tracked task (so a slow client cannot block
    a handler), so a test has to yield before reading what was sent.
    """
    for _ in range(3):
        await asyncio.sleep(0)


def _view(app: App[int]) -> Widget:
    """Render a one-line tree, so a rebuild is cheap.

    Args:
        app: The application handle.

    Returns:
        A column holding the state as text.
    """
    return Column(key="root", children=[Text(key="label", content=str(app.state))])


async def _mounted(theme: Theme | None) -> tuple[AppSession[int], RecordingTransport]:
    """Mount a session with the given theme.

    Args:
        theme: The theme to build the app with, or None.

    Returns:
        The started session and its recording transport.
    """
    transport = RecordingTransport()
    session: AppSession[int] = AppSession(
        state_factory=lambda: 0,
        view=_view,
        transport=transport,  # type: ignore[arg-type]
        theme=theme,
    )
    await session.start()
    return session, transport


async def _mounted_with_toggle(
    start_dark: bool = False,
) -> tuple[AppSession[int], RecordingTransport]:
    """Mount a session whose tree carries two theme-swapping buttons.

    The tree deliberately does **not** pass the theme to any widget: that is the
    case where a swap produces no patch at all, so it is the one worth pinning.

    Args:
        start_dark: Whether the app opens on the dark theme.

    Returns:
        The started session and its recording transport.
    """
    transport = RecordingTransport()

    def view(app: App[int]) -> Widget:
        """Render two buttons that swap the app's theme.

        Args:
            app: The application handle.

        Returns:
            A column with a dark and a light button.
        """
        return Column(
            key="root",
            children=[
                Button(
                    key="go-dark",
                    label="dark",
                    on_click=lambda: app.set_theme(Theme(mode=ThemeMode.DARK)),
                ),
                Button(
                    key="go-light",
                    label="light",
                    on_click=lambda: app.set_theme(Theme(mode=ThemeMode.LIGHT)),
                ),
            ],
        )

    mode = ThemeMode.DARK if start_dark else ThemeMode.LIGHT
    session: AppSession[int] = AppSession(
        state_factory=lambda: 0,
        view=view,
        transport=transport,  # type: ignore[arg-type]
        theme=Theme(mode=mode),
    )
    await session.start()
    transport.modes.clear()
    return session, transport


@pytest.mark.asyncio
async def test_a_dark_theme_is_reported_on_mount() -> None:
    """An app that opens dark tells the client before the first paint."""
    _, transport = await _mounted(Theme(mode=ThemeMode.DARK))
    assert transport.modes == ["dark"]


@pytest.mark.asyncio
async def test_the_first_light_is_not_reported() -> None:
    """A light app sends no theme frame: the sheet is already light.

    Marking light on mount would spend a frame saying what the stylesheet's own
    tokens already say — and every app that never touches the theme would pay it.
    """
    _, transport = await _mounted(Theme(mode=ThemeMode.LIGHT))
    assert transport.modes == []


@pytest.mark.asyncio
async def test_a_system_theme_reports_nothing_since_a_widget_resolves_light() -> None:
    """SYSTEM resolves light for a widget, so the sheet stays light too.

    The attribute exists to make the sheet agree with the inline styles already in
    the tree. A widget built with a SYSTEM theme never sees the OS — the core
    resolves it light — so darkening the page from the OS alone would put a light
    tree on a dark page.
    """
    _, transport = await _mounted(Theme(mode=ThemeMode.SYSTEM))
    assert transport.modes == []


@pytest.mark.asyncio
async def test_a_handler_that_swaps_the_theme_reports_it_both_ways() -> None:
    """Switching to dark reports dark; switching back reports light.

    Driven through ``dispatch``, which is how an app swaps a theme — and the case
    that used to be missed: a ``view`` that passes the theme to no widget rebuilds
    to the identical IR, so the core emits **no patch**, and a check that only ran
    on a patch batch never fired. The base sheet would then stay light under an
    app that had gone dark.
    """
    session, transport = await _mounted_with_toggle()
    await session.dispatch({"type": "click", "key": "go-dark", "payload": {}})
    await _settle()
    assert transport.modes == ["dark"]

    await session.dispatch({"type": "click", "key": "go-light", "payload": {}})
    await _settle()
    assert transport.modes == ["dark", "light"]


@pytest.mark.asyncio
async def test_an_unchanged_mode_is_not_repeated() -> None:
    """A handler that does not change the mode sends no theme frame."""
    session, transport = await _mounted_with_toggle(start_dark=True)
    await session.dispatch({"type": "click", "key": "go-dark", "payload": {}})
    await _settle()
    assert transport.modes == []
