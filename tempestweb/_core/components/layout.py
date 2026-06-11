"""Page-structure components: ``Sidebar``, ``Scaffold`` and ``Grid``.

``Sidebar`` is a fixed-width lateral column; ``Scaffold`` is the page frame that
stacks an app bar, a growing body and an optional bottom bar; ``Grid`` lays
children out in a fixed number of equal-width columns. All lower to primitive
``Column``/``Row``/``Container`` trees.
"""

from __future__ import annotations

from pydantic import Field

from tempestweb._core.components.base import BACKGROUND, ON_SURFACE, SURFACE, merge_style
from tempestweb._core.style import Edge, Style
from tempestweb._core.widgets import Column, Component, Container, Row, ScrollView, Widget

__all__ = ["Sidebar", "Scaffold", "Grid"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class Sidebar(Component):
    """A fixed-width lateral column of navigation/content widgets.

    Attributes:
        children: The widgets stacked top-to-bottom in the sidebar.
        width: The sidebar's fixed width in logical pixels.
    """

    children: list[Widget] = Field(
        description="The widgets stacked top-to-bottom in the sidebar.",
        default_factory=_no_widgets,
    )
    width: float = Field(
        default=240.0, description="The sidebar's fixed width in logical pixels."
    )

    def render(self) -> Widget:
        """Lower the sidebar into a fixed-width primitive column.

        Returns:
            A ``Column`` carrying the sidebar's children.
        """
        default = Style(
            width=self.width,
            padding=Edge.all(16.0),
            gap=10.0,
            background=SURFACE,
            color=ON_SURFACE,
        )
        return Column(
            key=self.key or "sidebar",
            style=merge_style(default, self.style),
            children=self.children,
        )


class Scaffold(Component):
    """A page frame: app bar on top, growing body, optional bottom bar.

    Attributes:
        app_bar: The top bar widget (commonly an :class:`AppBar`); omitted when
            ``None``.
        body: The main content; defaults to an empty column when ``None``.
        bottom_bar: A bottom bar widget (e.g. a :class:`NavBar` or ``Footer``);
            omitted when ``None``.
        scroll: When ``True``, the body is wrapped in a ``ScrollView`` (a Qt
            convenience; the Compose renderer scrolls natively post-Trilho-B).
    """

    app_bar: Widget | None = Field(
        default=None,
        description="The top bar widget (commonly an :class:`AppBar`); omitted when "
        "``None``.",
    )
    body: Widget | None = Field(
        default=None,
        description="The main content; defaults to an empty column when ``None``.",
    )
    bottom_bar: Widget | None = Field(
        default=None,
        description="A bottom bar widget (e.g. a :class:`NavBar` or ``Footer``); "
        "omitted when ``None``.",
    )
    scroll: bool = Field(
        default=False,
        description="When ``True``, the body is wrapped in a ``ScrollView`` (a Qt "
        "convenience; the Compose renderer scrolls natively post-Trilho-B).",
    )

    def render(self) -> Widget:
        """Lower the scaffold into a stacked primitive column.

        Returns:
            A ``Column`` stacking the app bar, the (growing) body and the bottom
            bar in order.
        """
        children: list[Widget] = []
        if self.app_bar is not None:
            children.append(self.app_bar)
        body: Widget = self.body if self.body is not None else Column()
        if self.scroll:
            body = ScrollView(
                children=[body], style=Style(grow=1.0), key="scaffold-body"
            )
        else:
            body = Container(child=body, style=Style(grow=1.0), key="scaffold-body")
        children.append(body)
        if self.bottom_bar is not None:
            children.append(self.bottom_bar)
        default = Style(gap=0.0, background=BACKGROUND)
        return Column(
            key=self.key or "scaffold",
            style=merge_style(default, self.style),
            children=children,
        )


class Grid(Component):
    """A fixed-column grid laying children out in equal-width cells.

    Attributes:
        children: The cell widgets, filled left-to-right then top-to-bottom.
        columns: The number of columns per row (clamped to at least 1).
        gap: The spacing between cells, both horizontally and vertically.
    """

    children: list[Widget] = Field(
        description="The cell widgets, filled left-to-right then top-to-bottom.",
        default_factory=_no_widgets,
    )
    columns: int = Field(
        default=2, description="The number of columns per row (clamped to at least 1)."
    )
    gap: float = Field(
        default=8.0,
        description="The spacing between cells, both horizontally and vertically.",
    )

    def render(self) -> Widget:
        """Lower the grid into a primitive column of rows.

        Returns:
            A ``Column`` of ``Row``s; each child is wrapped in a growing
            ``Container`` so columns share width, and short final rows are padded
            with empty cells to keep alignment.
        """
        columns = max(1, self.columns)
        rows: list[Widget] = []
        for start in range(0, len(self.children), columns):
            chunk = self.children[start : start + columns]
            cells: list[Widget] = [
                Container(
                    style=Style(grow=1.0),
                    child=child,
                    key=f"cell-{start + offset}",
                )
                for offset, child in enumerate(chunk)
            ]
            for pad in range(len(chunk), columns):
                cells.append(
                    Container(style=Style(grow=1.0), key=f"cell-pad-{start}-{pad}")
                )
            rows.append(
                Row(style=Style(gap=self.gap), children=cells, key=f"grid-row-{start}")
            )
        default = Style(gap=self.gap)
        return Column(
            key=self.key or "grid",
            style=merge_style(default, self.style),
            children=rows,
        )
