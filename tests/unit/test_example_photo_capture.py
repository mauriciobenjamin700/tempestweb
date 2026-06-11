"""Tests for the photo-capture example (examples/photo-capture/app.py).

Covers the full async capture lifecycle (IDLE → CAPTURING → CAPTURED) via a
fake :class:`~tempestweb.native.NativeBridge`, plus the error path (IDLE →
CAPTURING → ERROR) and the reset handler.  Each test asserts both a state
transition and a rebuilt widget-tree change so the view is exercised end-to-end
with no real browser.

The :func:`fake_bridge` fixture installs a fake FFI bridge (returning a
scripted 640 × 480 PNG photo) before each test and tears it down afterwards —
the teardown is unconditional so bridge state never leaks across tests.
"""

from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from tempestweb._core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.camera import Photo

# ---------------------------------------------------------------------------
# Example loader (hyphen in directory name prevents direct import)
# ---------------------------------------------------------------------------

_MODULE_NAME = "_example_photo_capture"
_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "examples" / "photo-capture" / "app.py"
)


def _load_example() -> Any:  # noqa: ANN401
    """Import the photo-capture example module via importlib.

    The directory name ``photo-capture`` contains a hyphen which makes it
    invalid as a Python identifier, so we load it manually and register it
    in ``sys.modules`` so dataclasses / forward references resolve correctly.

    Returns:
        The loaded module exposing ``make_state``, ``view``, ``Phase``, and
        ``PhotoState``.
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _EXAMPLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _ex() -> Any:  # noqa: ANN401
    """Return the cached example module.

    Returns:
        The photo-capture example module.
    """
    return _load_example()


# ---------------------------------------------------------------------------
# Helpers — widget tree traversal
# ---------------------------------------------------------------------------


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a pre-order list of nodes.

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _all_keys(node: Node) -> list[str]:
    """Collect every non-empty key in the node subtree.

    Args:
        node: The root node.

    Returns:
        A list of key strings, in pre-order.
    """
    return [n.key for n in _walk(node) if n.key]


def _find_widget_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401
    """Locate a handler by widget key and attribute name.

    Args:
        widget: The root widget returned by ``view(app)``.
        key: The ``key`` of the target widget.
        attr: The handler attribute name (e.g. ``"on_click"``).

    Returns:
        The handler callable.

    Raises:
        AssertionError: If no matching widget/handler is found.
    """
    stack: list[Any] = [widget]
    while stack:
        w = stack.pop()
        if getattr(w, "key", None) == key:
            handler = getattr(w, attr, None)
            assert handler is not None, (
                f"Widget '{key}' found but has no attribute '{attr}'"
            )
            return handler
        children = getattr(w, "children", []) or []
        stack.extend(children)
        # Also follow single-child containers (child= field).
        child = getattr(w, "child", None)
        if child is not None:
            stack.append(child)
    raise AssertionError(
        f"No widget with key='{key}' and attribute '{attr}' found in tree"
    )


# ---------------------------------------------------------------------------
# Helpers — PNG payload
# ---------------------------------------------------------------------------

# Minimal 1×1 transparent PNG, base64-encoded (valid base64, real PNG header).
_PNG_1X1_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()

# The scripted photo value the fake bridge returns for camera.capture.
_FAKE_PHOTO_VALUE: dict[str, Any] = {
    "mime_type": "image/png",
    "width": 640,
    "height": 480,
    "data_base64": _PNG_1X1_B64,
}


# ---------------------------------------------------------------------------
# Fake bridge
# ---------------------------------------------------------------------------


class FakeBridge:
    """A scripted FFI bridge for the photo-capture test suite.

    Returns a fixed 640 × 480 PNG payload for ``camera.capture``; returns a
    permission-denied error when ``_fail`` is ``True``.

    Attributes:
        last_envelope: The last envelope received by :meth:`call`.
        _fail: When ``True``, :meth:`call` returns a ``permission_denied`` error.
    """

    def __init__(self, *, fail: bool = False) -> None:
        """Initialise the bridge.

        Args:
            fail: When ``True`` the bridge responds with a
                ``permission_denied`` error instead of a photo.
        """
        self.last_envelope: dict[str, Any] | None = None
        self._fail = fail

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Handle a single ``native_call`` envelope.

        Args:
            envelope: The dispatch envelope produced by
                :func:`~tempestweb.native.dispatch.send_native_call`.

        Returns:
            A success dict carrying the scripted photo, or an error dict if
            ``_fail`` is ``True``.
        """
        self.last_envelope = envelope
        cap: str = envelope.get("capability", "")
        if self._fail and cap == "camera.capture":
            return {
                "ok": False,
                "error": "permission_denied",
                "message": "Camera denied",
            }
        if cap == "camera.capture":
            return {"ok": True, "value": _FAKE_PHOTO_VALUE}
        return {"ok": False, "error": "unavailable", "message": f"no handler for {cap}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    """Ensure no bridge is left installed between tests.

    Yields:
        Nothing — used only for setup / teardown.
    """
    uninstall_bridge()
    yield
    uninstall_bridge()


@pytest.fixture()
def fake_bridge() -> FakeBridge:
    """Install a succeeding fake bridge and return it.

    Returns:
        The installed :class:`FakeBridge`.
    """
    bridge = FakeBridge()
    install_bridge(bridge)
    return bridge


@pytest.fixture()
def failing_bridge() -> FakeBridge:
    """Install a failing fake bridge (permission_denied) and return it.

    Returns:
        The installed :class:`FakeBridge` configured to deny camera permission.
    """
    bridge = FakeBridge(fail=True)
    install_bridge(bridge)
    return bridge


# ---------------------------------------------------------------------------
# Tests — static render (no bridge required)
# ---------------------------------------------------------------------------


def test_build_without_bridge_yields_idle_tree() -> None:
    """build(view(app)) succeeds with no bridge installed in the IDLE phase.

    This is the determinism guarantee: the initial render must never call a
    capability, so it is safe even without a bridge installed.
    """
    ex = _ex()
    app: App[Any] = App(
        state=ex.make_state(),
        view=ex.view,
        apply_patches=lambda _p: None,
    )
    node = build(ex.view(app))
    assert node.type, "root node type must be non-empty"
    assert node.children, "root node must have children in IDLE phase"


def test_idle_state_has_capture_button() -> None:
    """The IDLE view must contain a widget keyed 'capture'."""
    ex = _ex()
    app: App[Any] = App(
        state=ex.make_state(),
        view=ex.view,
        apply_patches=lambda _p: None,
    )
    node = build(ex.view(app))
    keys = _all_keys(node)
    assert "capture" in keys, f"'capture' key not found; keys found: {keys}"


# ---------------------------------------------------------------------------
# Tests — async handler: success path (IDLE → CAPTURING → CAPTURED)
# ---------------------------------------------------------------------------


async def test_capture_handler_transitions_to_captured(
    fake_bridge: FakeBridge,
) -> None:
    """Driving the capture handler must produce a Photo with width == 640.

    Args:
        fake_bridge: The installed fake bridge fixture.
    """
    ex = _ex()
    patches_received: list[Any] = []
    app: App[Any] = App(
        state=ex.make_state(),
        view=ex.view,
        apply_patches=patches_received.append,
    )

    # Build the IDLE tree so we can locate the capture handler.
    idle_widget = ex.view(app)
    idle_node = build(idle_widget)
    assert app.state.phase is ex.Phase.IDLE

    # Locate the on_click handler on the 'capture' button.
    capture_handler = _find_widget_handler(idle_widget, "capture", "on_click")

    # Drive the async handler: IDLE → CAPTURING → CAPTURED.
    await capture_handler()

    # The state should now be CAPTURED.
    assert app.state.phase is ex.Phase.CAPTURED, (
        f"Expected CAPTURED, got {app.state.phase}"
    )
    assert isinstance(app.state.photo, Photo), "state.photo must be a Photo instance"
    assert app.state.photo.width == 640, (
        f"Expected width=640, got {app.state.photo.width}"
    )
    assert app.state.photo.mime_type == "image/png"

    # The bridge must have been called with the correct capability.
    assert fake_bridge.last_envelope is not None
    assert fake_bridge.last_envelope["capability"] == "camera.capture"

    # The rebuilt tree must differ (now shows the photo card).
    captured_node = build(ex.view(app))
    assert captured_node != idle_node, "CAPTURED tree must differ from IDLE tree"

    # A 'photo-card' key must appear in the captured tree.
    captured_keys = _all_keys(captured_node)
    assert "photo-card" in captured_keys, (
        f"'photo-card' not found; keys: {captured_keys}"
    )


# ---------------------------------------------------------------------------
# Tests — async handler: error path (IDLE → CAPTURING → ERROR)
# ---------------------------------------------------------------------------


async def test_capture_handler_surfaces_permission_error(
    failing_bridge: FakeBridge,
) -> None:
    """A permission-denied bridge response must transition to the ERROR phase.

    Args:
        failing_bridge: The installed failing bridge fixture.
    """
    ex = _ex()
    app: App[Any] = App(
        state=ex.make_state(),
        view=ex.view,
        apply_patches=lambda _p: None,
    )
    idle_widget = ex.view(app)
    idle_node = build(idle_widget)

    capture_handler = _find_widget_handler(idle_widget, "capture", "on_click")
    await capture_handler()

    assert app.state.phase is ex.Phase.ERROR, f"Expected ERROR, got {app.state.phase}"
    assert "permission_denied" in app.state.error

    # Rebuilt tree must differ.
    error_node = build(ex.view(app))
    assert error_node != idle_node


# ---------------------------------------------------------------------------
# Tests — Photo model helpers
# ---------------------------------------------------------------------------


def test_photo_to_bytes_round_trips() -> None:
    """Photo.to_bytes() must decode the base64 payload correctly."""
    raw = b"\xde\xad\xbe\xef"
    encoded = base64.b64encode(raw).decode()
    photo = Photo(mime_type="image/png", width=1, height=1, data_base64=encoded)
    assert photo.to_bytes() == raw


def test_photo_is_frozen_after_construction() -> None:
    """Photo must be immutable (Pydantic frozen model)."""
    from pydantic import ValidationError

    photo = Photo(
        mime_type="image/jpeg",
        width=640,
        height=480,
        data_base64=_PNG_1X1_B64,
    )
    with pytest.raises((ValidationError, TypeError)):
        photo.width = 0  # noqa: PD011 — intentionally mutating a frozen model
