"""The Mode A bundle must be import-closed.

``tempestweb build --mode wasm`` zips a *subset* of the package into the
artifact: the browser needs ``runtime``/``transports``/``native``/``components``
and not the server, CLI or devserver stacks. Nothing checked that the subset is
closed under its own module-level imports, so adding one import to a bundled
module could — and did — break the artifact while every test stayed green: the
test process has the whole package installed, and the failure only appears once
Pyodide runs the bundle in a tab (``No module named 'tempestweb.core'``).

This walks the bundled files and asserts every module-level ``tempestweb.X``
import names a part that is bundled too. Imports inside a function are ignored:
those are the lazy, optional paths (a server-only helper) that never run in the
browser.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tempestweb.cli.commands.build import _WASM_PACKAGE_PARTS

PACKAGE_ROOT: Path = Path(__file__).resolve().parents[2] / "tempestweb"


def _bundled_files() -> list[Path]:
    """Every ``.py`` file the wasm artifact's package zip contains."""
    files: list[Path] = []
    for part in _WASM_PACKAGE_PARTS:
        target = PACKAGE_ROOT / part
        if target.is_dir():
            files.extend(sorted(target.rglob("*.py")))
        elif target.is_file():
            files.append(target)
    return files


def _bundled_parts() -> set[str]:
    """The top-level ``tempestweb`` names available inside the bundle."""
    return {part.removesuffix(".py") for part in _WASM_PACKAGE_PARTS}


def _module_level_imports(tree: ast.Module) -> list[str]:
    """Collect the ``tempestweb.*`` names imported when the module is executed.

    Only statements in the module body count: an import nested in a function runs
    on call, which in the browser means "only if that path is used", and the
    bundle deliberately leaves those out.
    """
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("tempestweb"):
                names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(
                alias.name
                for alias in node.names
                if alias.name.startswith("tempestweb")
            )
    return names


def test_the_wasm_bundle_is_closed_under_its_imports() -> None:
    """No bundled module may import a part of tempestweb left out of the bundle."""
    available = _bundled_parts()
    missing: list[str] = []
    for path in _bundled_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _module_level_imports(tree):
            parts = module.split(".")
            if len(parts) < 2:
                continue
            if parts[1] not in available:
                missing.append(f"{path.relative_to(PACKAGE_ROOT)} imports {module}")
    assert missing == [], (
        "these modules are bundled into the Mode A artifact but import a part "
        f"that is not: {missing}"
    )


def test_the_bundle_lists_only_real_parts() -> None:
    """Every declared part exists, so a rename cannot silently drop one."""
    for part in _WASM_PACKAGE_PARTS:
        assert (PACKAGE_ROOT / part).exists(), f"{part} is declared but absent"
