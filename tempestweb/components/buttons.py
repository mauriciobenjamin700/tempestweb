"""Material 3 button variants as one-line helpers.

The always-on base stylesheet (``client/theme.js``) already gives a bare
:class:`~tempest_core.Button` the MD3 *filled* look — pill shape, primary fill,
state layer, hover elevation. These helpers build the other MD3 button variants
by handing the button a small inline :class:`~tempest_core.Style` (background /
text color / border / resting shadow); the base sheet still supplies the shape,
type ramp and interaction state layer on top.

    from tempestweb.components import filled_button, tonal_button, text_button

    filled_button("Save", on_click=save)
    text_button("Cancel", on_click=close)

Setting an inline ``background`` is also the signal the base sheet uses to *opt a
variant out* of the filled button's hover elevation, so tonal/outlined/text stay
flat while ``elevated_button`` carries its own resting shadow. Every variant
renders identically in Mode A (WASM) and Mode B (server).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tempest_core import Button, Style
from tempest_core.style import Border, Color, Shadow

__all__ = [
    "elevated_button",
    "filled_button",
    "outlined_button",
    "text_button",
    "tonal_button",
]

# Material 3 baseline tokens, mirrored from the CSS custom properties the base
# stylesheet defines (client/theme.js). Kept here so the Python-built variants
# match the always-on web theme exactly.
PRIMARY: Color = Color.from_hex("#6750a4")
ON_PRIMARY: Color = Color.from_hex("#ffffff")
SECONDARY_CONTAINER: Color = Color.from_hex("#e8def8")
ON_SECONDARY_CONTAINER: Color = Color.from_hex("#1d192b")
SURFACE: Color = Color.from_hex("#fef7ff")
OUTLINE: Color = Color.from_hex("#79747e")
TRANSPARENT: Color = Color(r=0, g=0, b=0, a=0.0)


def filled_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *filled* button — the high-emphasis default.

    Carries no inline style, so the base stylesheet supplies the full filled
    look (primary fill, white label, hover elevation + state layer).

    Args:
        label: The button text.
        on_click: Handler fired when the button is pressed.
        key: Optional reconciler key.

    Returns:
        A :class:`~tempest_core.Button` rendered as an MD3 filled button.
    """
    return Button(label=label, on_click=on_click, key=key)


def tonal_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *filled tonal* button — medium emphasis.

    A secondary-container fill with on-secondary-container text; flat (no
    elevation), relying on the base sheet's state layer for feedback.

    Args:
        label: The button text.
        on_click: Handler fired when the button is pressed.
        key: Optional reconciler key.

    Returns:
        A :class:`~tempest_core.Button` rendered as an MD3 filled tonal button.
    """
    return Button(
        label=label,
        on_click=on_click,
        key=key,
        style=Style(background=SECONDARY_CONTAINER, color=ON_SECONDARY_CONTAINER),
    )


def elevated_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *elevated* button — a surface tint with a resting shadow.

    Args:
        label: The button text.
        on_click: Handler fired when the button is pressed.
        key: Optional reconciler key.

    Returns:
        A :class:`~tempest_core.Button` rendered as an MD3 elevated button.
    """
    return Button(
        label=label,
        on_click=on_click,
        key=key,
        style=Style(
            background=SURFACE,
            color=PRIMARY,
            shadow=Shadow(
                color=Color(r=0, g=0, b=0, a=0.3), blur=3.0, offset_x=0.0, offset_y=1.0
            ),
        ),
    )


def outlined_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *outlined* button — medium emphasis, transparent fill.

    A primary-colored label inside an outline; flat. The transparent background
    opts the button out of the base sheet's filled-button hover elevation.

    Args:
        label: The button text.
        on_click: Handler fired when the button is pressed.
        key: Optional reconciler key.

    Returns:
        A :class:`~tempest_core.Button` rendered as an MD3 outlined button.
    """
    return Button(
        label=label,
        on_click=on_click,
        key=key,
        style=Style(
            background=TRANSPARENT,
            color=PRIMARY,
            border=Border(width=1.0, color=OUTLINE),
        ),
    )


def text_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *text* button — low emphasis, no fill or outline.

    A primary-colored label on a transparent background; the base sheet's state
    layer still tints it on hover/press.

    Args:
        label: The button text.
        on_click: Handler fired when the button is pressed.
        key: Optional reconciler key.

    Returns:
        A :class:`~tempest_core.Button` rendered as an MD3 text button.
    """
    return Button(
        label=label,
        on_click=on_click,
        key=key,
        style=Style(background=TRANSPARENT, color=PRIMARY),
    )
