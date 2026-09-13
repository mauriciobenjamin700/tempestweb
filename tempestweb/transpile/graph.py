"""Resolve the local module graph a Mode C entrypoint imports.

A Mode C app used to be one file: the emitter refused every import outside
``tempest_core``, ``tempestweb.components`` and ``tempestweb.native``, so an app
could not split a screen into modules and the typed client
``tempestweb gen api`` writes — a package — could not be imported at all.

This module walks the entrypoint's own imports, resolves each one to a file
under the project root, and returns the modules in dependency order so the
emitter can transcribe each into its own ES module. Only the app's own files are
followed: an import that resolves to no project file is left alone, and the
emitter refuses it with the diagnostic it always did.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from tempestweb.transpile.errors import TranspileError

__all__: list[str] = ["LocalModule", "absolute_target", "resolve_graph"]


@dataclass(frozen=True)
class LocalModule:
    """One project module reachable from the entrypoint.

    Attributes:
        name: The module's dotted name relative to the project root
            (``"api.tasks.service"``). The entrypoint's own name is included.
        path: The absolute path to the module's source file.
        source: The module's source text.
        tree: The parsed module.
        classes: The names of the classes the module declares at top level,
            needed by an importing module to know a name is constructible.
        is_package: Whether the file is an ``__init__.py``. A relative import
            inside a package is rooted at the package itself, not at its
            parent, so this decides what ``from .x import`` resolves to.
        is_entry: Whether this is the entrypoint the build starts from.
    """

    name: str
    path: Path
    source: str
    tree: ast.Module
    classes: frozenset[str]
    is_package: bool
    is_entry: bool


def _module_name(path: Path, root: Path) -> str:
    """Return the dotted name a project file is importable under.

    Args:
        path: The absolute path to the module file.
        root: The project root the name is relative to.

    Returns:
        The dotted module name (``api/tasks/service.py`` → ``api.tasks.service``,
        ``api/tasks/__init__.py`` → ``api.tasks``).
    """
    relative = path.relative_to(root)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _resolve_name(name: str, root: Path) -> Path | None:
    """Find the project file a dotted module name refers to.

    Args:
        name: The dotted module name.
        root: The project root to resolve against.

    Returns:
        The module file, or None when the project has no such file — in which
        case the name belongs to a library and the emitter judges it.
    """
    base = root.joinpath(*name.split("."))
    module = base.with_suffix(".py")
    if module.is_file():
        return module
    package = base / "__init__.py"
    if package.is_file():
        return package
    return None


def absolute_target(
    node: ast.ImportFrom, owner: str, *, is_package: bool = False
) -> str:
    """Return the dotted module an ``ImportFrom`` names, resolving relative form.

    Args:
        node: The import node.
        owner: The dotted name of the module containing the import.
        is_package: Whether ``owner`` is a package (an ``__init__.py``). One
            leading dot means the package the module *lives in*, which for a
            package's own ``__init__.py`` is that package itself — resolving it
            to the parent sends `from .schemas import …` one level too high.

    Returns:
        The absolute dotted module name the import targets.

    Raises:
        TranspileError: If the relative import climbs above the project root.
    """
    if not node.level:
        return node.module or ""
    parts = owner.split(".") if owner else []
    package = parts if is_package else parts[:-1]
    climb = node.level - 1
    if climb > len(package):
        raise TranspileError(
            f"the relative import climbs above the project root "
            f"(`{'.' * node.level}{node.module or ''}` from `{owner}`)",
            node,
            owner,
        )
    prefix = package[: len(package) - climb] if climb else package
    tail = [node.module] if node.module else []
    return ".".join([*prefix, *tail])


def _declared_classes(tree: ast.Module) -> frozenset[str]:
    """Return the names of the top-level classes a module declares.

    Args:
        tree: The parsed module.

    Returns:
        The class names, so an importing module knows the name is a class and
        constructs it with ``new`` instead of calling it.
    """
    return frozenset(node.name for node in tree.body if isinstance(node, ast.ClassDef))


def _read(path: Path, root: Path) -> LocalModule:
    """Parse one project module.

    Args:
        path: The module file to read.
        root: The project root the module's name is relative to.

    Returns:
        The parsed module record, with ``is_entry`` left False.

    Raises:
        TranspileError: If the file is not valid Python.
    """
    name = _module_name(path, root)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise TranspileError(f"cannot parse: {exc.msg}", None, path.name) from exc
    return LocalModule(
        name=name,
        path=path,
        source=source,
        tree=tree,
        classes=_declared_classes(tree),
        is_package=path.name == "__init__.py",
        is_entry=False,
    )


def resolve_graph(entry: Path, root: Path) -> list[LocalModule]:
    """Walk the entrypoint's local imports into a dependency-ordered graph.

    Depth-first, so a module always appears after everything it imports — the
    order the emitter and the build write them in.

    Args:
        entry: The absolute path to the entrypoint module.
        root: The project root local module names resolve against.

    Returns:
        Every project module reachable from the entrypoint, dependencies first
        and the entrypoint last. A single-file app returns a one-item list.

    Raises:
        TranspileError: If a local import cycles, or a relative import climbs
            above the project root. A cycle is refused rather than emitted: the
            ES modules would load, but a name read during evaluation of the
            other half throws on a temporal dead zone, at a line neither module
            names.
    """
    entry = entry.resolve()
    root = root.resolve()
    ordered: list[LocalModule] = []
    done: set[str] = set()
    stack: list[str] = []

    def walk(path: Path, is_entry: bool) -> None:
        """Visit one module, its dependencies first.

        Args:
            path: The module file to visit.
            is_entry: Whether this is the entrypoint.
        """
        module = _read(path, root)
        if module.name in done:
            return
        if module.name in stack:
            cycle = " → ".join([*stack[stack.index(module.name) :], module.name])
            raise TranspileError(
                f"local imports form a cycle ({cycle}); Mode C refuses it "
                "because the emitted modules would throw on a temporal dead "
                "zone at a line neither of them names",
                None,
                path.name,
            )
        stack.append(module.name)
        for node in module.tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            target = absolute_target(node, module.name, is_package=module.is_package)
            if not target:
                continue
            resolved = _resolve_name(target, root)
            if resolved is None:
                continue
            walk(resolved, False)
        stack.pop()
        done.add(module.name)
        ordered.append(
            LocalModule(
                name=module.name,
                path=module.path,
                source=module.source,
                tree=module.tree,
                classes=module.classes,
                is_package=module.is_package,
                is_entry=is_entry,
            )
        )

    walk(entry, True)
    return _propagate_reexports(ordered)


def _propagate_reexports(ordered: list[LocalModule]) -> list[LocalModule]:
    """Widen each module's class set with the classes it re-exports.

    A package's ``__init__.py`` declares nothing and re-exports — which is
    exactly the shape ``tempestweb gen api`` writes. Without this an importer
    reading a class through the package does not know it is a class, and the
    emitter calls it instead of constructing it: `TasksService()` in JS, which
    throws `TypeError: Class constructor cannot be invoked without 'new'`.

    Args:
        ordered: The modules, dependencies first.

    Returns:
        The same modules, each with ``classes`` widened by the class names it
        imports from a module earlier in the order.
    """
    known: dict[str, frozenset[str]] = {}
    widened: list[LocalModule] = []
    for module in ordered:
        classes = set(module.classes)
        for node in module.tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            target = absolute_target(node, module.name, is_package=module.is_package)
            exported = known.get(target)
            if exported is None:
                continue
            for alias in node.names:
                if alias.name in exported:
                    classes.add(alias.asname or alias.name)
        known[module.name] = frozenset(classes)
        widened.append(
            LocalModule(
                name=module.name,
                path=module.path,
                source=module.source,
                tree=module.tree,
                classes=frozenset(classes),
                is_package=module.is_package,
                is_entry=module.is_entry,
            )
        )
    return widened
