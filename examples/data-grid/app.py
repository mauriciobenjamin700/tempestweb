"""Data grid — a sortable, filterable table built from typed Python.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It showcases the core ``DataTable`` (header + string matrix with app-driven
sort), a ``SearchBar`` that filters the rows by mutating state, and ``Badge``
chips summarizing the live row counts. The application never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.events import TextChangeEvent
from tempestweb.components import Badge, DataTable, SearchBar

#: The grid columns, in display order.
COLUMNS: list[str] = ["Name", "Role", "Status"]


@dataclass(frozen=True)
class User:
    """A single row in the data grid.

    Attributes:
        name: The user's display name.
        role: The user's role label.
        status: The user's account status (``"Active"`` / ``"Invited"`` /
            ``"Disabled"``).
    """

    name: str
    role: str
    status: str


#: The full, unfiltered dataset rendered by the grid.
USERS: list[User] = [
    User(name="Ada Lovelace", role="Engineer", status="Active"),
    User(name="Alan Turing", role="Engineer", status="Active"),
    User(name="Grace Hopper", role="Admin", status="Active"),
    User(name="Katherine Johnson", role="Analyst", status="Invited"),
    User(name="Margaret Hamilton", role="Engineer", status="Active"),
    User(name="Dennis Ritchie", role="Engineer", status="Disabled"),
    User(name="Barbara Liskov", role="Admin", status="Active"),
    User(name="Edsger Dijkstra", role="Analyst", status="Invited"),
]


@dataclass
class DataGridState:
    """State for the data grid app.

    Attributes:
        query: The current free-text filter applied across all columns.
        sort_column: The zero-based index of the active sort column.
        sort_ascending: Whether the active sort is ascending.
        users: The backing dataset.
    """

    query: str = ""
    sort_column: int = 0
    sort_ascending: bool = True
    users: list[User] = field(default_factory=lambda: list(USERS))


def make_state() -> DataGridState:
    """Build the initial state.

    Returns:
        A fresh :class:`DataGridState` holding the full dataset.
    """
    return DataGridState()


def _user_fields(user: User) -> list[str]:
    """Project a user onto its column cells, in display order.

    Args:
        user: The user to project.

    Returns:
        The user's cells as a list aligned with :data:`COLUMNS`.
    """
    return [user.name, user.role, user.status]


def _matches(user: User, query: str) -> bool:
    """Report whether a user matches the free-text query.

    Args:
        user: The user to test.
        query: The lowercased filter text; an empty string matches everything.

    Returns:
        ``True`` if any of the user's cells contains ``query``.
    """
    if not query:
        return True
    return any(query in cell.lower() for cell in _user_fields(user))


def _visible_rows(state: DataGridState) -> list[list[str]]:
    """Compute the filtered and sorted rows for the current state.

    Args:
        state: The current application state.

    Returns:
        The body rows as a matrix of string cells, pre-filtered by the query
        and pre-sorted by the active column.
    """
    query = state.query.strip().lower()
    filtered = [user for user in state.users if _matches(user, query)]
    column = max(0, min(state.sort_column, len(COLUMNS) - 1))
    filtered.sort(
        key=lambda user: _user_fields(user)[column].lower(),
        reverse=not state.sort_ascending,
    )
    return [_user_fields(user) for user in filtered]


def view(app: App[DataGridState]) -> Widget:
    """Render the data grid UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_search(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "query", event.value))

    def on_clear() -> None:
        app.set_state(lambda s: setattr(s, "query", ""))

    def on_sort(column: int) -> None:
        def mutate(s: DataGridState) -> None:
            if s.sort_column == column:
                s.sort_ascending = not s.sort_ascending
            else:
                s.sort_column = column
                s.sort_ascending = True

        app.set_state(mutate)

    rows = _visible_rows(app.state)

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Team directory", key="title"),
            SearchBar(
                key="search",
                value=app.state.query,
                placeholder="Filter by name, role or status…",
                on_change=on_search,
                on_clear=on_clear,
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    Badge(label=f"{len(rows)} shown", tone="info", key="count"),
                    Badge(
                        label=f"{len(app.state.users)} total",
                        tone="success",
                        key="total",
                    ),
                ],
            ),
            DataTable(
                key="grid",
                columns=COLUMNS,
                rows=rows,
                sortable=True,
                sort_column=app.state.sort_column,
                sort_ascending=app.state.sort_ascending,
                on_sort=on_sort,
            ),
        ],
    )
