"""Sortable data table — exercises DataTable, SearchBar and column-sort state.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates the ``DataTable`` component driven entirely from Python state:

* A :class:`~tempestweb._core.components.SearchBar` filters the visible rows as
  the user types — no network call, no debounce, pure in-memory predicate.
* Clicking a column-header button sorts the rows ascending on the first click and
  descending on the second click of the same column (the classic toggle cycle).
* A summary line shows how many rows are visible versus the full dataset, so the
  user always knows the filter is active.

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import DataTable, SearchBar
from tempestweb._core.style import AlignItems, Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Row, Text
from tempestweb._core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Domain data
# ---------------------------------------------------------------------------

#: Sample employee dataset — all string columns (name, department, city, salary).
_EMPLOYEES: list[tuple[str, str, str, str]] = [
    ("Alice Martins", "Engineering", "São Paulo", "R$ 18.500"),
    ("Bruno Costa", "Design", "Rio de Janeiro", "R$ 12.000"),
    ("Carla Fonseca", "Product", "Belo Horizonte", "R$ 14.200"),
    ("Diego Ribeiro", "Engineering", "Curitiba", "R$ 16.800"),
    ("Elena Sousa", "Marketing", "Recife", "R$ 9.400"),
    ("Fernando Lima", "Engineering", "São Paulo", "R$ 19.100"),
    ("Gabriela Nunes", "HR", "Porto Alegre", "R$ 8.750"),
    ("Henrique Alves", "Finance", "São Paulo", "R$ 15.300"),
    ("Isabela Torres", "Design", "Florianópolis", "R$ 13.600"),
    ("João Mendes", "Product", "Manaus", "R$ 11.900"),
    ("Karina Prado", "Engineering", "Brasília", "R$ 17.400"),
    ("Lucas Ferreira", "Marketing", "Salvador", "R$ 10.200"),
    ("Mariana Castro", "Finance", "São Paulo", "R$ 14.800"),
    ("Nicolás Rocha", "HR", "Curitiba", "R$ 9.100"),
    ("Olivia Campos", "Engineering", "Rio de Janeiro", "R$ 20.000"),
]

#: Column headers in display order.
COLUMNS: list[str] = ["Nome", "Departamento", "Cidade", "Salário"]

#: Number of data columns.
_N_COLS: int = len(COLUMNS)


class SortDir(StrEnum):
    """Sort direction for a column.

    Attributes:
        ASC: Sort ascending (A → Z).
        DESC: Sort descending (Z → A).
    """

    ASC = "asc"
    DESC = "desc"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class DataTableState:
    """State for the sortable data-table app.

    Attributes:
        query: The current text in the search bar (controlled).
        sort_col: Index of the column currently sorted, or ``-1`` for none.
        sort_dir: Current sort direction (ascending or descending).
        rows: The full dataset as a list of string tuples.
    """

    query: str = ""
    sort_col: int = -1
    sort_dir: SortDir = SortDir.ASC
    rows: list[tuple[str, str, str, str]] = field(
        default_factory=lambda: list(_EMPLOYEES)
    )


def make_state() -> DataTableState:
    """Build the initial state pre-loaded with the employee dataset.

    Returns:
        A fresh :class:`DataTableState` with all rows visible and no sort active.
    """
    return DataTableState()


# ---------------------------------------------------------------------------
# Pure helper — no side effects, deterministic for tests
# ---------------------------------------------------------------------------


def _filtered_rows(
    rows: list[tuple[str, str, str, str]],
    query: str,
    sort_col: int,
    sort_dir: SortDir,
) -> list[list[str]]:
    """Return the filtered and sorted string matrix for ``DataTable.rows``.

    Filtering is case-insensitive: a row passes when any cell contains the
    ``query`` substring.  Sorting is lexicographic on the selected column;
    an inactive sort (``sort_col == -1``) preserves insertion order.

    Args:
        rows: The full dataset.
        query: The current search term (empty string keeps all rows).
        sort_col: Column index to sort on, or ``-1`` to skip sorting.
        sort_dir: Ascending or descending sort direction.

    Returns:
        A list of string lists ready to pass to :class:`DataTable`.
    """
    needle = query.strip().lower()
    visible = [
        row for row in rows if not needle or any(needle in cell.lower() for cell in row)
    ]
    if sort_col >= 0:
        visible = sorted(
            visible,
            key=lambda r: r[sort_col].lower(),
            reverse=(sort_dir is SortDir.DESC),
        )
    return [list(row) for row in visible]


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[DataTableState]) -> Widget:
    """Render the data table UI from the current state.

    The view consists of three logical zones:

    1. **Search bar** — a controlled ``SearchBar`` that updates ``state.query``.
    2. **Sort header** — a ``Row`` of ``Button``s, one per column; clicking a
       column button cycles through ascending → descending → (ascending again).
    3. **DataTable** — fed the filtered+sorted matrix derived from state; the
       active-sort column header carries a ▲/▼ glyph so the user can see which
       column drives the order.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state = app.state

    # -- Handlers ------------------------------------------------------------

    def on_search(event: TextChangeEvent) -> None:
        """Update the filter query on every keystroke.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "query", event.value))

    def on_clear() -> None:
        """Clear the search bar and show all rows."""
        app.set_state(lambda s: setattr(s, "query", ""))

    def sort_by(col: int) -> None:
        """Sort the table by ``col``, toggling direction on repeated clicks.

        Clicking a new column always starts with ascending order.  Clicking the
        already-active column flips the direction.

        Args:
            col: Zero-based column index to sort on.
        """

        def mutate(s: DataTableState) -> None:
            if s.sort_col == col:
                s.sort_dir = SortDir.DESC if s.sort_dir is SortDir.ASC else SortDir.ASC
            else:
                s.sort_col = col
                s.sort_dir = SortDir.ASC

        app.set_state(mutate)

    # -- Derived view data ---------------------------------------------------

    visible_matrix = _filtered_rows(
        state.rows, state.query, state.sort_col, state.sort_dir
    )

    total_count = len(state.rows)
    visible_count = len(visible_matrix)
    summary = (
        f"{visible_count} resultado{'s' if visible_count != 1 else ''} de {total_count}"
    )

    # -- Sort-header row (buttons per column) --------------------------------

    def _sort_label(col_idx: int) -> str:
        """Build the label for one sort-header button.

        Appends ▲ / ▼ to the active column so the user can see the current sort.

        Args:
            col_idx: Zero-based index of the column.

        Returns:
            The display label, optionally decorated with a direction arrow.
        """
        label = COLUMNS[col_idx]
        if state.sort_col == col_idx:
            return label + (" ▲" if state.sort_dir is SortDir.ASC else " ▼")
        return label

    sort_buttons: list[Widget] = [
        Button(
            label=_sort_label(col_idx),
            on_click=(lambda i=col_idx: lambda: sort_by(i))(),
            key=f"sort-btn-{col_idx}",
            style=Style(
                grow=1.0,
                padding=Edge.symmetric(vertical=8.0, horizontal=10.0),
                radius=6.0,
                font_weight=(
                    FontWeight.BOLD if state.sort_col == col_idx else FontWeight.NORMAL
                ),
            ),
        )
        for col_idx in range(_N_COLS)
    ]

    # -- Root tree -----------------------------------------------------------

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            Text(
                content="Tabela de Colaboradores",
                key="heading",
                style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
            ),
            SearchBar(
                value=state.query,
                placeholder="Filtrar por nome, depto, cidade…",
                on_change=on_search,
                on_clear=on_clear,
                key="searchbar",
            ),
            Text(
                content=summary,
                key="summary",
                style=Style(font_size=13.0),
            ),
            Row(
                key="sort-header",
                style=Style(gap=4.0, align=AlignItems.CENTER),
                children=sort_buttons,
            ),
            DataTable(
                columns=COLUMNS,
                rows=visible_matrix,
                sortable=False,
                key="table",
            ),
        ],
    )
