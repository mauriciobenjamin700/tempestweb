"""Disclosure components: ``Accordion`` (controlled expand/collapse section).

The ``open`` flag is controlled (lives in app state), toggled from the header
``on_toggle`` — mirroring ``Drawer``. No overlay needed: an open accordion simply
renders its body below the header.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestweb._core.components.base import ON_SURFACE, SURFACE, merge_style
from tempestweb._core.style import Edge, FontWeight, Style
from tempestweb._core.widgets import Button, Column, Component, Widget

__all__ = ["Accordion"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class Accordion(Component):
    """A titled section whose body shows only when ``open``.

    Attributes:
        title: The header text.
        open: Whether the body is expanded.
        children: The widgets revealed when open.
        on_toggle: Called when the header is tapped (flip ``open`` in state).
    """

    title: str = Field(default="", description="The header text.")
    open: bool = Field(default=False, description="Whether the body is expanded.")
    children: list[Widget] = Field(
        description="The widgets revealed when open.", default_factory=_no_widgets
    )
    on_toggle: Callable[[], Any] = Field(
        description="Called when the header is tapped (flip ``open`` in state)."
    )

    def render(self) -> Widget:
        """Lower the accordion into a primitive column.

        Returns:
            A ``Column`` of the header button and, when open, the body widgets.
        """
        marker = "▾" if self.open else "▸"
        header = Button(
            label=f"{marker}  {self.title}",
            on_click=self.on_toggle,
            key="accordion-header",
            style=Style(
                padding=Edge.symmetric(vertical=12.0, horizontal=14.0),
                radius=8.0,
                background=SURFACE,
                color=ON_SURFACE,
                font_weight=FontWeight.BOLD,
            ),
        )
        body: list[Widget] = []
        if self.open:
            body.append(
                Column(
                    style=Style(gap=8.0, padding=Edge.all(14.0)),
                    children=self.children,
                    key="accordion-body",
                )
            )
        default = Style(gap=6.0)
        return Column(
            key=self.key or "accordion",
            style=merge_style(default, self.style),
            children=[header, *body],
        )
