# Tabela de dados com ordenação e busca

Neste exemplo você vai construir uma **tabela de colaboradores** com busca ao
vivo e ordenação por coluna — tudo controlado por estado Python, zero JavaScript
escrito por você. 🚀

Ao final você terá:

- Um `SearchBar` que filtra as linhas a cada tecla digitada.
- Botões de cabeçalho que alternam a ordenação ASC/DESC por coluna.
- Um contador de resultados que sempre mostra quantas linhas estão visíveis.

---

## O que vamos construir

```
┌─ Tabela de Colaboradores ──────────────────────────────────┐
│  [ 🔍 Filtrar por nome, depto, cidade…              ✕ ]   │
│  15 resultados de 15                                        │
│  [ Nome ▲ ]  [ Departamento ]  [ Cidade ]  [ Salário ]      │
│  ─────────────────────────────────────────────────────      │
│  Alice Martins   Engineering   São Paulo   R$ 18.500        │
│  Bruno Costa     Design        Rio de…     R$ 12.000        │
│  …                                                          │
└────────────────────────────────────────────────────────────┘
```

---

## Pré-requisitos

!!! note "Nota"
    Se você ainda não conhece o ciclo básico do tempestweb (estado → view → patches),
    leia primeiro o [tutorial de introdução](../tutorial/index.md) — ele explica
    `App`, `set_state` e os dois modos de execução.

---

## 1. Os dados do domínio

Toda aplicação começa com os dados. Aqui temos uma lista de tuplas —
cada tupla é um colaborador com quatro campos: nome, departamento, cidade e
salário.

```python
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
```

Os dados são imutáveis (`_EMPLOYEES` é uma constante de módulo). O estado da
aplicação vai guardar apenas o filtro e a coluna de ordenação — **nunca** uma
cópia inteira dos dados transformados.

!!! tip "Dica — dados separados do estado"
    Mantendo o dataset no módulo e colocando apenas o filtro/sort no estado,
    você garante que `make_state()` é barato (um dataclass pequeno) e que os
    dados nunca são duplicados por sessão.

---

## 2. A direção de ordenação

Antes do estado, precisamos de um tipo que represente "ascendente ou
descendente":

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

`StrEnum` (Python 3.11+) faz com que `SortDir.ASC == "asc"` seja `True`, o que
facilita serialização e comparações.

---

## 3. O estado

O estado guarda apenas o que muda ao longo do tempo:

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

Veja cada campo:

| Campo | Tipo | Significado |
|-------|------|-------------|
| `query` | `str` | Texto digitado na busca (campo controlado). |
| `sort_col` | `int` | Índice da coluna ordenada; `-1` = nenhuma. |
| `sort_dir` | `SortDir` | Direção da ordenação atual. |
| `rows` | `list[tuple[...]]` | Dataset completo (cópia por sessão). |

!!! note "Nota — `rows` no estado"
    O campo `rows` está no estado (e não é a constante global) para que, no
    **Modo B**, cada sessão tenha seu próprio objeto. Isso abre a porta para
    atualizações do dataset em tempo real sem compartilhar estado entre clientes.

---

## 4. A função pura de filtragem e ordenação

Esta é a função mais importante do exemplo. Ela não tem efeitos colaterais —
recebe os dados e retorna a matriz já filtrada e ordenada:

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

O que ela faz, passo a passo:

1. **Normaliza o termo** de busca para minúsculas (`.lower()`).
2. **Filtra** — uma linha passa se `needle` é vazio *ou* aparece em qualquer célula.
3. **Ordena** — só quando `sort_col >= 0`; `reverse=True` para DESC.
4. **Converte** cada tupla para lista, pois `DataTable` espera `list[list[str]]`.

!!! tip "Dica — funções puras são fáceis de testar"
    Porque `_filtered_rows` não toca em `app.state`, você pode testá-la
    diretamente com `pytest` — sem montar nenhum runtime, sem mocks.

---

## 5. A view — os handlers

A função `view` começa definindo os três handlers que respondem a eventos:

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

Veja a lógica do `sort_by`:

- Clicou na **mesma coluna** → inverte a direção (ASC → DESC → ASC…).
- Clicou em **coluna diferente** → vai para essa coluna, sempre começando ASC.

