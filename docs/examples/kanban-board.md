# Kanban Board

> 🚀 **O que você vai construir:** um quadro Kanban com três colunas — *Backlog*, *In Progress* e *Done* — onde cartões são arrastados entre colunas com `Draggable` / `DragTarget`, e uma lixeira recebe drops para excluir cartões.

---

## Por que esse exemplo importa?

Drag-and-drop é uma das interações mais ricas da web. Em vez de lidar com eventos
de mouse/touch manualmente em JavaScript, o tempestweb expõe dois widgets declarativos:

- **`Draggable`** — envolve qualquer widget e define um `drag_data` (string de payload)
  que será entregue ao alvo do drop.
- **`DragTarget`** — envolve qualquer widget e define um `on_drop` (handler que recebe
  um `DragEvent`) a ser chamado quando um `Draggable` for solto sobre ele.

Neste tutorial você vai aprender a:

- Codificar um payload de arrastar no `drag_data` e decodificá-lo no handler;
- Usar múltiplos `DragTarget` com handlers distintos (mover vs. excluir);
- Compor colunas roláveis com `ScrollView` e zonas de drop;
- Adicionar cartões dinamicamente com `Input` + `Button`;
- Usar `set_state` com lambdas e funções de mutação completas.

!!! note "Nota"
    O mesmo `app.py` roda **sem nenhuma alteração** nos dois modos — WASM (Pyodide
    no browser) e Servidor (FastAPI + WebSocket). A `view()` Python não nomeia
    transporte algum.

---

## Pré-requisitos

Instale o tempestweb e confirme que o CLI está disponível:

```bash
pip install tempestweb
tempestweb --version
```

Leia o [tutorial central](../tutorial/index.md) se ainda não o fez — ele explica o
ciclo completo de `make_state` → `view` → `set_state`.

---

## Estrutura do projeto

```
examples/
└── kanban-board/
    └── app.py
```

```bash
mkdir -p examples/kanban-board
touch examples/kanban-board/app.py
```

---

## Passo 1 — Tipos de domínio e estado

Antes de qualquer widget, precisamos modelar os dados. O tabuleiro é uma lista de
cartões; cada cartão sabe em qual coluna está.

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import (
    AlignItems,
    Border,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
)
from tempest_core.widgets import (
    Button,
    Column,
    Container,
    Draggable,
    DragTarget,
    Input,
    Row,
    ScrollView,
    Text,
)
from tempest_core.widgets.events import DragEvent, TextChangeEvent

#: As três colunas do quadro, na ordem de exibição.
COLUMNS: list[str] = ["Backlog", "In Progress", "Done"]

#: Cor de fundo do cabeçalho de cada coluna.
_COLUMN_COLORS: dict[str, Color] = {
    "Backlog": Color(r=99, g=102, b=241),    # indigo-500
    "In Progress": Color(r=245, g=158, b=11), # amber-500
    "Done": Color(r=34, g=197, b=94),         # green-500
}

#: Cor de fundo suave da área de cartões de cada coluna.
_COLUMN_BG: dict[str, Color] = {
    "Backlog": Color(r=238, g=242, b=255),
    "In Progress": Color(r=255, g=251, b=235),
    "Done": Color(r=240, g=253, b=244),
}


@dataclass
class Card:
    """A single kanban card.

    Attributes:
        id: Stable unique identifier.
        title: The card's display text.
        column: The name of the column the card belongs to.
    """

    id: str
    title: str
    column: str


@dataclass
class KanbanState:
    """Full state for the kanban board.

    Attributes:
        cards: All cards on the board, in insertion order.
        draft: Draft title text for a new card being typed.
        draft_column: The column the new card will be added to.
        next_id: Monotonically increasing ID counter for new cards.
    """

    cards: list[Card] = field(default_factory=list)
    draft: str = ""
    draft_column: str = "Backlog"
    next_id: int = 1
