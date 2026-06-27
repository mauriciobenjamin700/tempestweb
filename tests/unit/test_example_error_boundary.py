"""Dedicated tests for the error-boundary example app.

Verifies:
* The initial mount (boom=False) builds a healthy tree without any bridge.
* Toggling boom=True makes the boundary render the fallback and call on_error.
* The on_error hook captures an :class:`~tempestweb.observability.ErrorInfo`.
* The telemetry_reporter inside on_error records a ``render_error`` event.
* App state is updated: crash_count > 0 and last_error is populated.
* Re-enabling the healthy path (boom=False) builds a healthy tree again.
* The Logger captured a WARNING record for the crash.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempest_core import App, Node, build, diff
from tempestweb.observability import (
    ErrorBoundary,
    ErrorInfo,
    TelemetryProvider,
    telemetry_reporter,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_module(name: str) -> ModuleType:
    """Import an example app module by its directory name.

    Args:
        name: The example directory under ``examples/`` (e.g. ``"error-boundary"``).

    Returns:
        The imported module exposing ``make_state``, ``view``,
        ``_log_records``, and ``_telemetry_events``.
    """
    module_key = f"_example_{name.replace('-', '_')}"
    path = EXAMPLES_DIR / name / "app.py"
    spec = importlib.util.spec_from_file_location(module_key, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: ModuleType) -> App[Any]:
    """Build an ``App`` around the example module's state and view.

    Args:
        module: The example module.

    Returns:
        An ``App`` whose ``apply_patches`` is a no-op.
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


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