!!! warning "Aviso — nunca mute `app.state` diretamente"
    Todo handler passa uma função para `app.set_state`. O runtime aplica essa
    função, detecta as mudanças e agenda um rebuild. Mutar `app.state` diretamente
    quebra o ciclo de detecção de mudanças.

---

## 6. A view — os dados derivados

Com o estado em mãos, calculamos os valores que vão alimentar a UI:

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

`summary` usa um f-string com plural condicional — "1 resultado de 15" vs
"15 resultados de 15".

---

## 7. A view — o cabeçalho de ordenação

Os botões de cabeçalho são criados com uma list comprehension. Cada botão
recebe um closure que captura o índice correto com `(lambda i=col_idx: lambda: sort_by(i))()`:

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

!!! info "Info — o padrão `(lambda i=col_idx: lambda: sort_by(i))()`"
    Em Python, closures em loops capturam a **variável**, não o valor. Se
    usássemos `on_click=lambda: sort_by(col_idx)`, todos os botões chamaria
    `sort_by(3)` (o último valor). O padrão `(lambda i=col_idx: lambda: sort_by(i))()`
    congela `i` no valor correto para cada botão.

O botão da coluna ativa recebe `FontWeight.BOLD` — uma dica visual que
complementa o `▲`/`▼` no label.

---

## 8. A view — a árvore raiz

Por fim, montamos a árvore completa com `Column`:

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

A estrutura da árvore:

```
Column
├── Text          (título)
├── SearchBar     (campo controlado — value=state.query)
├── Text          (contador de resultados)
├── Row           (botões de sort, um por coluna)
│   ├── Button    (col 0 — "Nome")
│   ├── Button    (col 1 — "Departamento")
│   ├── Button    (col 2 — "Cidade")
│   └── Button    (col 3 — "Salário")
└── DataTable     (matrix filtrada + ordenada)
```

!!! note "Nota — `sortable=False`"
    O `DataTable` tem uma prop `sortable` nativa, mas aqui a deixamos desativada
    (`sortable=False`) de propósito — todo o mecanismo de ordenação é implementado
    explicitamente em Python. Isso demonstra que você pode substituir comportamentos
    padrão de componentes com lógica customizada no estado.

---

## 9. O arquivo completo

Juntando tudo, o `app.py` final fica assim:

```python
"""Sortable data table — exercises DataTable, SearchBar and column-sort state.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import DataTable, SearchBar
from tempestweb._core.style import AlignItems, Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Row, Text
from tempestweb._core.widgets.events import TextChangeEvent

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

## 10. Executando o exemplo

Salve o arquivo em `examples/data-table/app.py` e rode com o comando abaixo
de acordo com o modo que você quer usar:

=== "Modo A — WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm examples/data-table/app.py
    ```

    O Pyodide carrega o Python no browser. A busca e a ordenação executam
    localmente — sem round-trip de rede, latência zero.

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/data-table/app.py
    ```

    O Python roda no servidor. Cada sessão tem seu próprio `DataTableState`
    isolado; o cliente recebe apenas patches JSON via WebSocket.

!!! check "Verificação"
    Abra o browser, digite "eng" na busca — você deve ver apenas os colaboradores
    de Engineering. Clique em "Nome ▲" — a lista deve ordenar por nome crescente.
    Clique de novo — "Nome ▼", ordem decrescente. ✅

---

## Recapitulando

Você aprendeu a:

- Usar `SearchBar` como campo controlado — `value=state.query` + handler `on_change`.
- Implementar sort bidirecional com um único campo `sort_col` + `sort_dir` no estado.
- Criar botões de cabeçalho em loop com closures corretas (padrão `lambda i=col_idx`).
- Manter a lógica de exibição em uma **função pura** (`_filtered_rows`) separada da view.
- Rodar o mesmo `app.py` nos dois modos sem alterar uma linha.

!!! tip "Dica — próximos passos"
    - Adicione paginação: guarde um campo `page: int` no estado e fatie
      `visible_matrix[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]`.
    - Combine com o exemplo de formulário para adicionar novos colaboradores
      em tempo real.
    - Veja o [tutorial de estado](../tutorial/state.md) para entender o ciclo
      evento → estado → rebuild em mais detalhes.
