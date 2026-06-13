"""Tests for the ``[wasm]`` build extras (config parsing + build wiring).

Covers the project-declared Mode A extras a real app needs: extra Pyodide
packages, bundled Python modules, copied static assets, and injected scripts.
"""

from __future__ import annotations

import importlib
import zipfile
from pathlib import Path

import pytest

from tempestweb.cli import build_artifact, scaffold_project
from tempestweb.cli.commands.build import WASM_PACKAGE_ARCHIVE, BuildError
from tempestweb.cli.config import ConfigError, WasmConfig, load_config


def _project_with_wasm(tmp_path: Path) -> Path:
    """Scaffold a project and add a ``[wasm]`` section + a module + an asset."""
    root = scaffold_project("famacha", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        """\
[project]
name = "famacha"
entrypoint = "app.py"

[dev]
mode = "wasm"

[wasm]
packages = ["numpy", "pillow"]
modules = ["mypkg"]
assets = ["models/*.onnx"]
scripts = ["./vendor/ort.js", "https://cdn.example/ort.js"]
""",
        encoding="utf-8",
    )
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""mypkg."""\n', encoding="utf-8")
    (pkg / "tool.py").write_text("VALUE = 1\n", encoding="utf-8")
    models = root / "models"
    models.mkdir()
    (models / "detect.onnx").write_bytes(b"fake-onnx-bytes")
    (models / "classify.onnx").write_bytes(b"fake-onnx-bytes-2")
    return root


def test_config_parses_wasm_section(tmp_path: Path) -> None:
    root = _project_with_wasm(tmp_path)
    cfg = load_config(root)
    assert cfg.wasm.packages == ["numpy", "pillow"]
    assert cfg.wasm.modules == ["mypkg"]
    assert cfg.wasm.assets == ["models/*.onnx"]
    assert cfg.wasm.scripts == ["./vendor/ort.js", "https://cdn.example/ort.js"]


def test_config_defaults_to_empty_wasm(tmp_path: Path) -> None:
    root = scaffold_project("plain", parent=tmp_path).root
    cfg = load_config(root)
    assert cfg.wasm == WasmConfig()


def test_config_rejects_non_list_wasm_field(tmp_path: Path) -> None:
    root = scaffold_project("bad", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        '[wasm]\npackages = "numpy"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="wasm.packages"):
        load_config(root)


def test_build_bundles_modules_into_package_archive(tmp_path: Path) -> None:
    root = _project_with_wasm(tmp_path)
    result = build_artifact(root, mode="wasm")
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        names = set(archive.namelist())
    assert "mypkg/__init__.py" in names
    assert "mypkg/tool.py" in names


def test_build_copies_assets_preserving_path(tmp_path: Path) -> None:
    root = _project_with_wasm(tmp_path)
    result = build_artifact(root, mode="wasm")
    assert (result.out_dir / "models" / "detect.onnx").is_file()
    assert (result.out_dir / "models" / "classify.onnx").is_file()
    assert "models/detect.onnx" in result.files


def test_build_injects_scripts_and_packages(tmp_path: Path) -> None:
    root = _project_with_wasm(tmp_path)
    result = build_artifact(root, mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert '<script src="./vendor/ort.js"></script>' in html
    assert '<script src="https://cdn.example/ort.js"></script>' in html
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    assert "numpy" in bootstrap
    assert "pillow" in bootstrap
    assert "pydantic" in bootstrap


def test_build_precaches_assets_and_local_scripts(tmp_path: Path) -> None:
    root = _project_with_wasm(tmp_path)
    result = build_artifact(root, mode="wasm")
    sw = (result.out_dir / "sw.js").read_text(encoding="utf-8")
    assert "/models/detect.onnx" in sw
    assert "/vendor/ort.js" in sw
    # External (CDN) scripts are not precached.
    assert "https://cdn.example/ort.js" not in sw


def test_build_loads_app_importing_a_bundled_module(tmp_path: Path) -> None:
    """app.py can import a sibling package the project ships (project root on path)."""
    root = _project_with_wasm(tmp_path)
    # Rewrite app.py to depend on the bundled `mypkg` so the render check exercises
    # the sibling import (regression: build failed with "No module named mypkg").
    (root / "app.py").write_text(
        "from dataclasses import dataclass\n"
        "from tempest_core import App, Text, Widget\n"
        "from mypkg.tool import VALUE\n\n"
        "@dataclass\n"
        "class State:\n"
        "    value: int = VALUE\n\n"
        "def make_state() -> State:\n"
        "    return State()\n\n"
        "def view(app: App[State]) -> Widget:\n"
        '    return Text(content=f"v{app.state.value}")\n',
        encoding="utf-8",
    )
    result = build_artifact(root, mode="wasm")
    assert (result.out_dir / "app.py").is_file()


def test_build_errors_on_empty_asset_glob(tmp_path: Path) -> None:
    root = scaffold_project("noassets", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        '[wasm]\nassets = ["models/*.onnx"]\n', encoding="utf-8"
    )
    with pytest.raises(Exception, match="matched no files"):
        build_artifact(root, mode="wasm")


def _install_external_package(site: Path, name: str) -> None:
    """Create an importable package under ``site`` (not under the project root)."""
    pkg = site / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(f'"""{name}."""\n', encoding="utf-8")
    (pkg / "tool.py").write_text("VALUE = 42\n", encoding="utf-8")


def test_build_bundles_module_from_site_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A module declared in ``[wasm].modules`` but absent from the project root
    is pulled from the installed environment (importlib), so a ``.venv`` dependency
    need not be vendored into the repo."""
    site = tmp_path / "site-packages"
    _install_external_package(site, "extpkg")
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()

    root = scaffold_project("withdep", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "withdep"\nentrypoint = "app.py"\n'
        '[dev]\nmode = "wasm"\n'
        '[wasm]\nmodules = ["extpkg"]\n',
        encoding="utf-8",
    )
    # No `extpkg` directory beside app.py — resolution must come from sys.path.
    assert not (root / "extpkg").exists()

    result = build_artifact(root, mode="wasm")
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        names = set(archive.namelist())
    assert "extpkg/__init__.py" in names
    assert "extpkg/tool.py" in names


