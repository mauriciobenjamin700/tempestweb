"""Shared helpers and default theme tokens for the composite components.

The components in this package lower to primitive widgets via
:class:`tempestroid.widgets.Component`. They ship a small dark default palette so
an ``AppBar`` or ``Scaffold`` looks intentional out of the box; every component
also accepts a ``style`` that is merged over its default (see :func:`merge_style`),
so callers override only the fields they care about.
"""

from __future__ import annotations

from tempestweb._core.style import Color, Style

__all__ = [
    "SURFACE",
    "BACKGROUND",
    "ACCENT",
    "MUTED",
    "ON_SURFACE",
    "ON_MUTED",
    "merge_style",
]

#: Default theme tokens (a restrained dark palette matching the examples).
BACKGROUND: Color = Color.from_hex("#0b0f14")
SURFACE: Color = Color.from_hex("#1f2937")
ACCENT: Color = Color.from_hex("#2563eb")
MUTED: Color = Color.from_hex("#374151")
ON_SURFACE: Color = Color.from_hex("#f9fafb")
ON_MUTED: Color = Color.from_hex("#9ca3af")


def merge_style(base: Style, override: Style | None) -> Style:
    """Overlay the set fields of ``override`` onto ``base``.

    Only fields explicitly set to a non-``None`` value on ``override`` win; every
    other field keeps the component's default. ``Style`` is frozen, so this
    returns a fresh merged copy.

    Args:
        base: The component's default style.
        override: The caller-supplied style, or ``None`` to keep the default.

    Returns:
        The merged style (``base`` unchanged when ``override`` is ``None``).
    """
    if override is None:
        return base
    updates: dict[str, object] = {
        name: getattr(override, name)
        for name in type(override).model_fields
        if getattr(override, name) is not None
    }
    return base.model_copy(update=updates)
