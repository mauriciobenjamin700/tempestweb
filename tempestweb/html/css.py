"""Translate a Style dump into a CSS declaration string (server-side).

This is a faithful Python port of the browser client's ``client/style.js``
(``styleToCss``). Both consume the **same** ``Style`` shape — a Pydantic
``model_dump(mode="json")`` — and must emit **byte-identical** CSS so a page
rendered on the server (``tempestweb.html``) and the same tree re-rendered by the
DOM client agree exactly (no hydration drift).

Field order mirrors the source model and the JS port: flex → box model → paint →
typography → dimensions → transition. Enum spellings map the core's vocabulary to
CSS (``start`` → ``flex-start`` etc.); every numeric value is stringified the way
JavaScript stringifies a ``Number`` (``8.0`` → ``"8"``, ``0.5`` → ``"0.5"``) so
the emitted units match the JS renderer down to the last character.

!!! note "Why not ``Color.to_rgba_string()``?"
    ``tempest_core.style.Color.to_rgba_string()`` renders a fully opaque color as
    ``rgba(r, g, b, 1.0)``, but the JS ``colorToRgba`` renders it as
    ``rgba(r, g, b, 1)`` (JavaScript drops the trailing ``.0``). To keep the two
    renderers byte-identical, colors are formatted here with the same
    JS-compatible number formatting used for every other numeric field.
"""

from __future__ import annotations

from typing import Any

__all__: list[str] = [
    "style_to_css",
]

# flex ``justify``/``align`` map cleanly except for "start"/"end", which CSS
# spells "flex-start"/"flex-end". Everything else (center, space-*, stretch) is
# identity. Mirrors FLEX_EDGE in client/style.js.
_FLEX_EDGE: dict[str, str] = {"start": "flex-start", "end": "flex-end"}

# Widget types that are flex containers by nature: they render ``display: flex``
# with this axis unless the style sets an explicit ``direction``. Mirrors
# FLEX_DIRECTION_BY_TYPE in client/style.js.
_FLEX_DIRECTION_BY_TYPE: dict[str, str] = {
    "Column": "column",
    "Row": "row",
    "LazyColumn": "column",
    "LazyRow": "row",
}

# CSS gradient axis keyword per core GradientDirection. Mirrors GRADIENT_DIRECTION.
_GRADIENT_DIRECTION: dict[str, str] = {
    "top-bottom": "to bottom",
    "bottom-top": "to top",
    "left-right": "to right",
    "right-left": "to left",
}

# CSS keyword per core FontStyle / TextDecoration (identity, but kept explicit so
# an unmapped value never silently leaks an invalid CSS keyword).
_FONT_STYLE: dict[str, str] = {"normal": "normal", "italic": "italic"}
_TEXT_DECORATION: dict[str, str] = {
    "none": "none",
    "underline": "underline",
    "line-through": "line-through",
}

# Core easing curves -> CSS transition-timing-function. The first five are CSS
# keywords; bounce/elastic have no keyword, so approximate them with the same
# overshooting cubic-beziers the native renderers use. Mirrors CURVE_CSS.
_CURVE_CSS: dict[str, str] = {
    "linear": "linear",
    "ease": "ease",
    "ease-in": "ease-in",
    "ease-out": "ease-out",
    "ease-in-out": "ease-in-out",
    "bounce": "cubic-bezier(0.68, -0.55, 0.27, 1.55)",
    "elastic": "cubic-bezier(0.68, -0.6, 0.32, 1.6)",
}


def _num(value: Any) -> str:  # noqa: ANN401 — accepts any JSON scalar from a dump
    """Stringify a number the way JavaScript's ``String(Number)`` does.

    A float whose value is integral loses its decimal part (``8.0`` → ``"8"``,
    ``1.0`` → ``"1"``); a non-integral float keeps its shortest round-trip form
    (``0.5`` → ``"0.5"``). This matches how ``client/style.js`` interpolates
    numeric style values, so the emitted CSS is byte-identical to the client's.

    Args:
        value: A number (``int`` or ``float``) drawn from a Style dump.

    Returns:
        The JavaScript-compatible string form of the number.
    """
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return repr(number)


def _color_to_rgba(color: dict[str, Any]) -> str:
    """Render a Color dump ``{r, g, b, a}`` as a CSS ``rgba(...)`` value.

    Mirrors ``colorToRgba`` in ``client/style.js``, including its
    JavaScript-style alpha formatting (a fully opaque color reads ``rgba(r, g, b,
    1)``, not ``rgba(r, g, b, 1.0)``).

    Args:
        color: A Color dump with integer ``r``/``g``/``b`` and float ``a``.

    Returns:
        The CSS ``rgba(...)`` string.
    """
    return (
        f"rgba({_num(color['r'])}, {_num(color['g'])}, "
        f"{_num(color['b'])}, {_num(color['a'])})"
    )


