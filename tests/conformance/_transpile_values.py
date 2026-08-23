"""Generate the Mode C module for the core's enums, value objects and tokens.

The transpiler routes every ``tempest_core`` name a module references to a JS
import. Widgets have generated builders (:mod:`._transpile_widgets`) and the
runtime/nav/i18n/theme names are hand-written, but the rest of the core — 32
enums, the non-widget value models (``Semantics``, ``Border``, ``Shadow``,
``Gradient`` …) and the module-level design tokens (``ACCENT``, ``ON_SURFACE``,
``HOVER_OPACITY`` …) — had no JS at all. A view that used ``TextAlign.CENTER``
or ``Semantics(label=…)`` therefore compiled to a module importing a name that
does not exist, which the browser refuses to load: a blank page, not an error.

What is emitted, all derived from the live core:

* an enum becomes a frozen object of member name → wire value;
* a non-widget model becomes a builder filling every declared field with its
  bare-built default, in the wire's snake_case (the same shape ``Style`` uses,
  because these objects *are* wire fragments);
* a JSON-able module constant becomes a frozen literal.

Names the hand-written client already exports (``Color``, ``Edge``, ``Style``,
``Theme``, ``Locale`` …) are skipped, so nothing is declared twice.
"""

from __future__ import annotations

import enum
import json
import typing
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import tempest_core
from tempest_core import Widget as WidgetBase

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
VALUES_MODULE: Path = CLIENT_DIR / "values.gen.js"

#: Sentinel for a field the caller must pass (no default to bake into the JS).
_NO_DEFAULT: Any = object()

#: Client modules whose exports already cover part of the core surface. A name
#: they export is skipped here, or the app would import two declarations of it.
_HAND_WRITTEN: tuple[str, ...] = (
    "widget-support.js",
    "runtime.js",
    "nav.js",
    "i18n.js",
    "theme.js",
    "motion.js",
    "animation.js",
    "validators.js",
    "native.js",
    "components.js",
    "widgets.gen.js",
)


def _hand_written_names() -> set[str]:
    """Names the non-generated Mode C modules already export.

    Returns:
        Every identifier exported by the hand-written client modules plus the
        generated widget builders.
    """
    names: set[str] = set()
    for module in _HAND_WRITTEN:
        path = CLIENT_DIR / module
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            for keyword in ("export function ", "export const ", "export class "):
                if stripped.startswith(keyword):
                    names.add(stripped[len(keyword) :].split("(")[0].split(" ")[0])
            if stripped.startswith("export {"):
                inner = stripped[len("export {") :].split("}")[0]
                names |= {
                    part.split(" as ")[-1].strip()
                    for part in inner.split(",")
                    if part.strip()
                }
    return names


def _runtime_only_names() -> set[str]:
    """Core models a view never constructs, so Mode C does not need a builder.

    The IR node/patch types are the wire format the reconciler speaks; emitting
    constructors for them would be dead bytes in every artifact.

    Event classes are **not** skipped, though they mostly arrive *from* the
    client: an app builds one when it simulates a host event, which is what
    ``examples/theme-switcher`` does with ``ThemeChangeEvent(mode=…)``. Excluding
    them barred that view from Mode C for the size of one object literal each.

    Returns:
        The names to skip, derived from the core rather than hand-listed.
    """
    names = {"Node", "Scene"}
    for member in typing.get_args(getattr(tempest_core, "Patch", None)):
        name = getattr(member, "__name__", None)
        if name:
            names.add(name)
    return names


def _lit(value: Any) -> str:
    """Render a JSON-able Python value as a JS literal.

    Args:
        value: The value to render.

    Returns:
        Its JS source, with sets and tuples rendered as sorted arrays.
    """
    if isinstance(value, (frozenset, set, tuple)):
        return json.dumps(sorted(value))
    return json.dumps(value)


def _enum_source(name: str, cls: type[enum.Enum]) -> str:
    """Emit an enum as a frozen object of member name to wire value.

    Args:
        name: The enum's name.
        cls: The enum class.

    Returns:
        The JS source for the export.
    """
    members = ",\n".join(f"  {member.name}: {_lit(member.value)}" for member in cls)
    return (
        f"/** `{name}` — the core enum's members, by wire value. */\n"
        f"export const {name} = Object.freeze({{\n{members},\n}});\n"
    )


