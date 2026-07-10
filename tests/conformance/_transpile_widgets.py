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
from pathlib import Path
from typing import Any

from tests.conformance._widgetspec import WidgetSpec, buildable_widgets

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
WIDGETS_MODULE: Path = CLIENT_DIR / "widgets.gen.js"

_NONE = "_"

# IR types the shared renderer (client/dom.js TAG_BY_TYPE) renders as a native
# form control that fires DOM `input`/`change`. Every other widget is a div/span
# whose interaction is a `click`, so a change/toggle handler on it binds to click.
_NATIVE_INPUT_TYPES: frozenset[str] = frozenset({"Input", "Checkbox"})

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
    ``input``/``change`` events only on widgets the renderer draws as a real form
    control (see :data:`_NATIVE_INPUT_TYPES`); on every other widget — a div/span
    toggle like ``Switch`` — they bind to ``click``. Other handlers use a fixed
    mapping, falling back to the ``on_``-stripped name.

    Args:
        handler: The ``on_*`` prop name.
        ir_type: The widget's IR node type.

    Returns:
        The DOM event type(s) that should invoke the handler.
    """
    if handler in ("on_change", "on_input", "on_toggle"):
        if ir_type in _NATIVE_INPUT_TYPES:
            return ["input", "change"] if handler != "on_input" else ["input"]
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


def _builder(spec: WidgetSpec) -> str:
    """Emit the JS source for one widget's builder function."""
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
    if spec.has_children:
        args.append("children = []")
    for handler in spec.handlers:
        args.append(f"{_camel(handler)} = null")

    # Wire props object: attrs, passthrough props (snake wire key = camel arg),
    # each handler prop forced null on the wire, and the resolved/passthrough style.
    lines: list[str] = ["      attrs,"]
    for prop in wire_props:
        lines.append(f"      {prop}: {_camel(prop)},")
    for handler in spec.handlers:
        lines.append(f"      {handler}: null,")
    if spec.styled:
        keys = set(spec.props) | set(spec.required)
        variant_key = _variant_axis(spec)
        variant_expr = _camel(variant_key) if variant_key else f'"{_NONE}"'
        size_expr = "size" if "size" in keys else f'"{_NONE}"'
        scheme_expr = "colorScheme" if "color_scheme" in keys else f'"{_NONE}"'
        style_expr = (
            f'resolveWidgetStyle("{spec.name}", {variant_expr}, '
            f"{size_expr}, {scheme_expr}, style)"
        )
    else:
        style_expr = "style"
    lines.append(f"      style: {style_expr},")
    props_block = "\n".join(sorted(lines))

    children_expr = "children" if spec.has_children else "[]"

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
        'import { resolveWidgetStyle, Style } from "./widget-support.js";\n'
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
