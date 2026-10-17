"""The Mode A package archive: precompiled bytecode and the subpackage trim.

Two build-time decisions shape how much work the browser does before the first
paint. Pyodide runs with ``sys.dont_write_bytecode``, so a ``.py`` with no
``.pyc`` beside it is compiled from source on *every* page load; and the archive
used to carry every Mode A subpackage whether the app imported it or not.

The bytecode half is only safe while it is exact: a ``.pyc`` from another
CPython is at best rejected and at worst misread. So these tests pin the target
(Python and magic number of the pinned Pyodide), prove a matching interpreter's
output is shipped and verified, and prove every mismatch falls back to source
with a warning rather than shipping bytecode silently.

The trim half is only safe while it over-includes: a subpackage an app reaches
by an import the walk cannot see dies in the browser with ``No module named``.
So the walk counts imports anywhere in a file, relative imports, attribute
chains and dotted string literals, and ``[wasm] keep`` / ``trim = false`` exist
for what is left.
"""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

from tempestweb.cli import build_artifact, scaffold_project, wasm_payload
from tempestweb.cli.commands.build import (
    _WASM_PACKAGE_PARTS,
    WASM_PACKAGE_ARCHIVE,
    BuildError,
    _zip_package,
)
from tempestweb.cli.config import ConfigError, load_config
from tempestweb.cli.wasm_payload import (
    PYC_FLAGS_CHECKED_HASH,
    WasmBytecodeWarning,
    bytecode_interpreter,
    compile_bytecode,
    pyodide_cache_tag,
    referenced_parts,
    resolve_wasm_parts,
)
from tempestweb.core.constants import (
    WASM_PYODIDE_PYC_MAGIC,
    WASM_PYODIDE_PYTHON,
    WASM_PYODIDE_VERSION,
)

PACKAGE_PARENT: Path = Path(__file__).resolve().parents[2]

needs_matching_python = pytest.mark.skipif(
    bytecode_interpreter() is None,
    reason=f"no CPython {WASM_PYODIDE_PYTHON} with the Pyodide magic on this host",
)


@pytest.fixture(autouse=True)
def _fresh_interpreter_lookup() -> None:
    """Forget the cached interpreter lookup, so a monkeypatch takes effect."""
    bytecode_interpreter.cache_clear()


def _write_project(tmp_path: Path, name: str, wasm: str, app: str | None) -> Path:
    """Scaffold a project, give it a ``[wasm]`` table and optionally an app."""
    root = scaffold_project(name, parent=tmp_path).root
    (root / "tempestweb.toml").write_text(
        f'[project]\nname = "{name}"\nentrypoint = "app.py"\n\n[wasm]\n{wasm}\n',
        encoding="utf-8",
    )
    if app is not None:
        original = (root / "app.py").read_text(encoding="utf-8")
        (root / "app.py").write_text(original + "\n" + app + "\n", encoding="utf-8")
    return root


def test_the_target_is_pinned_to_the_pyodide_release() -> None:
    """Pyodide v314.0.0 runs CPython 3.14, whose final releases share one magic.

    Read from the runtime itself (``importlib.util.MAGIC_NUMBER`` inside Pyodide
    v314.0.0 is ``2b0e0d0a``). Bumping the Pyodide pin without these two is the
    drift this test exists to catch.
    """
    assert WASM_PYODIDE_VERSION == "v314.0.0"
    assert WASM_PYODIDE_PYTHON == "3.14"
    assert WASM_PYODIDE_PYC_MAGIC.hex() == "2b0e0d0a"
    assert pyodide_cache_tag() == "cpython-314"


def test_config_defaults_ship_bytecode_and_trim(tmp_path: Path) -> None:
    root = scaffold_project("plain", parent=tmp_path).root
    cfg = load_config(root)
    assert cfg.wasm.bytecode == "alongside"
    assert cfg.wasm.trim is True
    assert cfg.wasm.keep == []


