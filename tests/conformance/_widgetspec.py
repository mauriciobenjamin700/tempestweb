"""Introspect tempest_core widgets into specs that drive Mode C codegen.

Shared by the widget-style table generator (:mod:`._transpile_widget_styles`) and
the native widget-builder generator (:mod:`._transpile_widgets`). Everything here
runs at *generation* time against the installed core — it is test/tooling code,
not shipped in the wheel.

A :class:`WidgetSpec` captures what a builder needs: the IR ``type``, the wire
prop names with their bare-built default values, which props are event handlers,
whether the widget resolves a Material 3 style, and whether it holds children.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

from tempest_core import build
from tempest_core import widgets as _widgets
from tempest_core.widgets.base import Widget as WidgetBase

# Candidate arguments used to satisfy a widget's required fields when building a
# bare instance for introspection. Keyed by parameter name.
_CANDIDATE_ARGS: dict[str, Any] = {
    "label": "x",
    "content": "x",
    "value": "x",
    "children": [],
    "items": [],
    "options": [],
    "columns": [],
    "data": [],
    "tabs": [],
    "pages": [],
    "sections": [],
    "src": "x",
    "source": "x",
    "name": "home",
    "title": "x",
    "message": "x",
    "url": "x",
    "min": 0.0,
    "max": 1.0,
    "progress": 0.5,
    "count": 3,
    "index": 0,
    "length": 4,
}

#: Wire props that every node carries but a builder handles specially (not plain
#: passthrough kwargs): ``style`` is resolved, ``attrs`` defaults to a fresh map.
SPECIAL_PROPS: frozenset[str] = frozenset({"style", "attrs"})


@dataclass(frozen=True)
class WidgetSpec:
    """Everything the Mode C generators need about one core widget.

    Attributes:
        name: The widget class name (also the JS builder name).
        cls: The widget class.
        ir_type: The IR node ``type`` the widget builds to.
        props: Wire prop name → bare-built default (JSON-able), excluding the
            special props (``style``/``attrs``), handler props, and required
            props (which have no default — see :attr:`required`).
        required: Wire prop names that map to a required widget field, so the
            builder must not fabricate a default (the caller passes them).
        handlers: The ``on_*`` prop names the widget declares.
        styled: Whether a bare build resolves a non-null ``style``.
        has_children: Whether the widget accepts a ``children`` argument.
        build_args: The candidate kwargs used to build a bare instance.
    """

    name: str
    cls: type[WidgetBase]
    ir_type: str
    props: dict[str, Any]
    required: tuple[str, ...]
    handlers: tuple[str, ...]
    styled: bool
    has_children: bool
    build_args: dict[str, Any] = field(default_factory=dict)


def _spec_for(name: str, cls: type[WidgetBase]) -> WidgetSpec | None:
    """Build a :class:`WidgetSpec` for a widget class, or ``None`` if unbuildable."""
    try:
        params = inspect.signature(cls).parameters
    except (TypeError, ValueError):
        return None
    # Required fields have no default — the builder must not fabricate one.
    required_fields = {
        fname for fname, finfo in cls.model_fields.items() if finfo.is_required()
    }
    # Supply candidates for REQUIRED fields only, so optional props keep their
    # true core defaults in the bare build (not an overriding candidate value).
    build_args = {
        p: _CANDIDATE_ARGS[p]
        for p in params
        if p in _CANDIDATE_ARGS and p in required_fields
    }
    try:
        node = build(cls(**build_args))
    except Exception:  # noqa: BLE001 - unbuildable widgets are simply skipped
        return None
    wire = node.model_dump(mode="json")["props"]
    handlers = tuple(k for k in wire if k.startswith("on_"))
    style = wire.get("style")
    styled = style is not None and any(v is not None for v in style.values())
    passthrough = {
        key: value
        for key, value in wire.items()
        if key not in SPECIAL_PROPS and not key.startswith("on_")
    }
    required = tuple(sorted(k for k in passthrough if k in required_fields))
    props = {k: v for k, v in passthrough.items() if k not in required_fields}
    return WidgetSpec(
        name=name,
        cls=cls,
        ir_type=node.type,
        props=props,
        required=required,
        handlers=handlers,
        styled=styled,
        # The IR node always uses a `children` list; a widget is a container if
        # it accepts children (`children`) or a single `child` (wrapped into the
        # list by the core). Either way the JS builder takes a `children` array.
        has_children="children" in params or "child" in params,
        build_args=build_args,
    )


def buildable_widgets() -> dict[str, WidgetSpec]:
    """Return specs for every buildable ``tempest_core`` widget, by name.

    Returns:
        A name-sorted mapping of widget name to :class:`WidgetSpec`, covering
        every ``Widget`` subclass that builds with the candidate arguments.
    """
    specs: dict[str, WidgetSpec] = {}
    for name in sorted(dir(_widgets)):
        if not name[0].isupper():
            continue
        cls = getattr(_widgets, name)
        if not (inspect.isclass(cls) and issubclass(cls, WidgetBase)):
            continue
        if cls is WidgetBase:
            continue
        spec = _spec_for(name, cls)
        if spec is not None:
            specs[name] = spec
    return specs
