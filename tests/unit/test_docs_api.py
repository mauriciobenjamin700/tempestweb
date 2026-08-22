"""Guard: every API a doc snippet names exists, with the keywords it passes.

The other docs guards check the *shape* of the site — links resolve, redirects
point somewhere, every subpackage has a reference page. None of them looks at
the Python inside a fenced block, so a recipe can teach an API that was renamed
(or never shipped) and every check stays green: ``mkdocs build --strict`` only
renders the text, and ``mkdocstrings`` reads the source, never the snippets.

That is how ``advanced/observability.md`` came to document ``telemetry.init()``
and ``ConsoleAdapter`` for several releases while the package shipped
``TelemetryProvider`` and ``ConsoleTelemetryAdapter``, and how two tutorial
pages kept passing ``children=`` to widgets whose field is ``child`` — silently
dropped before ``tempest-core`` 0.14.0, a ``ValidationError`` after it.

The check resolves each ``from tempestweb…``/``from tempest_core…`` import in a
block against the installed package and then, for every call it can trace back
to one of those imports, asserts the keywords exist as parameters. It is
deliberately narrow: a name the block never imported from us is somebody else's
problem, a call whose signature takes ``**kwargs`` accepts anything, and a
snippet that does not parse is skipped (walkthrough excerpts are fragments by
design). What is left is the class of error a reader hits on their first run.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
EXAMPLES = REPO_ROOT / "examples"
OUR_ROOTS = ("tempestweb", "tempest_core")
BLOCK = re.compile(r"^```(\w*)[^\n]*\n(.*?)^```", re.M | re.S)
ELLIPSIS_LINE = re.compile(r"^(\s*)\.\.\.\s*$", re.M)
MISSING = object()


def _pages() -> list[Path]:
    """The doc pages whose snippets are checked.

    Returns:
        Every Markdown page under ``docs/``, both languages, excluding the
        agent playbooks (which are prose about this repo, not user-facing).
    """
    return sorted(p for p in DOCS.rglob("*.md") if "agents" not in p.parts)


def _example_apps() -> list[Path]:
    """The example apps checked alongside the pages that walk through them.

    Returns:
        Every ``examples/*/app.py``, sorted by directory name.
    """
    return sorted(EXAMPLES.glob("*/app.py"))


