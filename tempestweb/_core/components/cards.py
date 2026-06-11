"""Content components: ``Card``, ``ListTile``, ``Avatar`` and ``Divider``.

Classic presentational building blocks that lower to primitives. Because tap
handling only exists on ``Button`` in the primitive set, ``ListTile`` is
presentational (no row-level ``on_click``); place a ``Button`` in its ``trailing``
slot for actions.
"""

from __future__ import annotations

from pydantic import Field

from tempestweb._core.components.base import (
    ACCENT,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestweb._core.style import AlignItems, Edge, FontWeight, Shadow, Style, TextAlign
from tempestweb._core.widgets import Column, Component, Container, Row, Text, Widget

__all__ = ["Card", "ListTile", "Avatar", "Divider"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class Card(Component):
    """An elevated surface grouping a stack of children.

    Attributes:
        children: The widgets stacked vertically inside the card.
    """

    children: list[Widget] = Field(
        description="The widgets stacked vertically inside the card.",
        default_factory=_no_widgets,
    )

    def render(self) -> Widget:
        """Lower the card into a padded, rounded, elevated container.

        Returns:
            A ``Container`` wrapping a ``Column`` of the children.
        """
        default = Style(
            padding=Edge.all(16.0),
            radius=14.0,
            background=SURFACE,
            shadow=Shadow(blur=12.0, offset_y=4.0),
        )
        return Container(
            key=self.key or "card",
            style=merge_style(default, self.style),
            child=Column(style=Style(gap=10.0), children=self.children),
        )


class ListTile(Component):
    """A single list row: optional leading/trailing widgets around a title block.

    Attributes:
        title: The row's primary text.
        subtitle: An optional secondary line shown muted under the title.
        leading: An optional widget shown before the text (e.g. an ``Avatar``).
        trailing: An optional widget shown after the text (e.g. a ``Button``).
    """

    title: str = Field(default="", description="The row's primary text.")
    subtitle: str | None = Field(
        default=None,
        description="An optional secondary line shown muted under the title.",
    )
    leading: Widget | None = Field(
        default=None,
        description="An optional widget shown before the text (e.g. an ``Avatar``).",
    )
    trailing: Widget | None = Field(
        default=None,
        description="An optional widget shown after the text (e.g. a ``Button``).",
    )

    def render(self) -> Widget:
        """Lower the list tile into a primitive row.

        Returns:
            A ``Row`` of the leading widget, the growing title block and the
            trailing widget.
        """
        text_children: list[Widget] = [
            Text(
                content=self.title,
                style=Style(font_size=16.0, color=ON_SURFACE),
                key="tile-title",
            )
        ]
        if self.subtitle is not None:
            text_children.append(
                Text(
                    content=self.subtitle,
                    style=Style(font_size=13.0, color=ON_MUTED),
                    key="tile-subtitle",
                )
            )
        children: list[Widget] = []
        if self.leading is not None:
            children.append(self.leading)
        children.append(
            Column(
                style=Style(grow=1.0, gap=2.0), children=text_children, key="tile-text"
            )
        )
        if self.trailing is not None:
            children.append(self.trailing)
        default = Style(
            gap=12.0,
            align=AlignItems.CENTER,
            padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
        )
        return Row(
            key=self.key or "listtile",
            style=merge_style(default, self.style),
            children=children,
        )


class Avatar(Component):
    """A round badge showing short initials.

    Attributes:
        initials: The short text shown inside the circle (e.g. ``"MB"``).
        size: The circle's diameter in logical pixels.
    """

    initials: str = Field(
        default="",
        description='The short text shown inside the circle (e.g. ``"MB"``).',
    )
    size: float = Field(
        default=40.0, description="The circle's diameter in logical pixels."
    )

    def render(self) -> Widget:
        """Lower the avatar into a circular container with centered initials.

        Returns:
            A ``Container`` sized to ``size`` wrapping a centered ``Text``.
        """
        default = Style(
            width=self.size,
            height=self.size,
            radius=self.size / 2.0,
            background=ACCENT,
            align=AlignItems.CENTER,
        )
        return Container(
            key=self.key or "avatar",
            style=merge_style(default, self.style),
            child=Text(
                content=self.initials,
                style=Style(
                    color=ON_SURFACE,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
                key="avatar-text",
            ),
        )


class Divider(Component):
    """A thin horizontal rule.

    Attributes:
        thickness: The line's height in logical pixels.
    """

    thickness: float = Field(
        default=1.0, description="The line's height in logical pixels."
    )

    def render(self) -> Widget:
        """Lower the divider into a thin, full-width container.

        Returns:
            An empty ``Container`` styled as a line.
        """
        default = Style(height=self.thickness, background=MUTED)
        return Container(
            key=self.key or "divider",
            style=merge_style(default, self.style),
        )
