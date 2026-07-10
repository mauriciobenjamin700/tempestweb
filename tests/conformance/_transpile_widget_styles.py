"""Regenerate the Mode C widget-style table from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_widget_styles

Mode C has no Python at runtime, so the native widget builders
(``client/transpile/widgets.gen.js``) cannot call the core to resolve a widget's
default Material 3 style from its variant / size / color_scheme. This module
introspects the *real* core at build time — building every combination of the
style axes a widget accepts and reading the resolved ``style`` the core bakes into
the IR — and emits a native JS data module the builders read. The table is
therefore derived from the core (same regenerable-golden guarantee as the wire
fixtures), never hand-typed.

The table is keyed uniformly ``WIDGET_STYLES[widget][variant][size][scheme]`` —
an axis a widget does not have collapses to the literal ``"_"``. Only the
resolved **non-null** style fields are stored; ``widgets.gen.js`` fills the rest
with ``null`` via its ``Style`` helper, so the emitted IR keeps the core's full
wire shape (a stable diff across re-renders).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from tempest_core import build
from tempest_core.style import Size, Variant
from tempest_core.variants import VALID_COLOR_SCHEMES
from tempest_core.widgets.base import Widget as WidgetBase
from tempest_core.widgets.inputs import FieldVariant
from tests.conformance._widgetspec import buildable_widgets

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
STYLES_MODULE: Path = CLIENT_DIR / "widget-styles.gen.js"

_VARIANTS: tuple[str, ...] = tuple(v.value for v in Variant)
_FIELD_VARIANTS: tuple[str, ...] = tuple(v.value for v in FieldVariant)
_SIZES: tuple[str, ...] = tuple(s.value for s in Size)
_SCHEMES: tuple[str, ...] = tuple(sorted(VALID_COLOR_SCHEMES))
_NONE = "_"  # collapsed key for an axis the widget does not have


def _nonnull_style(node: Any) -> dict[str, Any]:
    """Return the non-null fields of a built node's resolved style."""
    style = node.props.get("style")
    if style is None:
        return {}
    dumped: dict[str, Any] = style.model_dump(mode="json")
    return {key: value for key, value in dumped.items() if value is not None}


def _axes(
    cls: type[WidgetBase],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return the (variant, size, scheme) value spaces a widget accepts.

    Args:
        cls: The widget class to inspect.

    Returns:
        Three tuples of candidate values; an axis the widget lacks is ``("_",)``.
        The variant axis uses ``field_variant`` values when the widget has that
        parameter, else ``variant`` values, else ``("_",)``.
    """
    params = inspect.signature(cls).parameters
    if "field_variant" in params:
        variants: tuple[str, ...] = _FIELD_VARIANTS
    elif "variant" in params:
        variants = _VARIANTS
    else:
        variants = (_NONE,)
    sizes = _SIZES if "size" in params else (_NONE,)
    schemes = _SCHEMES if "color_scheme" in params else (_NONE,)
    return variants, sizes, schemes


def _variant_kwarg(cls: type[WidgetBase]) -> str | None:
    """Return the widget's variant parameter name (``field_variant``/``variant``)."""
    params = inspect.signature(cls).parameters
    if "field_variant" in params:
        return "field_variant"
    if "variant" in params:
        return "variant"
    return None


def build_table() -> dict[str, Any]:
    """Build ``{widget: {variant: {size: {scheme: nonNullStyle}}}}`` from the core.

    Only widgets whose bare build resolves a non-null style are included; each is
    built across the cartesian product of the axes it accepts.

    Returns:
        The nested style table, keyed uniformly with ``"_"`` for absent axes.
    """
    table: dict[str, Any] = {}
    for name, spec in buildable_widgets().items():
        if not spec.styled:
            continue
        cls = spec.cls
        variant_kw = _variant_kwarg(cls)
        variants, sizes, schemes = _axes(cls)
        base_args = dict(spec.build_args)
        by_variant: dict[str, Any] = {}
        for variant in variants:
            by_size: dict[str, Any] = {}
            for size in sizes:
                by_scheme: dict[str, Any] = {}
                for scheme in schemes:
                    kwargs = dict(base_args)
                    if variant_kw is not None and variant != _NONE:
                        kwargs[variant_kw] = variant
                    if size != _NONE:
                        kwargs["size"] = size
                    if scheme != _NONE:
                        kwargs["color_scheme"] = scheme
                    by_scheme[scheme] = _nonnull_style(build(cls(**kwargs)))
                by_size[size] = by_scheme
            by_variant[variant] = by_size
        table[name] = by_variant
    return table


def render_module_text() -> str:
    """Render the native JS data module for the style table."""
    table = json.dumps(build_table(), indent=2, sort_keys=True, ensure_ascii=False)
    header = (
        "// widget-styles.gen.js — GENERATED from tempest_core by "
        "tempestweb transpile (Mode C).\n"
        "// The core-resolved default Material 3 style per widget "
        "variant/size/color_scheme.\n"
        '// Axes a widget lacks collapse to "_". Regenerate: '
        "python -m tests.conformance._transpile_widget_styles. Do not edit.\n"
    )
    return f"{header}\nexport const WIDGET_STYLES = {table};\n"


def write_module() -> Path:
    """Write the style-table JS module to disk and return its path."""
    STYLES_MODULE.write_text(render_module_text(), encoding="utf-8")
    return STYLES_MODULE


def main() -> None:
    """Regenerate the widget-style table module and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
