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
from tempestweb.cli.scaffold import UnknownTemplateError


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
    assert "from tempest_core import" in app_src


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


def test_scaffold_in_place_uses_dir_basename_as_name(tmp_path: Path) -> None:
    """`new .` scaffolds into `parent` itself, naming the project after it."""
    target = tmp_path / "todolist"
    target.mkdir()
    result = scaffold_project(".", parent=target)
    assert result.root == target.resolve()
    assert (target / "app.py").is_file()
    # The project name is the directory basename, not ".".
    assert 'name = "todolist"' in (target / "tempestweb.toml").read_text(
        encoding="utf-8"
    )


def test_scaffold_in_place_tolerates_unrelated_files(tmp_path: Path) -> None:
    """In-place scaffolding writes alongside pre-existing, non-conflicting files."""
    target = tmp_path / "proj"
    target.mkdir()
    (target / "notes.md").write_text("keep", encoding="utf-8")
    result = scaffold_project(".", parent=target)
    assert (result.root / "app.py").is_file()
    assert (target / "notes.md").read_text(encoding="utf-8") == "keep"


def test_scaffold_in_place_refuses_to_clobber_scaffold_files(tmp_path: Path) -> None:
    """In-place scaffolding refuses to overwrite an existing app.py without force."""
    target = tmp_path / "proj"
    target.mkdir()
    (target / "app.py").write_text("# mine", encoding="utf-8")
    with pytest.raises(ProjectExistsError, match="app.py"):
        scaffold_project(".", parent=target)
    # force overwrites.
    scaffold_project(".", parent=target, force=True)
    assert "make_state" in (target / "app.py").read_text(encoding="utf-8")


def test_create_project_verifies_runnable(tmp_path: Path) -> None:
    result = create_project("counter", parent=tmp_path)
    assert (result.root / "app.py").is_file()


def test_create_project_in_place(tmp_path: Path) -> None:
    """`create_project(".")` scaffolds in place and stays runnable."""
    target = tmp_path / "inplace"
    target.mkdir()
    result = create_project(".", parent=target)
    assert result.root == target.resolve()
    assert (target / "app.py").is_file()


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


def test_pwa_template_renders_transpile_and_manifest() -> None:
    contents = render_files("mypwa", template="pwa")
    assert set(contents) == set(PROJECT_FILES)
    toml = contents["tempestweb.toml"]
    assert 'mode = "transpile"' in toml
    assert "[pwa]" in toml
    assert 'name = "mypwa"' in toml
    assert "native.install.prompt()" in contents["app.py"]
    assert "Progressive Web App" in contents["README.md"]


def test_unknown_template_raises() -> None:
    with pytest.raises(UnknownTemplateError):
        render_files("demo", template="nope")


def test_pwa_scaffold_is_runnable(tmp_path: Path) -> None:
    # verify=True renders the scaffolded app.py through the real core.
    result = create_project("mypwa", parent=tmp_path, template="pwa")
    assert (result.root / "app.py").is_file()
    assert 'mode = "transpile"' in (result.root / "tempestweb.toml").read_text(
        encoding="utf-8"
    )