def test_config_parses_the_payload_switches(tmp_path: Path) -> None:
    root = _write_project(
        tmp_path,
        "sw",
        'bytecode = "sourceless"\ntrim = false\nkeep = ["tabular"]',
        None,
    )
    cfg = load_config(root)
    assert cfg.wasm.bytecode == "sourceless"
    assert cfg.wasm.trim is False
    assert cfg.wasm.keep == ["tabular"]


@pytest.mark.parametrize(
    ("line", "match"),
    [
        ('bytecode = "always"', "wasm.bytecode"),
        ("bytecode = true", "wasm.bytecode"),
        ('trim = "false"', "wasm.trim"),
        ('keep = "tabular"', "wasm.keep"),
    ],
)
def test_config_rejects_bad_payload_switches(
    tmp_path: Path, line: str, match: str
) -> None:
    root = _write_project(tmp_path, "bad", line, None)
    with pytest.raises(ConfigError, match=match):
        load_config(root)


def _stage(tmp_path: Path) -> Path:
    """A tiny package tree to compile."""
    stage = tmp_path / "stage"
    (stage / "pkg").mkdir(parents=True)
    (stage / "pkg" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (stage / "pkg" / "mod.py").write_text("OTHER = 2\n", encoding="utf-8")
    (stage / "app.py").write_text("import pkg\n", encoding="utf-8")
    return stage


@needs_matching_python
def test_alongside_bytecode_is_checked_hash_with_the_pyodide_magic(
    tmp_path: Path,
) -> None:
    """Every ``.py`` gains a ``__pycache__`` entry Pyodide will load and verify."""
    stage = _stage(tmp_path)
    assert compile_bytecode(stage) is True
    tag = pyodide_cache_tag()
    for source in ("pkg/__init__.py", "pkg/mod.py", "app.py"):
        path = stage / source
        assert path.is_file()
        pyc = path.parent / "__pycache__" / f"{path.stem}.{tag}.pyc"
        header = pyc.read_bytes()[:16]
        assert header[:4] == WASM_PYODIDE_PYC_MAGIC
        assert int.from_bytes(header[4:8], "little") == PYC_FLAGS_CHECKED_HASH
        assert header[8:16] == importlib.util.source_hash(path.read_bytes())


@needs_matching_python
def test_sourceless_bytecode_replaces_sources_but_keeps_app(tmp_path: Path) -> None:
    """Sourceless moves each ``.pyc`` into place; ``app.py`` keeps its pair."""
    stage = _stage(tmp_path)
    app = stage / "app.py"
    assert compile_bytecode(stage, sourceless=True, keep_source=(app,)) is True
    assert not (stage / "pkg" / "__init__.py").exists()
    assert (stage / "pkg" / "__init__.pyc").read_bytes()[:4] == WASM_PYODIDE_PYC_MAGIC
    assert (stage / "pkg" / "mod.pyc").is_file()
    assert not (stage / "pkg" / "__pycache__").exists()
    assert app.is_file()
    assert (stage / "__pycache__" / f"app.{pyodide_cache_tag()}.pyc").is_file()


def test_no_matching_interpreter_ships_source_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A host without the Pyodide Python degrades to source, loudly."""
    monkeypatch.setattr(wasm_payload, "WASM_PYODIDE_PYC_MAGIC", b"\x00\x00\r\n")
    monkeypatch.setattr(
        wasm_payload, "_candidate_interpreters", lambda: [sys.executable]
    )
    stage = _stage(tmp_path)
    with pytest.warns(WasmBytecodeWarning, match="ships source only"):
        assert compile_bytecode(stage) is False
    assert not list(stage.rglob("*.pyc"))
    assert (stage / "pkg" / "mod.py").is_file()


def test_bytecode_that_fails_verification_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interpreter that writes the wrong magic never reaches the archive.

    The lookup is forced to accept the running interpreter while the expected
    magic says otherwise — the shape of a wrong pin — and every ``.pyc`` it wrote
    has to be gone afterwards.
    """
    monkeypatch.setattr(wasm_payload, "WASM_PYODIDE_PYC_MAGIC", b"\x00\x00\r\n")
    monkeypatch.setattr(wasm_payload, "bytecode_interpreter", lambda: sys.executable)
    monkeypatch.setattr(
        wasm_payload, "pyodide_cache_tag", lambda: sys.implementation.cache_tag
    )
    stage = _stage(tmp_path)
    with pytest.warns(WasmBytecodeWarning, match="discarded"):
        assert compile_bytecode(stage) is False
    assert not list(stage.rglob("__pycache__"))
    assert not list(stage.rglob("*.pyc"))


def test_an_unfound_interpreter_is_not_trusted_by_version_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A candidate whose magic differs (a 3.14 alpha, say) is skipped."""
    monkeypatch.setattr(wasm_payload, "WASM_PYODIDE_PYC_MAGIC", b"\x00\x00\r\n")
    monkeypatch.setattr(
        wasm_payload, "_candidate_interpreters", lambda: [sys.executable]
    )
    assert wasm_payload.bytecode_interpreter() is None


@pytest.mark.parametrize(
    ("source", "package", "expected"),
    [
        ("import tempestweb.tabular", None, {"tabular"}),
        ("from tempestweb.query.cache import X", None, {"query"}),
        ("from tempestweb import vision, export", None, {"vision", "export"}),
        ("def f():\n    from tempestweb.access import A\n", None, {"access"}),
        ("from ..tabular import grid", "tempestweb.presets", {"tabular"}),
        ("from . import sibling", "tempestweb.presets", {"presets"}),
        ('M = "tempestweb.transports.sse"', None, {"transports"}),
        ("import tempestweb\nx = tempestweb.html", None, {"html"}),
        ('"""See tempestweb.tabular for grids."""\nX = 1', None, set()),
        ("def f(:\n  'tempestweb.query'", None, {"query"}),
        ("import tempest_core\nfrom pydantic import BaseModel", None, set()),
    ],
)
def test_referenced_parts_sees_every_static_reference(
    source: str, package: str | None, expected: set[str]
) -> None:
    assert referenced_parts(source, package=package) == expected


def test_trim_walk_reaches_what_the_app_imports_and_the_runtime_needs() -> None:
    plain = resolve_wasm_parts(
        _WASM_PACKAGE_PARTS,
        tempestweb_root=PACKAGE_PARENT,
        app_source="from tempest_core import Text\n",
        seeds=("runtime",),
    )
    assert {"__init__.py", "core", "runtime", "transports", "native"} <= set(plain)
    assert "tabular" not in plain
    assert "vision" not in plain
    with_grid = resolve_wasm_parts(
        _WASM_PACKAGE_PARTS,
        tempestweb_root=PACKAGE_PARENT,
        app_source="from tempestweb.tabular import DataGrid\n",
        seeds=("runtime",),
    )
    assert "tabular" in with_grid
    kept = resolve_wasm_parts(
        _WASM_PACKAGE_PARTS,
        tempestweb_root=PACKAGE_PARENT,
        app_source="X = 1\n",
        seeds=("runtime",),
        keep=("vision",),
    )
    assert "vision" in kept


def test_trim_walk_follows_project_modules(tmp_path: Path) -> None:
    (tmp_path / "helpers").mkdir()
    (tmp_path / "helpers" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "helpers" / "grid.py").write_text(
        "from tempestweb.query import Q\n", encoding="utf-8"
    )
    parts = resolve_wasm_parts(
        _WASM_PACKAGE_PARTS,
        tempestweb_root=PACKAGE_PARENT,
        app_source="import helpers.grid\n",
        module_files=[
            (tmp_path / "helpers" / "__init__.py", tmp_path),
            (tmp_path / "helpers" / "grid.py", tmp_path),
        ],
    )
    assert "query" in parts


def test_keep_rejects_an_unknown_subpackage() -> None:
    with pytest.raises(ValueError, match="tabularr"):
        resolve_wasm_parts(
            _WASM_PACKAGE_PARTS,
            tempestweb_root=PACKAGE_PARENT,
            app_source="",
            keep=("tabularr",),
        )


def test_zip_package_defaults_keep_the_historical_archive(tmp_path: Path) -> None:
    """Called bare, the archive is every Mode A part, as source, as before."""
    dest = tmp_path / "pkg.zip"
    parts = _zip_package(dest)
    assert parts == _WASM_PACKAGE_PARTS
    with zipfile.ZipFile(dest) as archive:
        names = archive.namelist()
    assert "tempestweb/tabular/__init__.py" in names
    assert not any(name.endswith(".pyc") for name in names)


def _archive_names(root: Path) -> set[str]:
    """Build ``root`` for wasm and list its package archive."""
    result = build_artifact(root, mode="wasm")
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        return set(archive.namelist())


def test_build_trims_unreached_subpackages_by_default(tmp_path: Path) -> None:
    root = _write_project(tmp_path, "trimmed", 'bytecode = "off"', None)
    names = _archive_names(root)
    assert "tempestweb/runtime/wasm_main.py" in names
    assert not any(name.startswith("tempestweb/tabular/") for name in names)
    assert not any(name.startswith("tempestweb/vision/") for name in names)


def test_build_ships_a_subpackage_the_app_imports(tmp_path: Path) -> None:
    root = _write_project(
        tmp_path, "grid", 'bytecode = "off"', "import tempestweb.tabular  # noqa: F401"
    )
    assert "tempestweb/tabular/__init__.py" in _archive_names(root)


def test_build_without_trim_ships_every_mode_a_part(tmp_path: Path) -> None:
    root = _write_project(tmp_path, "full", 'bytecode = "off"\ntrim = false', None)
    names = _archive_names(root)
    for part in _WASM_PACKAGE_PARTS:
        prefix = f"tempestweb/{part}"
        assert any(name.startswith(prefix) for name in names), part


def test_build_keep_forces_a_subpackage_in(tmp_path: Path) -> None:
    root = _write_project(tmp_path, "kept", 'bytecode = "off"\nkeep = ["export"]', None)
    assert "tempestweb/export/__init__.py" in _archive_names(root)


def test_build_rejects_an_unknown_keep(tmp_path: Path) -> None:
    root = _write_project(tmp_path, "typo", 'keep = ["exprot"]', None)
    with pytest.raises(BuildError, match="exprot"):
        build_artifact(root, mode="wasm")


@needs_matching_python
def test_build_ships_bytecode_for_every_module_and_the_app(tmp_path: Path) -> None:
    root = _write_project(tmp_path, "fast", "", None)
    names = _archive_names(root)
    tag = pyodide_cache_tag()
    sources = {name for name in names if name.endswith(".py")}
    assert sources
    for source in sources:
        folder, _, file_name = source.rpartition("/")
        cached = f"{folder}/__pycache__/{file_name[:-3]}.{tag}.pyc".lstrip("/")
        assert cached in names, source
    assert f"__pycache__/app.{tag}.pyc" in names
    assert "app.py" not in names


@needs_matching_python
def test_build_sourceless_ships_no_package_source(tmp_path: Path) -> None:
    root = _write_project(tmp_path, "lean", 'bytecode = "sourceless"', None)
    names = _archive_names(root)
    assert not any(name.endswith(".py") for name in names)
    assert "tempestweb/runtime/wasm_main.pyc" in names
    assert f"__pycache__/app.{pyodide_cache_tag()}.pyc" in names


def test_dev_builds_skip_bytecode(tmp_path: Path) -> None:
    """The dev loop rebuilds on every save; it ships source and stays fast."""
    root = _write_project(tmp_path, "devloop", "", None)
    result = build_artifact(root, mode="wasm", dev=True)
    with zipfile.ZipFile(result.out_dir / WASM_PACKAGE_ARCHIVE) as archive:
        assert not any(name.endswith(".pyc") for name in archive.namelist())
