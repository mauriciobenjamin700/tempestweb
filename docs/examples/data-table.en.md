# Sortable data table with live search

In this example you will build an **employee table** with live search filtering
and per-column sort toggling — all driven from Python state, zero JavaScript
written by you. 🚀

By the end you will have:

- A `SearchBar` that filters rows on every keystroke.
- Header buttons that toggle the sort direction (ASC/DESC) per column.
- A result counter that always shows how many rows are currently visible.

---

## What we're building

```
┌─ Employee Table ───────────────────────────────────────────┐
│  [ 🔍 Filter by name, dept, city…                   ✕ ]   │
│  15 results of 15                                           │
│  [ Name ▲ ]  [ Department ]  [ City ]  [ Salary ]          │
│  ─────────────────────────────────────────────────────      │
│  Alice Martins   Engineering   São Paulo   R$ 18.500        │
│  Bruno Costa     Design        Rio de…     R$ 12.000        │
│  …                                                          │
└────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

!!! note "Note"
    If you are not yet familiar with the basic tempestweb cycle (state → view →
    patches), read the [introductory tutorial](../tutorial/index.md) first — it
    explains `App`, `set_state`, and the two execution modes.

---

## 1. Domain data

Every application starts with data. Here we have a list of tuples — each tuple
represents one employee with four fields: name, department, city, and salary.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.components import DataTable, SearchBar
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import Button, Column, Row, Text
from tempest_core.widgets.events import TextChangeEvent

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
```

The data is immutable (`_EMPLOYEES` is a module-level constant). The application
state only holds the filter term and the sort column — it **never** stores a
transformed copy of the full dataset.

!!! tip "Tip — data separate from state"
    Keeping the dataset in the module and putting only the filter/sort in state
    ensures that `make_state()` is cheap (a small dataclass) and that data is
    never duplicated per session.

---

## 2. Sort direction

Before defining the state, we need a type to represent "ascending or
descending":

```python
class SortDir(StrEnum):
    """Sort direction for a column.

    Attributes:
        ASC: Sort ascending (A → Z).
        DESC: Sort descending (Z → A).
    """

    ASC = "asc"
    DESC = "desc"
```

`StrEnum` (Python 3.11+) makes `SortDir.ASC == "asc"` evaluate to `True`, which
simplifies serialisation and comparisons.

---

## 3. State

The state stores only what changes over time:

```python
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
```

Each field at a glance:

| Field | Type | Meaning |
|-------|------|---------|
| `query` | `str` | Text typed in the search bar (controlled field). |
| `sort_col` | `int` | Index of sorted column; `-1` = none. |
| `sort_dir` | `SortDir` | Current sort direction. |
| `rows` | `list[tuple[...]]` | Full dataset (one copy per session). |

!!! note "Note — `rows` in state"
    Keeping `rows` in state (rather than always reading the global constant)
    means that in **Mode B** (server), each WebSocket session has its own object.
    This opens the door to real-time dataset updates without sharing state
    between clients.

---

## 4. The pure filter-and-sort function

This is the most important function in the example. It has no side effects — it
takes the data and returns the filtered, sorted matrix:

```python
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
```

Step by step:

1. **Normalise** the search term to lowercase (`.lower()`).
2. **Filter** — a row passes if `needle` is empty *or* appears in any cell.
3. **Sort** — only when `sort_col >= 0`; `reverse=True` for DESC.
4. **Convert** each tuple to a list, because `DataTable` expects `list[list[str]]`.

!!! tip "Tip — pure functions are easy to test"
    Because `_filtered_rows` does not touch `app.state`, you can test it
    directly with `pytest` — no runtime to mount, no mocks needed.

---

## 5. The view — handlers

The `view` function starts by defining the three handlers that respond to
events:

```python
def view(app: App[DataTableState]) -> Widget:
    """Render the data table UI from the current state."""
    state = app.state

    # -- Handlers ------------------------------------------------------------

    def on_search(event: TextChangeEvent) -> None:
        """Update the filter query on every keystroke."""
        app.set_state(lambda s: setattr(s, "query", event.value))

    def on_clear() -> None:
        """Clear the search bar and show all rows."""
        app.set_state(lambda s: setattr(s, "query", ""))

    def sort_by(col: int) -> None:
        """Sort the table by ``col``, toggling direction on repeated clicks."""

        def mutate(s: DataTableState) -> None:
            if s.sort_col == col:
                s.sort_dir = SortDir.DESC if s.sort_dir is SortDir.ASC else SortDir.ASC
            else:
                s.sort_col = col
                s.sort_dir = SortDir.ASC

        app.set_state(mutate)
```

The `sort_by` logic in plain English:

- Clicked the **same column** → flip direction (ASC → DESC → ASC…).
- Clicked a **different column** → switch to that column, always starting ASC.

!!! warning "Warning — never mutate `app.state` directly"
    Every handler passes a function to `app.set_state`. The runtime applies
    that function, detects the changes, and schedules a rebuild. Mutating
    `app.state` directly breaks the change-detection cycle.

---

## 6. The view — derived data

With the state available, we compute the values that feed the UI:

```python
    # -- Derived view data ---------------------------------------------------

    visible_matrix = _filtered_rows(
        state.rows, state.query, state.sort_col, state.sort_dir
    )

    total_count = len(state.rows)
    visible_count = len(visible_matrix)
    summary = (
        f"{visible_count} resultado{'s' if visible_count != 1 else ''} de {total_count}"
    )
```

