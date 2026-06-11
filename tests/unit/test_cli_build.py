"""Tests for ``tempestweb build`` artifact production (cli.commands.build)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tempestweb.cli import (
    SERVER_ARTIFACT_FILES,
    WASM_ARTIFACT_FILES,
    BuildError,
    BuildResult,
    build_artifact,
    scaffold_project,
)
from tempestweb.cli.commands.build import WASM_PACKAGE_ARCHIVE


def _project(tmp_path: Path) -> Path:
    return scaffold_project("buildme", parent=tmp_path).root


def test_build_wasm_layout(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    assert isinstance(result, BuildResult)
    assert result.mode == "wasm"
    assert result.out_dir == (root / "dist" / "wasm").resolve()
    for rel in WASM_ARTIFACT_FILES:
        assert (result.out_dir / rel).is_file(), rel
    assert set(result.files) == set(WASM_ARTIFACT_FILES)


def test_build_server_layout(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = build_artifact(root, mode="server")
    assert result.mode == "server"
    assert result.out_dir == (root / "dist" / "server").resolve()
    for rel in SERVER_ARTIFACT_FILES:
        assert (result.out_dir / rel).is_file(), rel
    assert set(result.files) == set(SERVER_ARTIFACT_FILES)


def test_wasm_index_html_titles_project(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert "<title>buildme</title>" in html
    assert 'src="./bootstrap.js"' in html


def test_wasm_bootstrap_is_live(tmp_path: Path) -> None:
    """The wasm bootstrap loads Pyodide and wires the WASM transport (not a stub)."""
    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    assert "loadPyodide" in bootstrap
    assert "createWasmTransport" in bootstrap
    assert "loadPackage" in bootstrap
    # The old placeholder must be gone.
    assert "provided by Track T3" not in bootstrap


def test_wasm_package_archive_carries_runtime(tmp_path: Path) -> None:
    """The bundled zip carries the tempestweb runtime + the tempest_core engine."""
    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        names = set(archive.namelist())
    assert "tempestweb/__init__.py" in names
    assert "tempestweb/runtime/wasm_main.py" in names
    assert "tempestweb/transports/wasm.py" in names
    # The renderer-agnostic core now ships as the separate tempest_core package.
    assert "tempest_core/__init__.py" in names
    assert "tempest_core/core/reconciler.py" in names
    # No bytecode leaks into the artifact.
    assert not any("__pycache__" in name for name in names)


def test_wasm_embeds_app_source(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    embedded = (result.out_dir / "app.py").read_text(encoding="utf-8")
    original = (root / "app.py").read_text(encoding="utf-8")
    assert embedded == original


def test_server_entrypoint_exposes_run(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = build_artifact(root, mode="server")
    server = (result.out_dir / "server.py").read_text(encoding="utf-8")
    assert "def run(" in server


def test_build_defaults_to_config_mode(tmp_path: Path) -> None:
    root = _project(tmp_path)  # config mode is "wasm"
    result = build_artifact(root)
    assert result.mode == "wasm"


def test_build_respects_out_dir(tmp_path: Path) -> None:
    root = _project(tmp_path)
    out = tmp_path / "custom-out"
    result = build_artifact(root, mode="wasm", out_dir=out)
    assert result.out_dir == out.resolve()
    assert (out / "index.html").is_file()


def test_build_cleans_stale_artifact(tmp_path: Path) -> None:
    root = _project(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    build_artifact(root, mode="wasm", out_dir=out, clean=True)
    assert not stale.exists()


def test_build_invalid_mode_raises(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(BuildError, match="invalid mode"):
        build_artifact(root, mode="native")


def test_build_unrunnable_project_raises(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "app.py").write_text("def broken( =", encoding="utf-8")
    with pytest.raises(BuildError, match="failed to build"):
        build_artifact(root, mode="wasm")
