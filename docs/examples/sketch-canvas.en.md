# Sketch Pad — Canvas & Gestures 🎨

Build an interactive drawing pad that stores strokes as draw-command lists and learn how to use tempestweb's **Canvas** widget.

---

## What you'll build

A sketch pad with:

- 🖼 A `Canvas` drawing surface 480 × 320 px
- 🔴 A **stroke color** selector (Black, Red, Blue, Green) via `Dropdown`
- 📏 A **stroke width** selector (1, 3, 6, 10 px) via `Dropdown`
- ➕ Three **preset shape** buttons: Diagonal, Box (rectangle), Cross (×)
- ↩ An **Undo** button that removes the last stroke
- 🗑 A **Clear** button that wipes everything

!!! note "Note — no live gestures"
    Continuous pan gestures (drag-to-draw) require a live renderer. This example uses preset shapes to exercise the **full Canvas API** deterministically — the code is identical in both execution modes and passes `ruff check / ruff format / mypy --strict / pytest` unchanged.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading before you start:

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

```bash
mkdir -p examples/sketch-canvas
touch examples/sketch-canvas/app.py
```

---

## Step 1 — Imports and constants

Every tempestweb app starts with imports. Besides the common widgets (`Button`, `Column`, `Row`, `Text`), this example introduces the Canvas-specific widgets:

```python
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
```

Next, define the constants that govern dimensions and available palettes:

```python
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
```

!!! tip "Tip — colors as `[r, g, b, a]` floats"
    `Canvas` works with normalized color values in `[0.0, 1.0]`. `Style` uses `Color(r=int, g=int, b=int)` with integers in `[0, 255]`. Watch out for the conversion when displaying a color swatch in the toolbar (see Step 4).

---

## Step 2 — The `Stroke` type and draw commands

The core idea behind the Canvas is simple: you pass a **flat list of `DrawCommand`**. A complete stroke always follows the same pattern:

```
MoveTo(x, y) → LineTo(x, y) → LineTo(x, y) → … → StrokeCmd(color, width)
```

We create a `Stroke` dataclass to represent a stroke as a list of points (easier to manipulate) and a `to_commands()` method that compiles those points into draw commands:

```python
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
```

!!! info "Note — `StrokeCmd` closes the stroke"
    `StrokeCmd` tells the renderer to **apply the style and draw** the accumulated path. Without it, the preceding `MoveTo`/`LineTo` commands sit in the queue and nothing appears on screen.

---

## Step 3 — State and preset shapes

The app state is minimal: a list of completed strokes, the active color name, and the active width.

```python
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
```

The three preset shapes are pure helpers — they receive color and width and return a `Stroke`:

```python
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
```

We also need the helper that **flattens** all active strokes into a single command list for `Canvas`:

```python
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
```

!!! tip "Tip — a single diff for everything"
    The reconciler treats `Canvas.commands` as **one value field**. Each time a stroke is added or removed, it emits **a single `Update` patch** carrying the complete new list. This is more efficient than creating one child widget per stroke.

---

## Step 4 — Event handlers

Inside `view()`, we define the handlers. Each one calls `app.set_state(mutator)`:

```python
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
```

!!! note "Note — `SelectEvent.value` is always a `str`"
    `Dropdown` returns `event.value` as a string. That is why the width handler converts with `float(event.value)` before saving to state.

---

## Step 5 — Building the widget tree

The UI has four sections stacked in a root `Column`:

| Section | Widgets |
|---|---|
| **Title bar** | `Row` with `Text` (title) + `Text` (stroke count) |
| **Toolbar** | `Row` with color `Dropdown`, visual swatch, width `Dropdown` |
| **Presets** | `Row` with three shape `Button`s |
| **Canvas** | `Canvas` widget with compiled commands |
| **Footer** | `Row` with Undo and Clear buttons |

```python
def view(app: App[SketchState]) -> Widget:
    """Render the sketch-pad UI from the current state."""
    state: SketchState = app.state
    current_color: list[float] = INK_COLORS.get(
        state.ink_color_name, INK_COLORS["Black"]
    )

    # ... (handlers defined here — see Step 4)

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

    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
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
            Row(
                key="toolbar",
                style=Style(gap=8.0, align=AlignItems.CENTER),
                children=[
                    Text(key="color-label", content="Ink:", style=Style(font_size=14.0)),
                    Dropdown(
                        key="color-picker",
                        options=list(INK_COLORS.keys()),
                        value=state.ink_color_name,
                        on_select=on_color_select,
                    ),
                    Column(key="color-dot", style=color_dot_style, children=[]),
                    Text(key="width-label", content="Width:", style=Style(font_size=14.0)),
                    Dropdown(
                        key="width-picker",
                        options=[str(int(w)) for w in STROKE_WIDTHS],
                        value=str(int(state.stroke_width)),
                        on_select=on_width_select,
                    ),
                ],
            ),
            Row(
                key="presets",
                style=Style(gap=6.0, align=AlignItems.CENTER),
                children=[
                    Text(key="presets-label", content="Add:", style=Style(font_size=14.0)),
                    Button(key="btn-diagonal", label="Diagonal", on_click=add_diagonal),
                    Button(key="btn-box", label="Box", on_click=add_box),
                    Button(key="btn-cross", label="Cross", on_click=add_cross),
                ],
            ),
            Canvas(
                key="canvas",
                commands=commands,
                width=CANVAS_WIDTH,
                height=CANVAS_HEIGHT,
            ),
            Row(
                key="footer",
                style=Style(gap=8.0, justify=JustifyContent.END),
                children=[
                    Button(key="btn-undo", label="Undo", on_click=undo),
                    Button(key="btn-clear", label="Clear", on_click=clear),
                ],
            ),
        ],
    )
```

