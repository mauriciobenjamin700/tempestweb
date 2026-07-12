"""Quality-gate helpers backing ``tempestweb lint``/``check``/``type``/etc.

These commands run in a **user's** project (not the framework repo): they shell
out to ``ruff``, ``mypy`` and ``pytest``, preferring an executable already on
``PATH`` and falling back to ``uv run <tool>`` so a project-local virtualenv
works without activation.

The CLI layers tempestweb's typing conventions on top of whatever the project's
own ``[tool.ruff]`` / ``[tool.mypy]`` already declares — it never relaxes them.
The single knob is ``[quality] typing_strictness`` in ``tempestweb.toml``
(``lenient`` | ``standard`` | ``strict``), overridable per-invocation with
``--strictness``. ``Any`` is always a valid annotation, so ANN401 is never
enabled at any level: the levels enforce that things *are* annotated, never that
they avoid ``Any``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Literal

__all__ = [
    "DEFAULT_STRICTNESS",
    "VALID_STRICTNESS",
    "Strictness",
    "mypy_flags",
    "run_full_check",
    "run_mypy",
    "run_pytest",
    "run_ruff_check",
    "run_ruff_fix",
    "run_ruff_format",
    "ruff_ann_select",
]

Strictness = Literal["lenient", "standard", "strict"]
"""Allowed values for ``[quality] typing_strictness``."""

DEFAULT_STRICTNESS: Strictness = "standard"
"""The level used when a project declares no ``[quality]`` section."""

VALID_STRICTNESS: frozenset[str] = frozenset({"lenient", "standard", "strict"})
"""The set of accepted strictness levels, for config validation."""

# ANN rules layered onto ruff per level. ANN401 (Any) is intentionally never
# included — ``Any`` is a valid annotation. The levels enforce presence of
# annotations, escalating from public functions (standard) to every def
# (strict).
_RUFF_ANN_BY_LEVEL: dict[Strictness, list[str]] = {
    "lenient": [],
    "standard": ["ANN001", "ANN201", "ANN202", "ANN205", "ANN206"],
    "strict": [
        "ANN001",
        "ANN002",
        "ANN003",
        "ANN201",
        "ANN202",
        "ANN204",
        "ANN205",
        "ANN206",
    ],
}

# mypy flags layered on per level (additive over the project's [tool.mypy]).
_MYPY_FLAGS_BY_LEVEL: dict[Strictness, list[str]] = {
    "lenient": [],
    "standard": ["--ignore-missing-imports"],
    "strict": ["--strict"],
}


def ruff_ann_select(level: Strictness) -> list[str]:
    """Return the ruff ANN rule codes to add for a strictness level.

    Args:
        level: The resolved strictness level.

    Returns:
        The ANN codes to layer on (empty for ``"lenient"``). ANN401 is never
        present.
    """
    return list(_RUFF_ANN_BY_LEVEL[level])


def mypy_flags(level: Strictness) -> list[str]:
    """Return the extra mypy flags to add for a strictness level.

    Args:
        level: The resolved strictness level.

    Returns:
        The mypy flags to layer on top of the project's ``[tool.mypy]`` config
        (empty for ``"lenient"``).
    """
    return list(_MYPY_FLAGS_BY_LEVEL[level])


def _ann_args(level: Strictness) -> list[str]:
    """Build the ruff ``--extend-select`` args for a level, or ``[]``.

    Args:
        level: The resolved strictness level.

    Returns:
        ``["--extend-select", "ANN001,..."]`` for a level that adds ANN rules,
        or ``[]`` for the lenient level.
    """
    codes = ruff_ann_select(level)
    if not codes:
        return []
    return ["--extend-select", ",".join(codes)]


def _resolve(executable: str) -> list[str] | None:
    """Return an argv prefix invoking ``executable`` or ``None`` when absent.

    Preference order:

    1. ``executable`` on ``PATH`` directly (an activated venv, global install).
    2. ``uv run <executable>`` when ``uv`` is on ``PATH`` (handles project-local
       virtualenvs without requiring activation).

    Args:
        executable: The command name (``ruff`` / ``mypy`` / ``pytest``).

    Returns:
        An argv prefix to extend with extra arguments, or ``None`` when no
        runner could be found.
    """
    direct = shutil.which(executable)
    if direct is not None:
        return [direct]
    uv = shutil.which("uv")
    if uv is not None:
        return [uv, "run", executable]
    return None


def _execute(executable: str, args: list[str]) -> int:
    """Run ``executable args`` and return its exit code.

    Args:
        executable: The command to run.
        args: Extra arguments to forward.

    Returns:
        The child process exit code, or ``127`` when neither the executable nor
        ``uv`` is available.
    """
    argv = _resolve(executable)
    if argv is None:
        print(
            f"tempestweb: '{executable}' is not on PATH and 'uv' is unavailable. "
            f"Install it (or activate the project venv) and retry.",
            file=sys.stderr,
        )
        return 127
    return subprocess.call([*argv, *args])


def run_ruff_check(target: str, *, level: Strictness = DEFAULT_STRICTNESS) -> int:
    """Invoke ``ruff check <target>`` with the level's ANN rules.

    Args:
        target: The path passed verbatim to ruff.
        level: The strictness level controlling the layered ANN rules.

    Returns:
        The ruff exit code.
    """
    return _execute("ruff", ["check", *_ann_args(level), target])


def run_ruff_fix(
    target: str,
    *,
    unsafe: bool = False,
    level: Strictness = DEFAULT_STRICTNESS,
) -> int:
    """Apply every automatic ruff fix, then format the target.

    Runs two passes so the formatter sees the rewritten file:

    1. ``ruff check --fix [--unsafe-fixes] <target>`` — sort/dedupe imports,
       drop unused imports, normalize quotes, fix the autofixable lint rules.
    2. ``ruff format <target>`` — normalize indentation, line length and blanks.

    Both passes always run: ``ruff check --fix`` exits non-zero when residual
    (non-autofixable) violations remain even though it already rewrote what it
    could, so short-circuiting would skip formatting. The format pass therefore
    runs unconditionally and the lint exit code is surfaced afterwards.

    Args:
        target: The path passed verbatim to ruff.
        unsafe: When ``True``, also apply ruff's unsafe autofixes.
        level: The strictness level controlling the layered ANN rules.

    Returns:
        ``0`` when both passes succeed with nothing left to fix; otherwise the
        lint pass exit code, or the format pass exit code when the lint pass was
        clean.
    """
    check_args = ["check", "--fix", *_ann_args(level)]
    if unsafe:
        check_args.append("--unsafe-fixes")
    check_args.append(target)
    check_code = _execute("ruff", check_args)
    format_code = _execute("ruff", ["format", target])
    return check_code or format_code


def run_ruff_format(target: str, *, check: bool) -> int:
    """Invoke ``ruff format`` (write or check-only).

    Args:
        target: The path passed verbatim to ruff.
        check: When ``True``, run ``ruff format --check`` (read-only).

    Returns:
        The ruff exit code.
    """
    args = ["format"]
    if check:
        args.append("--check")
    args.append(target)
    return _execute("ruff", args)


def run_mypy(target: str, *, level: Strictness = DEFAULT_STRICTNESS) -> int:
    """Invoke ``mypy <target>`` with the level's strictness flags.

    Args:
        target: The path passed verbatim to mypy.
        level: The strictness level controlling the layered mypy flags.

    Returns:
        The mypy exit code.
    """
    return _execute("mypy", [*mypy_flags(level), target])


# pytest's exit code for "no tests were collected". A fresh scaffold ships no
# tests, so this must not fail the gate — it is coerced to success.
_PYTEST_NO_TESTS_EXIT = 5


def _coerce_pytest(code: int) -> int:
    """Map pytest's "no tests collected" exit (5) to success.

    Args:
        code: The raw pytest exit code.

    Returns:
        ``0`` when pytest merely found no tests; the code unchanged otherwise.
    """
    return 0 if code == _PYTEST_NO_TESTS_EXIT else code


def run_pytest(target: str | None) -> int:
    """Invoke ``pytest`` with an optional path filter.

    "No tests collected" (pytest exit 5) is treated as success so the command
    does not fail a project that has not written tests yet.

    Args:
        target: Optional pytest path filter. ``None`` runs the default suite.

    Returns:
        The pytest exit code, with exit 5 (no tests) coerced to ``0``.
    """
    args = [target] if target else []
    return _coerce_pytest(_execute("pytest", args))


def run_full_check(target: str, *, level: Strictness = DEFAULT_STRICTNESS) -> int:
    """Run the entire quality gate sequentially.

    Order: ``ruff check`` → ``ruff format --check`` → ``mypy`` → ``pytest``.
    Stops at the first non-zero exit code so failures surface fast.

    Args:
        target: The path inspected by every step — ruff/mypy lint it and pytest
            collects tests under it, so ``check --path <dir>`` stays scoped to
            that project instead of leaking into the current directory.
        level: The strictness level controlling the layered ANN rules and mypy
            flags.

    Returns:
        The first non-zero exit code, or ``0`` when every gate passed.
    """
    steps: list[tuple[str, list[str]]] = [
        ("ruff", ["check", *_ann_args(level), target]),
        ("ruff", ["format", "--check", target]),
        ("mypy", [*mypy_flags(level), target]),
        ("pytest", [target]),
    ]
    for executable, args in steps:
        print(f"$ {executable} {' '.join(args)}", file=sys.stderr)
        code = _execute(executable, args)
        if executable == "pytest":
            code = _coerce_pytest(code)
        if code != 0:
            return code
    return 0