def test_build_prefers_vendored_copy_over_site_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vendored copy beside ``app.py`` wins over an installed package of the
    same name."""
    site = tmp_path / "site-packages"
    _install_external_package(site, "dual")
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()

    root = scaffold_project("vendored", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "vendored"\nentrypoint = "app.py"\n'
        '[dev]\nmode = "wasm"\n'
        '[wasm]\nmodules = ["dual"]\n',
        encoding="utf-8",
    )
    vendored = root / "dual"
    vendored.mkdir()
    (vendored / "__init__.py").write_text('"""vendored dual."""\n', encoding="utf-8")
    (vendored / "local_only.py").write_text("LOCAL = True\n", encoding="utf-8")

    result = build_artifact(root, mode="wasm")
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        names = set(archive.namelist())
    # The vendored copy is bundled (its unique file is present)…
    assert "dual/local_only.py" in names
    # …and the site-packages copy's unique file is not.
    assert "dual/tool.py" not in names


def test_build_errors_on_unresolvable_module(tmp_path: Path) -> None:
    """A module that is neither vendored nor importable fails the build."""
    root = scaffold_project("missingmod", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "missingmod"\nentrypoint = "app.py"\n'
        '[dev]\nmode = "wasm"\n'
        '[wasm]\nmodules = ["nope_not_a_real_module"]\n',
        encoding="utf-8",
    )
    with pytest.raises(BuildError, match="not found"):
        build_artifact(root, mode="wasm")


def test_build_ignores_stale_pycache_only_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory left holding only ``__pycache__`` (source deleted, bytecode
    lingering) must not shadow the installed package and bundle nothing — the
    installed copy is used instead."""
    site = tmp_path / "site-packages"
    _install_external_package(site, "stale")
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()

    root = scaffold_project("stalepkg", parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "stalepkg"\nentrypoint = "app.py"\n'
        '[dev]\nmode = "wasm"\n'
        '[wasm]\nmodules = ["stale"]\n',
        encoding="utf-8",
    )
    # Stale dir at the project root: only __pycache__, no real source files.
    cache = root / "stale" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "__init__.cpython-313.pyc").write_bytes(b"\x00stale-bytecode")

    result = build_artifact(root, mode="wasm")
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        names = set(archive.namelist())
    # Bundled from site-packages, not the empty vendored shell.
    assert "stale/__init__.py" in names
    assert "stale/tool.py" in names
    # The stale bytecode is never bundled.
    assert not any("__pycache__" in n for n in names if n.startswith("stale/"))