```

**O que está acontecendo:**

- `Card.column` é o único dado que muda ao arrastar — o reconciliador emite um patch
  mínimo apenas nesse campo.
- `draft` e `draft_column` controlam o formulário de adição de cartões.
- `next_id` garante IDs únicos sem precisar de UUID.

!!! tip "Dica"
    Usar um `@dataclass` com `field(default_factory=list)` evita o clássico bug de
    mutável como valor padrão em Python. O tempestweb chama `make_state()` uma vez por
    sessão, então cada usuário tem sua própria instância de `KanbanState`.

---

## Passo 2 — Estado inicial

A função `make_state` popula o tabuleiro com cartões de exemplo para que a UI já
apareça com conteúdo ao abrir o app.

```python
def make_state() -> KanbanState:
    """Build the initial kanban state with a handful of seed cards.

    Returns:
        A fresh :class:`KanbanState` pre-populated with sample cards.
    """
    return KanbanState(
        cards=[
            Card(id="c1", title="Design wireframes", column="Done"),
            Card(id="c2", title="Set up project repo", column="Done"),
            Card(id="c3", title="Implement core widgets", column="In Progress"),
            Card(id="c4", title="Write kanban example", column="In Progress"),
            Card(id="c5", title="Add drag-and-drop tests", column="Backlog"),
            Card(id="c6", title="Deploy to staging", column="Backlog"),
            Card(id="c7", title="Write user documentation", column="Backlog"),
        ],
        next_id=8,
    )
```

!!! info "Info"
    `next_id=8` começa após o último cartão semente (`c7`). Assim o primeiro
    cartão criado pelo usuário receberá o ID `c8`.

---

## Passo 3 — Handlers de evento

Toda a lógica de negócio vive como funções internas de `view`. Isso mantém os
handlers próximos do estado que manipulam e evita estado global.

```python
def view(app: App[KanbanState]) -> Widget:
    """Render the kanban board from the current state.

    The board shows three columns side-by-side.  Each card is wrapped in a
    :class:`~tempest_core.widgets.Draggable` whose ``drag_data`` encodes its
    id and source column (``"<id>:<column>"``).  Each column body and header is
    wrapped in a :class:`~tempest_core.widgets.DragTarget` whose ``on_drop``
    handler decodes that payload and moves the card in state.  A bottom trash-bin
    :class:`DragTarget` deletes the dropped card.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def edit_draft(event: TextChangeEvent) -> None:
        """Update the draft title as the user types.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "draft", event.value))

    def set_draft_column(col: str) -> None:
        """Set which column a new card will be added to.

        Args:
            col: The target column name.
        """
        app.set_state(lambda s: setattr(s, "draft_column", col))

    def add_card() -> None:
        """Append a new card to the draft column and reset the draft."""

        def mutate(s: KanbanState) -> None:
            title = s.draft.strip()
            if not title:
                return
            s.cards.append(Card(id=f"c{s.next_id}", title=title, column=s.draft_column))
            s.next_id += 1
            s.draft = ""

        app.set_state(mutate)

    def move_card(event: DragEvent, target_col: str) -> None:
        """Move the dragged card to ``target_col``.

        The ``drag_data`` payload is ``"<card_id>:<source_col>"``.  When the
        target column equals the source column the drop is a no-op.

        Args:
            event: The drag event carrying the card's encoded payload.
            target_col: The name of the column the card was dropped onto.
        """
        parts = event.data.split(":", 1)
        if len(parts) != 2:
            return
        card_id, source_col = parts
        if source_col == target_col:
            return

        def mutate(s: KanbanState) -> None:
            for card in s.cards:
                if card.id == card_id:
                    card.column = target_col
                    break

        app.set_state(mutate)

    def delete_card(event: DragEvent) -> None:
        """Remove the dragged card from the board entirely.

        Args:
            event: The drag event carrying the card's encoded payload.
        """
        parts = event.data.split(":", 1)
        if len(parts) != 2:
            return
        card_id = parts[0]

        def mutate(s: KanbanState) -> None:
            s.cards = [c for c in s.cards if c.id != card_id]

        app.set_state(mutate)
