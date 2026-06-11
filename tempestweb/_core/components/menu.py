"""Menu components: ``Burger`` (menu button) and ``Drawer`` (lateral panel).

Both lower to primitives. ``Drawer`` is *controlled*: its ``open`` flag lives in
app state (toggle it from a ``Burger``'s ``on_click``), mirroring every other
component. Because the layout model is flex-only (no stacking/overlay), an open
drawer renders as a lateral panel rather than a floating overlay with a scrim;
true overlay is a renderer follow-up.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestweb._core.components.base import MUTED, ON_SURFACE, SURFACE, merge_style
from tempestweb._core.style import Edge, Style
from tempestweb._core.widgets import Button, Column, Component, Container, Widget

__all__ = ["Burger", "Drawer"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class Burger(Component):
    """A hamburger menu button.

    Attributes:
        on_click: Invoked when the button is tapped (e.g. to toggle a ``Drawer``).
        glyph: The icon character to display (defaults to ``☰``).
    """

    on_click: Callable[[], Any] = Field(
        description="Invoked when the button is tapped (e.g. to toggle a ``Drawer``)."
    )
    glyph: str = Field(
        default="☰", description="The icon character to display (defaults to ``☰``)."
    )

    def render(self) -> Widget:
        """Lower the burger into a primitive button.

        Returns:
            A ``Button`` showing the menu glyph.
        """
        default = Style(
            padding=Edge.symmetric(vertical=8.0, horizontal=12.0),
            radius=8.0,
            background=MUTED,
            color=ON_SURFACE,
            font_size=20.0,
        )
        return Button(
            label=self.glyph,
            on_click=self.on_click,
            key=self.key or "burger",
            style=merge_style(default, self.style),
        )


class Drawer(Component):
    """A controlled lateral panel that shows its children when ``open``.

    Attributes:
        open: Whether the drawer is expanded; when ``False`` it collapses to an
            empty box.
        children: The widgets stacked inside the open drawer.
        width: The panel width in logical pixels when open.
    """

    open: bool = Field(
        default=False,
        description="Whether the drawer is expanded; when ``False`` it collapses to an "
        "empty box.",
    )
    children: list[Widget] = Field(
        description="The widgets stacked inside the open drawer.",
        default_factory=_no_widgets,
    )
    width: float = Field(
        default=260.0, description="The panel width in logical pixels when open."
    )

    def render(self) -> Widget:
        """Lower the drawer into a primitive panel or an empty box.

        Returns:
            A styled ``Column`` panel when open, otherwise an empty ``Container``.
        """
        if not self.open:
            return Container(key=self.key or "drawer")
        default = Style(
            width=self.width,
            padding=Edge.all(16.0),
            gap=10.0,
            background=SURFACE,
            color=ON_SURFACE,
        )
        return Column(
            key=self.key or "drawer",
            style=merge_style(default, self.style),
            children=self.children,
        )