def _shadowed(tree: ast.Module) -> set[str]:
    """The module-level names a file defines itself.

    A file that imports ``Card`` from the core and then defines its own
    ``class Card`` means the second one at every call site, so the import must
    not be used to check those calls.

    Args:
        tree: The parsed module.

    Returns:
        The names bound by a class, function or plain assignment at module
        level.
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _blocks(page: Path) -> list[str]:
    """The Python code blocks of a page.

    Args:
        page: The Markdown page to read.

    Returns:
        The body of each ``python``-tagged fenced block, with a bare ``...``
        line rewritten to ``pass`` so an elided body still parses.
    """
    text = page.read_text(encoding="utf-8")
    return [
        ELLIPSIS_LINE.sub(r"\1pass", code)
        for lang, code in BLOCK.findall(text)
        if lang.startswith("py")
    ]


def _parse(code: str) -> ast.Module | None:
    """Parse a snippet, tolerating an indented excerpt.

    Args:
        code: The block body.

    Returns:
        The parsed module, or ``None`` when the block is a fragment (a bare
        ``elif`` arm, half of a call) that no dedent makes valid Python.
    """
    for candidate in (code, textwrap.dedent(code)):
        try:
            return ast.parse(candidate)
        except SyntaxError:
            continue
    return None


def _resolve(module: str, name: str) -> Any:
    """Look a documented name up in the installed package.

    A plain ``from tempestweb import native`` imports a **submodule**, which is
    an attribute of the package only after something has imported it — so a
    missing attribute is retried as a module import before being reported, or
    the result would depend on which test ran first.

    Args:
        module: The module the snippet imports from.
        name: The imported symbol.

    Returns:
        The live object, ``MISSING`` when the module exists without it, or
        ``None`` when the module itself cannot be imported (an optional extra
        is not installed, so the snippet is out of scope here).
    """
    try:
        imported = importlib.import_module(module)
    except Exception:
        return None
    found = getattr(imported, name, MISSING)
    if found is MISSING:
        try:
            return importlib.import_module(f"{module}.{name}")
        except Exception:
            return MISSING
    return found


def _parameters(target: Any) -> set[str] | None:
    """The keyword names a callable accepts.

    Args:
        target: The object the snippet calls.

    Returns:
        The parameter names, or ``None`` when anything goes (the signature
        takes ``**kwargs``) or cannot be read.
    """
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return None
    kinds = [p.kind for p in signature.parameters.values()]
    if inspect.Parameter.VAR_KEYWORD in kinds:
        return None
    return set(signature.parameters)


def _imports(tree: ast.Module) -> tuple[dict[str, Any], list[str]]:
    """Bind the names a snippet imports from our packages.

    Args:
        tree: The parsed snippet.

    Returns:
        A pair of the local-name-to-object environment and the list of
        ``module.name`` imports that do not exist.
    """
    env: dict[str, Any] = {}
    missing: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.module or node.module.split(".")[0] not in OUR_ROOTS:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                obj = _resolve(node.module, alias.name)
                if obj is MISSING:
                    missing.append(f"{node.module}.{alias.name}")
                elif obj is not None:
                    env[alias.asname or alias.name] = obj
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in OUR_ROOTS and alias.asname:
                    try:
                        env[alias.asname] = importlib.import_module(alias.name)
                    except Exception:
                        continue
    return env, missing


def _calls(tree: ast.Module, env: dict[str, Any]) -> list[str]:
    """Check every call that traces back to one of our imports.

    Args:
        tree: The parsed snippet.
        env: The local names bound to live objects.

    Returns:
        One message per attribute that does not exist or keyword the callable
        does not accept.
    """
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target: Any = None
        label = ""
        if isinstance(node.func, ast.Name) and node.func.id in env:
            target, label = env[node.func.id], node.func.id
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in env
        ):
            base = env[node.func.value.id]
            label = f"{node.func.value.id}.{node.func.attr}"
            if not hasattr(base, node.func.attr):
                problems.append(f"{label} does not exist")
                continue
            target = getattr(base, node.func.attr)
        if target is None or inspect.ismodule(target):
            continue
        accepted = _parameters(target)
        if accepted is None:
            continue
        for keyword in node.keywords:
            if keyword.arg and keyword.arg not in accepted:
                problems.append(f"{label}(..., {keyword.arg}=...) is not a parameter")
    return problems


@pytest.mark.parametrize("page", _pages(), ids=lambda p: str(p.relative_to(DOCS)))
def test_snippets_name_an_api_that_exists(page: Path) -> None:
    """A snippet may only import, reach for and pass what the package has.

    Args:
        page: The doc page whose Python blocks are checked.
    """
    problems: list[str] = []
    for index, code in enumerate(_blocks(page), start=1):
        tree = _parse(code)
        if tree is None:
            continue
        env, missing = _imports(tree)
        problems += [f"block {index}: cannot import {name}" for name in missing]
        problems += [f"block {index}: {problem}" for problem in _calls(tree, env)]
    assert not problems, "\n".join(
        [f"{page.relative_to(DOCS)} documents an API that does not exist:", *problems]
    )


@pytest.mark.parametrize("app", _example_apps(), ids=lambda p: p.parent.name)
def test_example_apps_pass_keywords_the_widgets_declare(app: Path) -> None:
    """An example must build under every mode, not only the one it ships for.

    Mode C transpiles the source to JavaScript, where a widget builder takes
    the IR's uniform ``children`` array and validates nothing — so a kwarg the
    Python widget rejects runs fine there and raises the moment the same view
    is served by Mode A or B. ``examples/transpile-tour`` shipped exactly that.

    Args:
        app: The example's ``app.py``.
    """
    tree = ast.parse(app.read_text(encoding="utf-8"))
    env, missing = _imports(tree)
    for name in _shadowed(tree):
        env.pop(name, None)
    problems = [f"cannot import {name}" for name in missing]
    problems += _calls(tree, env)
    assert not problems, "\n".join(
        [f"{app.relative_to(REPO_ROOT)} uses an API that does not exist:", *problems]
    )
