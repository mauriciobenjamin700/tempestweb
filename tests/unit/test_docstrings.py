"""Guard: inner functions carry docstrings too, which ``ruff`` cannot check.

``pyproject.toml`` selects ruff's ``D`` rules, and the comment above that block
says docstrings are part of the gate. They are — for modules, classes, methods
and module-level functions. ``D`` inherits pydocstyle's semantics, and
pydocstyle treats a function defined **inside another function** as an
implementation detail that needs no docstring. There is no option to change
that.

The exemption lands exactly where this codebase puts its least obvious logic:
event handlers, authentication callbacks, connection teardown, and the
recursive ``walk`` helpers in the transpiler and the event registry. Twenty-four
such closures had drifted in undocumented with ``ruff check .`` fully green, and
an abandoned branch that documented four of them was never integrated — which is
what a missing guard looks like over time.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "tempestweb"

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _undocumented_closures(module: Path) -> list[str]:
    """Find inner functions in one module that carry no docstring.

    "Inner" means the function's immediate parent in the AST is itself a
    function — a closure or a local helper. A method on a class nested in a
    function is not one of these, and is already covered by ruff's ``D`` rules.

    Args:
        module: The Python file to scan.

    Returns:
        ``path:line name()`` entries, one per undocumented closure.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, _FunctionNode):
            continue
        if not isinstance(parents.get(node), _FunctionNode):
            continue
        if ast.get_docstring(node) is None:
            relative = module.relative_to(REPO_ROOT).as_posix()
            found.append(f"{relative}:{node.lineno} {node.name}()")
    return found


def test_inner_functions_are_documented() -> None:
    """Every closure in the package explains itself.

    Reported as a list of ``path:line`` rather than a count, so the failure is
    actionable: the fix is to write the docstring the report points at, not to
    update a number.

    ``tests/`` and ``examples/`` are deliberately exempt from ``D`` in
    ``pyproject.toml`` and stay exempt here — this guard covers shipped code.
    """
    missing: list[str] = []
    for module in sorted(PACKAGE.rglob("*.py")):
        missing.extend(_undocumented_closures(module))
    assert not missing, (
        f"{len(missing)} inner function(s) without a docstring — ruff's D rules "
        "cannot see these:\n  " + "\n  ".join(missing)
    )