```

**Por que `event.data.split(":", 1)`?**

O payload `"c3:In Progress"` contém dois tokens separados por `:`. O limite `1`
garante que o segundo token (`"In Progress"`) não seja partido novamente, mesmo que
o título do cartão contenha dois-pontos no futuro.

!!! warning "Aviso"
    O handler `move_card` verifica `source_col == target_col` e retorna sem fazer
    nada. Isso evita um `set_state` desnecessário — e portanto um re-render — quando
    o usuário solta um cartão na mesma coluna.

| Handler | Trigger | O que faz |
|---|---|---|
| `edit_draft` | `Input.on_change` | Atualiza `draft` enquanto o usuário digita |
| `set_draft_column` | `Button.on_click` (por coluna) | Define `draft_column` |
| `add_card` | `Button.on_click` (formulário) | Valida, anexa cartão, reseta draft |
| `move_card` | `DragTarget.on_drop` (coluna) | Decodifica payload, muda `card.column` |
| `delete_card` | `DragTarget.on_drop` (lixeira) | Remove cartão da lista |

---

## Passo 4 — Widget de cartão draggable

Cada cartão é envolvido por `Draggable`. O `drag_data` codifica tanto o ID do
cartão quanto a coluna de origem — informações que o handler de drop precisa.

```python
    def build_card(card: Card) -> Widget:
        """Build a draggable card widget.

        Args:
            card: The card data to render.

        Returns:
            A :class:`Draggable`-wrapped card container.
        """
        drag_payload = f"{card.id}:{card.column}"
        return Draggable(
            key=f"drag-{card.id}",
            drag_data=drag_payload,
            child=Container(
                key=f"card-{card.id}",
                style=Style(
                    background=Color(r=255, g=255, b=255),
                    border=Border(width=1.0, color=Color(r=209, g=213, b=219)),
                    radius=6.0,
                    padding=Edge.symmetric(vertical=8.0, horizontal=12.0),
                    margin=Edge(bottom=8.0),
                    shadow=None,
                ),
                child=Text(
                    key=f"card-text-{card.id}",
                    content=card.title,
                    style=Style(
                        font_size=14.0,
                        color=Color(r=31, g=41, b=55),
                    ),
                ),
            ),
        )
```

!!! tip "Dica"
    `drag_data` é sempre uma `str`. Para payloads complexos, codifique em JSON ou use
    um separador simples como `:` (como aqui). Mantenha o payload pequeno — ele trafega
    junto com cada evento de drop.

**Destaques:**

- `Draggable(drag_data=..., child=...)` — o `child` é o que o usuário vê e arrasta.
- O `key` do `Draggable` (`f"drag-{card.id}"`) é diferente do `key` do `Container`
  interno (`f"card-{card.id}"`). O reconciliador rastreia cada widget pelo seu `key`.
- `Edge.symmetric(vertical=8.0, horizontal=12.0)` aplica padding diferente nos eixos.

---

## Passo 5 — Widget de coluna com DragTarget

Cada coluna é um `DragTarget` que envolve a área de cartões. Um botão de atalho
"Add to [coluna]" define o `draft_column` para facilitar a adição direcionada.

```python
    def build_column(col: str) -> Widget:
        """Build a kanban column with its header and card drop zone.

        Args:
            col: The column name (one of the three in :data:`COLUMNS`).

        Returns:
            A :class:`DragTarget`-wrapped column widget.
        """
        header_color = _COLUMN_COLORS[col]
        bg_color = _COLUMN_BG[col]
        col_cards = [c for c in app.state.cards if c.column == col]
        card_count = len(col_cards)

        header = Container(
            key=f"col-header-{col}",
            style=Style(
                background=header_color,
                padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                radius=8.0,
                margin=Edge(bottom=8.0),
            ),
            child=Row(
                key=f"col-header-row-{col}",
                style=Style(
                    justify=JustifyContent.SPACE_BETWEEN,
                    align=AlignItems.CENTER,
                ),
                children=[
                    Text(
                        key=f"col-title-{col}",
                        content=col,
                        style=Style(
                            color=Color(r=255, g=255, b=255),
                            font_weight=FontWeight.BOLD,
                            font_size=15.0,
                        ),
                    ),
                    Text(
                        key=f"col-count-{col}",
                        content=str(card_count),
                        style=Style(
                            color=Color(r=255, g=255, b=255, a=0.85),
                            font_size=13.0,
                        ),
                    ),
                ],
            ),
        )

        cards_list = ScrollView(
            key=f"col-scroll-{col}",
            style=Style(min_height=200.0),
            children=[build_card(c) for c in col_cards],
        )

        # Envolve a área de cartões em um DragTarget para que soltar
        # um cartão sobre o corpo da coluna o mova para esta coluna.
        drop_zone = DragTarget(
            key=f"drop-{col}",
            on_drop=lambda event, c=col: move_card(event, c),
            child=Container(
                key=f"col-body-{col}",
                style=Style(
                    background=bg_color,
                    padding=Edge.all(8.0),
                    radius=6.0,
                    min_height=200.0,
                ),
                child=cards_list,
            ),
        )

        # Botão de atalho "adicionar a esta coluna"
        add_here_btn = Button(
            key=f"add-to-{col}",
            label=f"+ Add to {col}",
            on_click=lambda c=col: set_draft_column(c),
        )

        return Container(
            key=f"col-wrapper-{col}",
            style=Style(
                grow=1.0,
                margin=Edge.symmetric(horizontal=6.0),
                min_width=220.0,
            ),
            child=Column(
                key=f"col-{col}",
                style=Style(gap=4.0),
                children=[header, drop_zone, add_here_btn],
            ),
        )
