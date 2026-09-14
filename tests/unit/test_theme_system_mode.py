"""``ThemeMode.SYSTEM`` has to resolve against the platform, not against a default.

``SYSTEM`` is the mode of ``Theme()`` **and** of ``Theme.from_seed()``, and its
contract says it "defers to the platform". It did not: ``Theme.is_dark()`` takes
``platform_dark_mode`` as a keyword defaulting to ``False``, and no caller on the
render path ever filled it in, so every app that did not spell out
``mode=ThemeMode.DARK`` rendered light under a dark OS (tempestweb#217).

These pin the resolution on both halves of the #148 split at once — the colors
the components resolve inline, and the mode the base stylesheet is told about —
and pin that it is reversible, absolute modes are untouched, and an app that
swaps its own theme keeps ownership of it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempest_core import App, Button, Color, Column, Text, Theme, ThemeMode, Widget
from tempestweb.runtime import WasmRuntime, apply_media, resolve_platform_theme
from tempestweb.runtime.session import AppSession
from tempestweb.transports import WasmTransport

SEED: Color = Color(r=29, g=78, b=216)
SYSTEM_THEME: Theme = Theme.from_seed(seed=SEED)
LIGHT_PRIMARY: Color = SYSTEM_THEME.tokens.schemes.light.primary
DARK_PRIMARY: Color = SYSTEM_THEME.tokens.schemes.dark.primary


@dataclass
class _State:
    """State for the themed views."""

    clicks: int = 0


def _view(app: App[_State]) -> Widget:
    """Render a button, whose fill the core resolves from the active theme.

    Args:
        app: The application handle.

    Returns:
        The widget tree.
    """
    return Column(key="root", children=[Button(label="Go", key="go")])


def _walk(node: object) -> list[Any]:
    """Flatten a node tree, depth first.

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, the root first.
    """
    found: list[Any] = [node]
    for child in getattr(node, "children", []):
        found.extend(_walk(child))
    return found


def _button_fill(app: App[_State]) -> Color | None:
    """Read the resolved background of the tree's button.

    Args:
        app: A started app.

    Returns:
        The button's inline background, or ``None`` when it has no style.
    """
    scene = app.current_tree
    assert scene is not None
    button = next(node for node in _walk(scene.root) if node.key == "go")
    style = button.props.get("style")
    return None if style is None else style.background


def _started(theme: Theme | None) -> WasmRuntime[_State]:
    """Start a Mode A runtime carrying the given theme.

    Args:
        theme: The theme the app declares, or ``None``.

    Returns:
        The started runtime.
    """
    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(),
        _view,
        WasmTransport(lambda _patches: None),
        None,
        theme,
    )
    runtime.start()
    return runtime


async def _report_dark(app: App[_State], *, dark: bool) -> None:
    """Deliver the media report the client sends on mount and on change.

    The rebuild the report requests is coalesced onto the loop, so this yields
    until it has run: the resolved palette only reaches the tree on that build.

    Args:
        app: The application to report to.
        dark: The platform dark-mode flag to report.
    """
    apply_media(app, {"width": 1280.0, "height": 800.0, "platform_dark_mode": dark})
    await _settle()


async def _settle() -> None:
    """Let the app's coalesced rebuild run."""
    for _ in range(3):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_system_theme_follows_the_platform_dark_flag() -> None:
    """The same view, same theme, two flags — two palettes.

    This is the issue's own reproduction: before the fix both branches resolved
    the light primary, because ``platform_dark_mode`` never reached
    ``is_dark()``.
    """
    dark_side = _started(SYSTEM_THEME)
    await _report_dark(dark_side.app, dark=True)

    light_side = _started(SYSTEM_THEME)
    await _report_dark(light_side.app, dark=False)

    assert _button_fill(dark_side.app) == DARK_PRIMARY
    assert _button_fill(light_side.app) == LIGHT_PRIMARY
    assert _button_fill(dark_side.app) != _button_fill(light_side.app)


@pytest.mark.asyncio
async def test_the_stylesheet_half_agrees_with_the_tree() -> None:
    """``is_dark()`` reports dark too, so sheet and inline styles cannot split.

    The base sheet is told the mode through the ``theme`` envelope, which reads
    ``Theme.is_dark()``. Resolving ``SYSTEM`` by pinning the mode means the two
    halves read the same field rather than two sources that can disagree
    (tempestweb#148).
    """
    runtime = _started(SYSTEM_THEME)
    await _report_dark(runtime.app, dark=True)

    assert runtime.app.theme.is_dark() is True
    assert _button_fill(runtime.app) == DARK_PRIMARY