!!! tip "Tip — color swatch as an empty `Column`"
    The small circle next to the dropdown is a `Column` with no children, with `width`, `height`, and `radius` set in `Style`. It is the simplest way to display a solid color block in tempestweb — no special widget needed.

---

## The complete app

Here is the full file, ready to copy:

```python
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
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/sketch-canvas
```

Python runs **inside the browser** via Pyodide. No server required.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/sketch-canvas
```

Python runs on the server; the browser receives JSON patches over the WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode, you should see:

    1. A canvas with one black diagonal stroke already drawn (the seed from `make_state`)
    2. A toolbar with "Ink" and "Width" dropdowns and a circular color swatch
    3. A preset row: **Diagonal**, **Box**, **Cross** buttons
    4. A 480 × 320 px canvas surface
    5. **Undo** and **Clear** buttons right-aligned in the footer
    6. Click **Box** → a rectangle appears on the canvas; the counter changes to "2 strokes"
    7. Select **Red** in the color dropdown → the swatch turns red
    8. Click **Cross** → a red × appears; counter shows "3 strokes"
    9. Click **Undo** → the last stroke disappears
    10. Click **Clear** → the canvas is empty; counter shows "0 strokes"

---

## Automated verification ✅

Run the four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All should pass green. The example was specifically designed to be `mypy --strict` clean — every variable and return value is explicitly annotated.

---

## How it works under the hood

### The Canvas rendering pipeline

```
app.set_state(mutator)
      │
      ▼
new state with updated list of Stroke objects
      │
      ▼
view(app) called again
      │
      ▼
_build_commands(state.strokes)
   → each Stroke.to_commands() → [MoveTo, LineTo…, StrokeCmd]
   → flat concatenated list
      │
      ▼
Canvas(commands=[...])
      │
      ▼
reconciler: Update on commands (a single patch)
      │
      ▼
JS client redraws the <canvas> with the new commands
```

### Why store points rather than commands directly?

We store `Stroke(points=[...], color=[...], width=...)` in state rather than `list[DrawCommand]` for two reasons:

1. **Manipulation** — removing the last stroke (`pop()`) works at the whole-stroke level, not command by command.
2. **Re-derivation** — if you change color or width, you could recompile only the latest stroke with the new values without touching the earlier ones.

`to_commands()` is only called inside `view()`, keeping the state **free of rendering artifacts**.

### The color swatch — `Column` as a color block

```python
color_dot_style = Style(
    background=Color(
        r=int(current_color[0] * 255),  # convert [0,1] → [0,255]
        g=int(current_color[1] * 255),
        b=int(current_color[2] * 255),
    ),
    width=16.0,
    height=16.0,
    radius=8.0,  # turns square → circle
)
Column(key="color-dot", style=color_dot_style, children=[])
```

A `Column` with no children, fixed dimensions, and `radius` equal to half the width becomes a colored circle — the simplest possible swatch widget.

---

## Recap

In this tutorial you learned:

- ✅ How to use the **`Canvas`** widget with a flat `DrawCommand` list
- ✅ The **`MoveTo` → `LineTo`… → `StrokeCmd`** pattern for drawing paths
- ✅ How to separate the **domain** (`Stroke` with points) from the **rendering** (`to_commands()`)
- ✅ How to use `Dropdown` + `SelectEvent` for color and width selection
- ✅ How to implement **Undo** with `list.pop()` and **Clear** with `setattr`
- ✅ How to display a **color swatch** using an empty `Column` with a background style

---

## Next steps

Try extending the example:

- 💡 Add an **opacity selector** with a third `Dropdown` and use the `a` channel of `StrokeCmd`
- 💡 Persist strokes to `localStorage` via [native capabilities](../capabilities.md) in Mode A
- 💡 Explore the [Image Gallery](./image-gallery.md) example for another use of graphic surfaces
- 💡 Read the [wire contract](../wire-contract.md) to understand how `DrawCommand` objects are serialized as JSON and sent to the client
