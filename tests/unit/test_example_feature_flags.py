"""Dedicated tests for the feature-flags example.

Covers:
* Initial build: the view mounts cleanly from ``make_state()`` with no bridge.
* Beta banner: visible on initial build (``beta_banner=True`` by default); hidden
  after the toggle button for that flag is clicked.
* new_ui toggle: the tree swaps between the legacy-UI card and the new-UI card.
* Rebuild counter: incremented on each flag flip.
* diff: each toggle produces a non-empty patch list.
"""

from __future__ import annotations

from typing import Any

from tempest_core import App, Node, build, diff
from tempest_core.widgets import Button

# ---------------------------------------------------------------------------
# Helpers (no import from examples module at module level — tests load it lazily)
# ---------------------------------------------------------------------------


def _load() -> Any:  # noqa: ANN401 — returns the example module
    """Import the feature-flags example module.

    Returns:
        The loaded module exposing ``make_state`` and ``view``.
    """
    import importlib.util
    import sys
    from pathlib import Path

    module_name = "_example_feature_flags"
    if module_name in sys.modules:
        return sys.modules[module_name]

    path = Path(__file__).resolve().parents[2] / "examples" / "feature-flags" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: Any) -> App[Any]:  # noqa: ANN401
    """Build an ``App`` around the example module.

    Args:
        module: The example module exposing ``make_state`` and ``view``.

    Returns:
        An ``App`` with a no-op ``apply_patches``.
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree (pre-order).

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _find_button(widget: Any, key: str) -> Button:  # noqa: ANN401
    """Find the first :class:`Button` widget with the given ``key``.

    Args:
        widget: The root widget returned by an example ``view``.
        key: The target widget key.

    Returns:
        The matching :class:`Button` widget.

    Raises:
        AssertionError: If no such button is found.
    """
    stack: list[Any] = [widget]
    while stack:
        current = stack.pop()
        if getattr(current, "key", None) == key and isinstance(current, Button):
            return current
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
        child = getattr(current, "child", None)
        if child is not None:
            stack.append(child)
    raise AssertionError(f"no Button with key={key!r}")


def _key_set(node: Node) -> set[str]:
    """Collect every non-empty widget key in an IR tree.

    Args:
        node: The root node.

    Returns:
        The set of key strings found.
    """
    return {n.key for n in _walk(node) if n.key}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_build_is_valid() -> None:
    """``build(view(app))`` from ``make_state()`` yields a valid Node tree."""
    module = _load()
    app = _make_app(module)
    node = build(module.view(app))

    assert isinstance(node, Node)
    assert node.type
    assert node.children  # root Container > Column > multiple children


def test_initial_build_no_bridge_needed() -> None:
    """The initial mount is deterministic and requires no bridge.

    Verifies both key structural nodes are present in the initial tree.
    """
    module = _load()
    app = _make_app(module)
    node = build(module.view(app))
    keys = _key_set(node)

    assert "title" in keys  # header text
    assert "flags-panel" in keys  # flag management panel
    assert "rebuild-counter" in keys  # change counter badge


def test_beta_banner_visible_by_default() -> None:
    """``beta_banner`` flag is ``True`` by default — the banner widget is present."""
    module = _load()
    app = _make_app(module)
    node = build(module.view(app))
    keys = _key_set(node)

    assert "beta-banner" in keys


def test_legacy_ui_visible_when_new_ui_disabled() -> None:
    """``new_ui`` is ``False`` by default — the legacy card is rendered."""
    module = _load()
    app = _make_app(module)
    node = build(module.view(app))
    keys = _key_set(node)

    assert "legacy-ui-card" in keys
    assert "new-ui-card" not in keys


def test_toggle_new_ui_swaps_variant() -> None:
    """Clicking the new_ui toggle button swaps legacy-ui-card for new-ui-card.

    Drives the real ``on_click`` handler, asserts the state counter incremented,
    and confirms the rebuilt tree contains the new variant instead of the legacy one.
    """
    module = _load()
    app = _make_app(module)

    before = build(module.view(app))
    assert "legacy-ui-card" in _key_set(before)
    assert "new-ui-card" not in _key_set(before)
    assert app.state.rebuild_counter == 0

    # Drive the toggle button for the new_ui flag.
    btn = _find_button(module.view(app), "new-ui-toggle")
    assert btn.on_click is not None
    btn.on_click()

    # State counter incremented.
    assert app.state.rebuild_counter == 1

    # The flag itself was flipped.
    assert app.state.flags.is_enabled("new_ui") is True

    after = build(module.view(app))
    assert "new-ui-card" in _key_set(after)
    assert "legacy-ui-card" not in _key_set(after)

    # The diff is non-empty — the tree genuinely changed.
    patches = diff(before, after)
    assert patches


def test_toggle_new_ui_twice_restores_legacy() -> None:
    """Toggling new_ui twice returns to the legacy variant.

    Confirms the toggle is truly bidirectional.
    """
    module = _load()
    app = _make_app(module)

    for _ in range(2):
        btn = _find_button(module.view(app), "new-ui-toggle")
        assert btn.on_click is not None
        btn.on_click()

    assert app.state.flags.is_enabled("new_ui") is False
    node = build(module.view(app))
    assert "legacy-ui-card" in _key_set(node)
    assert "new-ui-card" not in _key_set(node)
    assert app.state.rebuild_counter == 2


def test_toggle_beta_banner_hides_banner() -> None:
    """Toggling beta_banner off removes the banner widget from the tree.

    Drives the ``beta-banner-flag-toggle`` button and checks the rebuilt tree.
    """
    module = _load()
    app = _make_app(module)

    before = build(module.view(app))
    assert "beta-banner" in _key_set(before)

    btn = _find_button(module.view(app), "beta-banner-flag-toggle")
    assert btn.on_click is not None
    btn.on_click()

    assert app.state.flags.is_enabled("beta_banner") is False

    after = build(module.view(app))
    assert "beta-banner" not in _key_set(after)

    patches = diff(before, after)
    assert patches


def test_rebuild_counter_increments_per_toggle() -> None:
    """The rebuild counter increments once per toggle, across multiple flags."""
    module = _load()
    app = _make_app(module)

    for expected, key in enumerate(
        ["new-ui-toggle", "beta-banner-flag-toggle", "new-ui-toggle"],
        start=1,
    ):
        btn = _find_button(module.view(app), key)
        assert btn.on_click is not None
        btn.on_click()
        assert app.state.rebuild_counter == expected


def test_flags_panel_always_present() -> None:
    """The flags panel is always present regardless of individual flag values."""
    module = _load()
    app = _make_app(module)

    # Initial state.
    assert "flags-panel" in _key_set(build(module.view(app)))

    # Flip both flags.
    for key in ["new-ui-toggle", "beta-banner-flag-toggle"]:
        btn = _find_button(module.view(app), key)
        assert btn.on_click is not None
        btn.on_click()

    assert "flags-panel" in _key_set(build(module.view(app)))
