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

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
STYLES_MODULE: Path = CLIENT_DIR / "widget-styles.gen.js"

#: The parameter spaces the table is built over, sorted for a stable output.
_VARIANTS: tuple[str, ...] = tuple(v.value for v in Variant)
_SIZES: tuple[str, ...] = tuple(s.value for s in Size)
_SCHEMES: tuple[str, ...] = tuple(sorted(VALID_COLOR_SCHEMES))


def _resolved_style(variant: str, size: str, scheme: str) -> dict[str, Any]:
    """Return the core-resolved non-null style for a Button combination.

    Args:
        variant: The button variant (e.g. ``"solid"``).
        size: The density size (e.g. ``"md"``).
        scheme: The Material 3 color scheme (e.g. ``"primary"``).

    Returns:
        The non-null fields of the style the core bakes into the built IR.
    """
    node = build(Button(label="x", variant=variant, size=size, color_scheme=scheme))
    style = node.props["style"]
    dumped: dict[str, Any] = style.model_dump(mode="json")
    return {key: value for key, value in dumped.items() if value is not None}


def build_table() -> dict[str, Any]:
    """Build the ``{widget: {variant: {size: {scheme: style}}}}`` style table.

    Returns:
        The nested table of resolved non-null styles for every Button combination.
    """
    button: dict[str, Any] = {}
    for variant in _VARIANTS:
        by_size: dict[str, Any] = {}
        for size in _SIZES:
            by_size[size] = {
                scheme: _resolved_style(variant, size, scheme) for scheme in _SCHEMES
            }
        button[variant] = by_size
    return {"Button": button}


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
