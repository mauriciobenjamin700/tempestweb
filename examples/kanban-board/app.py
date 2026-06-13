"""Kanban board — demonstrates Draggable / DragTarget to move cards between columns.

Cards live in one of three columns: Backlog, In Progress, and Done.  Dragging a
card onto a different column header (or its body) fires a ``DragEvent`` whose
``data`` field encodes ``"<card_id>:<source_col>"``; the drop handler decodes that
payload and moves the card in state.  A fourth ``DragTarget`` (the trash bin row)
deletes the dragged card.

Both modes run the exact same ``view`` — the application never names a transport::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

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

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

#: The three board columns, in display order.
COLUMNS: list[str] = ["Backlog", "In Progress", "Done"]

#: Color theme for each column header background.
_COLUMN_COLORS: dict[str, Color] = {
    "Backlog": Color(r=99, g=102, b=241),  # indigo-500
    "In Progress": Color(r=245, g=158, b=11),  # amber-500
    "Done": Color(r=34, g=197, b=94),  # green-500
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


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------


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

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Card widget builder
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Column widget builder
    # ------------------------------------------------------------------

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

        # Wrap cards area in a DragTarget so dropping a card onto the
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

    # ------------------------------------------------------------------
    # Add-card form
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Trash-bin drop target
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Board header
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Columns row
    # ------------------------------------------------------------------

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
