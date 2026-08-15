"""The dashboard page: a row of KPIs over a grid of titled sections."""

from __future__ import annotations

from collections.abc import Sequence

from tempest_core import Style, Widget
from tempest_core.components import Card, StatCard
from tempest_core.widgets import Column
from tempestweb.presets import roles
from tempestweb.presets.layout import box, heading, muted, page_header
from tempestweb.presets.models import Kpi, Section

__all__ = ["dashboard_page", "kpi_grid", "section_grid"]

#: Maps a KPI tone to the core StatCard colour scheme that carries it.
_TONE_SCHEME: dict[str, str] = {
    "neutral": "neutral",
    "success": "success",
    "warning": "warning",
    "danger": "error",
}


def kpi_grid(kpis: Sequence[Kpi], *, key: str = "tw-kpis") -> Widget:
    """Render headline numbers in a grid that reflows with the viewport.

    The grid is ``auto-fit``, so four KPIs become two columns on a tablet and one
    on a phone with no breakpoint of your own — and adding a fifth KPI does not
    require touching a layout.

    Args:
        kpis: The numbers to show, in order.
        key: The key prefix.

    Returns:
        The KPI grid container.
    """
    cards: list[Widget] = [
        StatCard(
            key=f"{key}-{index}",
            label=kpi.label,
            value=kpi.value,
            delta=kpi.delta,
            delta_up=kpi.up,
            color_scheme=_TONE_SCHEME.get(kpi.tone, "surface"),
        )
        for index, kpi in enumerate(kpis)
    ]
    return box(roles.KPI_GRID, cards, key=key)


def section_grid(sections: Sequence[Section], *, key: str = "tw-sections") -> Widget:
    """Render titled content blocks as cards in a reflowing grid.

    A section with ``span="full"`` takes the whole row — what a wide chart or a
    table wants — while the rest share the available tracks.

    Args:
        sections: The sections to render, in order.
        key: The key prefix.

    Returns:
        The section grid container.
    """
    blocks: list[Widget] = []
    for index, section in enumerate(sections):
        head: list[Widget] = [
            heading(section.title, key=f"{key}-{index}-title", level="group")
        ]
        if section.subtitle is not None:
            head.append(muted(section.subtitle, key=f"{key}-{index}-subtitle"))
        blocks.append(
            box(
                roles.SECTION,
                [
                    Card(
                        key=f"{key}-{index}-card",
                        children=[
                            Column(
                                key=f"{key}-{index}-head",
                                style=Style(gap=4.0),
                                children=head,
                            ),
                            section.body,
                        ],
                    )
                ],
                key=f"{key}-{index}",
                attrs={"data-tw-span": section.span},
            )
        )
    return box(roles.SECTION_GRID, blocks, key=key)


def dashboard_page(
    *,
    title: str,
    kpis: Sequence[Kpi] = (),
    sections: Sequence[Section] = (),
    subtitle: str | None = None,
    actions: Sequence[Widget] = (),
    key: str = "tw-dashboard",
) -> Widget:
    """Build a dashboard: a header, a KPI row and a grid of sections.

    Args:
        title: The page title.
        kpis: Headline numbers shown above the sections. Empty renders no row.
        sections: Titled content blocks. Empty renders no grid.
        subtitle: Optional line under the title.
        actions: Buttons shown opposite the title (a period picker, "Exportar").
        key: The key prefix for the page's widgets.

    Returns:
        The dashboard page.
    """
    children: list[Widget] = [
        page_header(
            title=title, subtitle=subtitle, actions=actions, key=f"{key}-header"
        )
    ]
    if kpis:
        children.append(kpi_grid(kpis, key=f"{key}-kpis"))
    if sections:
        children.append(section_grid(sections, key=f"{key}-sections"))
    return box(roles.PAGE, children, key=key)
