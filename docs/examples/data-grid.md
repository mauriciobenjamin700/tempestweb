# Data grid — tabela com ordenação e busca 🚀

Neste exemplo você vai montar uma **tabela de equipe** ordenável e filtrável,
usando o componente `DataTable` com ordenação nativa, um `SearchBar` que filtra
as linhas, e `Badge` chips que somam as contagens ao vivo. Tudo controlado por
estado Python tipado.

---

## O que você vai construir

- 🔍 Um **SearchBar** que filtra por nome, cargo ou status a cada tecla.
- ↕️ Um **DataTable** com ordenação nativa por coluna (`on_sort`).
- 🏷️ Dois **Badge** mostrando quantas linhas estão visíveis e o total.

---

## Pré-requisitos

```bash
pip install tempestweb
```

!!! tip "Dica"
    Se você ainda não conhece o ciclo estado → view → patches, leia o
    [tutorial de introdução](../tutorial/index.md). Compare também com o exemplo
    [Tabela de dados](data-table.md), que implementa o sort à mão; aqui usamos a
    ordenação **nativa** do `DataTable`.

---

## Passo 1 — A linha e os dados

Cada linha é um `User` imutável (`@dataclass(frozen=True)`). As colunas são uma
constante de módulo.

```python
from __future__ import annotations

from dataclasses import dataclass, field

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
```

---

## Passo 2 — O estado

O estado guarda apenas o filtro, a coluna de ordenação e a direção — mais uma
cópia do dataset por sessão.

```python
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
```

---

## Passo 3 — Funções puras de projeção, filtro e ordenação

Três helpers puros transformam os `User` na matriz de strings que o `DataTable`
espera:

```python
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
```

!!! note "Nota — `column` é sempre clampeado"
    `max(0, min(state.sort_column, len(COLUMNS) - 1))` garante que um índice de
    coluna inválido nunca quebre o `sort` — uma rede de segurança barata.

---

## Passo 4 — Os handlers

A `view` define três handlers. Note que `on_search` recebe um `TextChangeEvent`
e lê `event.value`.

```python
from tempest_core.widgets.events import TextChangeEvent

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
```

A lógica do `on_sort`:

- Clicou na **mesma coluna** → inverte a direção.
- Clicou em **outra coluna** → muda para ela, sempre começando ascendente.

---

## Passo 5 — A árvore de widgets

`DataTable` com `sortable=True` desenha as setas e chama `on_sort` ao clicar no
cabeçalho. Os `Badge` recebem um `label` e um `tone` (`"info"`, `"success"`…).

```python
from tempest_core import Column, Row, Style, Text
from tempest_core.style import Edge
from tempestweb.components import Badge, DataTable, SearchBar

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
```

---

## O app completo

```python
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
```

---

## Rodando o exemplo ▶

=== "Modo A — WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm examples/data-grid/app.py
    ```

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/data-grid/app.py
    ```

!!! check "Verificação"
    Digite "engineer" na busca → só os engenheiros aparecem, e o badge "shown"
    atualiza. Clique no cabeçalho **Name** → ordena por nome; clique de novo →
    inverte a direção. ✅

---

## Recapitulando

- ✅ Modelar linhas como `@dataclass(frozen=True)` e projetá-las em strings.
- ✅ Usar a ordenação **nativa** do `DataTable` via `sortable=True` + `on_sort`.
- ✅ Filtrar com `SearchBar` (`on_change` recebe `TextChangeEvent`).
- ✅ Mostrar contagens ao vivo com `Badge` (`label` + `tone`).
- ✅ Rodar o mesmo `app.py` nos dois modos sem alterar uma linha.

!!! tip "Próximos passos"
    - Adicione paginação fatiando `rows` antes de passar ao `DataTable`.
    - Compare com [Tabela de dados](data-table.md), que faz o sort manualmente.
