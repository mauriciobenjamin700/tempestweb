"""Regenerate the Mode C widget-style table from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_widget_styles

Mode C has no Python at runtime, so the native widget builders
(``client/transpile/widgets.js``) cannot call the core to resolve a widget's
default Material 3 style from its ``variant`` / ``size`` / ``color_scheme``. This
module introspects the *real* core at build time — building each combination and
reading the resolved ``style`` the core bakes into the IR — and emits a native JS
data module the builders read. The table is therefore derived from the core (same
regenerable-golden guarantee as the wire fixtures), never hand-typed.

Only the resolved **non-null** style fields are stored; ``widgets.js`` fills the
rest with ``null`` via its ``Style`` helper, so the emitted IR keeps the core's
full wire shape (a stable diff across re-renders).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Button, build
from tempest_core.style import Size, Variant
from tempest_core.variants import VALID_COLOR_SCHEMES
from tempest_core.widgets import Input
from tempest_core.widgets.inputs import FieldVariant

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
STYLES_MODULE: Path = CLIENT_DIR / "widget-styles.gen.js"

#: The parameter spaces the table is built over, sorted for a stable output.
_VARIANTS: tuple[str, ...] = tuple(v.value for v in Variant)
_FIELD_VARIANTS: tuple[str, ...] = tuple(v.value for v in FieldVariant)
_SIZES: tuple[str, ...] = tuple(s.value for s in Size)
_SCHEMES: tuple[str, ...] = tuple(sorted(VALID_COLOR_SCHEMES))


def _nonnull_style(node: Any) -> dict[str, Any]:
    """Return the non-null fields of a built node's resolved style.

    Args:
        node: A ``build(...)`` result whose ``props["style"]`` is a ``Style``.

    Returns:
        The non-null fields of the style the core baked into the IR.
    """
    dumped: dict[str, Any] = node.props["style"].model_dump(mode="json")
    return {key: value for key, value in dumped.items() if value is not None}


def _button_style(variant: str, size: str, scheme: str) -> dict[str, Any]:
    """Return the core-resolved non-null style for a Button combination."""
    return _nonnull_style(
        build(Button(label="x", variant=variant, size=size, color_scheme=scheme))
    )


def _input_style(field_variant: str, size: str, scheme: str) -> dict[str, Any]:
    """Return the core-resolved non-null style for an Input combination."""
    return _nonnull_style(
        build(Input(field_variant=field_variant, size=size, color_scheme=scheme))
    )


def build_table() -> dict[str, Any]:
    """Build the ``{widget: {variant: {size: {scheme: style}}}}`` style table.

    Returns:
        The nested table of resolved non-null styles per widget. ``Button`` is
        keyed by ``variant``; ``Input`` by ``field_variant`` — both then by
        ``size`` and ``color_scheme``.
    """
    button: dict[str, Any] = {
        variant: {
            size: {scheme: _button_style(variant, size, scheme) for scheme in _SCHEMES}
            for size in _SIZES
        }
        for variant in _VARIANTS
    }
    field_input: dict[str, Any] = {
        variant: {
            size: {scheme: _input_style(variant, size, scheme) for scheme in _SCHEMES}
            for size in _SIZES
        }
        for variant in _FIELD_VARIANTS
    }
    return {"Button": button, "Input": field_input}


def render_module_text() -> str:
    """Render the native JS data module for the style table.

    Returns:
        The ES-module source exporting the ``WIDGET_STYLES`` table as JSON.
    """
    table = json.dumps(build_table(), indent=2, sort_keys=True, ensure_ascii=False)
    header = (
        "// widget-styles.gen.js — GENERATED from tempest_core by "
        "tempestweb transpile (Mode C).\n"
        "// The core-resolved default Material 3 style per widget "
        "variant/size/color_scheme.\n"
        "// Regenerate: python -m tests.conformance._transpile_widget_styles. "
        "Do not edit.\n"
    )
    return f"{header}\nexport const WIDGET_STYLES = {table};\n"


def write_module() -> Path:
    """Write the style-table JS module to disk.

    Returns:
        The path the module was written to.
    """
    STYLES_MODULE.write_text(render_module_text(), encoding="utf-8")
    return STYLES_MODULE


def main() -> None:
    """Regenerate the widget-style table module and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