`summary` uses an f-string with a conditional plural — "1 resultado de 15" vs
"15 resultados de 15".

---

## 7. The view — sort header

The sort-header buttons are built with a list comprehension. Each button gets a
closure that captures the correct index using
`(lambda i=col_idx: lambda: sort_by(i))()`:

```python
    # -- Sort-header row (buttons per column) --------------------------------

    def _sort_label(col_idx: int) -> str:
        """Build the label for one sort-header button."""
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
```

!!! info "Info — the `(lambda i=col_idx: lambda: sort_by(i))()` pattern"
    In Python, closures in loops capture the **variable**, not the value. If
    we used `on_click=lambda: sort_by(col_idx)`, every button would call
    `sort_by(3)` (the last value). The pattern
    `(lambda i=col_idx: lambda: sort_by(i))()` freezes `i` at the correct
    value for each button.

The active-column button also gets `FontWeight.BOLD` — a visual hint that
complements the `▲`/`▼` glyph in the label.

---

## 8. The view — the root tree

Finally, we assemble the complete widget tree with `Column`:

```python
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
```

The widget tree structure:

```
Column
├── Text          (heading)
├── SearchBar     (controlled field — value=state.query)
├── Text          (result counter)
├── Row           (sort buttons, one per column)
│   ├── Button    (col 0 — "Nome")
│   ├── Button    (col 1 — "Departamento")
│   ├── Button    (col 2 — "Cidade")
│   └── Button    (col 3 — "Salário")
└── DataTable     (filtered + sorted matrix)
```

!!! note "Note — `sortable=False`"
    `DataTable` has a built-in `sortable` prop, but we disable it intentionally
    (`sortable=False`) — the entire sort mechanism is implemented explicitly in
    Python state. This shows that you can replace default component behaviour
    with custom logic whenever you need it.

---

## 9. The complete file

Putting it all together, the final `app.py` looks like this:

```python
"""Sortable data table — exercises DataTable, SearchBar and column-sort state.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.components import DataTable, SearchBar
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import Button, Column, Row, Text
from tempest_core.widgets.events import TextChangeEvent

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

COLUMNS: list[str] = ["Nome", "Departamento", "Cidade", "Salário"]
_N_COLS: int = len(COLUMNS)


class SortDir(StrEnum):
    """Sort direction for a column."""

    ASC = "asc"
    DESC = "desc"


@dataclass
class DataTableState:
    """State for the sortable data-table app."""

    query: str = ""
    sort_col: int = -1
    sort_dir: SortDir = SortDir.ASC
    rows: list[tuple[str, str, str, str]] = field(
        default_factory=lambda: list(_EMPLOYEES)
    )


def make_state() -> DataTableState:
    """Build the initial state pre-loaded with the employee dataset."""
    return DataTableState()


def _filtered_rows(
    rows: list[tuple[str, str, str, str]],
    query: str,
    sort_col: int,
    sort_dir: SortDir,
) -> list[list[str]]:
    """Return the filtered and sorted string matrix for ``DataTable.rows``."""
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


def view(app: App[DataTableState]) -> Widget:
    """Render the data table UI from the current state."""
    state = app.state

    def on_search(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "query", event.value))

    def on_clear() -> None:
        app.set_state(lambda s: setattr(s, "query", ""))

    def sort_by(col: int) -> None:
        def mutate(s: DataTableState) -> None:
            if s.sort_col == col:
                s.sort_dir = SortDir.DESC if s.sort_dir is SortDir.ASC else SortDir.ASC
            else:
                s.sort_col = col
                s.sort_dir = SortDir.ASC

        app.set_state(mutate)

    visible_matrix = _filtered_rows(
        state.rows, state.query, state.sort_col, state.sort_dir
    )

    total_count = len(state.rows)
    visible_count = len(visible_matrix)
    summary = (
        f"{visible_count} resultado{'s' if visible_count != 1 else ''} de {total_count}"
    )

    def _sort_label(col_idx: int) -> str:
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
```

---

## 10. Running the example

Save the file to `examples/data-table/app.py` and run it with the command below
for the mode you want:

=== "Mode A — WASM (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/data-table
    ```

    Pyodide loads Python directly in the browser. Search and sort execute
    locally — no network round-trip, zero latency.

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/data-table
    ```

    Python runs on the server. Each session gets its own isolated
    `DataTableState`; the client receives only JSON patches over WebSocket.

!!! check "Verification"
    Open the browser, type "eng" in the search box — you should see only
    Engineering employees. Click "Nome ▲" — the list should sort by name
    ascending. Click again — "Nome ▼", descending order. ✅

---

## Recap

You learned how to:

- Use `SearchBar` as a controlled field — `value=state.query` + `on_change` handler.
- Implement bidirectional sort with a single `sort_col` + `sort_dir` in state.
- Build loop buttons with correct closures (the `lambda i=col_idx` pattern).
- Keep display logic in a **pure function** (`_filtered_rows`) separate from the view.
- Run the same `app.py` in both modes without changing a single line.

!!! tip "Tip — next steps"
    - Add pagination: keep a `page: int` field in state and slice
      `visible_matrix[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]`.
    - Combine with a form example to add new employees in real time.
    - Read the [state tutorial](../tutorial/state.md) to understand the
      event → state → rebuild cycle in more depth.
