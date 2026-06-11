"""Dedicated tests for the clipboard-share example.

Verifies:

* The initial mount builds a valid widget tree with no bridge installed.
* Driving the ``do_copy`` async handler transitions IDLE → BUSY → COPIED and
  the status ``Text`` reflects the new state.
* Driving the ``do_share`` async handler transitions IDLE → BUSY → SHARED with
  a ``ShareOutcome.SHARED`` and updates the status text accordingly.
* ``ShareOutcome.CANCELLED`` is reflected correctly.
* ``ShareOutcome.UNSUPPORTED`` is reflected correctly.
* A NativeError during copy transitions to the ERROR phase and surfaces the
  message in the status text.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb._core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.share import ShareOutcome

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a list of nodes (pre-order).

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _find_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401
    """Locate a handler callable by widget key and attribute name.

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
        current = stack.pop()
        if getattr(current, "key", None) == key:
            handler = getattr(current, attr, None)
            if handler is not None:
                return handler
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
    raise AssertionError(f"no widget with key={key!r} and handler {attr!r}")


def _status_text(node: Node) -> str:
    """Return the ``content`` prop of the ``status`` Text node.

    Args:
        node: The root IR node of the built tree.

    Returns:
        The status text string.

    Raises:
        AssertionError: If no ``status`` node is found.
    """
    for n in _walk(node):
        if n.key == "status":
            return str(n.props.get("content", ""))
    raise AssertionError("no node with key='status' found")


# ---------------------------------------------------------------------------
# Fake bridge
# ---------------------------------------------------------------------------


class FakeBridge:
    """Fake native bridge for clipboard and share capabilities.

    Records the last envelope received and returns scripted responses so the
    tests run with no real browser present.

    Attributes:
        share_outcome: The share outcome string to return (default "shared").
        calls: Ordered list of capability names that were dispatched.
    """

    def __init__(self, *, share_outcome: str = "shared") -> None:
        """Initialise the bridge.

        Args:
            share_outcome: The ``ShareOutcome`` value to return from ``share.share``.
        """
        self.share_outcome: str = share_outcome
        self.calls: list[str] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Handle a native capability call.

        Args:
            envelope: The ``native_call`` envelope dispatched by the capability
                wrapper.

        Returns:
            A scripted ``ok`` / ``value`` response dict.
        """
        cap: str = envelope["capability"]
        self.calls.append(cap)

        if cap == "clipboard.write":
            return {"ok": True, "value": {}}
        if cap == "share.share":
            return {"ok": True, "value": {"outcome": self.share_outcome}}

        return {"ok": False, "error": "unavailable", "message": f"no fake for {cap}"}


class ErrorBridge:
    """Fake bridge that always returns an error response.

    Used to verify that the ERROR phase is surfaced correctly in the UI.
    """

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Return a permission_denied error for every call.

        Args:
            envelope: Ignored; every call returns an error.

        Returns:
            An ``ok: False`` response.
        """
        return {
            "ok": False,
            "error": "permission_denied",
            "message": "permission denied by user",
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_module() -> Any:  # noqa: ANN401
    """Import the clipboard-share example module.

    Returns:
        The imported module exposing ``make_state`` and ``view``.
    """
    import importlib.util
    import sys
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2] / "examples" / "clipboard-share" / "app.py"
    )
    spec = importlib.util.spec_from_file_location("_example_clipboard_share", path)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    sys.modules["_example_clipboard_share"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module() -> Any:  # noqa: ANN401
    """Return the clipboard-share example module.

    Returns:
        The imported example module.
    """
    return _make_module()


@pytest.fixture()
def app(module: Any) -> App[Any]:  # noqa: ANN401
    """Build an App from the example module's state and view.

    Args:
        module: The clipboard-share example module.

    Returns:
        An ``App`` whose ``apply_patches`` is a no-op.
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:  # noqa: ANN401
    """Guarantee no bridge leaks between tests.

    Yields:
        None.
    """
    uninstall_bridge()
    yield
    uninstall_bridge()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_build_no_bridge(module: Any, app: App[Any]) -> None:
    """build(view(app)) yields a valid Node tree with no bridge installed."""
    node = build(module.view(app))
    assert isinstance(node, Node)
    assert node.type
    assert node.children
    # The status text starts as the idle prompt.
    status = _status_text(node)
    assert "action" in status.lower() or status  # non-empty idle label present


def test_initial_status_is_idle(module: Any, app: App[Any]) -> None:
    """The status Text reflects the IDLE phase on first mount."""
    node = build(module.view(app))
    assert _status_text(node) == "Choose an action below."


async def test_copy_handler_transitions_to_copied(module: Any, app: App[Any]) -> None:
    """Driving do_copy with a fake bridge transitions IDLE -> COPIED."""
    bridge = FakeBridge()
    install_bridge(bridge)

    idle_node = build(module.view(app))
    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()

    assert app.state.phase.value == "copied"
    copied_node = build(module.view(app))
    assert _status_text(copied_node) == "Copied to clipboard!"
    assert _status_text(copied_node) != _status_text(idle_node)
    assert "clipboard.write" in bridge.calls


async def test_share_handler_shared_outcome(module: Any, app: App[Any]) -> None:
    """Driving do_share with outcome 'shared' transitions IDLE -> SHARED."""
    bridge = FakeBridge(share_outcome="shared")
    install_bridge(bridge)

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.phase.value == "shared"
    assert app.state.share_outcome is ShareOutcome.SHARED
    node = build(module.view(app))
    assert _status_text(node) == "Shared successfully."
    assert "share.share" in bridge.calls


async def test_share_handler_cancelled_outcome(module: Any, app: App[Any]) -> None:
    """A cancelled share sheet transitions to SHARED with CANCELLED outcome."""
    install_bridge(FakeBridge(share_outcome="cancelled"))

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.share_outcome is ShareOutcome.CANCELLED
    node = build(module.view(app))
    assert _status_text(node) == "Share cancelled."


async def test_share_handler_unsupported_outcome(module: Any, app: App[Any]) -> None:
    """An unsupported browser returns UNSUPPORTED outcome without raising."""
    install_bridge(FakeBridge(share_outcome="unsupported"))

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.share_outcome is ShareOutcome.UNSUPPORTED
    node = build(module.view(app))
    assert "not supported" in _status_text(node)


async def test_copy_error_transitions_to_error_phase(
    module: Any, app: App[Any]
) -> None:
    """A NativeError during clipboard.write transitions to the ERROR phase."""
    install_bridge(ErrorBridge())

    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()

    assert app.state.phase.value == "error"
    node = build(module.view(app))
    status = _status_text(node)
    assert status.startswith("Error:")


async def test_tree_changes_between_idle_and_copied(module: Any, app: App[Any]) -> None:
    """The rebuilt tree differs after a successful copy (diff-friendly)."""
    from tempestweb._core import diff

    install_bridge(FakeBridge())

    before = build(module.view(app))
    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()
    after = build(module.view(app))

    patches = diff(before, after)
    assert patches, "expected at least one patch after a state transition"
