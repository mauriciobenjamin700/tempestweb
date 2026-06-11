"""Tests for the file-storage example — Notes CRUD via ``native.storage``.

Drives the full async handler chain (save, list, open, delete) using an
in-memory :class:`FakeBridge` that backs its four storage operations with a plain
Python ``dict``, so no browser or IndexedDB is required.

Assertions cover both the backing dict state *and* the rebuilt widget tree so
that the test confirms the UI reacts correctly to each state transition, not just
that the bridge was called.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempestweb._core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_example(name: str) -> ModuleType:
    """Import an example ``app`` module by directory name.

    Args:
        name: The directory under ``examples/`` (e.g. ``"file-storage"``).

    Returns:
        The imported module exposing ``make_state`` and ``view``.
    """
    module_name = f"_example_{name.replace('-', '_')}"
    path = EXAMPLES_DIR / name / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: ModuleType) -> App[Any]:
    """Wrap a module's ``make_state``/``view`` in a no-op ``App``.

    Args:
        module: An example module exposing ``make_state`` and ``view``.

    Returns:
        An ``App`` whose ``apply_patches`` is a no-op (tests diff manually).
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a pre-order list.

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _find_key(root: Node, key: str) -> Node | None:
    """Find the first node whose ``key`` matches.

    Args:
        root: The root of the IR tree to search.
        key: The widget key to look for.

    Returns:
        The matching node, or ``None`` if not found.
    """
    return next((n for n in _walk(root) if n.key == key), None)


def _keys_set(root: Node) -> set[str]:
    """Collect all widget keys in the tree.

    Args:
        root: The root of the IR tree.

    Returns:
        The set of all non-empty ``key`` values found.
    """
    return {n.key for n in _walk(root) if n.key}


# ---------------------------------------------------------------------------
# Fake bridge (in-memory storage)
# ---------------------------------------------------------------------------


