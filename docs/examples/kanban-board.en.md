# Kanban Board

> 🚀 **What you'll build:** a three-column Kanban board — *Backlog*, *In Progress*, and *Done* — where cards are dragged between columns using `Draggable` / `DragTarget`, and a trash bin accepts drops to delete cards.

---

## Why this example matters

Drag-and-drop is one of the richest interactions on the web. Instead of manually
wiring mouse/touch events in JavaScript, tempestweb exposes two declarative widgets:

- **`Draggable`** — wraps any widget and sets a `drag_data` (string payload) that
  will be delivered to the drop target.
- **`DragTarget`** — wraps any widget and sets an `on_drop` handler (receives a
  `DragEvent`) called when a `Draggable` is released over it.

In this tutorial you will learn to:

- Encode a drag payload in `drag_data` and decode it in the drop handler;
- Use multiple `DragTarget` widgets with distinct handlers (move vs. delete);
- Compose scrollable columns with `ScrollView` and drop zones;
- Dynamically add cards with `Input` + `Button`;
- Use `set_state` with lambdas and full mutation functions.

!!! note "Note"
    The same `app.py` runs **without any changes** in both modes — WASM (Pyodide
    in the browser) and Server (FastAPI + WebSocket). The Python `view()` never
    names a transport.

---

## Prerequisites

Install tempestweb and confirm the CLI is available:

```bash
pip install tempestweb
tempestweb --version
```

Read the [core tutorial](../tutorial/index.md) if you haven't yet — it explains the
full cycle of `make_state` → `view` → `set_state`.

---

## Project structure

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

## Step 1 — Domain types and state

