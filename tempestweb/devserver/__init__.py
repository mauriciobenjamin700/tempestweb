"""tempestweb dev server — transport-agnostic file watch + reload.

See ``docs/plan.md`` §5. This package owns the two halves of the dev loop:

- :class:`ReloadSignal` — a publish/subscribe hub that decouples *"something
  changed"* from *"how the reload reaches the app"*. A transport subscribes; the
  watcher (or the interactive cockpit) triggers.
- :class:`FileWatcher` — observes a project directory and triggers the signal on
  every reload-worthy change.

Neither half names a transport. Mode A wires the signal to a browser reload; Mode
B wires it to a session restart. The watcher and the signal stay identical.
"""

from typing import TYPE_CHECKING, Any

from tempestweb.devserver.reload import ReloadEvent, ReloadKind, ReloadSignal
from tempestweb.devserver.watcher import (
    DEFAULT_WATCH_SUFFIXES,
    ChangeStream,
    FileWatcher,
)

if TYPE_CHECKING:
    # The dev HTTP server depends on Starlette (the ``server`` extra). Import it
    # under TYPE_CHECKING for tooling; at runtime it is loaded lazily by
    # ``__getattr__`` so a Mode A *build* (which only needs the watcher/signal)
    # never pulls the server stack.
    from tempestweb.devserver.http import (
        create_dev_app,
        livereload_frames,
        make_server,
        serve,
    )

#: Symbols loaded lazily on first access, keyed to their defining submodule.
_LAZY: dict[str, str] = {
    "create_dev_app": "tempestweb.devserver.http",
    "inject_livereload": "tempestweb.devserver.http",
    "livereload_frames": "tempestweb.devserver.http",
    "make_server": "tempestweb.devserver.http",
    "serve": "tempestweb.devserver.http",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401 - PEP 562 lazy re-export seam
    """Lazily import the Starlette-backed dev HTTP server on first access.

    Args:
        name: The attribute being accessed on the package.

    Returns:
        The resolved symbol from :mod:`tempestweb.devserver.http`.

    Raises:
        AttributeError: If ``name`` is not a known lazy export.
    """
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    attr = getattr(importlib.import_module(module_path), name)
    globals()[name] = attr  # cache so subsequent lookups skip __getattr__
    return attr


__all__ = [
    "DEFAULT_WATCH_SUFFIXES",
    "ChangeStream",
    "FileWatcher",
    "ReloadEvent",
    "ReloadKind",
    "ReloadSignal",
    "create_dev_app",
    "inject_livereload",
    "livereload_frames",
    "make_server",
    "serve",
]