class FakeBridge:
    """In-memory storage bridge for testing native.storage calls.

    Backs ``storage.put`` / ``storage.get`` / ``storage.list`` /
    ``storage.remove`` with a plain Python ``dict``.  Any other capability
    returns ``ok: False`` so tests fail explicitly if something unexpected is
    invoked.

    Attributes:
        store: The backing dictionary (``{key: content}``).
        calls: Every envelope dispatched through the bridge (audit log).
    """

    def __init__(self) -> None:
        """Initialise with an empty store and empty call log."""
        self.store: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a native call envelope to the in-memory store.

        Args:
            envelope: The ``native_call`` envelope with ``capability`` and
                ``args``.

        Returns:
            A result dict with ``ok: True`` and ``value`` on success, or
            ``ok: False`` and an ``error`` code for an unknown key / unknown
            capability.
        """
        self.calls.append(envelope)
        cap: str = envelope.get("capability", "")
        args: dict[str, Any] = envelope.get("args", {})

        if cap == "storage.put":
            self.store[args["name"]] = args["content"]
            return {"ok": True, "value": {}}

        if cap == "storage.get":
            name = args["name"]
            if name not in self.store:
                return {
                    "ok": False,
                    "error": "not_found",
                    "message": f"{name!r} not found",
                }
            return {"ok": True, "value": {"content": self.store[name]}}

        if cap == "storage.list":
            return {"ok": True, "value": {"keys": list(self.store.keys())}}

        if cap == "storage.remove":
            name = args["name"]
            if name not in self.store:
                return {
                    "ok": False,
                    "error": "not_found",
                    "message": f"{name!r} not found",
                }
            del self.store[name]
            return {"ok": True, "value": {}}

        return {"ok": False, "error": "unavailable", "message": f"unknown cap {cap!r}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    """Install a fresh FakeBridge before each test; remove it after.

    Yields:
        The ``FakeBridge`` installed for the duration of the test.
    """
    bridge = FakeBridge()
    install_bridge(bridge)
    yield bridge
    uninstall_bridge()


@pytest.fixture()
def module() -> ModuleType:
    """Load the file-storage example module.

    Returns:
        The imported ``examples/file-storage/app.py`` module.
    """
    return _load_example("file-storage")


@pytest.fixture()
def app(module: ModuleType) -> App[Any]:
    """Create a fresh App from the file-storage module.

    Args:
        module: The loaded example module.

    Returns:
        A fresh ``App`` instance.
    """
    return _make_app(module)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_build_has_no_bridge_required(module: ModuleType) -> None:
    """``build(view(app))`` succeeds with no bridge — determinism rule.

    The real storage callables are the defaults but are *never called* during
    the initial mount, so no ``BrowserUnavailableError`` is raised.
    """
    # Temporarily uninstall to verify the initial mount is truly bridge-free.
    uninstall_bridge()
    try:
        app: App[Any] = _make_app(module)
        node = build(module.view(app))
        assert isinstance(node, Node)
        assert node.type
        assert node.children
    finally:
        # Restore the autouse FakeBridge for subsequent tests in this module.
        install_bridge(FakeBridge())


def test_initial_render_shows_empty_list_hint(
    app: App[Any], module: ModuleType
) -> None:
    """The initial render includes the composer inputs and the empty-hint text."""
    node = build(module.view(app))
    keys = _keys_set(node)

    # Composer inputs must be present.
    assert "title-input" in keys
    assert "body-input" in keys
    assert "save-btn" in keys
    assert "reload-btn" in keys

    # No notes yet → empty-hint is shown.
    assert "empty-hint" in keys

    # No viewer section yet (no note is open).
    assert "viewer-title" not in keys


async def test_save_note_persists_to_store(
    app: App[Any], module: ModuleType, _clean_bridge: FakeBridge
) -> None:
    """The save handler calls storage.put and clears the draft fields.

    State transitions verified:
    * ``title_draft`` and ``body_draft`` are cleared after a successful save.
    * The FakeBridge backing dict contains the saved entry.
    """
    # Inject a draft via the state directly (simulating on_change events).
    app.set_state(lambda s: setattr(s, "title_draft", "My First Note"))
    app.set_state(lambda s: setattr(s, "body_draft", "Hello, storage!"))

    # Extract the save handler from the rendered tree.
    node = build(module.view(app))
    save_node = _find_key(node, "save-btn")
    assert save_node is not None
    save_handler = save_node.props.get("on_click")
    assert callable(save_handler)

    # Drive the async handler to completion.
    await save_handler()

    # Bridge backing dict must have the entry.
    assert _clean_bridge.store == {"My First Note": "Hello, storage!"}

    # App state draft fields must be cleared.
    assert app.state.title_draft == ""
    assert app.state.body_draft == ""
    assert app.state.saving is False
    assert app.state.error == ""


async def test_reload_list_populates_keys(
    app: App[Any], module: ModuleType, _clean_bridge: FakeBridge
) -> None:
    """The refresh handler fetches keys and renders one row per note.

    State transitions verified:
    * ``app.state.keys`` is populated from the bridge.
    * The rebuilt tree has Open/Delete buttons for each key.
    """
    # Seed the in-memory store directly (no round-trip through save_note).
    _clean_bridge.store["alpha"] = "Alpha body"
    _clean_bridge.store["beta"] = "Beta body"

    # Extract and drive the reload handler.
    node = build(module.view(app))
    reload_node = _find_key(node, "reload-btn")
    assert reload_node is not None
    reload_handler = reload_node.props.get("on_click")
    assert callable(reload_handler)

    await reload_handler()

    # State must reflect the two keys.
    assert set(app.state.keys) == {"alpha", "beta"}
    assert app.state.loading is False

    # Rebuilt tree must have Open/Delete buttons for each note.
    node2 = build(module.view(app))
    keys2 = _keys_set(node2)
    assert "open-alpha" in keys2
    assert "delete-alpha" in keys2
    assert "open-beta" in keys2
    assert "delete-beta" in keys2

    # The empty-hint must be gone now that keys are present.
    assert "empty-hint" not in keys2


async def test_open_note_populates_viewer(
    app: App[Any], module: ModuleType, _clean_bridge: FakeBridge
) -> None:
    """The open handler loads the note content and reveals the viewer panel.

    State transitions verified:
    * ``open_key`` is set to the requested key.
    * ``open_content`` is set to the stored content.
    * The rebuilt tree contains viewer widgets.
    """
    _clean_bridge.store["my-note"] = "Note body text"
    app.set_state(lambda s: setattr(s, "keys", ["my-note"]))

    # Render so the open handler is wired.
    node = build(module.view(app))
    open_node = _find_key(node, "open-my-note")
    assert open_node is not None
    open_handler = open_node.props.get("on_click")
    assert callable(open_handler)

    await open_handler()

    assert app.state.open_key == "my-note"
    assert app.state.open_content == "Note body text"
    assert app.state.loading is False

    # Viewer widgets must appear in the rebuilt tree.
    node2 = build(module.view(app))
    keys2 = _keys_set(node2)
    assert "viewer-title" in keys2
    assert "viewer-body" in keys2
    assert "close-btn" in keys2


async def test_delete_note_removes_from_store_and_list(
    app: App[Any], module: ModuleType, _clean_bridge: FakeBridge
) -> None:
    """The delete handler removes from the bridge dict and the state key list.

    State transitions verified:
    * The backing store no longer contains the deleted key.
    * ``app.state.keys`` no longer includes the deleted key.
    * If the deleted note was open, ``open_key`` / ``open_content`` are cleared.
    """
    _clean_bridge.store["note-a"] = "Content A"
    _clean_bridge.store["note-b"] = "Content B"
    app.set_state(lambda s: setattr(s, "keys", ["note-a", "note-b"]))
    app.set_state(lambda s: setattr(s, "open_key", "note-a"))
    app.set_state(lambda s: setattr(s, "open_content", "Content A"))

    node = build(module.view(app))
    delete_node = _find_key(node, "delete-note-a")
    assert delete_node is not None
    delete_handler = delete_node.props.get("on_click")
    assert callable(delete_handler)

    await delete_handler()

    # Bridge store must no longer have note-a.
    assert "note-a" not in _clean_bridge.store
    assert "note-b" in _clean_bridge.store

    # State list must only have note-b.
    assert app.state.keys == ["note-b"]

    # Viewer must be cleared because the deleted note was open.
    assert app.state.open_key == ""
    assert app.state.open_content == ""

    # Rebuilt tree: delete-note-a row gone; delete-note-b present.
    node2 = build(module.view(app))
    keys2 = _keys_set(node2)
    assert "delete-note-a" not in keys2
    assert "delete-note-b" in keys2


async def test_full_crud_cycle(
    app: App[Any], module: ModuleType, _clean_bridge: FakeBridge
) -> None:
    """Save → reload → open → delete performs a complete CRUD round-trip.

    This integration-style test chains all four handlers in sequence so any
    broken interaction between them surfaces as a single failing assertion.
    """
    # 1. Save a note.
    app.set_state(lambda s: setattr(s, "title_draft", "cycle-note"))
    app.set_state(lambda s: setattr(s, "body_draft", "cycle body"))

    save_node = _find_key(build(module.view(app)), "save-btn")
    assert save_node is not None
    await save_node.props["on_click"]()

    assert _clean_bridge.store == {"cycle-note": "cycle body"}
    assert app.state.title_draft == ""

    # 2. Reload the list.
    reload_node = _find_key(build(module.view(app)), "reload-btn")
    assert reload_node is not None
    await reload_node.props["on_click"]()
    assert "cycle-note" in app.state.keys

    # 3. Open the note.
    open_node = _find_key(build(module.view(app)), "open-cycle-note")
    assert open_node is not None
    await open_node.props["on_click"]()
    assert app.state.open_key == "cycle-note"
    assert app.state.open_content == "cycle body"

    # 4. Delete the note.
    delete_node = _find_key(build(module.view(app)), "delete-cycle-note")
    assert delete_node is not None
    await delete_node.props["on_click"]()
    assert "cycle-note" not in _clean_bridge.store
    assert app.state.keys == []
    assert app.state.open_key == ""