def _edge_to_css(edge: dict[str, Any]) -> str:
    """Render an Edge dump as a CSS ``top right bottom left`` shorthand (px).

    Args:
        edge: An Edge dump with ``top``/``right``/``bottom``/``left`` floats.

    Returns:
        The four-value px shorthand.
    """
    return (
        f"{_num(edge['top'])}px {_num(edge['right'])}px "
        f"{_num(edge['bottom'])}px {_num(edge['left'])}px"
    )


def _border_value(border: dict[str, Any]) -> str:
    """Render one uniform Border dump as a CSS ``Npx solid color`` value.

    Args:
        border: A Border dump with a ``width`` float and a nullable ``color``.

    Returns:
        The CSS border value (``currentColor`` when the color is null).
    """
    color = border.get("color")
    css_color = _color_to_rgba(color) if color else "currentColor"
    return f"{_num(border['width'])}px solid {css_color}"


def _is_side_border(border: dict[str, Any]) -> bool:
    """Test whether a border dump is per-side (SideBorder) rather than uniform.

    Args:
        border: A Border or SideBorder dump.

    Returns:
        ``True`` when the dump carries per-side keys.
    """
    return any(side in border for side in ("top", "right", "bottom", "left"))


def _border_rules(border: dict[str, Any]) -> list[str]:
    """Render a border dump (uniform or per-side) as CSS declarations.

    Args:
        border: A Border or SideBorder dump.

    Returns:
        A list of CSS declarations (one for uniform, one per set side otherwise).
    """
    if _is_side_border(border):
        rules: list[str] = []
        for name in ("top", "right", "bottom", "left"):
            value = border.get(name)
            if value is not None:
                rules.append(f"border-{name}: {_border_value(value)}")
        return rules
    return [f"border: {_border_value(border)}"]


def _radius_value(radius: Any) -> str:  # noqa: ANN401 — float | Corners dump
    """Render a radius dump (uniform float or per-corner Corners) as CSS.

    Args:
        radius: A float, or a Corners dump with the four corner radii.

    Returns:
        The CSS ``border-radius`` value (in px).
    """
    if isinstance(radius, dict):
        return (
            f"{_num(radius['top_left'])}px {_num(radius['top_right'])}px "
            f"{_num(radius['bottom_right'])}px {_num(radius['bottom_left'])}px"
        )
    return f"{_num(radius)}px"


def _background_to_css(background: dict[str, Any]) -> str:
    """Render a background dump (Color or Gradient) as a CSS background value.

    Args:
        background: A Color dump or a Gradient dump (with ``stops``).

    Returns:
        A CSS color or ``linear-gradient(...)`` value.
    """
    if isinstance(background.get("stops"), list):
        axis = _GRADIENT_DIRECTION.get(background.get("direction", ""), "to bottom")
        stops = ", ".join(
            f"{_color_to_rgba(stop['color'])} {_num(stop['position'] * 100)}%"
            for stop in background["stops"]
        )
        return f"linear-gradient({axis}, {stops})"
    return _color_to_rgba(background)


def _shadow_to_css(shadow: dict[str, Any]) -> str:
    """Render a Shadow dump as a CSS ``box-shadow`` value.

    Args:
        shadow: A Shadow dump with ``offset_x``/``offset_y``/``blur`` and a
            nullable ``color``.

    Returns:
        The CSS ``box-shadow`` value (a neutral tint when the color is null).
    """
    color = shadow.get("color")
    css_color = _color_to_rgba(color) if color else "rgba(0, 0, 0, 0.3)"
    return (
        f"{_num(shadow['offset_x'])}px {_num(shadow['offset_y'])}px "
        f"{_num(shadow['blur'])}px {css_color}"
    )


def _transition_to_css(transition: dict[str, Any]) -> str:
    """Render a Transition dump as a CSS ``transition`` shorthand.

    Args:
        transition: A Transition dump with ``duration_ms``/``curve``/``delay_ms``.

    Returns:
        e.g. ``"all 200ms ease-in-out 50ms"`` (the delay term is omitted at 0).
    """
    curve = _CURVE_CSS.get(transition["curve"], transition["curve"])
    delay_ms = transition.get("delay_ms")
    delay = f" {_num(delay_ms)}ms" if delay_ms else ""
    return f"all {_num(transition['duration_ms'])}ms {curve}{delay}"


