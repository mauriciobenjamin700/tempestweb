"""Load a tempestweb project's application module.

A tempestweb project is just a Python module (``app.py`` by convention) that
exposes two callables, mirroring the canonical counter example:

- ``make_state() -> State`` — build the initial application state.
- ``view(app) -> Widget`` — render the widget tree from ``app.state``.

This module loads that file, validates the contract, and offers a render helper
that proves the project is *runnable* by building its initial widget tree into a
core :class:`~tempest_core.Node`. The CLI uses this both to validate scaffold
output and as the entrypoint each transport will drive.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tempest_core import App, Node, Widget, build

__all__ = ["LoadedApp", "ProjectLoadError", "load_app", "render_initial_tree"]


class ProjectLoadError(RuntimeError):
    """Raised when a project module cannot be loaded or is missing its contract.

    This covers a missing entrypoint file, an import error inside the module, or
    the absence of the required ``make_state`` / ``view`` callables.
    """


@dataclass(slots=True)
class LoadedApp:
    """A successfully loaded project module and its contract callables.

    Attributes:
        path: The resolved path of the loaded entrypoint module.
        module: The imported module object.
        make_state: The project's ``make_state`` callable.
        view: The project's ``view`` callable.
    """

    path: Path
    module: Any
    make_state: Callable[[], Any]
    view: Callable[[App[Any]], Widget]


def load_app(entrypoint: str | Path) -> LoadedApp:
    """Import a project entrypoint and validate its public contract.

    Args:
        entrypoint: Path to the project's ``app.py`` (or any module exposing
            ``make_state`` and ``view``).

    Returns:
        A :class:`LoadedApp` bundling the module and its contract callables.

    Raises:
        ProjectLoadError: If the file does not exist, fails to import, or does
            not expose callable ``make_state`` and ``view`` attributes.
    """
    path = Path(entrypoint).resolve()
    if not path.is_file():
        raise ProjectLoadError(f"entrypoint not found: {path}")

    # Make the synthetic module name unique per resolved path so loading several
    # projects (each with its own ``app.py``) in one process never reuses a stale
    # module object from ``sys.modules``.
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    module_name = f"tempestweb_app_{path.stem}_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ProjectLoadError(f"cannot build an import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    # Register before exec so `@dataclass` (which resolves field types via
    # ``sys.modules[cls.__module__]`` under ``from __future__ import annotations``)
    # and any decorator that inspects the defining module work correctly.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import-time failure
        sys.modules.pop(module_name, None)
        raise ProjectLoadError(f"failed to import {path}: {exc}") from exc

    make_state = getattr(module, "make_state", None)
    view = getattr(module, "view", None)
    if not callable(make_state):
        raise ProjectLoadError(f"{path} must define a callable `make_state`")
    if not callable(view):
        raise ProjectLoadError(f"{path} must define a callable `view`")

    return LoadedApp(path=path, module=module, make_state=make_state, view=view)


def render_initial_tree(loaded: LoadedApp) -> Node:
    """Build the project's initial widget tree into a core IR node.

    This is the cheapest possible proof that a project is runnable: it builds the
    initial state, calls ``view`` with a minimal :class:`~tempest_core.App`
    handle, and reconciles the result into a :class:`~tempest_core.Node`. No
    transport, browser or server is involved.

    Args:
        loaded: A project loaded via :func:`load_app`.

    Returns:
        The reconciled root :class:`~tempest_core.Node` of the initial view.

    Raises:
        ProjectLoadError: If ``view`` does not return a widget or building the
            tree fails.
    """
    state = loaded.make_state()
    app: App[Any] = App(
        state=state,
        view=loaded.view,
        apply_patches=lambda _patches: None,
    )
    try:
        widget = loaded.view(app)
        return build(widget)
    except Exception as exc:  # noqa: BLE001 - surface any render failure
        raise ProjectLoadError(
            f"failed to render the initial view of {loaded.path}: {exc}"
        ) from exc
