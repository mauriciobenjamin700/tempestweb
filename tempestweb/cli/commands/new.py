"""``tempestweb new`` — scaffold a runnable project tree.

Thin orchestration over :mod:`tempestweb.cli.scaffold`: validate the name, write
the files, and (unless skipped) prove the scaffold is runnable by rendering its
initial view.
"""

from __future__ import annotations

from pathlib import Path

from tempestweb.cli.loader import load_app, render_initial_tree
from tempestweb.cli.scaffold import ScaffoldResult, scaffold_project

__all__ = ["NewError", "create_project"]


class NewError(RuntimeError):
    """Raised when a project cannot be scaffolded."""


def create_project(
    name: str,
    *,
    parent: str | Path = ".",
    force: bool = False,
    verify: bool = True,
) -> ScaffoldResult:
    """Scaffold a new project and optionally verify it renders.

    Args:
        name: The project name / directory.
        parent: The directory to create the project inside. Defaults to the cwd.
        force: Overwrite a non-empty target directory when ``True``.
        verify: When ``True`` (default), load the scaffolded ``app.py`` and
            render its initial view to confirm the project is runnable.

    Returns:
        The :class:`ScaffoldResult` describing the created tree.

    Raises:
        NewError: If the name is empty or the scaffold fails verification.
    """
    if not name or not name.strip():
        raise NewError("project name must not be empty")

    try:
        result = scaffold_project(name, parent=parent, force=force)
    except Exception as exc:  # noqa: BLE001 - normalize to NewError for the CLI
        raise NewError(str(exc)) from exc

    if verify:
        entrypoint = result.root / "app.py"
        try:
            loaded = load_app(entrypoint)
            render_initial_tree(loaded)
        except Exception as exc:  # noqa: BLE001 - scaffold must be runnable
            raise NewError(f"scaffolded project is not runnable: {exc}") from exc

    return result
