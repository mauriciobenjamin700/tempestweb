"""An app's palette has to reach the tree, because components resolve in Python.

A ``Theme`` is not only CSS: the core resolves a Button's fill, an Input's outline
and an indicator's accent **in Python**, inline on the widget. So a theme that
never reaches the tree is a theme that never paints, no matter what custom
properties the page carries.

Two halves were missing (issue #77, item 3): Mode A's runtime had no way to
accept a theme at all, and the generated artifacts never passed the one an app
declares. These pin both, plus the trap that made the theme-switcher example look
broken — a ``Theme`` built by filling in its loose convenience colours instead of
its token set.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tempest_core import App, Button, Color, Column, Theme, Widget
from tempestweb.runtime import WasmRuntime
from tempestweb.runtime.wasm_main import WasmAppHandle
from tempestweb.transports import WasmTransport

TEAL: Color = Color(r=28, g=176, b=163)

#: The theme the tests build, and the primary it actually resolves to.
#: ``from_seed`` harmonizes the seed rather than using it raw, so the expected
#: colour is the token set's own primary — reading it from the theme keeps the
#: test about "the theme reached the tree" instead of about the harmonizer.
TEAL_THEME: Theme = Theme.from_seed(seed=TEAL)
TEAL_PRIMARY: Color = TEAL_THEME.tokens.schemes.light.primary


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


def _walk(node: object) -> list:
    """Flatten a node tree, depth first.

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, the root first.
    """
    found = [node]
    for child in getattr(node, "children", []):
        found.extend(_walk(child))
    return found


def test_mode_a_runtime_takes_a_theme() -> None:
    """A theme handed to the Mode A runtime paints the components."""
    themed: WasmRuntime[_State] = WasmRuntime(
        _State(),
        _view,
        WasmTransport(lambda _patches: None),
        None,
        TEAL_THEME,
    )
    themed.start()

    assert _button_fill(themed.app) == TEAL_PRIMARY


def test_mode_a_runtime_without_a_theme_keeps_the_baseline() -> None:
    """No theme means the core's baseline palette, as before."""
    plain: WasmRuntime[_State] = WasmRuntime(
        _State(), _view, WasmTransport(lambda _patches: None)
    )
    plain.start()

    fill = _button_fill(plain.app)
    assert fill is not None
    assert fill != TEAL_PRIMARY


def test_a_theme_with_only_loose_colours_does_not_paint() -> None:
    """The trap: loose fields are not the token set components read.

    ``Theme(primary=...)`` sets a convenience field; every component reads
    ``theme.tokens``. Building a theme that way leaves the whole tree on the
    baseline palette — which is exactly why the theme-switcher example showed
    purple buttons under a teal accent, and why it now uses ``from_seed``.
    """
    loose: WasmRuntime[_State] = WasmRuntime(
        _State(),
        _view,
        WasmTransport(lambda _patches: None),
        None,
        Theme(primary=TEAL),
    )
    loose.start()

    assert _button_fill(loose.app) != TEAL_PRIMARY, "loose colours are not what paints"

    seeded: WasmRuntime[_State] = WasmRuntime(
        _State(),
        _view,
        WasmTransport(lambda _patches: None),
        None,
        TEAL_THEME,
    )
    seeded.start()
    assert _button_fill(seeded.app) == TEAL_PRIMARY, "a seeded token set does"


@pytest.mark.asyncio
async def test_the_handle_hands_the_page_its_theme_css() -> None:
    """Mode A's page is static, so the palette's CSS comes from the handle."""
    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(),
        _view,
        WasmTransport(lambda _patches: None),
        None,
        TEAL_THEME,
    )
    handle: WasmAppHandle[_State] = WasmAppHandle(
        runtime, WasmTransport(lambda _patches: None), theme=TEAL_THEME
    )

    css = handle.theme_css()
    expected = f"#{TEAL_PRIMARY.r:02x}{TEAL_PRIMARY.g:02x}{TEAL_PRIMARY.b:02x}"
    assert "--tw-primary" in css
    assert expected in css.lower(), f"{expected} missing from the emitted tokens"
    # The handle starts the runtime's event loop; close it or the task is left
    # pending and the interpreter complains about a coroutine never awaited.
    await handle.close()


@pytest.mark.asyncio
async def test_the_handle_emits_nothing_without_a_theme() -> None:
    """An app with no palette leaves the base sheet's own defaults standing."""
    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), _view, WasmTransport(lambda _patches: None)
    )
    handle: WasmAppHandle[_State] = WasmAppHandle(
        runtime, WasmTransport(lambda _patches: None)
    )

    assert handle.theme_css() == ""
    await handle.close()
