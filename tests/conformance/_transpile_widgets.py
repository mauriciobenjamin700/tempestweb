"""Regenerate the Mode C native widget builders from tempest_core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_widgets

Emits ``client/transpile/widgets.gen.js`` — one native-JS IR builder per
buildable ``tempest_core`` widget (see :mod:`._widgetspec`). Each builder returns
a serialized IR node in the core's wire shape: passthrough props (camelCase args →
snake_case wire keys) with their bare-built defaults, ``attrs`` defaulting to a
fresh map, a resolved Material 3 ``style`` for styled widgets, and event handlers
stashed off the wire in a non-wire ``__handlers`` map keyed by DOM event type (the
runtime dispatches from it). The table is derived from the core — same
regenerable-golden guarantee as the wire fixtures — never hand-typed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tests.conformance._widgetspec import (
    LAZY_WIDGETS,
    WidgetSpec,
    buildable_widgets,
)

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
WIDGETS_MODULE: Path = CLIENT_DIR / "widgets.gen.js"

_NONE = "_"


# IR types the shared renderer (client/dom.js) draws as a native form control
# firing DOM `input`/`change`. Every other widget is a div/span whose interaction
# is a `click`, so a change/toggle handler on it binds to click.
def _native_input_types() -> frozenset[str]:
    """Widgets the DOM renderer draws as a real form control.

    Read from ``NATIVE_CONTROL_TYPES`` in ``client/dom.js`` — the renderer's own
    declaration — rather than inferred here, because inference is what drifts. It
    used to read the tag table and add ``Checkbox`` by hand; that hand-add is the
    whole tell, since a Switch, an Autocomplete and the three pickers are
    ``<label>``s wrapping the control and a RangeSlider a div holding two range
    inputs. Every one of them would have been read as a div, so its ``on_change``
    would bind to ``click``: the widget renders, accepts input, and never tells
    the app. Measured on ``MaskedInput``, whose CEP field in
    ``examples/br-cadastro`` swallowed every keystroke (#142), and on the ten
    widgets of #143.

    Returns:
        The IR type names whose ``on_change`` binds to ``input``/``change``.

    Raises:
        ValueError: If ``client/dom.js`` no longer declares the set — a rename
            there must fail loudly here instead of yielding an empty set, which
            would silently map every value handler onto ``click``.
    """
    return _declared_types("NATIVE_CONTROL_TYPES")


def _declared_types(name: str) -> frozenset[str]:
    """Read one widget-type set the DOM renderer declares.

    Args:
        name: The exported constant's name in ``client/dom.js``.

    Returns:
        The IR type names it lists.

    Raises:
        ValueError: If the renderer no longer declares it — a rename there must
            fail loudly here instead of yielding an empty set, which would
            silently map every value handler onto ``click``.
    """
    dom = (Path(__file__).resolve().parents[2] / "client" / "dom.js").read_text(
        encoding="utf-8"
    )
    marker = f"export const {name} = new Set(["
    if marker not in dom:
        raise ValueError(f"client/dom.js no longer declares {name}")
    start = dom.index(marker)
    declaration = dom[start : dom.index("]);", start)]
    return frozenset(re.findall(r'"(\w+)"', declaration))


def _change_reporting_types() -> frozenset[str]:
    """Widgets whose ``on_change`` the renderer reports as a ``change`` event.

    A superset of the native controls: a ``TabBar`` is a div of buttons, so no
    tag says "change", yet a tab click is reported as one. Read from the renderer
    for the same reason as :func:`_native_input_types` — the alternative is a
    second list here that drifts from the one that does the reporting.

    Returns:
        The IR type names whose ``on_change`` binds to a ``change`` event.
    """
    declared = _declared_types("CHANGE_REPORTING_TYPES")
    return frozenset(declared | _NATIVE_INPUT_TYPES)


_NATIVE_INPUT_TYPES: frozenset[str] = _native_input_types()
_CHANGE_REPORTING_TYPES: frozenset[str] = _change_reporting_types()

# Handler props whose DOM event is fixed regardless of the widget's rendered tag.
_FIXED_HANDLER_EVENTS: dict[str, list[str]] = {
    "on_click": ["click"],
    "on_submit": ["submit"],
    "on_tap": ["tap"],
    "on_long_press": ["long_press"],
    "on_swipe": ["swipe"],
    "on_double_tap": ["double_tap"],
    "on_pan": ["pan"],
    "on_scale": ["scale"],
}


def _events_for(handler: str, ir_type: str) -> list[str]:
    """Return the DOM event types a handler binds, given the widget's IR type.

    Value handlers (``on_change``/``on_input``/``on_toggle``) bind to the native
    ``input``/``change`` events on widgets the renderer draws as a real form
    control (see :data:`_NATIVE_INPUT_TYPES`), and to ``change`` alone on the ones
    it reports a change for without being a control (a ``TabBar``'s tab click).
    On everything else they bind to ``click``. Other handlers use a fixed mapping,
    falling back to the ``on_``-stripped name.

    Args:
        handler: The ``on_*`` prop name.
        ir_type: The widget's IR node type.

    Returns:
        The DOM event type(s) that should invoke the handler.
    """
    if handler in ("on_change", "on_input", "on_toggle"):
        if ir_type in _NATIVE_INPUT_TYPES:
            return ["input", "change"] if handler != "on_input" else ["input"]
        if ir_type in _CHANGE_REPORTING_TYPES:
            return ["change"]
        return ["click"]
    if handler in _FIXED_HANDLER_EVENTS:
        return _FIXED_HANDLER_EVENTS[handler]
    return [handler.removeprefix("on_")]


def _camel(name: str) -> str:
    """Convert a snake_case wire prop name to a camelCase JS argument name."""
    head, *tail = name.split("_")
    return head + "".join(part.title() for part in tail)


def _lit(value: Any) -> str:
    """Render a JSON-able default value as a JS literal (JSON is valid JS)."""
    return json.dumps(value, ensure_ascii=False)


def _variant_axis(spec: WidgetSpec) -> str | None:
    """Return the wire key of the widget's variant axis, if any."""
    keys = set(spec.props) | set(spec.required)
    if "field_variant" in keys:
        return "field_variant"
    if "variant" in keys:
        return "variant"
    return None


def _is_validated_field(spec: WidgetSpec) -> bool:
    """Return whether the widget resolves its style against an invalid state.

    A field carrying an ``error`` message is *invalid*, and the core repaints its
    border and text in the ``error`` role while building it — a rule that lives
    in the built style, not in the stylesheet, so a passthrough builder drops it
    silently. Only a widget with both a field variant and an ``error`` prop has
    that state (``Input`` today).

    Args:
        spec: The introspected widget.

    Returns:
        True when the builder must resolve through ``resolveFieldStyle``.
    """
    keys = set(spec.props) | set(spec.required)
    return _variant_axis(spec) == "field_variant" and "error" in keys


def _children_expr(spec: WidgetSpec) -> str:
    """Emit the expression that folds the widget's child slots into the IR array.

    A lazy scroller has no child slot at all: its items are produced by running
    ``item_builder`` over the resolved window, so its expression is the
    ``lazyChildren`` call that mirrors the core.

    A node always carries one flat ``children`` list, but the Python slot it
    comes from varies: ``Column`` declares ``children`` (already a list),
    ``Container`` declares ``child`` (one widget or ``None``), ``Form`` declares
    ``fields``, and ``RouteDrawer`` declares ``child`` then ``drawer``. The
    builder therefore takes the *Python* names and folds them here, in
    declaration order, so a view written against the core builds the same tree
    in Mode C as in Modes A and B.

    Args:
        spec: The widget's spec.

    Returns:
        A JS expression evaluating to the node's ``children`` array.
    """
    if spec.name in LAZY_WIDGETS:
        return "lazyChildren(key, itemBuilder, itemCount, window, windowSize)"
    parts = [
        _camel(name) if is_list else f"({_camel(name)} == null ? [] : [{_camel(name)}])"
        for name, is_list in spec.child_fields
    ]
    if not parts:
        return "[]"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}.concat({', '.join(parts[1:])})"


def _builder(spec: WidgetSpec) -> str:
    """Emit the JS source for one widget's builder function.

    A styled widget's builder takes a ``theme`` argument. ``theme`` never crosses
    the wire — the core drops it when serializing — but it decides which mode's
    leaf of the style table the widget resolves from, so the builder has to accept
    it. Without it Mode C could not even be *asked* for dark: the table was baked
    light and the kwarg was refused (tempestweb#106).

    Args:
        spec: The widget's spec, from the shared widget table.

    Returns:
        The builder function's JS source.
    """
    # All wire prop names the builder writes through (required + defaulted).
    wire_props = sorted([*spec.required, *spec.props])

    # Destructured args: required props (no default) first, then defaulted
    # passthrough props, key, attrs, style, children (if any), handler args.
    args: list[str] = [_camel(prop) for prop in spec.required]
    args.append("key = null")
    for prop in sorted(spec.props):
        args.append(f"{_camel(prop)} = {_lit(spec.props[prop])}")
    args.append("attrs = {}")
    args.append("style = null")
    if spec.styled:
        args.append("theme = null")
    for name, is_list in spec.child_fields:
        args.append(f"{_camel(name)} = {'[]' if is_list else 'null'}")
    for handler in spec.handlers:
        args.append(f"{_camel(handler)} = null")

    # Wire props object: attrs, passthrough props (snake wire key = camel arg),
    # each handler prop and live callable forced null on the wire (they never
    # cross the boundary), and the resolved/passthrough style.
    lines: list[str] = ["      attrs,"]
    for prop in wire_props:
        value = "null" if prop in spec.callable_props else _camel(prop)
        lines.append(f"      {prop}: {value},")
    for handler in spec.handlers:
        lines.append(f"      {handler}: null,")
    if spec.styled:
        keys = set(spec.props) | set(spec.required)
        variant_key = _variant_axis(spec)
        variant_expr = _camel(variant_key) if variant_key else f'"{_NONE}"'
        size_expr = "size" if "size" in keys else f'"{_NONE}"'
        scheme_expr = "colorScheme" if "color_scheme" in keys else f'"{_NONE}"'
        if _is_validated_field(spec):
            style_expr = (
                f'resolveFieldStyle("{spec.name}", {variant_expr}, '
                f"{size_expr}, {scheme_expr}, error, style, theme)"
            )
        else:
            style_expr = (
                f'resolveWidgetStyle("{spec.name}", {variant_expr}, '
                f"{size_expr}, {scheme_expr}, style, theme)"
            )
    else:
        style_expr = "style"
    lines.append(f"      style: {style_expr},")
    props_block = "\n".join(sorted(lines))

    children_expr = _children_expr(spec)

    # Non-wire handler map: DOM event type -> the live closure.
    handler_entries: list[str] = []
    for handler in spec.handlers:
        arg = _camel(handler)
        for event in _events_for(handler, spec.ir_type):
            handler_entries.append(f'"{event}": {arg}')
    handlers_field = ""
    if handler_entries:
        handlers_field = "\n    __handlers: { " + ", ".join(handler_entries) + " },"

    return (
        f"/**\n"
        f" * Build a `{spec.name}` IR node (type `{spec.ir_type}`).\n"
        f" * @param {{Object}} [args]  Widget props (handlers stashed off-wire).\n"
        f' * @returns {{import("../transport.js").Node}}\n'
        f" */\n"
        f"export function {spec.name}({{ {', '.join(args)} }} = {{}}) {{\n"
        f"  return {{\n"
        f'    type: "{spec.ir_type}",\n'
        f"    key,\n"
        f"    props: {{\n{props_block}\n    }},\n"
        f"    children: {children_expr},{handlers_field}\n"
        f"  }};\n"
        f"}}"
    )


def render_module_text() -> str:
    """Render the full widgets.gen.js module source."""
    specs = buildable_widgets()
    header = (
        "// widgets.gen.js — GENERATED from tempest_core by tempestweb transpile "
        "(Mode C).\n"
        "// One native-JS IR builder per buildable core widget. Handlers are "
        "stashed in a\n"
        "// non-wire `__handlers` map (DOM event type -> closure); the runtime "
        "dispatches from it.\n"
        "// Regenerate: python -m tests.conformance._transpile_widgets. Do not "
        "edit.\n\n"
        "import { lazyChildren, resolveFieldStyle, resolveWidgetStyle, Style } "
        'from "./widget-support.js";\n'
        'export { Color, Edge, Style } from "./widget-support.js";\n\n'
        "// `Style` is re-exported for apps; reference it so linters see the "
        "import as used.\n"
        "void Style;\n"
    )
    builders = "\n\n".join(_builder(spec) for spec in specs.values())
    return f"{header}\n{builders}\n"


def write_module() -> Path:
    """Write widgets.gen.js to disk and return its path."""
    WIDGETS_MODULE.write_text(render_module_text(), encoding="utf-8")
    return WIDGETS_MODULE


def main() -> None:
    """Regenerate the widget-builder module and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
