"""Reorder demo — a list whose rows are sorted by dragging them.

:class:`~tempest_core.widgets.gestures.ReorderableList` declares ``on_reorder``,
and the handler receives the two positions: where the row came from and where it
was dropped. Moving the row is the app's job — the widget reports the gesture, the
state owns the order.

The rows are plain widgets; the client marks them draggable and reads a drag
between two of them as a reorder, so the same ``view`` sorts in every mode::

    tempestweb run --mode server --path examples/reorder_demo
    tempestweb run --mode wasm --path examples/reorder_demo
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import (
    App,
    Color,
    Column,
    Container,
    Edge,
    ReorderableList,
    ReorderEvent,
    Style,
    Text,
    Widget,
)


@dataclass
class ReorderState:
    """State for the reorder demo.

    Attributes:
        tasks: The rows, in the order the reader put them.
        moves: One line per completed move, most recent last.
    """

    tasks: list[str] = field(
        default_factory=lambda: [
            "Write the spec",
            "Review the PR",
            "Ship it",
            "Tell the team",
        ]
    )
    moves: list[str] = field(default_factory=list)


def make_state() -> ReorderState:
    """Build the initial state.

    Returns:
        A fresh :class:`ReorderState` with four tasks in their original order.
    """
    return ReorderState()


def view(app: App[ReorderState]) -> Widget:
    """Render the sortable list plus a log of the moves so far.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def moved(event: ReorderEvent) -> None:
        """Move a task from one position to another.

        Args:
            event: The reorder event carrying ``from_index`` and ``to_index``.
        """

        def mutate(state: ReorderState) -> None:
            tasks = state.tasks
            if not (0 <= event.from_index < len(tasks)):
                return
            task = tasks.pop(event.from_index)
            target = max(0, min(event.to_index, len(tasks)))
            tasks.insert(target, task)
            state.moves.append(f"{task}: {event.from_index} → {target}")

        app.set_state(mutate)

    rows: list[Widget] = [
        Container(
            key=f"task-{task}",
            style=Style(
                padding=Edge.all(12),
                radius=8.0,
                background=Color(r=234, g=221, b=255),
            ),
            child=Text(content=f"{index + 1}. {task}"),
        )
        for index, task in enumerate(app.state.tasks)
    ]
    log: list[Widget] = [
        Text(content=line, key=f"move-{position}")
        for position, line in enumerate(app.state.moves)
    ]
    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Drag a row onto another to reorder.", key="title"),
            ReorderableList(
                key="tasks",
                style=Style(gap=8.0),
                children=rows,
                on_reorder=moved,
            ),
            Text(content=f"Moves: {len(app.state.moves)}", key="count"),
            Column(key="log", style=Style(gap=4.0), children=log),
        ],
    )
