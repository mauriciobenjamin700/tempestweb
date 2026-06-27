"""Sketch pad — demonstrates Canvas, DrawCommand, and button-driven stroke editing.

A freehand sketch pad that stores strokes as sequences of :class:`MoveTo` and
:class:`LineTo` draw commands. Because continuous pan events require a live
renderer, the demo exposes a deterministic set of controls that exercise the
full Canvas API:

- **Preset strokes** — three ready-made shapes (diagonal, box, cross) that
  append a complete stroke to the canvas, verifying multi-command paths.
- **Color picker** — choose the ink color (black, red, blue, green) for the
  next stroke.
- **Stroke width slider** — a discrete width selection (1, 3, 6, 10 px).
- **Undo** — remove the most recently added stroke.
- **Clear** — wipe the whole canvas.

Each stroke is a self-contained list of :class:`DrawCommand` items:
``MoveTo`` → one or more ``LineTo`` → ``StrokeCmd``.  The full command list
sent to :class:`Canvas` is the flat concatenation of all active strokes, so
the reconciler diffs it as a single value field — one ``Update`` per change.

Both modes work unchanged::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
)
from tempest_core.widgets import (
    Canvas,
    DrawCommand,
    Dropdown,
    LineTo,
    MoveTo,
    SelectEvent,
    StrokeCmd,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canvas logical dimensions in pixels.
CANVAS_WIDTH: float = 480.0
CANVAS_HEIGHT: float = 320.0

#: Named ink color presets: display label → ``[r, g, b, a]`` float list.
INK_COLORS: dict[str, list[float]] = {
    "Black": [0.0, 0.0, 0.0, 1.0],
    "Red": [0.85, 0.1, 0.1, 1.0],
    "Blue": [0.1, 0.3, 0.9, 1.0],
    "Green": [0.1, 0.65, 0.2, 1.0],
}

#: Available stroke widths in logical pixels.
STROKE_WIDTHS: list[float] = [1.0, 3.0, 6.0, 10.0]


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class Stroke:
    """A single completed stroke on the canvas.

    A stroke is a sequence of absolute (x, y) waypoints recorded from a drag
    gesture (or a preset shape), tagged with the ink color and line width that
    were active when the stroke was created.

    Attributes:
        points: Ordered sequence of (x, y) tuples forming the polyline.
        color: Stroke color as ``[r, g, b, a]`` floats in ``[0, 1]``.
        width: Stroke width in logical pixels.
    """

    points: list[tuple[float, float]]
    color: list[float]
    width: float

    def to_commands(self) -> list[DrawCommand]:
        """Compile the stroke into a flat list of draw commands.

        Produces ``MoveTo`` → ``LineTo`` … → ``StrokeCmd``.  A stroke with
        fewer than two points is silently skipped (nothing to paint).

        Returns:
            The ordered draw commands for this stroke, or an empty list when
            the stroke has fewer than two waypoints.
        """
        if len(self.points) < 2:
            return []
        cmds: list[DrawCommand] = [MoveTo(x=self.points[0][0], y=self.points[0][1])]
        for x, y in self.points[1:]:
            cmds.append(LineTo(x=x, y=y))
        cmds.append(StrokeCmd(color=self.color, width=self.width))
        return cmds


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SketchState:
    """Mutable state for the sketch-pad application.

    Attributes:
        strokes: All completed strokes in draw order.
        ink_color_name: Display name of the currently selected ink color.
        stroke_width: Currently selected stroke width in logical pixels.
    """

    strokes: list[Stroke] = field(default_factory=list)
    ink_color_name: str = "Black"
    stroke_width: float = 3.0


def make_state() -> SketchState:
    """Build the initial sketch state with one seed stroke.

    Seeding with a diagonal line ensures the first mount renders a non-empty
    canvas and exercises the ``to_commands`` path immediately.

    Returns:
        A fresh :class:`SketchState` pre-populated with one diagonal stroke.
    """
    seed = Stroke(
        points=[(40.0, 40.0), (440.0, 280.0)],
        color=INK_COLORS["Black"],
        width=2.0,
    )
    return SketchState(strokes=[seed])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_commands(strokes: list[Stroke]) -> list[DrawCommand]:
    """Flatten all strokes into a single ordered draw-command list.

    The :class:`Canvas` widget receives the concatenated commands for every
    active stroke.  The reconciler diffs the whole list as a single field, so
    adding or removing a stroke produces one ``Update`` patch carrying the new
    command list.

    Args:
        strokes: The ordered strokes to compile.

    Returns:
        Flat list of :data:`DrawCommand` items ready for :attr:`Canvas.commands`.
    """
    result: list[DrawCommand] = []
    for stroke in strokes:
        result.extend(stroke.to_commands())
    return result


def _make_box_stroke(color: list[float], width: float) -> Stroke:
    """Create a closed rectangular stroke occupying the canvas centre.

    Args:
        color: Ink color as ``[r, g, b, a]`` floats in ``[0, 1]``.
        width: Stroke width in logical pixels.

    Returns:
        A :class:`Stroke` tracing a 200 × 140 px box centred on the canvas.
    """
    cx: float = CANVAS_WIDTH / 2.0
    cy: float = CANVAS_HEIGHT / 2.0
    hw: float = 100.0
    hh: float = 70.0
    return Stroke(
        points=[
            (cx - hw, cy - hh),
            (cx + hw, cy - hh),
            (cx + hw, cy + hh),
            (cx - hw, cy + hh),
            (cx - hw, cy - hh),
        ],
        color=color,
        width=width,
    )


def _make_cross_stroke(color: list[float], width: float) -> Stroke:
    """Create a diagonal cross (×) stroke inscribed in the canvas.

    The cross is drawn as two separate line segments joined into one polyline
    via a short jump to the centre, giving the appearance of two diagonals.

    Args:
        color: Ink color as ``[r, g, b, a]`` floats in ``[0, 1]``.
        width: Stroke width in logical pixels.

    Returns:
        A :class:`Stroke` drawing both diagonals of the canvas.
    """
    cx: float = CANVAS_WIDTH / 2.0
    cy: float = CANVAS_HEIGHT / 2.0
    return Stroke(
        points=[
            (60.0, 40.0),
            (cx, cy),
            (420.0, 280.0),
            (cx, cy),
            (60.0, 280.0),
            (cx, cy),
            (420.0, 40.0),
        ],
        color=color,
        width=width,
    )


def _make_diagonal_stroke(color: list[float], width: float) -> Stroke:
    """Create a simple top-left to bottom-right diagonal stroke.

    Args:
        color: Ink color as ``[r, g, b, a]`` floats in ``[0, 1]``.
        width: Stroke width in logical pixels.

    Returns:
        A :class:`Stroke` tracing the main diagonal of the canvas.
    """
    return Stroke(
        points=[(40.0, 40.0), (440.0, 280.0)],
        color=color,
        width=width,
    )


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[SketchState]) -> Widget:
    """Render the sketch-pad UI from the current state.

    The tree is a :class:`~tempest_core.widgets.Column` with three
    sections:

    1. **Title bar** — heading and stroke count.
    2. **Toolbar** — ink color selector, width selector, shape presets.
    3. **Canvas** — a :class:`~tempest_core.widgets.Canvas` showing all
       compiled draw commands.
    4. **Footer** — Undo and Clear buttons.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: SketchState = app.state
    current_color: list[float] = INK_COLORS.get(
        state.ink_color_name, INK_COLORS["Black"]
    )

    # -- Handlers -----------------------------------------------------------

    def add_diagonal() -> None:
        """Append a diagonal stroke in the current ink color and width."""

        def _mutate(s: SketchState) -> None:
            s.strokes.append(
                _make_diagonal_stroke(
                    INK_COLORS.get(s.ink_color_name, INK_COLORS["Black"]),
                    s.stroke_width,
                )
            )

        app.set_state(_mutate)

    def add_box() -> None:
        """Append a rectangular stroke in the current ink color and width."""

        def _mutate(s: SketchState) -> None:
            s.strokes.append(
                _make_box_stroke(
                    INK_COLORS.get(s.ink_color_name, INK_COLORS["Black"]),
                    s.stroke_width,
                )
            )

        app.set_state(_mutate)

    def add_cross() -> None:
        """Append a cross (×) stroke in the current ink color and width."""

        def _mutate(s: SketchState) -> None:
            s.strokes.append(
                _make_cross_stroke(
                    INK_COLORS.get(s.ink_color_name, INK_COLORS["Black"]),
                    s.stroke_width,
                )
            )

        app.set_state(_mutate)

    def undo() -> None:
        """Remove the most recently added stroke."""

        def _mutate(s: SketchState) -> None:
            if s.strokes:
                s.strokes.pop()

        app.set_state(_mutate)

    def clear() -> None:
        """Remove all strokes from the canvas."""
        app.set_state(lambda s: setattr(s, "strokes", []))

    def on_color_select(event: SelectEvent) -> None:
        """Update the active ink color when the user picks a new one.

        Args:
            event: The selection event carrying the chosen color name.
        """
        app.set_state(lambda s: setattr(s, "ink_color_name", event.value))

    def on_width_select(event: SelectEvent) -> None:
        """Update the active stroke width when the user picks a new one.

        Args:
            event: The selection event carrying the chosen width string.
        """
        app.set_state(lambda s: setattr(s, "stroke_width", float(event.value)))

    # -- Derived values -----------------------------------------------------

    commands: list[DrawCommand] = _build_commands(state.strokes)
    stroke_count: int = len(state.strokes)

    color_dot_style = Style(
        background=Color(
            r=int(current_color[0] * 255),
            g=int(current_color[1] * 255),
            b=int(current_color[2] * 255),
        ),
        width=16.0,
        height=16.0,
        radius=8.0,
    )

    # -- Tree ---------------------------------------------------------------

    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            # -- Title row --
            Row(
                key="title-row",
                style=Style(
                    justify=JustifyContent.SPACE_BETWEEN,
                    align=AlignItems.CENTER,
                ),
                children=[
                    Text(
                        key="title",
                        content="Sketch Pad",
                        style=Style(
                            font_size=22.0,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Text(
                        key="stroke-count",
                        content=(
                            f"{stroke_count} stroke{'s' if stroke_count != 1 else ''}"
                        ),
                        style=Style(font_size=13.0, color=Color(r=120, g=120, b=120)),
                    ),
                ],
            ),
            # -- Toolbar --
            Row(
                key="toolbar",
                style=Style(
                    gap=8.0,
                    align=AlignItems.CENTER,
                ),
                children=[
                    Text(
                        key="color-label",
                        content="Ink:",
                        style=Style(font_size=14.0),
                    ),
                    Dropdown(
                        key="color-picker",
                        options=list(INK_COLORS.keys()),
                        value=state.ink_color_name,
                        on_select=on_color_select,
                    ),
                    # Visual swatch
                    Column(
                        key="color-dot",
                        style=color_dot_style,
                        children=[],
                    ),
                    Text(
                        key="width-label",
                        content="Width:",
                        style=Style(font_size=14.0),
                    ),
                    Dropdown(
                        key="width-picker",
                        options=[str(int(w)) for w in STROKE_WIDTHS],
                        value=str(int(state.stroke_width)),
                        on_select=on_width_select,
                    ),
                ],
            ),
            # -- Shape presets row --
            Row(
                key="presets",
                style=Style(gap=6.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        key="presets-label",
                        content="Add:",
                        style=Style(font_size=14.0),
                    ),
                    Button(
                        key="btn-diagonal",
                        label="Diagonal",
                        on_click=add_diagonal,
                    ),
                    Button(
                        key="btn-box",
                        label="Box",
                        on_click=add_box,
                    ),
                    Button(
                        key="btn-cross",
                        label="Cross",
                        on_click=add_cross,
                    ),
                ],
            ),
            # -- Canvas surface --
            Canvas(
                key="canvas",
                commands=commands,
                width=CANVAS_WIDTH,
                height=CANVAS_HEIGHT,
            ),
            # -- Footer actions --
            Row(
                key="footer",
                style=Style(gap=8.0, justify=JustifyContent.END),
                children=[
                    Button(
                        key="btn-undo",
                        label="Undo",
                        on_click=undo,
                    ),
                    Button(
                        key="btn-clear",
                        label="Clear",
                        on_click=clear,
                    ),
                ],
            ),
        ],
    )