def _types(node: Node) -> set[str]:
    """Collect all widget type tags present in the IR tree.

    Args:
        node: The root node.

    Returns:
        The set of ``type`` strings found across the whole subtree.
    """
    return {n.type for n in _walk(node)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def module() -> ModuleType:
    """Load a fresh copy of the error-boundary example module for each test.

    The module-level lists (``_log_records``, ``_telemetry_events``) are reset
    on each load because a new module object is created per test.

    Returns:
        The freshly imported example module.
    """
    # Use a unique sys.modules key per test to avoid cross-test pollution.
    unique_key = f"_example_error_boundary_{id(object())}"
    path = EXAMPLES_DIR / "error-boundary" / "app.py"
    spec = importlib.util.spec_from_file_location(unique_key, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_key] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests — initial mount (no bridge required)
# ---------------------------------------------------------------------------


def test_initial_build_is_green_with_no_bridge(module: ModuleType) -> None:
    """The initial mount builds without any native bridge installed."""
    app = _make_app(module)
    node = build(module.view(app))

    assert isinstance(node, Node)
    assert node.type  # non-empty type tag (Column)
    assert node.children  # at least header + controls + boundary + error + log


def test_initial_tree_has_expected_widget_types(module: ModuleType) -> None:
    """The healthy initial tree contains Column, Button, and Text widgets."""
    app = _make_app(module)
    node = build(module.view(app))
    types = _types(node)

    assert "Column" in types
    assert "Button" in types
    assert "Text" in types


def test_initial_state_is_healthy(module: ModuleType) -> None:
    """The default state starts with boom=False, zero crashes, empty error."""
    app = _make_app(module)

    assert app.state.boom is False
    assert app.state.crash_count == 0
    assert app.state.last_error == ""
    assert app.state.log_entries == []


# ---------------------------------------------------------------------------
# Tests — boom=True path (boundary catches the error)
# ---------------------------------------------------------------------------


def test_boom_true_renders_fallback_not_healthy_subtree(module: ModuleType) -> None:
    """With boom=True the boundary renders the fallback instead of the healthy tree."""
    app = _make_app(module)

    # Trigger the crash.
    app.set_state(lambda s: setattr(s, "boom", True))

    before = build(module.view(app))
    all_keys = {n.key for n in _walk(before)}

    # The healthy subtree widgets must NOT appear.
    assert "healthy-subtree" not in all_keys
    assert "healthy-label" not in all_keys
    # The fallback (from default_fallback) renders a Column with Text children.
    assert "Column" in _types(before)


def test_boom_true_updates_crash_count_and_last_error(module: ModuleType) -> None:
    """When the boundary catches the error it updates crash_count and last_error."""
    app = _make_app(module)

    app.set_state(lambda s: setattr(s, "boom", True))
    build(module.view(app))  # triggers on_error → set_state

    assert app.state.crash_count == 1
    assert "RuntimeError" in app.state.last_error
    assert "simulated render failure" in app.state.last_error


def test_boom_true_populates_log_entries(module: ModuleType) -> None:
    """After a crash, log_entries is non-empty and contains the error type."""
    app = _make_app(module)

    app.set_state(lambda s: setattr(s, "boom", True))
    build(module.view(app))

    assert len(app.state.log_entries) >= 1
    assert "RuntimeError" in app.state.log_entries[-1]


def test_on_error_captures_error_info_directly(module: ModuleType) -> None:
    """The on_error closure correctly captures an ErrorInfo with type and message."""
    captured: list[ErrorInfo] = []

    # Build a standalone ErrorBoundary that raises, wired to our capture list.
    def child() -> Any:  # noqa: ANN401 — deliberate raise for test
        raise ValueError("test boom")

    boundary = ErrorBoundary(child_builder=child, on_error=captured.append)
    boundary.render()  # does not raise; calls on_error

    assert len(captured) == 1
    assert captured[0].error_type == "ValueError"
    assert captured[0].message == "test boom"
    assert "ValueError" in captured[0].stack


def test_telemetry_reporter_records_render_error_event() -> None:
    """telemetry_reporter forwards the error to the provider as a render_error event."""
    events: list[tuple[str, dict[str, Any]]] = []

    class CapturingAdapter:
        """A minimal adapter that appends to the outer events list."""

        def track(self, event: str, props: dict[str, Any]) -> None:
            """Record a tracked event.

            Args:
                event: The event name.
                props: Event properties.

            Returns:
                None.
            """
            events.append((event, props))

        def identify(self, user_id: str, traits: dict[str, Any]) -> None:
            """No-op identify.

            Args:
                user_id: Unused.
                traits: Unused.

            Returns:
                None.
            """

    provider = TelemetryProvider(CapturingAdapter())

    def bad_child() -> Any:  # noqa: ANN401 — deliberate raise for test
        raise RuntimeError("upstream crash")

    boundary = ErrorBoundary(
        child_builder=bad_child,
        on_error=telemetry_reporter(provider),
    )
    boundary.render()

    assert len(events) == 1
    event_name, props = events[0]
    assert event_name == "render_error"
    assert props["error_type"] == "RuntimeError"
    assert props["message"] == "upstream crash"
    assert "RuntimeError" in props["stack"]


def test_module_telemetry_events_captured_after_crash(module: ModuleType) -> None:
    """The module-level _telemetry_events list is populated after a crash."""
    app = _make_app(module)

    # Clear the list before triggering the crash.
    module._telemetry_events.clear()

    app.set_state(lambda s: setattr(s, "boom", True))
    build(module.view(app))

    assert len(module._telemetry_events) >= 1
    event_name, props = module._telemetry_events[0]
    assert event_name == "render_error"
    assert props.get("error_type") == "RuntimeError"


def test_module_log_records_captured_after_crash(module: ModuleType) -> None:
    """The module-level _log_records list gets a WARNING record after a crash."""
    app = _make_app(module)

    # Clear records before the crash.
    module._log_records.clear()

    app.set_state(lambda s: setattr(s, "boom", True))
    build(module.view(app))

    warning_records = [r for r in module._log_records if r.level == "WARNING"]
    assert len(warning_records) >= 1
    rec = warning_records[0]
    assert rec.message == "render_error_caught"
    assert rec.fields.get("error_type") == "RuntimeError"


# ---------------------------------------------------------------------------
# Tests — recovery path (boom=True → boom=False)
# ---------------------------------------------------------------------------


def test_recovery_from_crash_restores_healthy_subtree(module: ModuleType) -> None:
    """After clearing boom, the next build renders the healthy subtree again."""
    app = _make_app(module)

    # Trigger crash.
    app.set_state(lambda s: setattr(s, "boom", True))
    crashed = build(module.view(app))
    assert "healthy-subtree" not in {n.key for n in _walk(crashed)}

    # Recover.
    app.set_state(lambda s: setattr(s, "boom", False))
    recovered = build(module.view(app))
    all_keys = {n.key for n in _walk(recovered)}

    assert "healthy-subtree" in all_keys
    assert "healthy-label" in all_keys


def test_diff_emits_patches_on_transition(module: ModuleType) -> None:
    """Diffing the tree before and after a boom transition produces patches."""
    app = _make_app(module)

    healthy = build(module.view(app))

    app.set_state(lambda s: setattr(s, "boom", True))
    crashed = build(module.view(app))

    patches = diff(healthy, crashed)
    assert patches  # at least one structural change


def test_multiple_crashes_accumulate_crash_count(module: ModuleType) -> None:
    """Toggling boom on and off multiple times accumulates crash_count correctly."""
    app = _make_app(module)

    for _ in range(3):
        app.set_state(lambda s: setattr(s, "boom", True))
        build(module.view(app))
        app.set_state(lambda s: setattr(s, "boom", False))
        build(module.view(app))

    assert app.state.crash_count == 3


def test_log_entries_capped_at_five(module: ModuleType) -> None:
    """The log_entries list is capped at 5 entries to keep the panel readable."""
    app = _make_app(module)

    for _ in range(8):
        app.set_state(lambda s: setattr(s, "boom", True))
        build(module.view(app))
        app.set_state(lambda s: setattr(s, "boom", False))
        build(module.view(app))

    assert len(app.state.log_entries) <= 5
