"""The form and settings pages: labelled fields in a grid over an action bar."""

from __future__ import annotations

from collections.abc import Sequence

from tempest_core import Style, Widget
from tempest_core.components import Card
from tempest_core.components.base import ON_SURFACE
from tempest_core.style import Color, FontWeight
from tempest_core.widgets import Column, Text
from tempestweb.presets import roles
from tempestweb.presets.layout import box, heading, muted, page_header
from tempestweb.presets.models import FormField, FormSection

__all__ = ["form_page", "form_section", "settings_page"]

#: The core's error red, for a field's validation line.
_ERROR = Color(r=179, g=38, b=30, a=1.0)


def _field(field: FormField, *, key: str) -> Widget:
    """Render one labelled control with its help or error line.

    Args:
        field: The field to render.
        key: The widget key prefix.

    Returns:
        The field container, spanning the full row when the field asks for it.
    """
    children: list[Widget] = [
        Text(
            content=field.label,
            key=f"{key}-label",
            style=Style(font_size=13.0, font_weight=FontWeight.BOLD, color=ON_SURFACE),
        ),
        field.control,
    ]
    if field.error is not None:
        children.append(
            Text(
                content=field.error,
                key=f"{key}-error",
                style=Style(font_size=12.0, color=_ERROR),
            )
        )
    elif field.help is not None:
        children.append(muted(field.help, key=f"{key}-help", size=12.0))
    return box(
        roles.FORM_FIELD,
        [Column(key=f"{key}-col", style=Style(gap=6.0), children=children)],
        key=key,
        attrs={"data-tw-span": field.span},
    )


def form_section(section: FormSection, *, key: str) -> Widget:
    """Render a titled group of fields as a card.

    Args:
        section: The group to render.
        key: The widget key prefix.

    Returns:
        The section card.
    """
    head: list[Widget] = [heading(section.title, key=f"{key}-title", size=18.0)]
    if section.subtitle is not None:
        head.append(muted(section.subtitle, key=f"{key}-subtitle"))
    fields = box(
        roles.FORM_GRID,
        [
            _field(item, key=f"{key}-f{index}")
            for index, item in enumerate(section.fields)
        ],
        key=f"{key}-grid",
    )
    return Card(
        key=key,
        children=[
            Column(key=f"{key}-head", style=Style(gap=4.0), children=head),
            fields,
        ],
    )


def form_page(
    *,
    title: str,
    fields: Sequence[FormField] = (),
    sections: Sequence[FormSection] = (),
    actions: Sequence[Widget] = (),
    subtitle: str | None = None,
    key: str = "tw-form",
) -> Widget:
    """Build a form screen: fields in a responsive grid over an action bar.

    Pass ``fields`` for a flat form or ``sections`` for a grouped one; passing
    both puts the loose fields first, in their own grid. Field widths come from
    the grid, which fits as many columns as the viewport allows and drops to one
    on a phone — a field marked ``span="full"`` always takes the whole row.

    The action bar sits at the end, right-aligned on a wide screen and stacked
    (primary action last, so it lands under the thumb) on a phone.

    Args:
        title: The page title.
        fields: Ungrouped fields, rendered before any sections.
        sections: Grouped fields, each rendered as a card.
        actions: The submit/cancel buttons. Empty renders no action bar.
        subtitle: Optional line under the title.
        key: The key prefix for the page's widgets.

    Returns:
        The form page.
    """
    children: list[Widget] = [
        page_header(title=title, subtitle=subtitle, key=f"{key}-header")
    ]
    if fields:
        children.append(
            box(
                roles.FORM_GRID,
                [
                    _field(item, key=f"{key}-f{index}")
                    for index, item in enumerate(fields)
                ],
                key=f"{key}-grid",
            )
        )
    for index, section in enumerate(sections):
        children.append(form_section(section, key=f"{key}-s{index}"))
    if actions:
        children.append(box(roles.FORM_ACTIONS, actions, key=f"{key}-actions"))
    return box(roles.PAGE, children, key=key)


def settings_page(
    *,
    title: str,
    sections: Sequence[FormSection],
    actions: Sequence[Widget] = (),
    subtitle: str | None = None,
    key: str = "tw-settings",
) -> Widget:
    """Build a settings screen — a form page whose fields are always grouped.

    Args:
        title: The page title.
        sections: The setting groups, each rendered as a card.
        actions: The save/discard buttons.
        subtitle: Optional line under the title.
        key: The key prefix for the page's widgets.

    Returns:
        The settings page.
    """
    return form_page(
        title=title,
        sections=sections,
        actions=actions,
        subtitle=subtitle,
        key=key,
    )
