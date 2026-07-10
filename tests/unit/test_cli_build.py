"""Tests for ``tempestweb build`` artifact production (cli.commands.build)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tempestweb.cli import (
    SERVER_ARTIFACT_FILES,
    TRANSPILE_ARTIFACT_FILES,
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


def test_build_transpile_layout(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = build_artifact(root, mode="transpile")
    assert result.mode == "transpile"
    assert result.out_dir == (root / "dist" / "transpile").resolve()
    for rel in TRANSPILE_ARTIFACT_FILES:
        assert (result.out_dir / rel).is_file(), rel
    assert set(result.files) == set(TRANSPILE_ARTIFACT_FILES)
    # No Python, no transport file, no Pyodide payload in a transpile artifact.
    assert not (result.out_dir / "app.py").exists()
    assert not (result.out_dir / WASM_PACKAGE_ARCHIVE).exists()


def test_transpile_emits_generated_native_module(tmp_path: Path) -> None:
    """The generated app module is native JS importing the runtime + widgets."""
    root = _project(tmp_path)
    result = build_artifact(root, mode="transpile")
    gen = (result.out_dir / "client" / "transpile" / "app.gen.js").read_text(
        encoding="utf-8"
    )
    assert "GENERATED from app.py" in gen
    assert 'from "./runtime.js"' in gen
    assert 'from "./widgets.js"' in gen
    assert "export function view(app)" in gen
    assert "app.setState(" in gen  # set_state -> setState


def test_transpile_index_mounts_via_native_runtime(tmp_path: Path) -> None:
    """The shell mounts through mountApp with no transport and no Python."""
    root = _project(tmp_path)
    result = build_artifact(root, mode="transpile")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert "<title>buildme</title>" in html
    assert "mountApp" in html
    assert "./client/transpile/runtime.js" in html
    assert "./client/transpile/app.gen.js" in html
    assert "Pyodide" not in html and "transport" not in html


def test_transpile_build_rejects_out_of_subset_app(tmp_path: Path) -> None:
    """A valid-but-out-of-subset app fails the build with a clear transpile error.

    The app renders fine as Python (so the build's load/render gate passes), but
    the ``*`` operator is outside the spike subset — the transpile step turns the
    ``TranspileError`` into a ``BuildError``.
    """
    root = _project(tmp_path)
    # A set literal is valid Python (the view renders fine) but outside the subset.
    (root / "app.py").write_text(
        "from dataclasses import dataclass\n"
        "from tempest_core import App, Column, Text, Widget\n\n"
        "@dataclass\n"
        "class State:\n"
        "    value: int = 0\n\n"
        "def make_state() -> State:\n"
        "    return State()\n\n"
        "def view(app: App[State]) -> Widget:\n"
        '    return Column(children=[Text(content=c, key=c) for c in {"a"}])\n',
        encoding="utf-8",
    )
    with pytest.raises(BuildError, match="transpile failed"):
        build_artifact(root, mode="transpile")


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


def test_wasm_emits_installable_manifest(tmp_path: Path) -> None:
    """The wasm artifact ships an installable manifest linked from index.html."""
    import json

    from tempestweb.pwa import validate_installable

    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    manifest = json.loads(
        (result.out_dir / "manifest.webmanifest").read_text(encoding="utf-8")
    )
    assert validate_installable(manifest) == []
    assert manifest["display"] == "standalone"
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "register.js" in html  # the page registers the service worker


def test_wasm_service_worker_placeholders_are_filled(tmp_path: Path) -> None:
    """The emitted sw.js has its precache list and cache version injected."""
    import json

    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    sw = (result.out_dir / "sw.js").read_text(encoding="utf-8")
    # The quoted code placeholders must be gone (a comment may still name them).
    assert '"__PRECACHE_MANIFEST__"' not in sw
    assert '"__CACHE_VERSION__"' not in sw
    # A content-hashed cache version was injected.
    assert "tw-" in sw
    # The precache list parses and carries the app-shell entrypoints.
    start = sw.index('"[')
    end = sw.index(']"', start) + 2
    precache = json.loads(json.loads(sw[start:end]))
    assert "/index.html" in precache
    assert "/manifest.webmanifest" in precache


def test_wasm_default_build_loads_pyodide_from_cdn(tmp_path: Path) -> None:
    """A non-offline build points the bootstrap at the jsdelivr CDN."""
    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm")
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    assert "https://cdn.jsdelivr.net/pyodide/" in bootstrap
    assert "./pyodide/" not in bootstrap
    assert not (result.out_dir / "pyodide").exists()
    assert not any(f.startswith("pyodide/") for f in result.files)


def test_wasm_offline_build_vendors_and_precaches_pyodide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An offline build vendors Pyodide locally, points the bootstrap at it, and
    precaches it — without hitting the network (the vendor step is stubbed)."""
    import json
    import sys

    vendored = ["pyodide-lock.json", "pyodide.mjs", "pyodide.asm.wasm"]

    def fake_vendor(
        out_dir: Path,
        *,
        version: str,
        packages: tuple[str, ...],
        fetch: object = None,
    ) -> list[str]:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        for name in vendored:
            (Path(out_dir) / name).write_bytes(b"stub")
        return vendored

    build_module = sys.modules["tempestweb.cli.commands.build"]
    monkeypatch.setattr(build_module, "vendor_pyodide", fake_vendor)

    root = _project(tmp_path)
    result = build_artifact(root, mode="wasm", offline=True)

    # Bootstrap loads from the local vendored copy, not the CDN.
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    assert 'const PYODIDE_BASE = "./pyodide/";' in bootstrap
    assert "cdn.jsdelivr.net" not in bootstrap

    # The vendored files exist and are listed in the build result.
    for name in vendored:
        assert (result.out_dir / "pyodide" / name).is_file()
        assert f"pyodide/{name}" in result.files

    # The service worker precaches the vendored runtime so it boots offline.
    sw = (result.out_dir / "sw.js").read_text(encoding="utf-8")
    start = sw.index('"[')
    end = sw.index(']"', start) + 2
    precache = json.loads(json.loads(sw[start:end]))
    assert "/pyodide/pyodide.asm.wasm" in precache
    assert "/pyodide/pyodide-lock.json" in precache


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
