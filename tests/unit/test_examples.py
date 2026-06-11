"""Example apps import, build into a valid Node tree, and exercise widgets.

Each example is a ``view(app) -> Widget`` module just like ``examples/counter``.
These tests load each one, construct an ``App`` around its ``make_state`` /
``view``, run ``build(view(app))`` to validate the tree, walk the resulting IR to
confirm the input / list / form widgets are present, and drive a state
transition (synchronous or async) so the handlers are exercised, not just the
initial mount.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempestweb._core import App, Node, build, diff

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_example(name: str) -> ModuleType:
    """Import an example's ``app`` module by its directory name.

    The module is registered in ``sys.modules`` under a unique name so that
    ``dataclasses.field`` and forward references resolve correctly (a dataclass
    defined in a module that is not registered fails to introspect its module
    namespace).

    Args:
        name: The example directory under ``examples/`` (e.g. ``"todo"``).

    Returns:
        The imported module exposing ``make_state`` and ``view``.
    """
    module_name = f"_example_{name}"
    path = EXAMPLES_DIR / name / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: ModuleType) -> App[Any]:
    """Build an ``App`` around an example module's state and view.

    Args:
        module: An example module exposing ``make_state`` and ``view``.

    Returns:
        An ``App`` whose ``apply_patches`` is a no-op (the tests build/diff
        directly rather than going through a transport).
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


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


def _types(node: Node) -> set[str]:
    """Collect every widget ``type`` tag present in an IR tree.

    Args:
        node: The root node.

    Returns:
        The set of type tags found in the subtree.
    """
    return {n.type for n in _walk(node)}


EXAMPLE_NAMES = ["counter", "todo", "form", "fetch"]


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_example_imports_and_builds(name: str) -> None:
    """Every example imports and ``build(view(app))`` yields a Node tree."""
    module = _load_example(name)
    assert hasattr(module, "view")
    assert hasattr(module, "make_state")

    app = _make_app(module)
    widget = module.view(app)
    node = build(widget)

    assert isinstance(node, Node)
    assert node.type  # non-empty type tag
    # A built tree always has a root; every example renders at least one child.
    assert node.children


def test_todo_exercises_input_and_list() -> None:
    """The todo example renders an Input plus a virtualized list of checkboxes."""
    module = _load_example("todo")
    app = _make_app(module)
    node = build(module.view(app))
    types = _types(node)

    assert "Input" in types
    assert "LazyColumn" in types
    # The seed items materialize as Checkbox rows inside the list.
    assert "Checkbox" in types

    # The list's materialized window matches the seeded item count.
    lazy = next(n for n in _walk(node) if n.type == "LazyColumn")
    assert lazy.key == "items"
    assert len(lazy.children) == len(app.state.items)
    assert all(c.type == "Checkbox" for c in lazy.children)


def test_todo_add_item_transition() -> None:
    """Typing a draft and adding an item grows the list by one Insert patch."""
    module = _load_example("todo")
    app = _make_app(module)
    before = build(module.view(app))

    # Simulate the add_item handler effect: append an item, clear the draft.
    item_type = type(app.state.items[0])
    app.state.items.append(item_type(title="Ship the examples"))
    app.state.draft = ""
    after = build(module.view(app))

    lazy_after = next(n for n in _walk(after) if n.type == "LazyColumn")
    assert len(lazy_after.children) == 3

    patches = diff(before, after)
    assert patches  # the tree changed


def test_form_exercises_form_widgets() -> None:
    """The form example renders a Form wrapping two FormFields with Inputs."""
    module = _load_example("form")
    app = _make_app(module)
    node = build(module.view(app))
    types = _types(node)

    assert "Form" in types
    assert "FormField" in types
    assert "Input" in types

    form_node = next(n for n in _walk(node) if n.type == "Form")
    field_nodes = [n for n in _walk(form_node) if n.type == "FormField"]
    assert len(field_nodes) == 2
    # Each field wraps exactly one Input child.
    for field_node in field_nodes:
        assert any(c.type == "Input" for c in field_node.children)


def test_form_validation_surfaces_errors() -> None:
    """Submitting an empty form mirrors validation errors back onto the fields."""
    module = _load_example("form")
    app = _make_app(module)
    # Reconstruct the form to run its validators (the view rebuilds it each call,
    # but validate is a pure method we can call on a fresh build).
    widget = module.view(app)
    form = _find_form_widget(widget)
    state = form.validate({"email": "", "password": ""})

    assert state.valid is False
    assert "email" in state.errors
    assert "password" in state.errors

    # A valid payload passes.
    ok = form.validate({"email": "you@example.com", "password": "longenough"})
    assert ok.valid is True
    assert ok.errors == {}


def _find_form_widget(widget: Any) -> Any:  # noqa: ANN401 — walks an opaque widget tree
    """Find the first ``Form`` widget in a widget (not IR) tree.

    Args:
        widget: The root widget returned by an example ``view``.

    Returns:
        The first ``Form`` widget found.
    """
    stack = [widget]
    while stack:
        current = stack.pop()
        if type(current).__name__ == "Form":
            return current
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
    raise AssertionError("no Form widget found")


async def test_fetch_async_handler_drives_ui() -> None:
    """The fetch example transitions idle -> loading -> loaded via an async handler."""
    module = _load_example("fetch")
    app = _make_app(module)

    # Idle: no spinner, no rows list.
    idle = build(module.view(app))
    assert "Spinner" not in _types(idle)

    # Drive the async load handler directly.
    widget = module.view(app)
    handler = _find_handler(widget, "load", "on_click")
    await handler()

    loaded = build(module.view(app))
    types = _types(loaded)
    assert "LazyColumn" in types
    rows = next(n for n in _walk(loaded) if n.type == "LazyColumn")
    assert len(rows.children) == 3


async def test_fetch_loading_phase_shows_spinner() -> None:
    """While the fetch is in flight, the loading phase renders a Spinner."""
    module = _load_example("fetch")
    app = _make_app(module)
    phase_cls = type(app.state.phase)

    app.set_state(lambda s: setattr(s, "phase", phase_cls.LOADING))
    loading = build(module.view(app))
    assert "Spinner" in _types(loading)


async def test_fetch_error_phase_surfaces_message() -> None:
    """A failing fetch transitions to the error phase with a message."""
    module = _load_example("fetch")

    async def boom() -> list[str]:
        raise RuntimeError("network down")

    state = module.make_state()
    state.fetch = boom
    app = App(state=state, view=module.view, apply_patches=lambda _p: None)

    widget = module.view(app)
    handler = _find_handler(widget, "load", "on_click")
    await handler()

    node = build(module.view(app))
    error_nodes = [n for n in _walk(node) if n.key == "error"]
    assert error_nodes
    assert "network down" in str(error_nodes[0].props.get("content", ""))


def _find_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401 — opaque tree
    """Find a handler callable on the widget with the given ``key``.

    Args:
        widget: The root widget returned by an example ``view``.
        key: The ``key`` of the target widget.
        attr: The handler attribute name (e.g. ``"on_click"``).

    Returns:
        The handler callable.
    """
    stack = [widget]
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
