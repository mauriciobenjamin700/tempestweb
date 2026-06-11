"""Core engine: intermediate representation and the reconciler.

The reconciler is renderer-agnostic — it turns widget trees into IR nodes and
diffs them into patches that any leaf renderer can apply.
"""

from tempestweb._core.core.introspection import (
    event_catalog,
    introspect,
    widget_catalog,
)
from tempestweb._core.core.ir import (
    Insert,
    Node,
    Patch,
    Path,
    Remove,
    Reorder,
    Replace,
    Scene,
    Update,
)
from tempestweb._core.core.reconciler import build, build_scene, diff, diff_scene
from tempestweb._core.core.state import App, OverlayEntry

__all__ = [
    "Path",
    "Node",
    "Scene",
    "Replace",
    "Update",
    "Insert",
    "Remove",
    "Reorder",
    "Patch",
    "build",
    "diff",
    "build_scene",
    "diff_scene",
    "App",
    "OverlayEntry",
    "introspect",
    "widget_catalog",
    "event_catalog",
]
