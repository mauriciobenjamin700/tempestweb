"""``tempestweb sync`` — auto-fill ``[wasm].modules`` from the installed env.

A Mode A app bundles its own Python source into the wasm artifact (see
``[wasm].modules`` and :func:`tempestweb.cli.commands.build._resolve_module`). For
third-party **pure-Python** dependencies that resolution already pulls the source
from the project's ``.venv`` — but each one still has to be *listed* under
``[wasm].modules``. This command removes that bookkeeping: it reads the app's
declared dependencies, keeps the ones that are installed **and** pure-Python, and
writes their import names into ``[wasm].modules`` for you.

What is included:

- A name appears in ``[project.dependencies]`` of the project's ``pyproject.toml``
  **and** is installed in the current environment.
- Its distribution is **pure-Python** (ships no compiled extension — no ``.so`` /
  ``.pyd`` / ``.dylib``). Packages with native code (numpy, pillow, …) belong
  under ``[wasm].packages`` instead — Pyodide provides their wheels — so they are
  skipped here.

What is excluded:

- The framework itself (``tempestweb``, ``tempest-core``, ``pydantic`` &c.) — the
  build always bundles the Mode A core.
- Anything already declared under ``[wasm].packages`` (Pyodide-provided).

Existing ``[wasm].modules`` entries are **preserved** (your local app package, a
manually vendored copy) — the command only ever *adds* discovered names. It is
idempotent: a second run with no environment change writes nothing.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

from tempestweb.cli.config import load_config

__all__ = ["SyncError", "SyncResult", "sync_modules"]


class SyncError(RuntimeError):
    """Raised when ``tempestweb sync`` cannot complete."""


#: Distribution suffixes that mark a wheel as carrying compiled (non-pure) code.
_BINARY_SUFFIXES: frozenset[str] = frozenset({".so", ".pyd", ".dylib"})

#: Framework distributions the Mode A build always bundles — never listed.
_FRAMEWORK: frozenset[str] = frozenset(
    {
        "tempestweb",
        "tempest-core",
        "pydantic",
        "pydantic-core",
        "annotated-types",
        "typing-extensions",
    }
)

#: Matches the distribution name at the head of a PEP 508 requirement string.
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass(slots=True)
class SyncResult:
    """Outcome of a ``tempestweb sync`` run.

    Attributes:
        config_path: The ``tempestweb.toml`` that was (or would be) written.
        modules: The full ``[wasm].modules`` list after the sync.
        added: The module names newly discovered and added this run.
        changed: Whether the config would change (``added`` is non-empty).
        written: Whether the config file was actually written (``False`` for a
            dry run, or when nothing changed).
    """

    config_path: Path
    modules: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    changed: bool = False
    written: bool = False


def _normalize(name: str) -> str:
    """Normalize a distribution/module name for comparison (PEP 503).

    Args:
        name: A distribution or top-level module name.

    Returns:
        The lowercased name with runs of ``-``/``_``/``.`` collapsed to ``-``.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _project_dependencies(root: Path) -> list[str]:
    """Read the project's declared dependency distribution names.

    Args:
        root: The project directory holding ``pyproject.toml``.

    Returns:
        The distribution names from ``[project.dependencies]`` with version
        specifiers, extras, and environment markers stripped. Empty when there is
        no ``pyproject.toml`` or no dependencies.

    Raises:
        SyncError: If ``pyproject.toml`` exists but is malformed.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SyncError(f"invalid {pyproject}: {exc}") from exc
    raw_deps = data.get("project", {}).get("dependencies", [])
    names: list[str] = []
    for spec in raw_deps:
        match = _REQUIREMENT_NAME.match(str(spec))
        if match:
            names.append(match.group(1))
    return names


def _top_level_modules(dist: metadata.Distribution) -> list[str]:
    """Return the importable top-level module names a distribution provides.

    Prefers the wheel's ``top_level.txt``; falls back to inferring top-level
    packages/modules from the recorded file list.

    Args:
        dist: The installed distribution.

    Returns:
        The top-level import names (e.g. ``["ort_vision_sdk"]``).
    """
    top_level = dist.read_text("top_level.txt")
    if top_level:
        return [line.strip() for line in top_level.splitlines() if line.strip()]

    tops: set[str] = set()
    for entry in dist.files or ():
        parts = entry.parts
        if not parts:
            continue
        head = parts[0]
        if head.endswith((".dist-info", ".egg-info", ".data")):
            continue
        if len(parts) >= 2 and parts[1] == "__init__.py":
            tops.add(head)
        elif len(parts) == 1 and head.endswith(".py"):
            tops.add(head[:-3])
    return sorted(tops)


def _is_pure_python(dist: metadata.Distribution) -> bool:
    """Tell whether a distribution ships only Python (no compiled extension).

    Args:
        dist: The installed distribution.

    Returns:
        ``True`` if no recorded file is a native extension (``.so``/``.pyd``/
        ``.dylib``); a distribution with no recorded files is treated as pure.
    """
    return all(entry.suffix not in _BINARY_SUFFIXES for entry in dist.files or ())


def _discover_modules(root: Path, exclude: set[str]) -> list[str]:
    """Discover bundlable pure-Python modules from the project's dependencies.

    Args:
        root: The project directory.
        exclude: Normalized names to skip (framework + ``[wasm].packages``).

    Returns:
        The de-duplicated import names to add to ``[wasm].modules``, in dependency
        declaration order.
    """
    found: list[str] = []
    seen: set[str] = set()
    for dependency in _project_dependencies(root):
        if _normalize(dependency) in exclude:
            continue
        try:
            dist = metadata.distribution(dependency)
        except metadata.PackageNotFoundError:
            continue
        if not _is_pure_python(dist):
            continue
        for module in _top_level_modules(dist):
            if _normalize(module) in exclude or module in seen:
                continue
            seen.add(module)
            found.append(module)
    return found


def _write_modules(config_path: Path, modules: list[str]) -> None:
    """Write ``modules`` into the ``[wasm].modules`` array, preserving the file.

    Uses ``tomlkit`` for a round-trip edit so comments and formatting survive.

    Args:
        config_path: The ``tempestweb.toml`` to edit in place.
        modules: The full module list to store under ``[wasm].modules``.

    Raises:
        SyncError: If ``tomlkit`` is not installed.
    """
    try:
        import tomlkit
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised via install
        raise SyncError(
            "tomlkit is required for `tempestweb sync` — "
            'install it with `uv add "tempestweb[cli]"`'
        ) from exc

    document = tomlkit.parse(config_path.read_text(encoding="utf-8"))
    wasm = document.get("wasm")
    if wasm is None:
        wasm = tomlkit.table()
        document["wasm"] = wasm
    array = tomlkit.array()
    array.extend(modules)
    array.multiline(len(modules) > 1)
    wasm["modules"] = array
    config_path.write_text(tomlkit.dumps(document), encoding="utf-8")


def sync_modules(path: str | Path, *, dry_run: bool = False) -> SyncResult:
    """Fill ``[wasm].modules`` from the project's installed pure-Python deps.

    Reads ``[project.dependencies]`` from the project's ``pyproject.toml``, keeps
    the dependencies that are installed and pure-Python (excluding the framework
    and anything already under ``[wasm].packages``), and adds their import names
    to ``[wasm].modules`` — preserving any existing entries. Idempotent.

    Args:
        path: The project directory (the one holding ``tempestweb.toml``).
        dry_run: When ``True``, compute the result but do not write the file.

    Returns:
        A :class:`SyncResult` describing the final module list and what changed.

    Raises:
        SyncError: If there is no ``tempestweb.toml``, the ``pyproject.toml`` is
            malformed, or the write back-end (``tomlkit``) is missing.
    """
    config = load_config(path)
    config_path = config.root / "tempestweb.toml"
    if not config_path.is_file():
        raise SyncError(
            f"no tempestweb.toml in {config.root} — run `tempestweb new` first"
        )

    # Normalize the framework names too (not just the config packages) so the
    # exclude set always matches the normalized dependency/module names compared
    # against it — robust even if a name here is added in non-canonical form.
    exclude = {
        *(_normalize(name) for name in _FRAMEWORK),
        *(_normalize(package) for package in config.wasm.packages),
    }
    discovered = _discover_modules(config.root, exclude)

    existing = list(config.wasm.modules)
    added = [module for module in discovered if module not in existing]
    modules = existing + added
    changed = bool(added)

    written = False
    if changed and not dry_run:
        _write_modules(config_path, modules)
        written = True

    return SyncResult(
        config_path=config_path,
        modules=modules,
        added=added,
        changed=changed,
        written=written,
    )
