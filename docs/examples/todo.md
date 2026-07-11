# Lista de tarefas — input, lista virtualizada e checkboxes ✅

**Modos: A/B** — usa widgets com valor e o formato Python de evento (`event.value`).

Depois do [Contador](../tutorial/index.md), este é o próximo passo natural: um
app que **acumula uma lista**. Você digita uma tarefa, aperta **Add**, e ela
aparece numa lista com um checkbox por item. 🚀

!!! note "O que muda em relação ao Contador"
    O Contador tem um único inteiro no estado. Aqui o estado carrega uma **lista de
    objetos** (`list[TodoItem]`) e um rascunho de texto — e a UI usa um
    `LazyColumn` virtualizado, que materializa na IR só a janela visível.

---

## O que este exemplo mostra

- **`Input` controlado** — o valor vem do estado (`app.state.draft`) e volta pelo
  handler `on_change`, lendo `event.value` do `TextChangeEvent`.
- **`LazyColumn` virtualizado** — declara `item_count` e um `item_builder`; só a
  janela visível é renderizada.
- **`Checkbox` por linha** — alterna `done` no item pelo índice.
- **Mutações de lista com `set_state`** — funções internas mutam o estado no lugar.

---

## Rodando ▶

```bash
tempestweb run --mode wasm     examples/todo   # Python no browser (Pyodide)
tempestweb run --mode server   examples/todo   # Python no servidor (FastAPI + WS)
```

---

## O código

```python
"""Todo list — exercises input, list and toggle widgets."""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Checkbox,
    Column,
    Input,
    LazyColumn,
    Row,
    Text,
)
from tempest_core.widgets.events import TextChangeEvent


@dataclass
class TodoItem:
    """A single todo entry.

    Attributes:
        title: The text of the item.
        done: Whether the item has been completed.
    """

    title: str
    done: bool = False


@dataclass
class TodoState:
    """State for the todo-list app.

    Attributes:
        draft: The text currently typed into the new-item field.
        items: The todo items, in insertion order.
    """

    draft: str = ""
    items: list[TodoItem] = field(default_factory=list)


def make_state() -> TodoState:
    """Build the initial state with two seed items.

    Returns:
        A fresh :class:`TodoState` pre-populated with sample items.
    """
    return TodoState(
        items=[
            TodoItem(title="Read docs/plan.md", done=True),
            TodoItem(title="Write the todo example", done=False),
        ]
    )


def view(app: App[TodoState]) -> Widget:
    """Render the todo UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def edit_draft(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "draft", event.value))

    def add_item() -> None:
        def mutate(s: TodoState) -> None:
            title = s.draft.strip()
            if title:
                s.items.append(TodoItem(title=title))
                s.draft = ""

        app.set_state(mutate)

    def toggle(index: int) -> None:
        def mutate(s: TodoState) -> None:
            s.items[index].done = not s.items[index].done

        app.set_state(mutate)

    def build_row(index: int) -> Widget:
        item = app.state.items[index]
        return Checkbox(
            label=item.title,
            checked=item.done,
            on_change=lambda _event, i=index: toggle(i),
        )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Todo", key="title"),
            Row(
                style=Style(gap=8.0),
                children=[
                    Input(
                        value=app.state.draft,
                        placeholder="What needs doing?",
                        on_change=edit_draft,
                        key="draft",
                    ),
                    Button(label="Add", on_click=add_item, key="add"),
                ],
            ),
            LazyColumn(
                item_count=len(app.state.items),
                item_builder=build_row,
                key="items",
            ),
        ],
    )
```

---

## Peça por peça

### O input controlado

```python
def edit_draft(event: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "draft", event.value))
```

O `Input` recebe `value=app.state.draft` e `on_change=edit_draft`. Cada tecla
dispara um `TextChangeEvent`; lemos `event.value` e guardamos no estado. Isso é um
**controlled input**: a única fonte de verdade é o estado.

### Adicionar sem itens vazios

```python
def add_item() -> None:
    def mutate(s: TodoState) -> None:
        title = s.draft.strip()
        if title:
            s.items.append(TodoItem(title=title))
            s.draft = ""
    app.set_state(mutate)
```

`add_item` faz `strip()` e só adiciona se sobrou texto — depois limpa o rascunho.

### A lista virtualizada

```python
LazyColumn(
    item_count=len(app.state.items),
    item_builder=build_row,
    key="items",
)
```

`LazyColumn` não recebe uma lista de widgets pronta: recebe uma **contagem** e um
**builder** chamado por índice. Só a janela visível vira IR — a lista pode ter
milhares de itens sem custo.

!!! tip "Por que `i=index` no lambda?"
    ```python
    on_change=lambda _event, i=index: toggle(i)
    ```
    Capturar `index` como argumento default congela o valor no momento da criação
    do lambda — o clássico truque de closures em loops do Python.

---

## Recapitulando

Neste exemplo você viu:

- ✅ Um **`Input` controlado** lendo `event.value` do `TextChangeEvent`
- ✅ **Mutações de lista** com funções internas em `set_state`
- ✅ Um **`LazyColumn` virtualizado** dirigido por `item_count` + `item_builder`
- ✅ Um **`Checkbox` por linha** alternando estado por índice
- ✅ O padrão rodando inalterado nos **Modos A/B**

---

## Próximos passos

- 💡 Volte ao [Contador](../tutorial/index.md) para o padrão `set_state` mais simples
- 💡 Veja o [Formulário](form.md) para validação com `Form` + `FormField`
- 💡 O [Chat UI](chat-ui.md) usa `LazyColumn` com muito mais itens
