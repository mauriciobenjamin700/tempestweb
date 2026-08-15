"""The shared building blocks every preset is assembled from.

:func:`box` is the one place a layout role reaches the DOM: it wraps children in
a :class:`~tempest_core.widgets.Stack` carrying ``data-tw-layout``. ``Stack`` and
not ``Column``/``Row`` on purpose — the client writes an inline ``display: flex``
for those two widget types, and inline beats the stylesheet, so a grid rule would
never apply. ``Stack`` renders a bare ``div`` with no inline display, leaving the
layout to ``client/layouts.js``.
"""

from __future__ import annotations

from collections.abc import Sequence

from tempest_core import Style, Text, Widget
from tempest_core.components.base import ON_MUTED, ON_SURFACE
from tempest_core.style import FontWeight
from tempest_core.widgets import Column, Stack
from tempestweb.presets import roles

__all__ = ["box", "heading", "muted", "page_header"]


def box(
    role: str,
    children: Sequence[Widget],
    *,
    key: str,
    attrs: dict[str, str] | None = None,
    style: Style | None = None,
) -> Widget:
    """Wrap ``children`` in a container tagged with a layout role.

    Args:
        role: A role from :mod:`tempestweb.presets.roles`; the stylesheet keys
            its rules off this value.
        children: The container's children, in order.
        key: The widget key, unique among its siblings.
        attrs: Extra attributes merged after the role (``data-tw-open``,
            ``data-tw-span``, …). It cannot override the role itself.
        style: Optional inline style. Leave it unset for anything the sheet lays
            out — an inline declaration wins over the sheet's rule.

    Returns:
        The tagged container.
    """
    merged: dict[str, str] = dict(attrs or {})
    merged[roles.LAYOUT_ATTR] = role
    return Stack(key=key, children=list(children), attrs=merged, style=style)


def heading(text: str, *, key: str, size: float = 20.0) -> Widget:
    """Render a section or page heading.

    Args:
        text: The heading text.
        key: The widget key.
        size: The font size in pixels.

    Returns:
        A bold, on-surface :class:`~tempest_core.widgets.Text`.
    """
    return Text(
        content=text,
        key=key,
        style=Style(font_size=size, font_weight=FontWeight.BOLD, color=ON_SURFACE),
    )


def muted(text: str, *, key: str, size: float = 13.0) -> Widget:
    """Render supporting text (a subtitle, a hint, a help line).

    Args:
        text: The text.
        key: The widget key.
        size: The font size in pixels.

    Returns:
        A muted :class:`~tempest_core.widgets.Text`.
    """
    return Text(content=text, key=key, style=Style(font_size=size, color=ON_MUTED))


def page_header(
    *,
    title: str,
    key: str,
    subtitle: str | None = None,
    actions: Sequence[Widget] = (),
) -> Widget:
    """Render a page's title block with its action buttons.

    The title and the actions sit on one row on a wide screen and stack on a
    phone — the sheet handles the switch, so nothing here measures the viewport.

    Args:
        title: The page title.
        key: The key prefix for the header's widgets.
        subtitle: Optional line under the title.
        actions: Buttons shown opposite the title ("Novo", "Exportar").

    Returns:
        The header container.
    """
    titles: list[Widget] = [heading(title, key=f"{key}-title", size=24.0)]
    if subtitle is not None:
        titles.append(muted(subtitle, key=f"{key}-subtitle"))
    children: list[Widget] = [
        Column(key=f"{key}-titles", style=Style(gap=4.0), children=titles)
    ]
    if actions:
        children.append(box(roles.PAGE_ACTIONS, actions, key=f"{key}-actions"))
    return box(roles.PAGE_HEADER, children, key=key)
