"""Generate the resolved style tables the Mode C components need.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_component_styles

The core's component layer resolves its look through pure resolvers
(:func:`tempest_core.variants.resolve_surface_variant` and friends) reading the
theme's color, spacing and shape scales. Mode C has no Python, so the resolvers
cannot run there — but they are deterministic, so their *output* travels as a
table, the same trick ``widget-styles.gen.js`` already uses for the styled
widgets.

The tables, each keyed by the axes the components actually expose:

* ``COLOR_ROLES`` — the 39 Material 3 roles of the default theme.
* ``SHAPE_STEPS`` — the shape scale (corner radii), by step name.
* ``SURFACE_STYLES`` — variant × color scheme × elevation, resolved with
  ``padding_step="none"`` and ``radius_step="none"`` so the caller applies its
  own padding and radius from the scales (the resolver assigns both fields
  directly, so factoring them out keeps the result identical and divides the
  table by 49).
* ``BADGE_STYLES`` — variant × size × color scheme, for the chip pill.
* ``SELECTION_ACCENT`` — size × color scheme × checked, but only the ``color``
  field a radio row reads, because that is all the component uses.
* ``ALERT_STYLES`` — variant × color scheme, for the ``Banner``/``Alert`` block.
  The resolver's ``padding_step``/``radius_step`` stay at their defaults because
  neither component exposes them.
* ``FIELD_STYLES`` — variant × size × color scheme at the resting, valid state,
  which is the only combination ``SearchBar`` asks for.
* ``TYPOGRAPHY`` — the type scale, but only the ``font_size``/``font_weight``
  pair the components read off a role; the line height and letter spacing no
  component consumes would be dead bytes.
* ``AVATAR_COLORS`` — color scheme → the tonal ``(background, color)`` pair the
  ``Avatar`` circle fills with, resolved through the core's own role mapping so
  the pairing cannot drift here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import (
    VALID_COLOR_SCHEMES,
    AlertVariant,
    BadgeVariant,
    CardVariant,
    ColorRole,
    FieldVariant,
    Size,
    Theme,
)
from tempest_core.components.cards import _avatar_colors
from tempest_core.variants import (
    resolve_alert_variant,
    resolve_badge_variant,
    resolve_field_variant,
    resolve_selection_variant,
    resolve_surface_variant,
)

CLIENT_DIR: Path = Path(__file__).resolve().parents[2] / "client" / "transpile"
STYLES_MODULE: Path = CLIENT_DIR / "component-styles.gen.js"

#: Material 3 elevation levels a surface accepts, plus the per-variant default.
_ELEVATIONS: tuple[str, ...] = ("default", "0", "1", "2", "3", "4", "5")


def _schemes() -> list[str]:
    """The color schemes the resolvers accept.

    Returns:
        The scheme names, sorted for a stable golden.
    """
    return sorted(VALID_COLOR_SCHEMES)


def _dump(style: Any) -> dict[str, Any]:
    """Serialize a resolved ``Style`` to its wire dict, without the unset fields.

    Only the fields the resolver actually set are carried: the JS ``Style()``
    helper fills the rest with ``null``, which is the same convention
    ``widget-styles.gen.js`` uses and the difference between a 412 KB table and
    a fifth of that in every artifact.

    Args:
        style: The resolved style.

    Returns:
        The JSON-able mapping of the set fields.
    """
    return {
        field: value
        for field, value in style.model_dump(mode="json").items()
        if value is not None
    }


def color_roles(theme: Theme) -> dict[str, Any]:
    """Every Material 3 role of a theme, by role name.

    Args:
        theme: The theme to resolve against.

    Returns:
        Role name → serialized color.
    """
    return {role.value: theme.color(role).model_dump(mode="json") for role in ColorRole}


def shape_steps(theme: Theme) -> dict[str, float]:
    """The shape scale, by step name.

    Args:
        theme: The theme whose tokens carry the scale.

    Returns:
        Step name → corner radius in logical pixels.
    """
    return {step: theme.radius(step) for step in type(theme.tokens.shape).model_fields}


def surface_styles(theme: Theme) -> dict[str, Any]:
    """Resolved surface styles, by variant, color scheme and elevation.

    Args:
        theme: The theme to resolve against.

    Returns:
        variant → scheme → elevation key → serialized style, where the elevation
        key ``"default"`` is the variant's own default level.
    """
    table: dict[str, Any] = {}
    for variant in CardVariant:
        per_scheme: dict[str, Any] = {}
        for scheme in _schemes():
            per_level: dict[str, Any] = {}
            for key in _ELEVATIONS:
                level = None if key == "default" else int(key)
                per_level[key] = _dump(
                    resolve_surface_variant(
                        variant=variant,
                        color_scheme=scheme,
                        theme=theme,
                        elevation=level,
                        padding_step="none",
                        radius_step="none",
                    )
                )
            per_scheme[scheme] = per_level
        table[variant.value] = per_scheme
    return table


def badge_styles(theme: Theme) -> dict[str, Any]:
    """Resolved badge styles, by variant, size and color scheme.

    Args:
        theme: The theme to resolve against.

    Returns:
        variant → size → scheme → serialized style.
    """
    table: dict[str, Any] = {}
    for variant in BadgeVariant:
        per_size: dict[str, Any] = {}
        for size in Size:
            per_size[size.value] = {
                scheme: _dump(
                    resolve_badge_variant(
                        variant=variant,
                        size=size,
                        color_scheme=scheme,
                        theme=theme,
                    )
                )
                for scheme in _schemes()
            }
        table[variant.value] = per_size
    return table


def selection_accent(theme: Theme) -> dict[str, Any]:
    """The accent color a selection control paints, by size, scheme and state.

    Only the ``color`` field is kept: a radio row reads the accent and paints its
    own box, so carrying the whole style would be dead bytes.

    Args:
        theme: The theme to resolve against.

    Returns:
        size → scheme → ``"checked"``/``"unchecked"`` → serialized color or
        ``None``.
    """
    table: dict[str, Any] = {}
    for size in Size:
        per_scheme: dict[str, Any] = {}
        for scheme in _schemes():
            per_state: dict[str, Any] = {}
            for state, checked in (("checked", True), ("unchecked", False)):
                style = resolve_selection_variant(
                    size=size, color_scheme=scheme, theme=theme, checked=checked
                )
                color = style.color
                per_state[state] = (
                    color.model_dump(mode="json") if color is not None else None
                )
            per_scheme[scheme] = per_state
        table[size.value] = per_scheme
    return table


def alert_styles(theme: Theme) -> dict[str, Any]:
    """Resolved alert block styles, by variant and color scheme.

    Args:
        theme: The theme to resolve against.

    Returns:
        variant → scheme → serialized style.
    """
    return {
        variant.value: {
            scheme: _dump(
                resolve_alert_variant(variant=variant, color_scheme=scheme, theme=theme)
            )
            for scheme in _schemes()
        }
        for variant in AlertVariant
    }


def field_styles(theme: Theme) -> dict[str, Any]:
    """Resolved input-field styles, by variant, size and color scheme.

    Args:
        theme: The theme to resolve against.

    Returns:
        variant → size → scheme → serialized style, at the resting valid state.
    """
    return {
        variant.value: {
            size.value: {
                scheme: _dump(
                    resolve_field_variant(
                        variant=variant,
                        size=size,
                        color_scheme=scheme,
                        theme=theme,
                    )
                )
                for scheme in _schemes()
            }
            for size in Size
        }
        for variant in FieldVariant
    }


def typography(theme: Theme) -> dict[str, Any]:
    """The type scale, by role name, reduced to what a component reads.

    Args:
        theme: The theme whose tokens carry the scale.

    Returns:
        Role name → ``{"font_size", "font_weight"}``.
    """
    return {
        role: {
            "font_size": theme.typography(role).font_size,
            "font_weight": theme.typography(role).font_weight,
        }
        for role in type(theme.tokens.typography).model_fields
    }


def avatar_colors(theme: Theme) -> dict[str, Any]:
    """The tonal fill/content pair an avatar circle paints, by color scheme.

    The pairing comes from the core's own role map, so an unknown scheme falls
    back to the primary container exactly as the component does.

    Args:
        theme: The theme to resolve against.

    Returns:
        Scheme name → ``{"background", "color"}`` serialized colors.
    """
    table: dict[str, Any] = {}
    for scheme in _schemes():
        background, content = _avatar_colors(scheme, theme)
        table[scheme] = {
            "background": background.model_dump(mode="json"),
            "color": content.model_dump(mode="json"),
        }
    return table


def render_module_text() -> str:
    """Render the component style tables as a native JS module.

    Returns:
        The full ``component-styles.gen.js`` source.
    """
    theme = Theme()
    header = (
        "// component-styles.gen.js — GENERATED from tempest_core by tempestweb "
        "transpile (Mode C).\n"
        "// The core-resolved styles the ported components need: surface variants, "
        "badge pills,\n"
        "// selection accents, alert blocks, input fields, avatar pairs, plus the "
        "color-role,\n"
        "// shape and type scales. Regenerate:\n"
        "// python -m tests.conformance._transpile_component_styles. Do not edit.\n"
    )

    def block(name: str, value: Any) -> str:
        """Render one exported table.

        Args:
            name: The export name.
            value: The JSON-able table.

        Returns:
            The export statement.
        """
        body = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
        return f"export const {name} = {body};\n"

    return (
        f"{header}\n"
        + block("COLOR_ROLES", color_roles(theme))
        + "\n"
        + block("SHAPE_STEPS", shape_steps(theme))
        + "\n"
        + block("SURFACE_STYLES", surface_styles(theme))
        + "\n"
        + block("BADGE_STYLES", badge_styles(theme))
        + "\n"
        + block("SELECTION_ACCENT", selection_accent(theme))
        + "\n"
        + block("ALERT_STYLES", alert_styles(theme))
        + "\n"
        + block("FIELD_STYLES", field_styles(theme))
        + "\n"
        + block("TYPOGRAPHY", typography(theme))
        + "\n"
        + block("AVATAR_COLORS", avatar_colors(theme))
    )


def write_module() -> Path:
    """Write the component style tables to disk.

    Returns:
        The path written.
    """
    STYLES_MODULE.write_text(render_module_text(), encoding="utf-8")
    return STYLES_MODULE


def main() -> None:
    """Regenerate the tables and print the path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
