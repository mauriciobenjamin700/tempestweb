"""Example apps import, build into a valid Node tree, and exercise widgets.

Each example is a ``view(app) -> Widget`` module just like ``examples/counter``.
These tests load each one, construct an ``App`` around its ``make_state`` /
``view``, run ``build(view(app))`` to validate the tree, walk the resulting IR to
confirm the input / list / form widgets are present, and drive a state
transition (synchronous or async) so the handlers are exercised, not just the
initial mount.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from tempest_core import App, Node, build, diff
from tempest_core.widgets.events import TextChangeEvent, ToggleEvent

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


EXAMPLE_NAMES = [
    "counter",
    "todo",
    "form",
    "fetch",
    "async_demo",
    "overlay_demo",
    "anim_demo",
    "gesture_demo",
    "a11y_demo",
    "list_demo",
    "router_demo",
]


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
    """Driving the real ``add_item`` handler grows the list and clears the draft."""
    module = _load_example("todo")
    app = _make_app(module)

    # Type a draft through the Input's on_change handler, then add it.
    edit = _find_handler(module.view(app), "draft", "on_change")
    edit(TextChangeEvent(value="Ship the examples"))
    assert app.state.draft == "Ship the examples"

    before = build(module.view(app))

    # Invoke the actual add_item closure (key="add", on_click) — this exercises
    # the .strip() and the append + draft-clear effect, not a reimplementation.
    add = _find_handler(module.view(app), "add", "on_click")
    add()

    assert len(app.state.items) == 3
    assert app.state.items[-1].title == "Ship the examples"
    assert app.state.items[-1].done is False
    assert app.state.draft == ""  # the handler clears the draft

    after = build(module.view(app))
    lazy_after = next(n for n in _walk(after) if n.type == "LazyColumn")
    assert len(lazy_after.children) == 3

    patches = diff(before, after)
    assert patches  # the tree changed


def test_todo_add_item_strips_and_guards_blank() -> None:
    """The ``add_item`` handler strips whitespace and rejects a blank draft."""
    module = _load_example("todo")
    app = _make_app(module)
    seed_count = len(app.state.items)

    # A whitespace-only draft is guarded: no item is appended, draft untouched.
    edit = _find_handler(module.view(app), "draft", "on_change")
    edit(TextChangeEvent(value="   "))
    add = _find_handler(module.view(app), "add", "on_click")
    add()
    assert len(app.state.items) == seed_count

    # A padded draft is stripped before being stored.
    edit = _find_handler(module.view(app), "draft", "on_change")
    edit(TextChangeEvent(value="  Buy milk  "))
    add = _find_handler(module.view(app), "add", "on_click")
    add()
    assert len(app.state.items) == seed_count + 1
    assert app.state.items[-1].title == "Buy milk"
    assert app.state.draft == ""


def test_todo_toggle_handler_flips_done() -> None:
    """Each row's ``on_change`` closure flips the right item via its captured index."""
    module = _load_example("todo")
    app = _make_app(module)

    # The seed items start as [done=True, done=False].
    assert [item.done for item in app.state.items] == [True, False]

    # The LazyColumn's item_builder is the real build_row factory; calling it per
    # index materializes the row Checkbox whose on_change is the per-row closure
    # ``lambda _event, i=index: toggle(i)``. Driving it exercises the i=index
    # capture and the done = not done flip — not a reimplementation.
    lazy = _find_lazy_column(module.view(app))
    row_one = lazy.item_builder(1)
    assert row_one.on_change is not None
    row_one.on_change(ToggleEvent(checked=True))
    assert app.state.items[0].done is True  # untouched
    assert app.state.items[1].done is True  # flipped False -> True

    # Rebuild and toggle row 0: only item 0 flips, proving each closure captured
    # its own index rather than sharing the loop variable.
    lazy = _find_lazy_column(module.view(app))
    row_zero = lazy.item_builder(0)
    assert row_zero.on_change is not None
    row_zero.on_change(ToggleEvent(checked=False))
    assert app.state.items[0].done is False  # flipped True -> False
    assert app.state.items[1].done is True  # untouched


def _find_lazy_column(widget: Any) -> Any:  # noqa: ANN401 — opaque widget tree
    """Find the first ``LazyColumn`` widget in a widget (not IR) tree.

    Args:
        widget: The root widget returned by an example ``view``.

    Returns:
        The first ``LazyColumn`` widget found.
    """
    stack = [widget]
    while stack:
        current = stack.pop()
        if type(current).__name__ == "LazyColumn":
            return current
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
    raise AssertionError("no LazyColumn widget found")


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


def test_form_submit_handler_mirrors_errors_onto_state() -> None:
    """Driving the real submit closure wires validate() results onto state."""
    module = _load_example("form")
    app = _make_app(module)

    # Empty fields: invoking the actual submit handler (key="submit", on_click)
    # must run validate and mirror its errors onto state without marking submitted.
    submit = _find_handler(module.view(app), "submit", "on_click")
    submit()

    assert app.state.submitted is False
    assert "email" in app.state.errors
    assert "password" in app.state.errors

    # The mirrored errors flow back into the FormFields on the next build.
    node = build(module.view(app))
    field_nodes = [n for n in _walk(node) if n.type == "FormField"]
    field_errors = {n.props.get("name"): n.props.get("error", "") for n in field_nodes}
    assert field_errors["email"] == app.state.errors["email"]
    assert field_errors["password"] == app.state.errors["password"]


def test_form_submit_handler_marks_submitted_when_valid() -> None:
    """A valid payload drives submit to clear errors and mark submitted."""
    module = _load_example("form")
    app = _make_app(module)

    # Populate both fields (the submit closure reads app.state.email/password).
    app.set_state(lambda s: setattr(s, "email", "you@example.com"))
    app.set_state(lambda s: setattr(s, "password", "longenough"))

    submit = _find_handler(module.view(app), "submit", "on_click")
    submit()

    assert app.state.submitted is True
    assert app.state.errors == {}

    # The status Text reflects the submitted flag on the next build.
    node = build(module.view(app))
    status = next(n for n in _walk(node) if n.key == "status")
    assert status.props.get("content") == "Welcome!"


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


async def test_async_demo_handler_is_async_and_commits_after_await() -> None:
    """The async_demo ``load`` handler is async and commits state after awaiting."""
    module = _load_example("async_demo")
    app = _make_app(module)

    assert app.state.status == "idle"
    handler = _find_handler(module.view(app), "load", "on_click")
    assert asyncio.iscoroutinefunction(handler)

    await handler()
    assert app.state.status == "done"
    assert app.state.loads == 1


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
