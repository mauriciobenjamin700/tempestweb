r"""Tabular components: ``Table`` and ``DataTable``.

Both are :class:`Component`\s that lower to a primitive ``Column`` of ``Row``s of
``Container``/``Text`` cells, so they render identically in the Qt simulator and
on the Compose device with zero renderer changes. ``Table`` is a static
rows-by-columns grid built from typed :class:`TableRow`/:class:`TableCell`
values; ``DataTable`` is a string-matrix convenience that adds a header row and
an optional sortable affordance, both expressed purely as primitives.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tempestweb._core.components.base import (
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestweb._core.style import Border, Edge, FontWeight, SideBorder, Style
from tempestweb._core.widgets import Column, Component, Container, Row, Text, Widget

__all__ = ["TableCell", "TableRow", "Table", "DataTable"]

_CELL_PADDING: Edge = Edge.symmetric(vertical=8.0, horizontal=12.0)
_ROW_DIVIDER: SideBorder = SideBorder(bottom=Border(width=1.0, color=MUTED))


def _no_cells() -> list[TableCell]:
    """Provide a fresh, typed empty cell list for default factories.

    Returns:
        A new empty list of table cells.
    """
    return []


def _no_rows() -> list[TableRow]:
    """Provide a fresh, typed empty row list for default factories.

    Returns:
        A new empty list of table rows.
    """
    return []


def _no_str_rows() -> list[list[str]]:
    """Provide a fresh, typed empty string-matrix for default factories.

    Returns:
        A new empty list of string rows.
    """
    return []


def _no_str() -> list[str]:
    """Provide a fresh, typed empty string list for default factories.

    Returns:
        A new empty list of strings.
    """
    return []


class TableCell(BaseModel):
    """A single cell of a :class:`Table`.

    Attributes:
        content: The cell's text content.
        colspan: How many columns the cell spans (currently informational; the
            primitive lowering renders one cell per entry).
        rowspan: How many rows the cell spans (currently informational).
        style: An optional style overlaid on the cell's default padding/text.
    """

    model_config = ConfigDict(frozen=True)

    content: str = Field(description="The cell's text content.")
    colspan: int = Field(
        default=1,
        description="How many columns the cell spans (currently informational; the "
        "primitive lowering renders one cell per entry).",
    )
    rowspan: int = Field(
        default=1, description="How many rows the cell spans (currently informational)."
    )
    style: Style | None = None


class TableRow(BaseModel):
    """A single row of a :class:`Table`.

    Attributes:
        cells: The ordered cells of the row.
        style: An optional style overlaid on the row's default layout.
    """

    model_config = ConfigDict(frozen=True)

    cells: list[TableCell] = Field(
        description="The ordered cells of the row.", default_factory=_no_cells
    )
    style: Style | None = None


class Table(Component):
    r"""A static data table laid out as rows of equal-width cells.

    Attributes:
        rows: The body rows, each a :class:`TableRow` of :class:`TableCell`\s.
        headers: Optional header labels rendered as an emphasised first row.
        style: An optional style overlaid on the table's default surface.
    """

    rows: list[TableRow] = Field(
        description="The body rows, each a :class:`TableRow` of :class:`TableCell`\\s.",
        default_factory=_no_rows,
    )
    headers: list[str] = Field(
        description="Optional header labels rendered as an emphasised first row.",
        default_factory=_no_str,
    )
    style: Style | None = None

    def _cell(self, content: str, *, header: bool, key: str) -> Widget:
        """Build one primitive cell wrapped in a growing container.

        Args:
            content: The cell text.
            header: Whether the cell belongs to the header row.
            key: A stable key for the cell container.

        Returns:
            A growing ``Container`` wrapping the cell's ``Text``.
        """
        text_style = Style(
            color=ON_SURFACE if header else ON_MUTED,
            font_weight=FontWeight.BOLD if header else FontWeight.NORMAL,
        )
        return Container(
            key=key,
            style=Style(grow=1.0, padding=_CELL_PADDING),
            child=Text(content=content, style=text_style),
        )

    def render(self) -> Widget:
        """Lower the table into a primitive column of rows.

        Returns:
            A ``Column`` of ``Row``s; each row carries a bottom divider and each
            cell grows to share the row width evenly.
        """
        body: list[Widget] = []
        if self.headers:
            body.append(
                Row(
                    key="table-header",
                    style=Style(border=_ROW_DIVIDER, background=SURFACE),
                    children=[
                        self._cell(text, header=True, key=f"th-{index}")
                        for index, text in enumerate(self.headers)
                    ],
                )
            )
        for r_index, row in enumerate(self.rows):
            default_row = Style(border=_ROW_DIVIDER)
            body.append(
                Row(
                    key=f"table-row-{r_index}",
                    style=merge_style(default_row, row.style),
                    children=[
                        self._cell(
                            cell.content,
                            header=False,
                            key=f"td-{r_index}-{c_index}",
                        )
                        for c_index, cell in enumerate(row.cells)
                    ],
                )
            )
        default = Style(background=SURFACE)
        return Column(
            key=self.key or "table",
            style=merge_style(default, self.style),
            children=body,
        )


class DataTable(Component):
    """A string-matrix table with a header row and optional sort affordance.

    A convenience over :class:`Table` for the common case of a header plus a
    matrix of string rows. ``sortable`` only annotates the header (an arrow glyph
    is appended); the application performs the actual sort by reordering ``rows``
    in its state — no renderer logic is involved.

    Attributes:
        columns: The column header labels.
        rows: The body rows as a matrix of string cells.
        sortable: Whether to mark headers as sortable with an indicator glyph.
        style: An optional style overlaid on the table's default surface.
    """

    columns: list[str] = Field(
        description="The column header labels.", default_factory=_no_str
    )
    rows: list[list[str]] = Field(
        description="The body rows as a matrix of string cells.",
        default_factory=_no_str_rows,
    )
    sortable: bool = Field(
        default=False,
        description="Whether to mark headers as sortable with an indicator glyph.",
    )
    style: Style | None = None

    def render(self) -> Widget:
        """Lower the data table into a :class:`Table` of typed rows.

        Returns:
            A :class:`Table` built from the column headers and string matrix.
        """
        headers = [f"{label} ▾" if self.sortable else label for label in self.columns]
        table_rows = [
            TableRow(cells=[TableCell(content=value) for value in row])
            for row in self.rows
        ]
        return Table(
            key=self.key or "data-table",
            headers=headers,
            rows=table_rows,
            style=self.style,
        )
