"""Tests for ``tempestweb new`` scaffolding (cli.scaffold + cli.commands.new)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tempestweb.cli import (
    PROJECT_FILES,
    NewError,
    ProjectExistsError,
    ScaffoldResult,
    create_project,
    render_files,
    scaffold_project,
)


def test_render_files_covers_every_project_file() -> None:
    contents = render_files("demo")
    assert set(contents) == set(PROJECT_FILES)
    for body in contents.values():
        assert body  # no empty files


def test_render_files_embeds_project_name() -> None:
    contents = render_files("acme")
    assert 'name = "acme"' in contents["tempestweb.toml"]
    assert "# acme" in contents["README.md"]


def test_scaffold_project_writes_runnable_tree(tmp_path: Path) -> None:
    result = scaffold_project("myapp", parent=tmp_path)
    assert isinstance(result, ScaffoldResult)
    assert result.root == (tmp_path / "myapp").resolve()
    assert result.files == PROJECT_FILES
    for rel in PROJECT_FILES:
        assert (result.root / rel).is_file()


def test_scaffold_app_py_defines_contract(tmp_path: Path) -> None:
    result = scaffold_project("myapp", parent=tmp_path)
    app_src = (result.root / "app.py").read_text(encoding="utf-8")
    assert "def make_state(" in app_src
    assert "def view(" in app_src
    assert "from tempestweb._core import" in app_src


def test_scaffold_refuses_non_empty_dir(tmp_path: Path) -> None:
    target = tmp_path / "myapp"
    target.mkdir()
    (target / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ProjectExistsError):
        scaffold_project("myapp", parent=tmp_path)


def test_scaffold_force_overwrites_non_empty_dir(tmp_path: Path) -> None:
    target = tmp_path / "myapp"
    target.mkdir()
    (target / "existing.txt").write_text("keep", encoding="utf-8")
    result = scaffold_project("myapp", parent=tmp_path, force=True)
    assert (result.root / "app.py").is_file()
    # The pre-existing file is left untouched.
    assert (target / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_scaffold_into_empty_existing_dir_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "myapp"
    target.mkdir()
    result = scaffold_project("myapp", parent=tmp_path)
    assert (result.root / "app.py").is_file()


def test_create_project_verifies_runnable(tmp_path: Path) -> None:
    result = create_project("counter", parent=tmp_path)
    assert (result.root / "app.py").is_file()


def test_create_project_rejects_empty_name(tmp_path: Path) -> None:
    with pytest.raises(NewError):
        create_project("   ", parent=tmp_path)


def test_create_project_reports_unrunnable_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempestweb.cli.commands.new as new_mod

    original = new_mod.scaffold_project

    def _broken(name: str, **kwargs: object) -> ScaffoldResult:
        result = original(name, **kwargs)  # type: ignore[arg-type]
        (result.root / "app.py").write_text("def oops( = ", encoding="utf-8")
        return result

    monkeypatch.setattr(new_mod, "scaffold_project", _broken)
    with pytest.raises(NewError, match="not runnable"):
        create_project("broken", parent=tmp_path)
