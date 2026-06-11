"""Vendored renderer-agnostic core from tempestroid.

This package is a **temporary vendored copy** of tempestroid's renderer-agnostic
engine: the IR, reconciler, state model, style model, widgets, components and the
cross-cutting helpers (animation, i18n, navigation, theme, validators). It carries
no platform-coupled code (no Qt, no JNI, no Android) so it imports cleanly under
CPython, Pyodide and a headless server.

It will be replaced by a proper ``tempest-core`` PyPI dependency once that package
is extracted from tempestroid. Until then, ``tempestweb`` imports the engine from
here so overnight work never has to touch the tempestroid repository.

Do not edit modules under this package by hand — they are a mechanical copy. Fix
upstream in tempestroid and re-vendor.
"""

from tempestweb._core.animation import AnimationController
from tempestweb._core.core import (
    App,
    Insert,
    Node,
    OverlayEntry,
    Patch,
    Path,
    Remove,
    Reorder,
    Replace,
    Scene,
    Update,
    build,
    build_scene,
    diff,
    diff_scene,
    event_catalog,
    introspect,
    widget_catalog,
)
from tempestweb._core.i18n import Locale, t, translate
from tempestweb._core.navigation import NavStack, Route, routes_from_path
from tempestweb._core.style import Style
from tempestweb._core.theme import MediaQueryData, Theme, ThemeMode
from tempestweb._core.widgets import (
    Button,
    Column,
    Component,
    Container,
    Row,
    Text,
    Widget,
)

__all__ = [
    "AnimationController",
    "App",
    "Button",
    "Column",
    "Component",
    "Container",
    "Insert",
    "Locale",
    "MediaQueryData",
    "NavStack",
    "Node",
    "OverlayEntry",
    "Patch",
    "Path",
    "Remove",
    "Reorder",
    "Replace",
    "Route",
    "Row",
    "Scene",
    "Style",
    "Text",
    "Theme",
    "ThemeMode",
    "Update",
    "Widget",
    "build",
    "build_scene",
    "diff",
    "diff_scene",
    "event_catalog",
    "introspect",
    "routes_from_path",
    "t",
    "translate",
    "widget_catalog",
]
