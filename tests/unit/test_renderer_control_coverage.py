"""The audit of #130/#143, as a test: no interactive core widget renders mute.

``client/dom.js`` decides what tag each IR widget becomes and which of them report
a ``change``. A widget the core gives ``value``/``on_change``/``checked`` to and
the renderer does not know about draws an anonymous ``<div>``: it looks roughly
right (the base sheet styles by ``data-tw-type``), takes no input, and tells the
app nothing. That failure is silent in every direction — no exception, no lint, no
type error — which is why it survived three rounds and needed a hand audit twice.

This is that audit, run on every commit: every interactive widget the core
declares is either a control the renderer draws, or a listed exception whose
reason is itself checked against the core.
"""

from __future__ import annotations

import re
from pathlib import Path

from tempest_core import Component
from tempest_core.widgets.base import Widget

#: Props that make a widget interactive: the reader changes it, or it carries a
#: value the app binds. The criterion the #130 audit asked for, widened by the
#: two-thumb pair a RangeSlider uses instead of ``value``.
INTERACTIVE_PROPS: frozenset[str] = frozenset(
    {"value", "on_change", "checked", "selected", "mask", "low", "high"}
)

#: Interactive widgets the renderer deliberately does not draw as a control, and
#: the reason each one is legitimate. A reason is not prose here — every one of
#: them is verified against the core below, so an exception cannot outlive it.
DOCUMENTED_EXCEPTIONS: dict[str, str] = {
    # `value` is a reading, not a control: a bar shows progress, nobody drags it.
    "ProgressBar": "display-only",
    # Both hold IR children, so a renderer-owned tab strip would land on a child
    # index the patch paths address. The strip is a TabBar beside them.
    "TabView": "holds-ir-children",
    "RouteDrawer": "holds-ir-children",
}

_CLIENT_DOM: Path = Path(__file__).resolve().parents[2] / "client" / "dom.js"


def _tag_table() -> dict[str, str]:
    """Parse ``TAG_BY_TYPE`` out of the DOM renderer.

    Returns:
        The IR type to HTML tag mapping the renderer declares.
    """
    dom = _CLIENT_DOM.read_text(encoding="utf-8")
    start = dom.index("const TAG_BY_TYPE = Object.freeze({")
    table = dom[start : dom.index("});", start)]
    return dict(re.findall(r'^\s*(\w+): "(\w+)"', table, re.M))


def _declared_set(name: str) -> frozenset[str]:
    """Parse one exported ``new Set([...])`` of IR type names out of the renderer.

    Args:
        name: The exported constant's name.

    Returns:
        The IR type names it lists.
    """
    dom = _CLIENT_DOM.read_text(encoding="utf-8")
    marker = f"export const {name} = new Set(["
    assert marker in dom, f"client/dom.js no longer declares {name}"
    start = dom.index(marker)
    return frozenset(re.findall(r'"(\w+)"', dom[start : dom.index("]);", start)]))


def _interactive_widgets() -> dict[str, type[Widget]]:
    """Every core IR widget that declares an interactive prop.

    ``Component`` subclasses are excluded: they lower to primitives and never
    reach the renderer as themselves. Private bases (``_FieldWidget``) are
    excluded for the same reason — they are never a node type.

    Returns:
        ``{type name: widget class}``.
    """
    found: dict[str, type[Widget]] = {}

    def walk(cls: type[Widget]) -> None:
        """Recurse the widget subclass tree, recording interactive widgets.

        Args:
            cls: The subtree root to descend from.
        """
        for subclass in cls.__subclasses__():
            name = subclass.__name__
            interactive = INTERACTIVE_PROPS & set(subclass.model_fields)
            lowered = issubclass(subclass, Component)
            if interactive and not name.startswith("_") and not lowered:
                found[name] = subclass
            walk(subclass)

    walk(Widget)
    return found


def test_every_interactive_widget_is_drawn_or_documented() -> None:
    """No interactive core widget renders as an anonymous div by omission."""
    reporting = _declared_set("CHANGE_REPORTING_TYPES") | _declared_set(
        "NATIVE_CONTROL_TYPES"
    )
    mute = sorted(
        name
        for name in _interactive_widgets()
        if name not in reporting and name not in DOCUMENTED_EXCEPTIONS
    )
    assert not mute, (
        f"{len(mute)} interactive widget(s) the renderer does not know about: "
        f"{mute}. Each renders an anonymous <div>: styled about right, unusable, "
        "and silent. Give it a tag in TAG_BY_TYPE plus a branch in "
        "applyControlProps, or add it to DOCUMENTED_EXCEPTIONS with a reason this "
        "test can check."
    )


def test_declared_control_types_are_real_core_widgets() -> None:
    """Nothing in the renderer's sets is a widget the core no longer has.

    A stale name is not harmless: the set feeds Mode C's handler mapping, so a
    renamed widget would keep an entry that matches nothing while the widget it
    replaced falls through to ``click``.
    """
    known = {cls.__name__ for cls in _walk_all_widgets()}
    declared = _declared_set("CHANGE_REPORTING_TYPES") | _declared_set(
        "NATIVE_CONTROL_TYPES"
    )
    assert not sorted(declared - known), (
        f"renderer declares widgets the core does not have: {sorted(declared - known)}"
    )


def test_native_controls_all_have_a_tag() -> None:
    """Every declared native control has an explicit tag, not the div fallback."""
    tags = _tag_table()
    controls = _declared_set("NATIVE_CONTROL_TYPES")
    missing = sorted(name for name in controls if name not in tags)
    assert not missing, f"native controls falling back to <div>: {missing}"


def test_documented_exceptions_still_earn_their_exception() -> None:
    """Each exception's reason is checked against the core, not trusted."""
    widgets = _interactive_widgets()
    for name, reason in DOCUMENTED_EXCEPTIONS.items():
        assert name in widgets, f"{name} is no longer an interactive widget"
        fields = set(widgets[name].model_fields)
        if reason == "display-only":
            assert not {f for f in fields if f.startswith("on_")}, (
                f"{name} now declares a handler, so it is no longer display-only "
                "— it needs a control, not an exception"
            )
        elif reason == "holds-ir-children":
            assert fields & {"child", "children", "drawer", "fields"}, (
                f"{name} no longer holds IR children, so the renderer can draw its "
                "own — drop the exception and give it a tag"
            )
        else:  # pragma: no cover — a typo in the table, not a code path
            raise AssertionError(f"unknown exception reason: {reason}")


def _walk_all_widgets() -> list[type[Widget]]:
    """Every ``Widget`` subclass currently imported, flattened.

    Returns:
        The widget classes, in discovery order.
    """
    out: list[type[Widget]] = []

    def walk(cls: type[Widget]) -> None:
        """Recurse the subclass tree, appending each class found.

        Args:
            cls: The subtree root to descend from.
        """
        for subclass in cls.__subclasses__():
            out.append(subclass)
            walk(subclass)

    walk(Widget)
    return out
