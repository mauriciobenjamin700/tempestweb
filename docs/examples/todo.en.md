# To-do list — input, virtualized list, and checkboxes ✅

**Modes: A/B** — uses value-bearing widgets and the Python event shape (`event.value`).

After the [Counter](../tutorial/index.md), this is the natural next step: an app
that **accumulates a list**. You type a task, press **Add**, and it shows up in a
list with a checkbox per item. 🚀

!!! note "What changes from the Counter"
    The Counter holds a single integer in state. Here the state carries a **list of
    objects** (`list[TodoItem]`) plus a text draft — and the UI uses a virtualized
    `LazyColumn`, which materializes only the visible window into the IR.

---

## What this example shows

- **Controlled `Input`** — the value comes from state (`app.state.draft`) and flows
  back through the `on_change` handler, reading `event.value` off the `TextChangeEvent`.
- **Virtualized `LazyColumn`** — declares an `item_count` and an `item_builder`;
  only the visible window is rendered.
- **Per-row `Checkbox`** — toggles the item's `done` by index.
- **List mutations via `set_state`** — inner functions mutate state in place.

---

## Running ▶

```bash
tempestweb run --mode wasm     examples/todo   # Python in the browser (Pyodide)
tempestweb run --mode server   examples/todo   # Python on the server (FastAPI + WS)
```

---

## The code

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

## Piece by piece

### The controlled input

```python
def edit_draft(event: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "draft", event.value))
```

The `Input` takes `value=app.state.draft` and `on_change=edit_draft`. Every
keystroke fires a `TextChangeEvent`; we read `event.value` and store it in state.
This is a **controlled input**: state is the single source of truth.

### Adding without empty items

```python
def add_item() -> None:
    def mutate(s: TodoState) -> None:
        title = s.draft.strip()
        if title:
            s.items.append(TodoItem(title=title))
            s.draft = ""
    app.set_state(mutate)
```

`add_item` calls `strip()` and only appends if text remains — then clears the draft.

### The virtualized list

```python
LazyColumn(
    item_count=len(app.state.items),
    item_builder=build_row,
    key="items",
)
```

`LazyColumn` does not take a ready-made list of widgets: it takes a **count** and a
**builder** called by index. Only the visible window becomes IR — the list can hold
thousands of items at no cost.

!!! tip "Why `i=index` in the lambda?"
    ```python
    on_change=lambda _event, i=index: toggle(i)
    ```
    Capturing `index` as a default argument freezes the value at lambda-creation
    time — the classic Python loop-closure trick.

---

## Recap

In this example you saw:

- ✅ A **controlled `Input`** reading `event.value` off the `TextChangeEvent`
- ✅ **List mutations** with inner functions in `set_state`
- ✅ A **virtualized `LazyColumn`** driven by `item_count` + `item_builder`
- ✅ A **per-row `Checkbox`** toggling state by index
- ✅ The pattern running unchanged in **Modes A/B**

---

## Next steps

- 💡 Back to the [Counter](../tutorial/index.md) for the simplest `set_state` pattern
- 💡 See the [Form](form.md) for validation with `Form` + `FormField`
- 💡 The [Chat UI](chat-ui.md) uses `LazyColumn` with many more items
