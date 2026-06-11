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

from tempestweb.devserver.reload import ReloadEvent, ReloadKind, ReloadSignal
from tempestweb.devserver.watcher import (
    DEFAULT_WATCH_SUFFIXES,
    ChangeStream,
    FileWatcher,
)

__all__ = [
    "DEFAULT_WATCH_SUFFIXES",
    "ChangeStream",
    "FileWatcher",
    "ReloadEvent",
    "ReloadKind",
    "ReloadSignal",
]