def _default_wire_value(field: Any) -> Any:
    """The JSON-able default of one model field, or ``_NO_DEFAULT``.

    Args:
        field: The Pydantic ``FieldInfo``.

    Returns:
        The default rendered the way the wire carries it, or ``_NO_DEFAULT``
        when the field is required (the caller passes it) or does not
        serialize.
    """
    if field.is_required():
        return _NO_DEFAULT
    value = field.get_default(call_default_factory=True)
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, enum.Enum):
        value = value.value
    try:
        json.dumps(
            value if not isinstance(value, (frozenset, set, tuple)) else sorted(value)
        )
    except TypeError:
        return _NO_DEFAULT
    return value


def _model_source(name: str, cls: type[BaseModel]) -> str:
    """Emit a non-widget value model as a wire-shape builder.

    A required field has no default to bake in — the caller passes it, exactly
    as in Python — so only the optional fields seed the object. That is what
    lets ``Gradient`` and the other models with required fields exist here at
    all; keying off a bare instance skipped every one of them.

    Args:
        name: The model's name.
        cls: The model class.

    Returns:
        The JS source for the export, or an empty string when the model has no
        field whose default survives serialization and no field at all.
    """
    defaults: dict[str, Any] = {}
    for field_name, field in cls.model_fields.items():
        value = _default_wire_value(field)
        if value is not _NO_DEFAULT:
            defaults[field_name] = value
    if not cls.model_fields:
        return ""
    fields = ",\n".join(
        f"  {key}: {_lit(value)}" for key, value in sorted(defaults.items())
    )
    body = f"{{\n{fields},\n}}" if defaults else "{}"
    return (
        f"/**\n"
        f" * Build a `{name}` wire fragment.\n"
        f" * @param {{Object}} [partial]  Fields to override, in the wire's "
        f"snake_case.\n"
        f" * @returns {{Object}}\n"
        f" */\n"
        f"export function {name}(partial = {{}}) {{\n"
        f"  return {{ ...{name}_DEFAULTS, ...partial }};\n"
        f"}}\n\n"
        f"const {name}_DEFAULTS = Object.freeze({body});\n"
    )


def _constant_source(name: str, value: Any) -> str:
    """Emit a module-level design token as a frozen literal.

    Args:
        name: The constant's name.
        value: Its value (JSON-able, or a model that dumps to JSON).

    Returns:
        The JS source for the export, or an empty string when it does not
        serialize.
    """
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    try:
        rendered = _lit(value)
    except TypeError:
        return ""
    if isinstance(value, (dict, list)):
        rendered = f"Object.freeze({rendered})"
    return (
        f"/** `{name}` — a core design token. */\nexport const {name} = {rendered};\n"
    )


def collect() -> dict[str, str]:
    """Render one export per core value the hand-written client does not cover.

    Returns:
        A name-sorted mapping of core name to its JS source.
    """
    taken = _hand_written_names() | _runtime_only_names()
    out: dict[str, str] = {}
    for name in sorted(getattr(tempest_core, "__all__", [])):
        if name in taken:
            continue
        value = getattr(tempest_core, name)
        if isinstance(value, type) and issubclass(value, enum.Enum):
            out[name] = _enum_source(name, value)
        elif (
            isinstance(value, type)
            and issubclass(value, BaseModel)
            and not issubclass(value, WidgetBase)
        ):
            source = _model_source(name, value)
            if source:
                out[name] = source
        elif isinstance(
            value, (BaseModel, bool, int, float, str, dict, frozenset, tuple)
        ):
            source = _constant_source(name, value)
            if source:
                out[name] = source
    return out


def render_module_text() -> str:
    """Render the native JS module source for the core's values.

    Returns:
        The full ``values.gen.js`` source.
    """
    header = (
        "// values.gen.js — GENERATED from tempest_core by tempestweb transpile "
        "(Mode C).\n"
        "// The core's enums, non-widget value objects and design tokens, in the "
        "wire shape.\n"
        "// Regenerate: python -m tests.conformance._transpile_values. Do not "
        "edit.\n"
    )
    body = "\n".join(collect().values())
    return f"{header}\n{body}"


def write_module() -> Path:
    """Write the values module to disk.

    Returns:
        The path written.
    """
    VALUES_MODULE.write_text(render_module_text(), encoding="utf-8")
    return VALUES_MODULE


def main() -> None:
    """Regenerate the values module and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
