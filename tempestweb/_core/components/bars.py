"""Bar components: ``AppBar``, ``Header`` and ``Footer``.

Each is a :class:`Component` that lowers to a primitive ``Row``/``Column`` tree,
so they render identically in the Qt simulator and on the Compose device.
"""

from __future__ import annotations

from pydantic import Field

from tempestweb._core.components.base import (
    BACKGROUND,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestweb._core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    Style,
)
from tempestweb._core.widgets import Column, Component, Container, Row, Text, Widget

__all__ = ["AppBar", "Header", "Footer", "CollapsingAppBar"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class AppBar(Component):
    """A top application bar: optional leading widget, title and trailing actions.

    Attributes:
        title: The bar's title text.
        leading: An optional widget shown before the title (e.g. a menu or back
            button); omitted when ``None``.
        actions: Trailing action widgets laid out at the end of the bar.
    """

    title: str = Field(default="", description="The bar's title text.")
    leading: Widget | None = Field(
        default=None,
        description="An optional widget shown before the title (e.g. a menu or back "
        "button); omitted when ``None``.",
    )
    actions: list[Widget] = Field(
        description="Trailing action widgets laid out at the end of the bar.",
        default_factory=_no_widgets,
    )

    def render(self) -> Widget:
        """Lower the app bar into a horizontal primitive row.

        Returns:
            A ``Row`` with the leading widget, a growing title and the actions.
        """
        children: list[Widget] = []
        if self.leading is not None:
            children.append(self.leading)
        children.append(
            Text(
                content=self.title,
                style=Style(
                    grow=1.0,
                    font_size=20.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="appbar-title",
            )
        )
        if self.actions:
            children.append(
                Row(style=Style(gap=8.0), children=self.actions, key="appbar-actions")
            )
        default = Style(
            padding=Edge.symmetric(vertical=14.0, horizontal=16.0),
            gap=12.0,
            align=AlignItems.CENTER,
            background=SURFACE,
        )
        return Row(
            key=self.key or "appbar",
            style=merge_style(default, self.style),
            children=children,
        )


class Header(Component):
    """A page header band: a title with an optional subtitle.

    Attributes:
        title: The header's primary line.
        subtitle: An optional secondary line shown muted under the title.
    """

    title: str = Field(default="", description="The header's primary line.")
    subtitle: str | None = Field(
        default=None,
        description="An optional secondary line shown muted under the title.",
    )

    def render(self) -> Widget:
        """Lower the header into a stacked primitive column.

        Returns:
            A ``Column`` with the title and, when set, the subtitle.
        """
        children: list[Widget] = [
            Text(
                content=self.title,
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="header-title",
            )
        ]
        if self.subtitle is not None:
            children.append(
                Text(
                    content=self.subtitle,
                    style=Style(font_size=14.0, color=ON_MUTED),
                    key="header-subtitle",
                )
            )
        default = Style(padding=Edge.all(20.0), gap=4.0, background=BACKGROUND)
        return Column(
            key=self.key or "header",
            style=merge_style(default, self.style),
            children=children,
        )


class Footer(Component):
    """A bottom bar holding arbitrary, centered content.

    Attributes:
        children: The widgets laid out in the footer (e.g. links or labels).
    """

    children: list[Widget] = Field(
        description="The widgets laid out in the footer (e.g. links or labels).",
        default_factory=_no_widgets,
    )

    def render(self) -> Widget:
        """Lower the footer into a centered primitive row.

        Returns:
            A ``Row`` containing the footer's children.
        """
        default = Style(
            padding=Edge.symmetric(vertical=12.0, horizontal=16.0),
            gap=12.0,
            align=AlignItems.CENTER,
            background=SURFACE,
        )
        return Row(
            key=self.key or "footer",
            style=merge_style(default, self.style),
            children=self.children,
        )


class CollapsingAppBar(Component):
    """A sliver-style app bar that shrinks as the user scrolls the content down.

    Coordinates with a scrollable container's ``on_scroll`` handler entirely
    through state: the application reads the current scroll offset from the
    list's :class:`~tempestroid.ScrollEvent`, stores it, and passes it back as
    :attr:`scroll_offset`. The component derives a height that eases from
    :attr:`expanded_height` (offset ``0``) down to :attr:`collapsed_height` (once
    the offset exceeds the collapse distance) and renders accordingly — so the
    reconciler simply diffs the derived ``Style.height`` as an ordinary prop,
    needing no new IR, no new event and no renderer change. The title's font
    shrinks in step with the bar.

    Attributes:
        title: The bar's title text.
        expanded_height: The bar height at the top of the scroll (offset ``0``).
        collapsed_height: The minimum bar height once fully collapsed.
        scroll_offset: The current scroll offset (logical pixels) driven by the
            application from the scrollable's ``on_scroll`` handler.
        background: An optional background color (defaults to the surface token).
        style: An optional style overlaid on the bar's derived default.
    """

    title: str = Field(default="", description="The bar's title text.")
    expanded_height: float = Field(
        default=200.0,
        description="The bar height at the top of the scroll (offset ``0``).",
    )
    collapsed_height: float = Field(
        default=56.0, description="The minimum bar height once fully collapsed."
    )
    scroll_offset: float = Field(
        default=0.0,
        description="The current scroll offset (logical pixels) driven by the "
        "application from the scrollable's ``on_scroll`` handler.",
    )
    background: Color | None = Field(
        default=None,
        description="An optional background color (defaults to the surface token).",
    )
    style: Style | None = None

    def _height(self) -> float:
        """Derive the current bar height from the scroll offset.

        The bar collapses linearly over a distance equal to the difference
        between the expanded and collapsed heights, clamped to that band.

        Returns:
            The current bar height in logical pixels.
        """
        span = max(0.0, self.expanded_height - self.collapsed_height)
        consumed = min(max(self.scroll_offset, 0.0), span)
        return self.expanded_height - consumed

    def render(self) -> Widget:
        """Lower the collapsing app bar into a primitive container with a title.

        Returns:
            A bottom-aligned ``Container`` whose height tracks the scroll offset,
            wrapping the title (whose size eases between expanded and collapsed).
        """
        height = self._height()
        span = max(1.0, self.expanded_height - self.collapsed_height)
        progress = (self.expanded_height - height) / span  # 0 expanded .. 1 collapsed
        font_size = 28.0 - 8.0 * progress  # 28 expanded -> 20 collapsed
        default = Style(
            height=height,
            padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
            justify=JustifyContent.END,
            background=self.background or SURFACE,
        )
        return Container(
            key=self.key or "collapsing-app-bar",
            style=merge_style(default, self.style),
            child=Column(
                style=Style(justify=JustifyContent.END, align=AlignItems.START),
                children=[
                    Text(
                        content=self.title,
                        style=Style(
                            font_size=font_size,
                            font_weight=FontWeight.BOLD,
                            color=ON_SURFACE,
                        ),
                        key="collapsing-title",
                    )
                ],
            ),
        )
