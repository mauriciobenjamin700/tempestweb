"""Material 3 button variants as one-line helpers.

tempest-core resolves each :class:`~tempest_core.Button` *variant* to its resting
Material 3 style inline — fill, border, shape and text color all come from the
core's ``Variant`` + ``color_scheme`` system. These helpers are the MD3-named
façade over that system: each picks the core variant and color scheme for one
Material 3 button type, so app code reads in MD3 vocabulary (``filled_button`` /
``tonal_button`` / …) instead of the generic enum.

    from tempestweb.components import filled_button, tonal_button, text_button

    filled_button("Save", on_click=save)
    text_button("Cancel", on_click=close)

The always-on base stylesheet (``client/theme.js``) adds only what inline style
cannot express — the :hover / :focus-visible / :active state layer and focus ring.
``elevated_button`` has no core variant of its own, so it layers a small resting
shadow over the filled style — the one place a helper still adds inline Style;
the core merges that override onto the variant-resolved base. Every variant
renders identically in Mode A (WASM) and Mode B (server).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tempest_core import Button, Variant
from tempest_core.style import Color, Shadow, Style

__all__ = [
    "elevated_button",
    "filled_button",
    "outlined_button",
    "text_button",
    "tonal_button",
]


def filled_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *filled* button — the high-emphasis default.

    Delegates to the core ``SOLID`` variant on the ``primary`` color scheme, so
    the primary fill and white label come from the core's resolved style.

    Args:
        label: The button text.
        on_click: Handler fired when the button is pressed.
        key: Optional reconciler key.

    Returns:
        A :class:`~tempest_core.Button` rendered as an MD3 filled button.
    """
    return Button(
        label=label,
        on_click=on_click,
        key=key,
        variant=Variant.SOLID,
        color_scheme="primary",
    )


def tonal_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *filled tonal* button — medium emphasis.

    Delegates to the core ``SOLID`` variant on the ``secondary`` color scheme for
    a lower-emphasis, secondary-toned fill.

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
        variant=Variant.SOLID,
        color_scheme="secondary",
    )


def elevated_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *elevated* button — a filled button with a resting shadow.

    The core has no elevated variant, so this layers a small inline
    :class:`~tempest_core.style.Shadow` over the ``SOLID`` / ``primary`` fill; the
    core merges the shadow override onto the variant-resolved base style.

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
        variant=Variant.SOLID,
        color_scheme="primary",
        style=Style(
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
    """Build a Material 3 *outlined* button — medium emphasis with a border.

    Delegates to the core ``OUTLINE`` variant, whose resolved style draws the
    primary-toned border.

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
        variant=Variant.OUTLINE,
    )


def text_button(
    label: str,
    on_click: Callable[[], Any] | None = None,
    *,
    key: str | None = None,
) -> Button:
    """Build a Material 3 *text* button — low emphasis, no border.

    Delegates to the core ``GHOST`` variant, the lowest-emphasis button: a bare
    label with no border, the base sheet's state layer still tinting it on
    hover/press.

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
        variant=Variant.GHOST,
    )