Before any widget, we need to model the data. The board is a list of cards; each
card knows which column it belongs to.

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import (
    AlignItems,
    Border,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
)
from tempestweb._core.widgets import (
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
from tempestweb._core.widgets.events import DragEvent, TextChangeEvent

#: The three board columns, in display order.
COLUMNS: list[str] = ["Backlog", "In Progress", "Done"]

#: Color theme for each column header background.
_COLUMN_COLORS: dict[str, Color] = {
    "Backlog": Color(r=99, g=102, b=241),    # indigo-500
    "In Progress": Color(r=245, g=158, b=11), # amber-500
    "Done": Color(r=34, g=197, b=94),         # green-500
}

#: Softer card-area background for each column.
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

**What is happening here:**

- `Card.column` is the only field that changes when dragging — the reconciler emits
  a minimal patch for just that field.
- `draft` and `draft_column` control the card-addition form.
- `next_id` guarantees unique IDs without needing UUIDs.

!!! tip "Tip"
    Using a `@dataclass` with `field(default_factory=list)` avoids the classic Python
    mutable-default-argument bug. tempestweb calls `make_state()` once per session,
    so each user gets their own `KanbanState` instance.

---

## Step 2 — Initial state

The `make_state` function seeds the board with example cards so the UI already
shows content when the app opens.

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
    `next_id=8` starts after the last seed card (`c7`). The first card a user creates
    will therefore receive the ID `c8`.

---

## Step 3 — Event handlers

All business logic lives as inner functions inside `view`. This keeps handlers close
to the state they mutate and avoids global state.

```python
def view(app: App[KanbanState]) -> Widget:
    """Render the kanban board from the current state.

    The board shows three columns side-by-side.  Each card is wrapped in a
    :class:`~tempestweb._core.widgets.Draggable` whose ``drag_data`` encodes its
    id and source column (``"<id>:<column>"``).  Each column body and header is
    wrapped in a :class:`~tempestweb._core.widgets.DragTarget` whose ``on_drop``
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

**Why `event.data.split(":", 1)`?**

The payload `"c3:In Progress"` contains two tokens separated by `:`. The limit `1`
ensures the second token (`"In Progress"`) is not split again, even if a card title
contains a colon in the future.

!!! warning "Warning"
    The `move_card` handler checks `source_col == target_col` and returns early. This
    avoids an unnecessary `set_state` — and therefore an unnecessary re-render — when
    the user drops a card onto the same column it came from.

| Handler | Trigger | What it does |
|---|---|---|
| `edit_draft` | `Input.on_change` | Updates `draft` while the user types |
| `set_draft_column` | `Button.on_click` (per column) | Sets `draft_column` |
| `add_card` | `Button.on_click` (form) | Validates, appends card, resets draft |
| `move_card` | `DragTarget.on_drop` (column) | Decodes payload, changes `card.column` |
| `delete_card` | `DragTarget.on_drop` (trash bin) | Removes card from the list |

---

## Step 4 — Draggable card widget

Each card is wrapped by `Draggable`. The `drag_data` encodes both the card ID and
the source column — information the drop handler needs.

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

!!! tip "Tip"
    `drag_data` is always a `str`. For complex payloads, encode as JSON or use a
    simple separator like `:` (as done here). Keep the payload small — it travels
    with every drop event.

**Highlights:**

- `Draggable(drag_data=..., child=...)` — the `child` is what the user sees and drags.
- The `Draggable`'s `key` (`f"drag-{card.id}"`) differs from the inner `Container`'s
  key (`f"card-{card.id}"`). The reconciler tracks each widget by its `key`.
- `Edge.symmetric(vertical=8.0, horizontal=12.0)` applies different padding per axis.

---

## Step 5 — Column widget with DragTarget

Each column is a `DragTarget` wrapping the cards area. A shortcut button
"+ Add to [column]" sets `draft_column` to make targeted card addition easy.

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

        # Wrap the cards area in a DragTarget so dropping a card onto the
        # column body moves it to this column.
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

        # The "add to this column" shortcut button
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

!!! warning "Warning — lambda variable capture"
    `lambda event, c=col: move_card(event, c)` uses the `c=col` pattern to capture
    the current value of `col` at the time the lambda is created. Without it, all
    lambdas would capture the **last** loop iteration of `col` — a classic Python
    closure bug.

**Highlights:**

- `ScrollView` with `min_height=200.0` ensures empty columns still have a visible
  drop area — essential for usability.
- `card_count = len(col_cards)` is recalculated on every `view()` call — the count
  in the header always reflects the current state without any manual bookkeeping.
- `grow=1.0` on each column wrapper makes the three columns divide horizontal space
  equally.

---

## Step 6 — Add card form and trash bin

The form uses `Input` + `Button`. The trash bin is yet another `DragTarget` — this
time with `delete_card` as its handler.

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

!!! tip "Tip"
    The form label displays `app.state.draft_column` in real time: "New card in
    [Backlog]" changes to "New card in [Done]" the instant you click "+ Add to Done".
    This is reactive state with no extra logic — just read `app.state` inside `view`.

---

## Step 7 — Assembling the full board

With all blocks ready, `view` assembles them in its return statement.

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

**Final widget tree hierarchy:**

```
Column (root)
├── Container (board-header)
│   └── Text "Kanban Board"
└── Container (board-body)
    └── Column (board-inner)
        ├── Container (add-form-container)        ← form
        ├── Row (columns-row)
        │   ├── Container (col-wrapper-Backlog)
        │   │   └── Column → [header, DragTarget → ScrollView → [Draggable…], Button]
        │   ├── Container (col-wrapper-In Progress)
        │   │   └── …
        │   └── Container (col-wrapper-Done)
        │       └── …
        └── DragTarget (trash-zone)               ← trash bin
```

---

## Step 8 — Run the app

Run in **Mode A** (Python in the browser via Pyodide):

```bash
tempestweb dev --mode wasm examples/kanban-board/app.py
```

Run in **Mode B** (Python on the server via FastAPI + WebSocket):

```bash
tempestweb dev --mode server examples/kanban-board/app.py
```

Open `http://localhost:8000` in your browser. You should see:

- ✅ Three coloured columns with pre-seeded cards;
- ✅ Dragging a card to another column moves it immediately;
- ✅ Dragging a card to the trash bin removes it from the board;
- ✅ Typing a title and clicking "Add" creates a new card;
- ✅ Clicking "+ Add to Done" changes the form label before adding;
- ✅ The card count in each column header updates in real time.

!!! check "Automated checks"
    All four checks pass green:

    ```bash
    ruff check .
    ruff format --check .
    mypy tempestweb
    pytest -q
    ```

---

## Recap

In this tutorial you built a full Kanban board with drag-and-drop and learned:

- 💡 **`Draggable(drag_data=..., child=...)`** — sets the payload and the visual
  widget of the draggable item. Keep `drag_data` small and encode context (ID +
  source column) in a simple string.
- 💡 **`DragTarget(on_drop=..., child=...)`** — receives the `DragEvent` when a
  `Draggable` is released over it. `event.data` contains exactly the `drag_data`
  of the dragged widget.
- 💡 **`lambda event, c=col: handler(event, c)` pattern** — captures the loop
  variable by value to avoid Python's closure bug in lists of lambdas.
- 💡 **`ScrollView`** with `min_height` ensures empty columns have a visible drop
  area — essential for usability.
- 💡 **`set_state(mutate)`** with a full mutation function is ideal when the logic
  needs to read and write multiple state fields atomically.
- 💡 The same `app.py` runs in both modes — WASM and Server — without any changes.

---

## Next steps

- Read the [core tutorial](../tutorial/index.md) to understand the full
  `make_state` → `view` → `set_state` lifecycle.
- Explore the [data table example](data-table.md) to see how filters and pagination
  combine with `ScrollView`.
- See the [stopwatch example](stopwatch.md) to understand timers and async
  `set_state`.
- Add persistence by saving `KanbanState` to `localStorage` via the Mode A storage
  API, or to a database in Mode B.
