"""Tests for ``tempestweb sync`` — auto-filling ``[wasm].modules``.

Fabricates installed distributions (pure-Python, native, framework) under a temp
``site`` directory on ``sys.path`` so ``importlib.metadata`` resolves them, then
checks that ``sync_modules`` adds the right import names to ``[wasm].modules``.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tempestweb.cli import load_config, scaffold_project, sync_modules
from tempestweb.cli.commands.sync import SyncError


def _make_dist(site: Path, dist_name: str, top: str, *, binary: bool = False) -> None:
    """Create a fake installed distribution discoverable by importlib.metadata.

    Args:
        site: The temp site-packages directory (must be on ``sys.path``).
        dist_name: The distribution (PyPI) name.
        top: The top-level import package name.
        binary: When ``True``, add a compiled extension so the dist is non-pure.
    """
    pkg = site / top
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(f'"""{top}."""\n', encoding="utf-8")
    record = [f"{top}/__init__.py,,"]
    if binary:
        (pkg / "_speedups.so").write_bytes(b"\x7fELF\x00fake")
        record.append(f"{top}/_speedups.so,,")

    info = site / f"{dist_name.replace('-', '_')}-1.0.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {dist_name}\nVersion: 1.0.0\n",
        encoding="utf-8",
    )
    (info / "top_level.txt").write_text(f"{top}\n", encoding="utf-8")
    record.append(f"{info.name}/METADATA,,")
    record.append(f"{info.name}/top_level.txt,,")
    (info / "RECORD").write_text("\n".join(record) + "\n", encoding="utf-8")


def _project(tmp_path: Path, deps: list[str], *, modules: str, packages: str) -> Path:
    """Scaffold a project with given dependencies and a [wasm] section."""
    root = scaffold_project("app", parent=tmp_path).root
    dep_list = ", ".join(f'"{d}"' for d in deps)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "app"\nversion = "0.1.0"\ndependencies = [{dep_list}]\n',
        encoding="utf-8",
    )
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "app"\nentrypoint = "app.py"\n'
        '[dev]\nmode = "wasm"\n'
        f"[wasm]\nmodules = {modules}\npackages = {packages}\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A temp site-packages directory placed on sys.path."""
    path = tmp_path / "site"
    path.mkdir()
    monkeypatch.syspath_prepend(str(path))
    importlib.invalidate_caches()
    return path


def test_sync_adds_pure_python_dep(site: Path, tmp_path: Path) -> None:
    _make_dist(site, "ort-vision-sdk", "ort_vision_sdk")
    root = _project(tmp_path, ["ort-vision-sdk"], modules='["app"]', packages="[]")
    result = sync_modules(root)
    assert result.added == ["ort_vision_sdk"]
    assert result.modules == ["app", "ort_vision_sdk"]
    assert result.written is True
    # Persisted and re-readable.
    assert "ort_vision_sdk" in load_config(root).wasm.modules


def test_sync_skips_native_dep(site: Path, tmp_path: Path) -> None:
    _make_dist(site, "numpy", "numpy", binary=True)
    root = _project(tmp_path, ["numpy"], modules='["app"]', packages="[]")
    result = sync_modules(root)
    assert result.added == []
    assert "numpy" not in result.modules


def test_sync_skips_packages_declared_in_wasm(site: Path, tmp_path: Path) -> None:
    # Pure-Python but explicitly a Pyodide package — must not be bundled as source.
    _make_dist(site, "pure-pyodide-lib", "pure_pyodide_lib")
    root = _project(
        tmp_path,
        ["pure-pyodide-lib"],
        modules='["app"]',
        packages='["pure_pyodide_lib"]',
    )
    result = sync_modules(root)
    assert result.added == []


def test_sync_skips_framework(site: Path, tmp_path: Path) -> None:
    _make_dist(site, "pydantic", "pydantic")
    root = _project(tmp_path, ["pydantic"], modules='["app"]', packages="[]")
    result = sync_modules(root)
    assert result.added == []


def test_sync_preserves_existing_and_is_idempotent(site: Path, tmp_path: Path) -> None:
    _make_dist(site, "ort-vision-sdk", "ort_vision_sdk")
    root = _project(tmp_path, ["ort-vision-sdk"], modules='["app"]', packages="[]")
    first = sync_modules(root)
    assert first.added == ["ort_vision_sdk"]
    # Second run sees no change.
    second = sync_modules(root)
    assert second.added == []
    assert second.changed is False
    assert second.written is False
    assert second.modules == ["app", "ort_vision_sdk"]


def test_sync_dry_run_does_not_write(site: Path, tmp_path: Path) -> None:
    _make_dist(site, "ort-vision-sdk", "ort_vision_sdk")
    root = _project(tmp_path, ["ort-vision-sdk"], modules='["app"]', packages="[]")
    result = sync_modules(root, dry_run=True)
    assert result.added == ["ort_vision_sdk"]
    assert result.written is False
    # File untouched.
    assert load_config(root).wasm.modules == ["app"]


def test_sync_ignores_uninstalled_dep(site: Path, tmp_path: Path) -> None:
    # Declared but not installed → silently skipped, no crash.
    root = _project(
        tmp_path, ["not-installed-anywhere"], modules='["app"]', packages="[]"
    )
    result = sync_modules(root)
    assert result.added == []


def test_sync_preserves_toml_comments(site: Path, tmp_path: Path) -> None:
    _make_dist(site, "ort-vision-sdk", "ort_vision_sdk")
    root = scaffold_project("app", parent=tmp_path).root
    (root / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "0.1.0"\n'
        'dependencies = ["ort-vision-sdk"]\n',
        encoding="utf-8",
    )
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "app"\nentrypoint = "app.py"\n\n'
        "[wasm]\n"
        "# keep me: numpy ships from Pyodide\n"
        'packages = ["numpy"]\n'
        'modules = ["app"]\n',
        encoding="utf-8",
    )
    sync_modules(root)
    text = (root / "tempestweb.toml").read_text(encoding="utf-8")
    assert "# keep me: numpy ships from Pyodide" in text
    assert "ort_vision_sdk" in text


def test_sync_errors_without_tempestweb_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\ndependencies = []\n',
        encoding="utf-8",
    )
    with pytest.raises(SyncError, match="no tempestweb.toml"):
        sync_modules(tmp_path)
