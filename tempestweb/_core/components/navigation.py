"""Navigation components: ``NavBar`` (a.k.a. tab bar) and ``Breadcrumb``.

``NavBar`` generalises the ``examples/tabs`` pattern into a reusable component:
a row of selectable items with a highlighted active index. ``Breadcrumb`` renders
a path trail with separators. Because a :class:`Component`'s :meth:`render` runs
wherever ``build`` runs (desktop *and* device), the per-item handlers can close
over the caller's ``on_select`` and the item index directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestweb._core.components.base import (
    ACCENT,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestweb._core.style import AlignItems, Edge, FontWeight, JustifyContent, Style
from tempestweb._core.widgets import Button, Component, Row, Text, Widget

__all__ = ["NavBar", "Breadcrumb"]


def _no_labels() -> list[str]:
    """Provide a fresh, typed empty label list for the default factory.

    Returns:
        A new empty list of strings.
    """
    return []


class NavBar(Component):
    """A horizontal navigation/tab bar with a highlighted active item.

    Attributes:
        items: The visible item labels, in order.
        active: The index of the currently selected item.
        on_select: Called with the tapped item's index when an item is pressed.
    """

    items: list[str] = Field(
        description="The visible item labels, in order.", default_factory=_no_labels
    )
    active: int = Field(
        default=0, description="The index of the currently selected item."
    )
    on_select: Callable[[int], Any] = Field(
        description="Called with the tapped item's index when an item is pressed."
    )

    def _make_handler(self, index: int) -> Callable[[], None]:
        """Build a zero-argument handler that selects ``index``.

        Args:
            index: The item index this handler selects.

        Returns:
            A click handler invoking ``on_select`` with ``index``.
        """

        def handler() -> None:
            self.on_select(index)

        return handler

    def _item(self, index: int, label: str) -> Widget:
        """Build one navigation item button.

        Args:
            index: The item's position in the bar.
            label: The item's visible label.

        Returns:
            A button styled as active or inactive for ``self.active``.
        """
        active = index == self.active
        return Button(
            label=label,
            on_click=self._make_handler(index),
            key=f"nav-{index}",
            style=Style(
                grow=1.0,
                padding=Edge.symmetric(vertical=12.0, horizontal=8.0),
                radius=10.0,
                background=ACCENT if active else MUTED,
                color=ON_SURFACE,
                font_weight=FontWeight.BOLD if active else FontWeight.NORMAL,
            ),
        )

    def render(self) -> Widget:
        """Lower the navigation bar into a primitive row of buttons.

        Returns:
            A ``Row`` of item buttons with the active one highlighted.
        """
        default = Style(
            gap=8.0,
            padding=Edge.all(8.0),
            justify=JustifyContent.CENTER,
            background=SURFACE,
        )
        return Row(
            key=self.key or "navbar",
            style=merge_style(default, self.style),
            children=[
                self._item(index, label) for index, label in enumerate(self.items)
            ],
        )


class Breadcrumb(Component):
    """A path trail of crumbs joined by a separator.

    Attributes:
        items: The crumb labels from root to current, in order.
        separator: The text drawn between crumbs.
        on_select: Optional handler called with a crumb's index when tapped; when
            ``None`` the crumbs are presentational. The last crumb (current) is
            never tappable.
    """

    items: list[str] = Field(
        description="The crumb labels from root to current, in order.",
        default_factory=_no_labels,
    )
    separator: str = Field(default="/", description="The text drawn between crumbs.")
    on_select: Callable[[int], Any] | None = Field(
        default=None,
        description="Optional handler called with a crumb's index when tapped; when "
        "``None`` the crumbs are presentational. The last crumb (current) is never "
        "tappable.",
    )

    def _handler(self, index: int) -> Callable[[], None]:
        """Build a zero-argument handler selecting crumb ``index``.

        Args:
            index: The crumb index to report.

        Returns:
            A click handler invoking ``on_select`` with ``index``.
        """

        def handler() -> None:
            if self.on_select is not None:
                self.on_select(index)

        return handler

    def _crumb(self, index: int, label: str) -> Widget:
        """Build one crumb (tappable unless it is the current/last one).

        Args:
            index: The crumb's position.
            label: The crumb text.

        Returns:
            A ``Button`` for navigable crumbs, else a ``Text``.
        """
        is_last = index == len(self.items) - 1
        if self.on_select is not None and not is_last:
            return Button(
                label=label,
                on_click=self._handler(index),
                key=f"crumb-{index}",
                style=Style(
                    padding=Edge.symmetric(vertical=4.0, horizontal=6.0),
                    radius=6.0,
                    background=SURFACE,
                    color=ACCENT,
                    font_size=14.0,
                ),
            )
        return Text(
            content=label,
            key=f"crumb-{index}",
            style=Style(
                color=ON_SURFACE if is_last else ON_MUTED,
                font_size=14.0,
                font_weight=FontWeight.BOLD if is_last else FontWeight.NORMAL,
            ),
        )

    def render(self) -> Widget:
        """Lower the breadcrumb into a primitive row of crumbs and separators.

        Returns:
            A ``Row`` interleaving crumbs with separator labels.
        """
        children: list[Widget] = []
        for index, label in enumerate(self.items):
            if index:
                children.append(
                    Text(
                        content=self.separator,
                        style=Style(color=ON_MUTED, font_size=14.0),
                        key=f"sep-{index}",
                    )
                )
            children.append(self._crumb(index, label))
        default = Style(gap=6.0, align=AlignItems.CENTER)
        return Row(
            key=self.key or "breadcrumb",
            style=merge_style(default, self.style),
            children=children,
        )