@pytest.mark.asyncio
async def test_the_resolution_is_reversible() -> None:
    """The platform going back to light takes the app back with it."""
    runtime = _started(SYSTEM_THEME)

    await _report_dark(runtime.app, dark=True)
    assert _button_fill(runtime.app) == DARK_PRIMARY

    await _report_dark(runtime.app, dark=False)
    assert _button_fill(runtime.app) == LIGHT_PRIMARY


@pytest.mark.asyncio
async def test_an_unchanged_flag_installs_nothing() -> None:
    """Repeating the same report is a no-op, so no rebuild is requested."""
    runtime = _started(SYSTEM_THEME)
    await _report_dark(runtime.app, dark=True)
    installed = runtime.app.theme

    assert resolve_platform_theme(runtime.app) is False
    assert runtime.app.theme is installed


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [ThemeMode.LIGHT, ThemeMode.DARK])
async def test_an_absolute_mode_ignores_the_platform(mode: ThemeMode) -> None:
    """``LIGHT`` and ``DARK`` are absolute: the OS flag does not move them.

    Args:
        mode: The absolute mode the app declares.
    """
    declared = Theme.from_seed(seed=SEED, mode=mode)
    runtime = _started(declared)

    await _report_dark(runtime.app, dark=mode is ThemeMode.LIGHT)

    assert runtime.app.theme.mode is mode
    expected = DARK_PRIMARY if mode is ThemeMode.DARK else LIGHT_PRIMARY
    assert _button_fill(runtime.app) == expected


@pytest.mark.asyncio
async def test_an_app_that_swaps_its_own_theme_keeps_it() -> None:
    """``App.set_theme`` wins: the swapped theme becomes the declared one."""
    runtime = _started(SYSTEM_THEME)
    await _report_dark(runtime.app, dark=True)

    runtime.app.set_theme(Theme.from_seed(seed=SEED, mode=ThemeMode.LIGHT))
    await _settle()
    await _report_dark(runtime.app, dark=True)

    assert runtime.app.theme.mode is ThemeMode.LIGHT
    assert _button_fill(runtime.app) == LIGHT_PRIMARY


@pytest.mark.asyncio
async def test_a_system_app_swapping_to_system_still_follows_the_platform() -> None:
    """A swap back to ``SYSTEM`` is re-resolved, not left unpinned."""
    runtime = _started(Theme.from_seed(seed=SEED, mode=ThemeMode.LIGHT))
    await _report_dark(runtime.app, dark=True)
    assert _button_fill(runtime.app) == LIGHT_PRIMARY

    runtime.app.set_theme(SYSTEM_THEME)
    await _settle()
    await _report_dark(runtime.app, dark=True)

    assert _button_fill(runtime.app) == DARK_PRIMARY


class _RecordingTransport:
    """A Mode B transport double that records the theme envelopes it is sent."""

    def __init__(self) -> None:
        """Start with empty logs."""
        self.modes: list[str] = []

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Ignore patches.

        Args:
            patches: The wire patches for this tick.
        """
        return None

    async def send_navigate(self, path: str) -> None:
        """Ignore navigation.

        Args:
            path: The new top-route path.
        """
        return None

    async def send_theme(self, mode: str) -> None:
        """Record one theme envelope.

        Args:
            mode: The resolved theme mode.
        """
        self.modes.append(mode)

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native calls.

        Args:
            call_id: Correlation id.
            capability: Capability name.
            args: Capability arguments.
        """
        return None

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore subscriptions.

        Args:
            sub_id: Subscription id.
            capability: Capability name.
            args: Capability arguments.
        """
        return None

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Ignore unsubscriptions.

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


def _session_view(app: App[int]) -> Widget:
    """Render a one-line tree, so a rebuild is cheap.

    Args:
        app: The application handle.

    Returns:
        A column holding the state as text.
    """
    return Column(key="root", children=[Text(key="label", content=str(app.state))])


@pytest.mark.asyncio
async def test_mode_b_sends_dark_when_the_client_reports_a_dark_platform() -> None:
    """The Mode B half resolves the same way, over the wire.

    ``session.py`` makes the same ``is_dark()`` call ``wasm.py`` does, so the fix
    lands on both runtimes through ``apply_media`` rather than being re-derived
    per mode.
    """
    transport = _RecordingTransport()
    session: AppSession[int] = AppSession(
        state_factory=lambda: 0,
        view=_session_view,
        transport=transport,  # type: ignore[arg-type]
        theme=SYSTEM_THEME,
    )
    await session.start()
    for _ in range(3):
        await asyncio.sleep(0)
    assert transport.modes == [], "the first light is not worth a frame"

    await session.dispatch(
        {"type": "media", "key": "root", "payload": {"platform_dark_mode": True}}
    )
    for _ in range(3):
        await asyncio.sleep(0)

    assert transport.modes == ["dark"]
    await session.close()
