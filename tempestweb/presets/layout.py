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
from typing import Literal

from tempest_core import Column, Stack, Style, Text, Widget
from tempestweb.presets import roles

__all__ = ["Level", "box", "heading", "muted", "page_header"]

#: Which step of the type scale a heading sits on.
Level = Literal["page", "section", "group"]


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


def heading(text: str, *, key: str, level: Level = "section") -> Widget:
    """Render a page, section or group heading.

    Size, weight and colour come from the stylesheet, not from here. A preset
    that hard-coded them would pick a colour from one palette and land on a page
    themed with another — a white title on a white page. The sheet resolves them
    from the theme's own tokens, so a rebranded app rebrands its headings too.

    Args:
        text: The heading text.
        key: The widget key.
        level: Which step of the type scale to use.

    Returns:
        The heading text, tagged for the sheet.
    """
    return Text(
        content=text,
        key=key,
        attrs={roles.LAYOUT_ATTR: roles.TITLE, "data-tw-level": level},
    )


def muted(text: str, *, key: str) -> Widget:
    """Render supporting text (a subtitle, a hint, a help line).

    Args:
        text: The text.
        key: The widget key.

    Returns:
        The text, tagged so the sheet gives it the muted treatment.
    """
    return Text(content=text, key=key, attrs={roles.LAYOUT_ATTR: roles.SUBTITLE})


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
    titles: list[Widget] = [heading(title, key=f"{key}-title", level="page")]
    if subtitle is not None:
        titles.append(muted(subtitle, key=f"{key}-subtitle"))
    children: list[Widget] = [
        Column(key=f"{key}-titles", style=Style(gap=4.0), children=titles)
    ]
    if actions:
        children.append(box(roles.PAGE_ACTIONS, actions, key=f"{key}-actions"))
    return box(roles.PAGE_HEADER, children, key=key)
