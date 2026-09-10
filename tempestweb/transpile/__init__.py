"""Mode C transpiler — typed Python app layer → native JavaScript.

Transcribes a tempestweb app module (state dataclasses + `view` + handlers) into
an ES module that runs on the native JS runtime (`client/transpile/runtime.js`),
with zero Python at execution time. See docs/modo-c-transpile.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tempestweb.transpile.codegen import generate, local_module_specifier
from tempestweb.transpile.errors import TranspileError
from tempestweb.transpile.graph import LocalModule, resolve_graph

__all__: list[str] = [
    "LocalModule",
    "TranspileError",
    "local_module_specifier",
    "resolve_graph",
    "transpile_file",
    "transpile_project",
    "transpile_source",
]


def transpile_source(
    source: str, filename: str = "<source>", *, banner: str | None = None
) -> str:
    """Transpile Python module source into native-JS module source.

    Args:
        source: The Python source to transpile.
        filename: Source name for diagnostics and the default banner.
        banner: Optional leading comment line (see :func:`generate`).

    Returns:
        The generated JavaScript module source.

    Raises:
        TranspileError: If the module uses a construct outside the subset.
    """
    return generate(source, filename, banner=banner)


def transpile_file(path: str | Path, *, banner: str | None = None) -> str:
    """Transpile a Python source file into native-JS module source.

    Args:
        path: Path to the `.py` module to transpile.
        banner: Optional leading comment line (see :func:`generate`).

    Returns:
        The generated JavaScript module source.

    Raises:
        TranspileError: If the module uses a construct outside the subset.
    """
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    return generate(source, file_path.name, banner=banner)


def transpile_project(
    entry: str | Path,
    root: str | Path,
    *,
    entry_filename: str = "app.gen.js",
    banner: str | None = None,
    reserved: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Transpile an entrypoint and every project module it imports.

    A Mode C app is no longer one file: each local module the entrypoint reaches
    becomes its own ES module next to it, and the emitted imports wire them
    together. That is what lets an app import the typed client
    ``tempestweb gen api`` writes, which is a package.

    Args:
        entry: Path to the entrypoint `.py` module.
        root: The project root that local module names resolve against.
        entry_filename: The artifact name for the entrypoint's own module. The
            other modules are named after their dotted path.
        banner: Optional leading comment line for the entrypoint (see
            :func:`generate`). Siblings always get the default banner.
        reserved: Artifact file names the emitted modules must not take —
            the client assets shipped into the same directory. A project module
            named ``widgets`` would otherwise write ``widgets.gen.js`` over the
            renderer's own, and the app would load the wrong file with no error
            anywhere.

    Returns:
        Artifact file name → generated JavaScript source, the entrypoint
        included. A single-file app returns exactly one entry.

    Raises:
        TranspileError: If any module falls outside the subset, the local
            imports cycle, a relative import climbs above the root, or a module
            name collides with a reserved artifact.
    """
    modules = resolve_graph(Path(entry), Path(root))
    exported: Mapping[str, frozenset[str]] = {
        module.name: module.classes for module in modules
    }
    taken = reserved | {entry_filename}
    output: dict[str, str] = {}
    for module in modules:
        name = (
            entry_filename
            if module.is_entry
            else local_module_specifier(module.name).removeprefix("./")
        )
        if not module.is_entry and name in taken:
            raise TranspileError(
                f"the module `{module.name}` would be emitted as `{name}`, "
                "which the Mode C client already ships — rename it",
                None,
                module.path.name,
            )
        output[name] = generate(
            module.source,
            module.path.name,
            banner=banner if module.is_entry else None,
            module_name=module.name,
            module_is_package=module.is_package,
            local_modules=exported,
        )
    return output
