"""Feedback components: ``Banner``, ``EmptyState`` and ``Badge``.

Inline (non-overlay) status surfaces built from primitives. Transient/overlay
feedback (snackbars, toasts, dialogs) needs a stacking layer and is out of scope
until the renderer grows one.
"""

from __future__ import annotations

from pydantic import Field

from tempestweb._core.components.base import ON_SURFACE, merge_style
from tempestweb._core.style import AlignItems, Color, Edge, FontWeight, Style, TextAlign
from tempestweb._core.widgets import Column, Component, Row, Text, Widget

__all__ = ["Banner", "EmptyState", "Badge"]

#: Tone → background color for status surfaces.
_TONES: dict[str, Color] = {
    "info": Color.from_hex("#2563eb"),
    "success": Color.from_hex("#16a34a"),
    "warning": Color.from_hex("#d97706"),
    "error": Color.from_hex("#dc2626"),
}


def _tone_color(tone: str) -> Color:
    """Resolve a tone name to its background color.

    Args:
        tone: One of ``"info"``, ``"success"``, ``"warning"`` or ``"error"``.

    Returns:
        The mapped color, falling back to the ``"info"`` color when unknown.
    """
    return _TONES.get(tone, _TONES["info"])


class Banner(Component):
    """An inline status bar with a message and an optional trailing action.

    Attributes:
        message: The banner text.
        tone: The status tone (``"info"`` / ``"success"`` / ``"warning"`` /
            ``"error"``) selecting the background color.
        action: An optional trailing widget (e.g. a dismiss ``Button``).
    """

    message: str = Field(default="", description="The banner text.")
    tone: str = Field(
        default="info",
        description='The status tone (``"info"`` / ``"success"`` / ``"warning"`` / '
        '``"error"``) selecting the background color.',
    )
    action: Widget | None = Field(
        default=None,
        description="An optional trailing widget (e.g. a dismiss ``Button``).",
    )

    def render(self) -> Widget:
        """Lower the banner into a primitive row.

        Returns:
            A toned ``Row`` with the growing message and the optional action.
        """
        children: list[Widget] = [
            Text(
                content=self.message,
                style=Style(grow=1.0, color=ON_SURFACE, font_size=14.0),
                key="banner-text",
            )
        ]
        if self.action is not None:
            children.append(self.action)
        default = Style(
            gap=12.0,
            align=AlignItems.CENTER,
            padding=Edge.symmetric(vertical=12.0, horizontal=14.0),
            radius=10.0,
            background=_tone_color(self.tone),
        )
        return Row(
            key=self.key or "banner",
            style=merge_style(default, self.style),
            children=children,
        )


class EmptyState(Component):
    """A centered placeholder for empty screens: glyph, title, subtitle, action.

    Attributes:
        title: The primary message.
        subtitle: An optional secondary line.
        glyph: A large text glyph shown above the title (no icon font needed).
        action: An optional call-to-action widget (e.g. a ``Button``).
    """

    title: str = Field(default="", description="The primary message.")
    subtitle: str | None = Field(
        default=None, description="An optional secondary line."
    )
    glyph: str = Field(
        default="○",
        description="A large text glyph shown above the title (no icon font needed).",
    )
    action: Widget | None = Field(
        default=None,
        description="An optional call-to-action widget (e.g. a ``Button``).",
    )

    def render(self) -> Widget:
        """Lower the empty state into a centered primitive column.

        Returns:
            A ``Column`` stacking the glyph, title, optional subtitle and action.
        """
        children: list[Widget] = [
            Text(
                content=self.glyph,
                style=Style(
                    font_size=48.0, color=ON_SURFACE, text_align=TextAlign.CENTER
                ),
                key="empty-glyph",
            ),
            Text(
                content=self.title,
                style=Style(
                    font_size=18.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
                key="empty-title",
            ),
        ]
        if self.subtitle is not None:
            children.append(
                Text(
                    content=self.subtitle,
                    style=Style(
                        font_size=14.0,
                        color=ON_SURFACE,
                        text_align=TextAlign.CENTER,
                    ),
                    key="empty-subtitle",
                )
            )
        if self.action is not None:
            children.append(self.action)
        default = Style(gap=10.0, align=AlignItems.CENTER, padding=Edge.all(24.0))
        return Column(
            key=self.key or "emptystate",
            style=merge_style(default, self.style),
            children=children,
        )


class Badge(Component):
    """A small inline status pill (count or short label).

    Attributes:
        label: The badge text (e.g. a count like ``"3"`` or ``"NEW"``).
        tone: The status tone selecting the background color.
    """

    label: str = Field(
        default="",
        description='The badge text (e.g. a count like ``"3"`` or ``"NEW"``).',
    )
    tone: str = Field(
        default="error", description="The status tone selecting the background color."
    )

    def render(self) -> Widget:
        """Lower the badge into a primitive pill.

        Returns:
            A small rounded ``Text`` pill in the tone color.
        """
        default = Style(
            padding=Edge.symmetric(vertical=2.0, horizontal=8.0),
            radius=10.0,
            background=_tone_color(self.tone),
            color=ON_SURFACE,
            font_size=12.0,
            font_weight=FontWeight.BOLD,
            text_align=TextAlign.CENTER,
        )
        return Text(
            content=self.label,
            key=self.key or "badge",
            style=merge_style(default, self.style),
        )
