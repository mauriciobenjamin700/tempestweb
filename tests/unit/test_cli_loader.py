"""Tests for ``tempestweb.cli.loader`` (project module loading + render)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tempest_core import Node

from tempestweb.cli import (
    LoadedApp,
    ProjectLoadError,
    load_app,
    render_initial_tree,
    scaffold_project,
)


def _scaffolded_app(tmp_path: Path) -> Path:
    result = scaffold_project("loader_demo", parent=tmp_path)
    return result.root / "app.py"


def test_load_app_returns_contract(tmp_path: Path) -> None:
    loaded = load_app(_scaffolded_app(tmp_path))
    assert isinstance(loaded, LoadedApp)
    assert callable(loaded.make_state)
    assert callable(loaded.view)


def test_render_initial_tree_builds_node(tmp_path: Path) -> None:
    loaded = load_app(_scaffolded_app(tmp_path))
    node = render_initial_tree(loaded)
    assert isinstance(node, Node)


def test_missing_entrypoint_raises(tmp_path: Path) -> None:
    with pytest.raises(ProjectLoadError, match="not found"):
        load_app(tmp_path / "does_not_exist.py")


def test_import_error_is_wrapped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("import nonexistent_module_xyz\n", encoding="utf-8")
    with pytest.raises(ProjectLoadError, match="failed to import"):
        load_app(bad)


def test_missing_make_state_raises(tmp_path: Path) -> None:
    mod = tmp_path / "no_state.py"
    mod.write_text("def view(app):\n    return None\n", encoding="utf-8")
    with pytest.raises(ProjectLoadError, match="make_state"):
        load_app(mod)


def test_missing_view_raises(tmp_path: Path) -> None:
    mod = tmp_path / "no_view.py"
    mod.write_text("def make_state():\n    return 0\n", encoding="utf-8")
    with pytest.raises(ProjectLoadError, match="view"):
        load_app(mod)


def test_view_returning_non_widget_raises(tmp_path: Path) -> None:
    mod = tmp_path / "bad_view.py"
    mod.write_text(
        "def make_state():\n    return 0\n\ndef view(app):\n    return 42\n",
        encoding="utf-8",
    )
    loaded = load_app(mod)
    with pytest.raises(ProjectLoadError, match="failed to render"):
        render_initial_tree(loaded)


def test_two_apps_load_independently(tmp_path: Path) -> None:
    a = scaffold_project("app_a", parent=tmp_path).root / "app.py"
    b = scaffold_project("app_b", parent=tmp_path).root / "app.py"
    loaded_a = load_app(a)
    loaded_b = load_app(b)
    assert loaded_a.module is not loaded_b.module
    assert isinstance(render_initial_tree(loaded_a), Node)
    assert isinstance(render_initial_tree(loaded_b), Node)
