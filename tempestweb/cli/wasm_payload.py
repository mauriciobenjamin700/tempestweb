"""Shape the Mode A Python payload: trim it to what the app reaches, precompile it.

The wasm bootstrap unpacks ``tempestweb-pkg.zip`` into Pyodide's working
directory and imports ``app`` from there. Two properties of that archive decide
how much work the browser does before the first paint, and both are settled
here, at build time:

- **Which ``tempestweb`` subpackages travel.** :func:`resolve_wasm_parts` walks
  the imports of ``app.py``, the project's ``[wasm] modules`` and the runtime
  entry, and keeps only the Mode A subpackages that walk reaches (plus any the
  project names under ``[wasm] keep``).
- **Whether the modules arrive as bytecode.** Pyodide sets
  ``sys.dont_write_bytecode``, so without a ``.pyc`` in the archive every module
  is compiled from source on every page load. :func:`compile_bytecode` runs
  ``compileall`` with an interpreter whose magic number is exactly
  :data:`~tempestweb.core.constants.WASM_PYODIDE_PYC_MAGIC`, and refuses — with a
  :class:`WasmBytecodeWarning`, shipping source instead — when no such
  interpreter exists or the output does not verify.
"""

from __future__ import annotations

import ast
import functools
import importlib.util
import re
import shutil
import subprocess
import sys
import warnings
from collections.abc import Iterable
from pathlib import Path

from tempestweb.core.constants import WASM_PYODIDE_PYC_MAGIC, WASM_PYODIDE_PYTHON

__all__ = [
    "PYC_FLAGS_CHECKED_HASH",
    "WasmBytecodeWarning",
    "bytecode_interpreter",
    "compile_bytecode",
    "pyodide_cache_tag",
    "referenced_parts",
    "resolve_wasm_parts",
]

#: The ``flags`` word of a checked hash-based ``.pyc`` (PEP 552): bit 0 says the
#: file is hash-based, bit 1 says the loader must check that hash against the
#: source. Every ``.pyc`` the build ships carries it, so a ``.py`` that changed
#: after the archive was made (``app.py`` is fetched separately from the zip) is
#: recompiled instead of silently running stale bytecode.
PYC_FLAGS_CHECKED_HASH: int = 0b11

#: Matches a dotted ``tempestweb.<part>`` reference inside a string literal — the
#: shape of an ``importlib.import_module("tempestweb.transports.sse")`` call.
_DOTTED_REFERENCE: re.Pattern[str] = re.compile(r"\btempestweb\.([A-Za-z_]\w*)")

#: Asks an interpreter for its bytecode magic number, as hex, on stdout.
_MAGIC_PROBE: str = (
    "import importlib.util, sys; sys.stdout.write(importlib.util.MAGIC_NUMBER.hex())"
)

#: Seconds a probe or a ``compileall`` run may take before the build gives up on
#: bytecode (and ships source).
_SUBPROCESS_TIMEOUT: float = 300.0


class WasmBytecodeWarning(UserWarning):
    """Emitted when the build ships source instead of the bytecode it was asked for.

    Bytecode is an optimization, so its absence never fails a build: the artifact
    still boots, it just compiles every module in the browser. The warning says
    why, so the cause (usually: no CPython of the Pyodide version on the build
    host) can be fixed.
    """


def pyodide_cache_tag() -> str:
    """Return the ``sys.implementation.cache_tag`` of the Pyodide runtime.

    Returns:
        ``"cpython-<major><minor>"`` for :data:`WASM_PYODIDE_PYTHON` — the name
        segment importlib looks for in ``__pycache__/<module>.<tag>.pyc``.
    """
    major, minor = WASM_PYODIDE_PYTHON.split(".")
    return f"cpython-{major}{minor}"


