"""The Mode A bundle must be import-closed — and must carry what apps import.

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

Closure alone was not enough. The subset was closed and still shipped **nothing
an app imports by name**: `tempestweb.tabular`, `.vision`, `.query`, `.access`
and `.export` were all absent, so a Mode A artifact using any of them died on
`No module named` at boot — found by running one in a tab, not by the suite. So
`test_every_app_facing_subpackage_is_bundled` inverts the question: everything
that is not server-side or build-time has to be in the bundle, and a new package
has to be classified on purpose rather than forgotten.

Presence is still not the property that matters. `tempestweb.vision` was added to
the bundle to fix a `No module named 'tempestweb.vision'`, and being in the zip
did not fix it: `vision/__init__.py` imports `tasks` → `ort_vision_sdk` and
`backend` → `numpy` at module level, while the Mode A bootstrap loads
`["pydantic", *packages]` — so the boot went on dying, one message later, at
`No module named 'numpy'`. `test_every_bundled_part_imports_on_pyodides_baseline`
therefore asks the real question in a subprocess with those packages blocked:
every bundled part must *import*, or be declared here as one an app can only
reach after naming its packages under `[wasm]`.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

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


#: Subpackages that must never enter the browser bundle, and why. The server and
#: devserver stacks need FastAPI/Starlette/uvicorn (absent in Pyodide, and useless
#: in a tab); the CLI is the tool that *writes* artifacts; the transpiler is a
#: build-time compiler whose output is what runs; ``pwa`` is the build-time
#: *emitter* the CLI calls to write ``manifest.webmanifest`` and the icons —
#: ``vendor_pyodide`` even downloads over ``urllib.request`` — and its only
#: importers are ``cli/commands/build.py`` and one example's build script, so the
#: 9,384 bytes it added to every Mode A artifact were code the browser never runs.
_NOT_IN_THE_BROWSER: frozenset[str] = frozenset(
    {"cli", "devserver", "pwa", "server", "transpile"}
)


def test_every_app_facing_subpackage_is_bundled() -> None:
    """A package an app can import must be in the artifact, or excluded on purpose."""
    bundled = _bundled_parts()
    absent = [
        directory.name
        for directory in sorted(PACKAGE_ROOT.iterdir())
        if directory.is_dir()
        and (directory / "__init__.py").exists()
        and directory.name not in _NOT_IN_THE_BROWSER
        and directory.name not in bundled
    ]
    assert absent == [], (
        "these subpackages ship to PyPI but not into the Mode A artifact, so an "
        f"app that imports one dies at boot with `No module named`: {absent}. "
        "Bundle them, or add them to _NOT_IN_THE_BROWSER with the reason."
    )


#: What Pyodide has before the app declares anything. The Mode A bootstrap calls
#: ``loadPackage(["pydantic", *packages])`` and the artifact's zip carries
#: ``tempest_core`` beside ``tempestweb``, so these two are the floor every
#: bundled module may import unconditionally.
_PYODIDE_BASELINE: frozenset[str] = frozenset({"pydantic", "tempest_core"})

#: Bundled parts that cannot import on that floor, and the packages an app has to
#: declare under ``[wasm] packages`` for them to. ``vision`` is the whole list and
#: is in the bundle on purpose: the package has to travel for an app that declares
#: ``packages = ["numpy"]`` (and reaches ``ort_vision_sdk``) to have anything to
#: import. What is *not* true is that bundling it made ``import tempestweb.vision``
#: work in a plain artifact — measured, that still dies, on ``numpy``.
_NEEDS_DECLARED_PACKAGES: dict[str, tuple[str, ...]] = {
    "vision": ("numpy", "ort_vision_sdk"),
}

#: Imports ``tempestweb.<part>`` with a set of top-level packages made
#: unimportable, which is the state of a fresh Pyodide runtime. The finder raises
#: instead of returning ``None`` so the error names the module that was refused,
#: exactly as the browser reports it.
_IMPORT_PROBE = """
import sys

blocked = set(sys.argv[1].split(","))
for name in [name for name in sys.modules if name.split(".")[0] in blocked]:
    del sys.modules[name]


class PyodideBaseline:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise ModuleNotFoundError(
                f"No module named {fullname!r}", name=fullname
            )
        return None


sys.meta_path.insert(0, PyodideBaseline())
__import__(sys.argv[2])
"""


def _third_party_imports() -> set[str]:
    """Top-level non-stdlib packages the bundled files import when executed.

    Returns:
        The names outside :data:`_PYODIDE_BASELINE`, so a dependency added to a
        bundled module joins the blocked set without anyone updating a list.
    """
    names: set[str] = set()
    for path in _bundled_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            imported: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            names.update(name.split(".")[0] for name in imported)
    return {
        name
        for name in names
        if name not in sys.stdlib_module_names
        and name != "tempestweb"
        and name not in _PYODIDE_BASELINE
    }


def _bundled_modules() -> list[tuple[str, str]]:
    """Every bundled part as ``(part, importable module name)``."""
    return [
        (part, "tempestweb" if part == "__init__.py" else f"tempestweb.{part}")
        for part in (name.removesuffix(".py") for name in _WASM_PACKAGE_PARTS)
    ]


@pytest.mark.parametrize(("part", "module"), _bundled_modules())
def test_every_bundled_part_imports_on_pyodides_baseline(
    part: str, module: str
) -> None:
    """Being in the zip is not being importable, and only the second one boots."""
    blocked = sorted(_third_party_imports())
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _IMPORT_PROBE, ",".join(blocked), module],
        capture_output=True,
        text=True,
        cwd=PACKAGE_ROOT.parent,
        check=False,
    )
    required = _NEEDS_DECLARED_PACKAGES.get(part, ())
    if not required:
        assert done.returncode == 0, (
            f"{module} is bundled into the Mode A artifact and does not import "
            f"with only {sorted(_PYODIDE_BASELINE)} available, so the boot dies "
            f"there instead of at the missing-module message being fixed:\n"
            f"{done.stderr.strip()}"
        )
        return
    assert done.returncode != 0, (
        f"{module} now imports on Pyodide's baseline, so its entry in "
        "_NEEDS_DECLARED_PACKAGES is stale — drop it, and drop the requirement "
        "from the docs that send an app to declare "
        f"{list(required)} under [wasm] packages"
    )
    assert any(name in done.stderr for name in required), (
        f"{module} fails to import for a reason other than the "
        f"{list(required)} it declares:\n{done.stderr.strip()}"
    )


def test_the_packages_an_app_must_declare_are_really_bundled() -> None:
    """A part that needs declared packages still has to be in the artifact.

    Excluding it instead would be the wrong fix: the app that declares
    ``packages = ["numpy"]`` under ``[wasm]`` needs the Python to import.
    """
    bundled = _bundled_parts()
    for part in _NEEDS_DECLARED_PACKAGES:
        assert part in bundled, (
            f"{part} needs declared packages to import, which is a reason to "
            "document the requirement, not a reason to leave it out of the zip"
        )