```

!!! warning "Aviso — captura de variável em lambdas"
    `lambda event, c=col: move_card(event, c)` usa o padrão `c=col` para capturar
    o valor atual de `col` no momento da criação do lambda. Sem isso, todos os lambdas
    capturariam a **última** iteração de `col` (um bug clássico de closure em Python).

**Destaques:**

- `ScrollView` com `min_height=200.0` garante que colunas vazias ainda tenham área
  de drop visível.
- `card_count = len(col_cards)` é recalculado a cada `view()` — o número no cabeçalho
  sempre reflete o estado atual sem nenhum bookkeeping manual.
- `grow=1.0` nas colunas faz com que elas dividam o espaço horizontal igualmente.

---

## Passo 6 — Formulário de adição e lixeira

O formulário usa `Input` + `Button`. A lixeira é mais um `DragTarget` — desta vez
com `delete_card` como handler.

```python
    add_form = Container(
        key="add-form-container",
        style=Style(
            background=Color(r=249, g=250, b=251),
            border=Border(width=1.0, color=Color(r=229, g=231, b=235)),
            radius=8.0,
            padding=Edge.all(12.0),
            margin=Edge(bottom=16.0),
        ),
        child=Row(
            key="add-form-row",
            style=Style(gap=8.0, align=AlignItems.CENTER),
            children=[
                Text(
                    key="add-form-label",
                    content=f"New card in [{app.state.draft_column}]:",
                    style=Style(
                        font_size=13.0,
                        color=Color(r=107, g=114, b=128),
                    ),
                ),
                Input(
                    key="add-form-input",
                    value=app.state.draft,
                    placeholder="Card title…",
                    on_change=edit_draft,
                    style=Style(grow=1.0),
                ),
                Button(key="add-form-btn", label="Add", on_click=add_card),
            ],
        ),
    )

    trash = DragTarget(
        key="trash-zone",
        on_drop=delete_card,
        child=Container(
            key="trash-container",
            style=Style(
                background=Color(r=254, g=242, b=242),
                border=Border(width=2.0, color=Color(r=252, g=165, b=165)),
                radius=8.0,
                padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
                margin=Edge(top=16.0),
            ),
            child=Row(
                key="trash-row",
                style=Style(
                    justify=JustifyContent.CENTER,
                    align=AlignItems.CENTER,
                    gap=8.0,
                ),
                children=[
                    Text(
                        key="trash-icon",
                        content="🗑",
                        style=Style(font_size=18.0),
                    ),
                    Text(
                        key="trash-label",
                        content="Drop here to delete card",
                        style=Style(
                            font_size=14.0,
                            color=Color(r=185, g=28, b=28),
                        ),
                    ),
                ],
            ),
        ),
    )