def _interpreter_magic(executable: str) -> bytes | None:
    """Ask ``executable`` for its bytecode magic number.

    Args:
        executable: Path to a Python interpreter.

    Returns:
        The interpreter's ``importlib.util.MAGIC_NUMBER``, or ``None`` when it
        cannot be run or answers with something that is not hex.
    """
    try:
        done = subprocess.run(  # noqa: S603 - argv list, no shell
            [executable, "-I", "-c", _MAGIC_PROBE],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        return bytes.fromhex(done.stdout.strip())
    except ValueError:
        return None


def _candidate_interpreters() -> list[str]:
    """List host interpreters that may match the Pyodide Python, best first.

    The order is: ``uv python find <version>`` (when ``uv`` is on ``PATH``; it
    only *finds*, it never downloads), then ``python<version>`` on ``PATH``.
    Every candidate is still verified by magic number before use.

    Returns:
        Interpreter paths, de-duplicated, possibly empty.
    """
    candidates: list[str] = []
    uv = shutil.which("uv")
    if uv is not None:
        try:
            found = subprocess.run(  # noqa: S603 - argv list, no shell
                [uv, "python", "find", "--no-project", WASM_PYODIDE_PYTHON],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            found = None
        if found is not None and found.returncode == 0 and found.stdout.strip():
            candidates.append(found.stdout.strip().splitlines()[0])
    on_path = shutil.which(f"python{WASM_PYODIDE_PYTHON}")
    if on_path is not None:
        candidates.append(on_path)
    return list(dict.fromkeys(candidates))


@functools.cache
def bytecode_interpreter() -> str | None:
    """Find a host interpreter whose bytecode the pinned Pyodide can load.

    The interpreter running the build wins when its magic number matches
    :data:`WASM_PYODIDE_PYC_MAGIC`; otherwise :func:`_candidate_interpreters` are
    probed. Matching the ``major.minor`` is not enough — a pre-release of the
    same minor carries a different magic — so only the exact magic qualifies.
    The answer is cached for the process: the ``tempestweb dev`` loop rebuilds
    on every save and should not re-probe the host each time.

    Returns:
        The interpreter path, or ``None`` when no host interpreter matches.
    """
    if importlib.util.MAGIC_NUMBER == WASM_PYODIDE_PYC_MAGIC:
        return sys.executable
    for candidate in _candidate_interpreters():
        if _interpreter_magic(candidate) == WASM_PYODIDE_PYC_MAGIC:
            return candidate
    return None


def _pyc_path(source: Path) -> Path:
    """Return where importlib looks for the cached bytecode of ``source``.

    Args:
        source: A ``.py`` file.

    Returns:
        ``<dir>/__pycache__/<stem>.<pyodide cache tag>.pyc``.
    """
    return source.parent / "__pycache__" / f"{source.stem}.{pyodide_cache_tag()}.pyc"


def _discard_bytecode(stage: Path) -> None:
    """Remove every ``__pycache__`` directory under ``stage``.

    Args:
        stage: The staged payload root.
    """
    for cache in sorted(stage.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache, ignore_errors=True)


def _verified(sources: list[Path]) -> str | None:
    """Check that every source has a ``.pyc`` Pyodide will load and validate.

    Args:
        sources: The staged ``.py`` files that were compiled.

    Returns:
        ``None`` when every ``.pyc`` exists with the pinned magic and the checked
        hash flags; otherwise a sentence naming the first offender.
    """
    for source in sources:
        pyc = _pyc_path(source)
        if not pyc.is_file():
            return f"no bytecode was written for {source.name}"
        header = pyc.read_bytes()[:8]
        if header[:4] != WASM_PYODIDE_PYC_MAGIC:
            return f"{pyc.name} carries magic {header[:4].hex()}"
        if int.from_bytes(header[4:8], "little") != PYC_FLAGS_CHECKED_HASH:
            return f"{pyc.name} is not a checked hash-based pyc"
    return None


def _make_sourceless(sources: list[Path], keep_source: frozenset[Path]) -> None:
    """Replace each source with its bytecode, moved beside it as ``<stem>.pyc``.

    Args:
        sources: The staged ``.py`` files, each already compiled.
        keep_source: Sources that keep their ``.py`` and ``__pycache__`` entry
            (``app.py``, which the bootstrap writes next to the archive anyway).
    """
    for source in sources:
        if source in keep_source:
            continue
        _pyc_path(source).replace(source.with_suffix(".pyc"))
        source.unlink()
    for cache in sorted(
        (path.parent for path in sources if path not in keep_source), reverse=True
    ):
        pycache = cache / "__pycache__"
        if pycache.is_dir() and not any(pycache.iterdir()):
            pycache.rmdir()


def compile_bytecode(
    stage: Path,
    *,
    sourceless: bool = False,
    keep_source: Iterable[Path] = (),
) -> bool:
    """Precompile every ``.py`` under ``stage`` for the pinned Pyodide Python.

    Runs ``compileall`` with :func:`bytecode_interpreter` in checked-hash mode,
    so importlib in Pyodide loads the ``.pyc`` after hashing the source instead
    of compiling it — and recompiles, rather than running stale code, if a
    source ever disagrees with its bytecode. Then verifies every output header.
    Any failure discards the bytecode, emits a :class:`WasmBytecodeWarning` and
    returns ``False``: mismatched bytecode is never shipped.

    Args:
        stage: The staged payload root (the archive's future contents).
        sourceless: When ``True``, ship ``<stem>.pyc`` in place of each ``.py``
            (except ``keep_source``) instead of next to it.
        keep_source: Staged files that keep their source in sourceless mode.

    Returns:
        ``True`` when the stage now carries verified bytecode, ``False`` when it
        was left as source.
    """
    sources = sorted(path for path in stage.rglob("*.py") if path.is_file())
    if not sources:
        return True
    interpreter = bytecode_interpreter()
    if interpreter is None:
        warnings.warn(
            f"no CPython {WASM_PYODIDE_PYTHON} with bytecode magic "
            f"{WASM_PYODIDE_PYC_MAGIC.hex()} found on this host, so the wasm "
            "package ships source only and Pyodide compiles it on every load. "
            f"Install one (`uv python install {WASM_PYODIDE_PYTHON}`) or set "
            '`bytecode = "off"` under [wasm] to silence this.',
            WasmBytecodeWarning,
            stacklevel=2,
        )
        return False
    try:
        done = subprocess.run(  # noqa: S603 - argv list, no shell
            [
                interpreter,
                "-I",
                "-m",
                "compileall",
                "-q",
                "-f",
                "--invalidation-mode",
                "checked-hash",
                "-s",
                str(stage),
                str(stage),
            ],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
        problem = (
            f"compileall exited {done.returncode}: {done.stdout.strip()}"
            if done.returncode != 0
            else _verified(sources)
        )
    except (OSError, subprocess.SubprocessError) as exc:
        problem = f"compileall could not run: {exc}"
    if problem is not None:
        _discard_bytecode(stage)
        warnings.warn(
            f"wasm bytecode discarded, shipping source instead ({problem})",
            WasmBytecodeWarning,
            stacklevel=2,
        )
        return False
    if sourceless:
        _make_sourceless(sources, frozenset(keep_source))
    return True


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Return the ``id`` of every docstring constant in ``tree``.

    Docstrings name subpackages in prose ("see ``tempestweb.tabular``"), which
    is not a reference; counting them would ship whatever the docs mention.

    Args:
        tree: A parsed module.

    Returns:
        ``id()`` of each docstring :class:`ast.Constant`.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            found.add(id(body[0].value))
    return found


def referenced_parts(source: str, *, package: str | None = None) -> set[str]:
    """Name the ``tempestweb`` subpackages a module's source refers to.

    Counts every import anywhere in the file (function-level and
    ``TYPE_CHECKING`` ones included — conservative on purpose), relative imports
    resolved against ``package``, ``tempestweb.<part>`` attribute chains, and
    dotted ``"tempestweb.<part>..."`` string literals (the lazy
    ``importlib.import_module`` pattern). Docstrings are ignored. A file that
    does not parse falls back to a plain-text scan, which over-includes rather
    than miss a reference.

    Args:
        source: The module's source text.
        package: The module's package (``__package__``), used to resolve relative
            imports; ``None`` for a top-level module.

    Returns:
        The first name segment after ``tempestweb.`` of each reference (which
        may not be a real subpackage; the caller filters).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(_DOTTED_REFERENCE.findall(source))
    docstrings = _docstring_nodes(tree)
    parts: set[str] = set()

    def from_dotted(name: str, aliases: Iterable[str] = ()) -> None:
        """Record the part a dotted module name lands in.

        Args:
            name: An absolute module name.
            aliases: Names imported *from* it, which are parts themselves when
                ``name`` is the ``tempestweb`` root.
        """
        segments = name.split(".")
        if segments[0] != "tempestweb":
            return
        if len(segments) > 1:
            parts.add(segments[1])
        else:
            parts.update(aliases)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                from_dotted(alias.name)
        elif isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            if node.level == 0:
                if node.module:
                    from_dotted(node.module, names)
                continue
            if package is None:
                continue
            try:
                resolved = importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package
                )
            except ImportError:
                continue
            from_dotted(resolved, names)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "tempestweb"
        ):
            parts.add(node.attr)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            parts.update(_DOTTED_REFERENCE.findall(node.value))
    return parts


def _module_package(path: Path, root: Path) -> str | None:
    """Return the ``__package__`` a staged file runs under.

    Args:
        path: A ``.py`` file under ``root``.
        root: The directory on ``sys.path`` (the archive root).

    Returns:
        The dotted package, or ``None`` for a top-level module.
    """
    relative = path.relative_to(root).with_suffix("")
    segments = list(relative.parts)
    if segments[-1] == "__init__":
        segments.pop()
    else:
        segments = segments[:-1]
    return ".".join(segments) or None


def _python_files(target: Path) -> list[Path]:
    """List the ``.py`` files of a module file or package directory.

    Args:
        target: A ``.py`` file or a package directory.

    Returns:
        The files, sorted, ``__pycache__`` excluded.
    """
    if target.is_file():
        return [target] if target.suffix == ".py" else []
    return sorted(
        path
        for path in target.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    )


def _scan(files: Iterable[tuple[Path, Path]]) -> set[str]:
    """Collect :func:`referenced_parts` over ``(file, sys.path root)`` pairs.

    Args:
        files: Each file with the directory it is imported relative to.

    Returns:
        The union of the referenced part names.
    """
    found: set[str] = set()
    for path, root in files:
        source = path.read_text(encoding="utf-8", errors="replace")
        found |= referenced_parts(source, package=_module_package(path, root))
    return found


def resolve_wasm_parts(
    available: tuple[str, ...],
    *,
    tempestweb_root: Path,
    app_source: str,
    module_files: Iterable[tuple[Path, Path]] = (),
    seeds: Iterable[str] = (),
    keep: Iterable[str] = (),
) -> tuple[str, ...]:
    """Compute which Mode A ``tempestweb`` parts an app actually reaches.

    Starts from the parts ``app.py``, the project's modules and ``seeds`` (the
    runtime entry the bootstrap imports) refer to, then adds whatever every
    reached part refers to in turn, scanning **every** file of a reached part
    (a part ships whole, so its lazy paths travel too). The package root
    (``__init__.py``) always ships.

    Args:
        available: The parts a Mode A archive may contain, in their canonical
            order (directory names, plus ``"__init__.py"``).
        tempestweb_root: The directory that holds the ``tempestweb`` package.
        app_source: The app's ``app.py`` source.
        module_files: ``(file, sys.path root)`` for each file of the project's
            ``[wasm] modules``.
        seeds: Part names always reached (e.g. ``"runtime"``).
        keep: Part names the project forces in (``[wasm] keep``).

    Returns:
        The reached parts, in ``available`` order.

    Raises:
        ValueError: If ``keep`` names a part that is not in ``available``.
    """
    names = {part.removesuffix(".py"): part for part in available}
    unknown = sorted(set(keep) - set(names))
    if unknown:
        raise ValueError(
            f"[wasm] keep names unknown tempestweb subpackages {unknown}; "
            f"expected any of {sorted(name for name in names if name != '__init__')}"
        )
    pending = (
        referenced_parts(app_source)
        | _scan(module_files)
        | set(seeds)
        | set(keep)
        | {"__init__"}
    )
    reached: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reached or name not in names:
            continue
        reached.add(name)
        target = tempestweb_root / "tempestweb" / names[name]
        pending |= _scan((path, tempestweb_root) for path in _python_files(target))
    return tuple(part for part in available if part.removesuffix(".py") in reached)
