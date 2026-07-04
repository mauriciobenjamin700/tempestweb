"""Parity tests for ``style_to_css`` against the JS ``styleToCss`` algorithm.

The Python port (:func:`tempestweb.html.css.style_to_css`) and the browser
client's ``client/style.js`` consume the same Style dump and MUST emit
byte-identical CSS, so a server-rendered page and the client agree with no
hydration drift. The expected strings below are exactly what ``client/style.js``
produces for the same inputs (cross-checked against the JS test suite in
``tests/client/style.test.js``), including its JavaScript number formatting where
a fully opaque color reads ``rgba(r, g, b, 1)`` (not ``1.0``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempestweb.html import style_to_css

FIXTURES: Path = Path(__file__).resolve().parents[1] / "fixtures"


def _sample() -> dict[str, Any]:
    return json.loads((FIXTURES / "style_sample.json").read_text(encoding="utf-8"))


def test_none_style_is_empty() -> None:
    assert style_to_css(None) == ""


def test_empty_style_is_empty() -> None:
    assert style_to_css({}) == ""


def test_style_sample_fixture_matches_js() -> None:
    # Identical to what client/style.js emits for style_sample.json + "Column".
    assert style_to_css(_sample(), "Column") == (
        "display: flex; flex-direction: column; gap: 8px; "
        "padding: 16px 16px 16px 16px; background: rgba(255, 255, 255, 1); "
        "color: rgba(17, 17, 17, 1); width: 320px"
    )


def test_row_column_are_flex_by_type() -> None:
    assert style_to_css(None, "Column") == "display: flex; flex-direction: column"
    assert style_to_css(None, "Row") == "display: flex; flex-direction: row"


def test_explicit_direction_overrides_type_axis() -> None:
    assert style_to_css({"direction": "row"}, "Column") == (
        "display: flex; flex-direction: row"
    )


def test_non_flex_type_stays_block() -> None:
    assert style_to_css(None, "Container") == ""


def test_flex_fields_and_start_end_mapping() -> None:
    assert style_to_css(
        {
            "justify": "start",
            "align": "end",
            "align_self": "start",
            "grow": 1,
            "gap": 8,
            "flex_wrap": "wrap",
        }
    ) == (
        "justify-content: flex-start; align-items: flex-end; "
        "align-self: flex-start; flex-grow: 1; gap: 8px; flex-wrap: wrap"
    )


def test_box_model_border_radius() -> None:
    assert (
        style_to_css(
            {
                "border": {"width": 2, "color": {"r": 0, "g": 0, "b": 0, "a": 1}},
                "radius": 8,
            }
        )
        == "border: 2px solid rgba(0, 0, 0, 1); border-radius: 8px"
    )


def test_side_border_only_set_sides() -> None:
    assert (
        style_to_css(
            {
                "border": {
                    "top": None,
                    "right": None,
                    "bottom": {"width": 1, "color": {"r": 200, "g": 0, "b": 0, "a": 1}},
                    "left": None,
                }
            }
        )
        == "border-bottom: 1px solid rgba(200, 0, 0, 1)"
    )


def test_border_null_color_is_currentcolor() -> None:
    assert style_to_css({"border": {"width": 1, "color": None}}) == (
        "border: 1px solid currentColor"
    )


def test_per_corner_radius() -> None:
    assert (
        style_to_css(
            {
                "radius": {
                    "top_left": 1,
                    "top_right": 2,
                    "bottom_right": 3,
                    "bottom_left": 4,
                }
            }
        )
        == "border-radius: 1px 2px 3px 4px"
    )


def test_gradient_background() -> None:
    assert style_to_css(
        {
            "background": {
                "direction": "left-right",
                "stops": [
                    {"color": {"r": 0, "g": 0, "b": 0, "a": 1}, "position": 0},
                    {"color": {"r": 255, "g": 255, "b": 255, "a": 1}, "position": 1},
                ],
            }
        }
    ) == (
        "background: linear-gradient(to right, rgba(0, 0, 0, 1) 0%, "
        "rgba(255, 255, 255, 1) 100%)"
    )


def test_paint_opacity_and_shadow() -> None:
    assert (
        style_to_css(
            {
                "opacity": 0.25,
                "shadow": {
                    "color": {"r": 0, "g": 0, "b": 0, "a": 0.3},
                    "blur": 6,
                    "offset_x": 0,
                    "offset_y": 2,
                },
            }
        )
        == "opacity: 0.25; box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.3)"
    )


def test_shadow_null_color_neutral_tint() -> None:
    assert (
        style_to_css(
            {"shadow": {"color": None, "blur": 4, "offset_x": 1, "offset_y": 1}}
        )
        == "box-shadow: 1px 1px 4px rgba(0, 0, 0, 0.3)"
    )


def test_typography_fields() -> None:
    assert style_to_css(
        {
            "font_family": "Inter",
            "font_size": 14,
            "font_weight": 700,
            "font_style": "italic",
            "text_align": "center",
            "text_decoration": "underline",
            "letter_spacing": 0.5,
            "line_height": 1.5,
        }
    ) == (
        "font-family: Inter; font-size: 14px; font-weight: 700; "
        "font-style: italic; text-align: center; text-decoration: underline; "
        "letter-spacing: 0.5px; line-height: 1.5"
    )


def test_dimension_fields() -> None:
    assert style_to_css(
        {
            "width": 100,
            "height": 50,
            "min_width": 10,
            "max_width": 200,
            "min_height": 20,
            "max_height": 300,
            "aspect_ratio": 1.5,
        }
    ) == (
        "width: 100px; height: 50px; min-width: 10px; max-width: 200px; "
        "min-height: 20px; max-height: 300px; aspect-ratio: 1.5"
    )


def test_transition_shorthand_with_and_without_delay() -> None:
    assert (
        style_to_css(
            {"transition": {"duration_ms": 200, "curve": "ease-in-out", "delay_ms": 50}}
        )
        == "transition: all 200ms ease-in-out 50ms"
    )
    assert (
        style_to_css(
            {"transition": {"duration_ms": 120, "curve": "linear", "delay_ms": 0}}
        )
        == "transition: all 120ms linear"
    )


def test_bounce_curve_falls_back_to_cubic_bezier() -> None:
    css = style_to_css(
        {"transition": {"duration_ms": 100, "curve": "bounce", "delay_ms": 0}}
    )
    assert css == "transition: all 100ms cubic-bezier(0.68, -0.55, 0.27, 1.55)"


def test_float_values_stringify_like_javascript() -> None:
    # 8.0 -> "8" (not "8.0"); the alpha 1.0 -> "1"; 0.5 stays "0.5".
    assert style_to_css({"gap": 8.0}) == "gap: 8px"
    assert style_to_css({"color": {"r": 1, "g": 2, "b": 3, "a": 1.0}}) == (
        "color: rgba(1, 2, 3, 1)"
    )