```

!!! tip "Dica"
    O rótulo do formulário exibe `app.state.draft_column` em tempo real: "New card in
    [Backlog]" muda para "New card in [Done]" assim que você clica em "+ Add to Done".
    Isso é estado reativo sem nenhuma lógica extra — basta ler `app.state` na `view`.

---

## Passo 7 — Montando o tabuleiro completo

Com todos os blocos prontos, a `view` os monta no retorno final.

```python
    board_header = Container(
        key="board-header",
        style=Style(
            background=Color(r=15, g=23, b=42),
            padding=Edge.symmetric(vertical=16.0, horizontal=20.0),
            margin=Edge(bottom=16.0),
        ),
        child=Text(
            key="board-title",
            content="Kanban Board",
            style=Style(
                color=Color(r=255, g=255, b=255),
                font_size=22.0,
                font_weight=FontWeight.BOLD,
            ),
        ),
    )

    columns_row = Row(
        key="columns-row",
        style=Style(
            gap=0.0,
            align=AlignItems.START,
        ),
        children=[build_column(col) for col in COLUMNS],
    )

    return Column(
        key="root",
        style=Style(padding=Edge.all(0.0)),
        children=[
            board_header,
            Container(
                key="board-body",
                style=Style(padding=Edge.symmetric(vertical=0.0, horizontal=16.0)),
                child=Column(
                    key="board-inner",
                    style=Style(gap=0.0),
                    children=[add_form, columns_row, trash],
                ),
            ),
        ],
    )
```

**Hierarquia final da árvore de widgets:**

```
Column (root)
├── Container (board-header)
│   └── Text "Kanban Board"
└── Container (board-body)
    └── Column (board-inner)
        ├── Container (add-form-container)        ← formulário
        ├── Row (columns-row)
        │   ├── Container (col-wrapper-Backlog)
        │   │   └── Column → [header, DragTarget → ScrollView → [Draggable…], Button]
        │   ├── Container (col-wrapper-In Progress)
        │   │   └── …
        │   └── Container (col-wrapper-Done)
        │       └── …
        └── DragTarget (trash-zone)               ← lixeira
```

---

## Passo 8 — Executar o app

Execute no **Modo A** (Python no browser via Pyodide):

```bash
tempestweb dev --mode wasm examples/kanban-board/app.py
```

Execute no **Modo B** (Python no servidor via FastAPI + WebSocket):

```bash
tempestweb dev --mode server examples/kanban-board/app.py
```

Abra `http://localhost:8000` no browser. Você deve ver:

- ✅ Três colunas coloridas com cartões pré-populados;
- ✅ Arrastar um cartão para outra coluna move-o imediatamente;
- ✅ Arrastar um cartão para a lixeira o remove do tabuleiro;
- ✅ Digitar um título e clicar "Add" cria um novo cartão;
- ✅ Clicar "+ Add to Done" muda o rótulo do formulário antes de adicionar;
- ✅ O contador de cartões no cabeçalho de cada coluna se atualiza em tempo real.

!!! check "Verificação automática"
    Todos os quatro checks passam em verde:

    ```bash
    ruff check .
    ruff format --check .
    mypy tempestweb
    pytest -q
    ```

---

## Recapitulando

Neste tutorial você construiu um Kanban board completo com drag-and-drop e aprendeu:

- 💡 **`Draggable(drag_data=..., child=...)`** — define o payload e o widget visual
  do item arrastável. Mantenha `drag_data` pequeno e encode informações de contexto
  (ID + coluna de origem) em uma string simples.
- 💡 **`DragTarget(on_drop=..., child=...)`** — recebe o `DragEvent` quando um
  `Draggable` é solto sobre ele. `event.data` contém exatamente o `drag_data` do
  widget arrastado.
- 💡 **Padrão `lambda event, c=col: handler(event, c)`** — captura a variável de loop
  por valor para evitar o bug de closure de Python em listas de lambdas.
- 💡 **`ScrollView`** com `min_height` garante que colunas vazias tenham área de
  drop visível — essencial para usabilidade.
- 💡 **`set_state(mutate)`** com uma função de mutação completa é ideal quando a
  lógica precisa ler e escrever múltiplos campos do estado atomicamente.
- 💡 O mesmo `app.py` roda nos dois modos — WASM e Servidor — sem nenhuma alteração.

---

## Próximos passos

- Veja o [tutorial central](../tutorial/index.md) para entender o ciclo completo
  de `make_state` → `view` → `set_state`.
- Explore o [exemplo de tabela de dados](data-table.md) para ver como filtros e
  paginação se combinam com `ScrollView`.
- Veja o [exemplo stopwatch](stopwatch.md) para entender timers e `set_state`
  assíncrono.
- Adicione persistência salvando `KanbanState` em `localStorage` via a API de
  storage do Modo A ou em banco de dados no Modo B.
