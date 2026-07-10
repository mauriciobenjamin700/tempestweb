"""Regenerate the Mode C spacing-token scale from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_spacing

The ergonomic layout components (``HStack`` / ``VStack``) accept a ``gap`` as a
spacing **token** (``"md"``) that the core resolves to logical pixels against the
theme's spacing scale. Mode C has no Python at runtime, so this introspects the
scale from the core and emits it as a native JS map the component builders read.
Derived from the core — same regenerable-golden guarantee as the wire fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from tempest_core import build
from tempest_core.components import HStack

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
SPACING_MODULE: Path = CLIENT_DIR / "spacing.gen.js"

# The spacing-scale token names the core exposes (probed against the theme).
_TOKENS: tuple[str, ...] = ("none", "xs", "sm", "md", "lg", "xl", "xxl")


def build_scale() -> dict[str, float]:
    """Resolve each spacing token to its logical-pixel value via the core.

    Returns:
        A token → pixels map (e.g. ``{"md": 16.0}``), built by reading the gap a
        token produces on a resolved :class:`HStack`.
    """
    scale: dict[str, float] = {}
    for token in _TOKENS:
        node = build(HStack(children=[], gap=token))
        gap = node.props["style"].model_dump(mode="json")["gap"]
        if gap is not None:
            scale[token] = gap
    return scale


def render_module_text() -> str:
    """Render the native JS spacing-scale module source."""
    scale = json.dumps(build_scale(), indent=2, sort_keys=True)
    header = (
        "// spacing.gen.js — GENERATED from tempest_core by tempestweb transpile "
        "(Mode C).\n"
        "// The theme spacing scale: token -> logical pixels, for HStack/VStack "
        "`gap` tokens.\n"
        "// Regenerate: python -m tests.conformance._transpile_spacing. Do not "
        "edit.\n"
    )
    return f"{header}\nexport const SPACING_STEPS = {scale};\n"


def write_module() -> Path:
    """Write the spacing-scale JS module to disk and return its path."""
    SPACING_MODULE.write_text(render_module_text(), encoding="utf-8")
    return SPACING_MODULE


def main() -> None:
    """Regenerate the spacing-scale module and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