def style_to_css(style: dict[str, Any] | None, widget_type: str | None = None) -> str:
    """Translate a Style dump into a CSS string (declarations joined by ``"; "``).

    A faithful port of ``styleToCss`` in ``client/style.js``. Field order follows
    the source model (flex, box model, paint, typography, dimensions, transition)
    so the emitted declarations are stable and identical to the client's.
    ``None``/absent fields are skipped entirely — they mean "unset" and let the
    browser default apply.

    A ``Row``/``Column`` (and their lazy variants) becomes a flex container by
    type even with no explicit ``direction`` in the style, so ``gap``/``justify``/
    ``align`` are never silently inert.

    Args:
        style: A Style dump (``model_dump(mode="json")``), or ``None``.
        widget_type: The widget type (``"Row"``/``"Column"``/...), so flex
            containers default to the right ``flex-direction`` even when the style
            does not set one. Optional.

    Returns:
        A ``"; "``-joined CSS declaration body (``""`` when empty/null).
    """
    direction = (style.get("direction") if style else None) or (
        _FLEX_DIRECTION_BY_TYPE.get(widget_type) if widget_type else None
    )
    if style is None and direction is None:
        return ""

    rules: list[str] = []

    # Flexbox layout. Row/Column are flex containers by type; an explicit
    # ``direction`` in the style overrides the type's natural axis.
    if direction is not None:
        rules.append("display: flex")
        rules.append(f"flex-direction: {direction}")
    if style is None:
        return "; ".join(rules)
    if style.get("justify") is not None:
        rules.append(
            f"justify-content: {_FLEX_EDGE.get(style['justify'], style['justify'])}"
        )
    if style.get("align") is not None:
        rules.append(f"align-items: {_FLEX_EDGE.get(style['align'], style['align'])}")
    if style.get("align_self") is not None:
        rules.append(
            f"align-self: {_FLEX_EDGE.get(style['align_self'], style['align_self'])}"
        )
    if style.get("grow") is not None:
        rules.append(f"flex-grow: {_num(style['grow'])}")
    if style.get("gap") is not None:
        rules.append(f"gap: {_num(style['gap'])}px")
    if style.get("flex_wrap") is not None:
        rules.append(f"flex-wrap: {style['flex_wrap']}")

    # Box model.
    if style.get("padding") is not None:
        rules.append(f"padding: {_edge_to_css(style['padding'])}")
    if style.get("margin") is not None:
        rules.append(f"margin: {_edge_to_css(style['margin'])}")
    if style.get("border") is not None:
        rules.extend(_border_rules(style["border"]))
    if style.get("radius") is not None:
        rules.append(f"border-radius: {_radius_value(style['radius'])}")

    # Paint.
    if style.get("background") is not None:
        rules.append(f"background: {_background_to_css(style['background'])}")
    if style.get("color") is not None:
        rules.append(f"color: {_color_to_rgba(style['color'])}")
    if style.get("opacity") is not None:
        rules.append(f"opacity: {_num(style['opacity'])}")
    if style.get("shadow") is not None:
        rules.append(f"box-shadow: {_shadow_to_css(style['shadow'])}")

    # Typography.
    if style.get("font_family") is not None:
        rules.append(f"font-family: {style['font_family']}")
    if style.get("font_size") is not None:
        rules.append(f"font-size: {_num(style['font_size'])}px")
    if style.get("font_weight") is not None:
        rules.append(f"font-weight: {_num(style['font_weight'])}")
    if style.get("font_style") is not None:
        rules.append(
            f"font-style: {_FONT_STYLE.get(style['font_style'], style['font_style'])}"
        )
    if style.get("text_align") is not None:
        rules.append(f"text-align: {style['text_align']}")
    if style.get("text_decoration") is not None:
        decoration = _TEXT_DECORATION.get(
            style["text_decoration"], style["text_decoration"]
        )
        rules.append(f"text-decoration: {decoration}")
    if style.get("letter_spacing") is not None:
        rules.append(f"letter-spacing: {_num(style['letter_spacing'])}px")
    if style.get("line_height") is not None:
        rules.append(f"line-height: {_num(style['line_height'])}")

    # Dimensions.
    if style.get("width") is not None:
        rules.append(f"width: {_num(style['width'])}px")
    if style.get("height") is not None:
        rules.append(f"height: {_num(style['height'])}px")
    if style.get("min_width") is not None:
        rules.append(f"min-width: {_num(style['min_width'])}px")
    if style.get("max_width") is not None:
        rules.append(f"max-width: {_num(style['max_width'])}px")
    if style.get("min_height") is not None:
        rules.append(f"min-height: {_num(style['min_height'])}px")
    if style.get("max_height") is not None:
        rules.append(f"max-height: {_num(style['max_height'])}px")
    if style.get("aspect_ratio") is not None:
        rules.append(f"aspect-ratio: {_num(style['aspect_ratio'])}")

    # Implicit animation: tween changed visual properties on the next rebuild.
    if style.get("transition") is not None:
        rules.append(f"transition: {_transition_to_css(style['transition'])}")

    return "; ".join(rules)
