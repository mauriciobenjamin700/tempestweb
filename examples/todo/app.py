"""Todo list — exercises input, list and toggle widgets.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates the value-bearing widgets of the core: a single-line
:class:`~tempestweb._core.widgets.Input` to type a new item, a virtualized
:class:`~tempestweb._core.widgets.LazyColumn` to render the list (only the
visible window is materialized into the IR), and a per-row
:class:`~tempestweb._core.widgets.Checkbox` to toggle completion. The
application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Edge
from tempestweb._core.widgets import (
    Button,
    Checkbox,
    Column,
    Input,
    LazyColumn,
    Row,
    Text,
)
from tempestweb._core.widgets.events import TextChangeEvent


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
        A fresh :class:`TodoState` pre-populated with sample items so the first
        mount renders a non-empty list.
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
