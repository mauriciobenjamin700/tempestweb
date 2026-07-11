# Sketch Pad — Canvas e Gestos 🎨

Construa um bloco de rascunho interativo que armazena traços como listas de comandos de desenho e aprenda a usar o widget **Canvas** do tempestweb.

---

## O que você vai construir

Um sketch pad com:

- 🖼 Superfície de desenho `Canvas` de 480 × 320 px
- 🔴 Seletor de **cor do traço** (Black, Red, Blue, Green) via `Dropdown`
- 📏 Seletor de **espessura** (1, 3, 6, 10 px) via `Dropdown`
- ➕ Três botões de **formas predefinidas**: Diagonal, Box (retângulo), Cross (×)
- ↩ Botão **Undo** que remove o último traço
- 🗑 Botão **Clear** que apaga tudo

!!! note "Nota — sem gestos ao vivo"
    Gestos de pan contínuo (arrastar o dedo) dependem de um renderer ao vivo. Este exemplo usa formas predefinidas para exercitar **toda** a API do Canvas de forma determinística — o código é idêntico nos dois modos de execução e passa em `ruff check / ruff format / mypy --strict / pytest` sem modificações.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leia antes (opcional, mas recomendado):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

```bash
mkdir -p examples/sketch-canvas
touch examples/sketch-canvas/app.py
```

---

## Passo 1 — Imports e constantes

Todo app tempestweb começa pelos imports. Além dos widgets comuns (`Button`, `Column`, `Row`, `Text`), este exemplo apresenta os widgets de Canvas:

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

Em seguida definimos as constantes que governam as dimensões e as paletas disponíveis:

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

!!! tip "Dica — cores como `[r, g, b, a]` float"
    O `Canvas` trabalha com valores de cor normalizados em `[0.0, 1.0]`. O `Style` usa `Color(r=int, g=int, b=int)` com inteiros em `[0, 255]`. Fique atento à conversão quando exibir um swatch de cor na toolbar (ver Passo 4).

---

## Passo 2 — O tipo `Stroke` e os draw commands

A ideia central do Canvas é simples: você passa uma **lista plana de `DrawCommand`**. Um traço completo segue sempre o mesmo padrão:

```
MoveTo(x, y) → LineTo(x, y) → LineTo(x, y) → … → StrokeCmd(color, width)
```

Criamos um dataclass `Stroke` para representar um traço ainda como pontos (mais fácil de manipular) e um método `to_commands()` que compila esses pontos em draw commands:

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

!!! info "Nota — `StrokeCmd` fecha o traço"
    `StrokeCmd` instrui o renderer a **aplicar o estilo e desenhar** o caminho acumulado. Sem ele, os `MoveTo`/`LineTo` anteriores ficam na fila sem aparecer na tela.

---

## Passo 3 — Estado e formas predefinidas

O estado do app é mínimo: uma lista de traços completos, o nome da cor ativa e a espessura ativa.

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

As três formas predefinidas são helpers puros — recebem cor e espessura e devolvem um `Stroke`:

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

Também precisamos do helper que **achata** todos os traços ativos em uma única lista de comandos para o `Canvas`:

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

!!! tip "Dica — um único diff para tudo"
    O reconciliador trata `Canvas.commands` como **um campo de valor**. Cada vez que um traço é adicionado ou removido, ele gera **um único patch `Update`** carregando a nova lista completa. Isso é mais eficiente do que criar um widget filho por traço.

---

## Passo 4 — Os handlers de evento

Dentro de `view()`, definimos os handlers. Cada um chama `app.set_state(mutador)`:

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

!!! note "Nota — `SelectEvent.value` é sempre `str`"
    O `Dropdown` retorna `event.value` como string. Por isso o handler de espessura converte com `float(event.value)` antes de salvar no estado.

---

## Passo 5 — Construindo a árvore de widgets

A UI tem quatro seções empilhadas em um `Column` raiz:

| Seção | Widgets |
|---|---|
| **Barra de título** | `Row` com `Text` (título) + `Text` (contagem de traços) |
| **Toolbar** | `Row` com `Dropdown` de cor, swatch visual, `Dropdown` de espessura |
| **Presets** | `Row` com três `Button` de formas |
| **Canvas** | Widget `Canvas` com os comandos compilados |
| **Rodapé** | `Row` com botões Undo e Clear |

```python
def view(app: App[SketchState]) -> Widget:
    """Render the sketch-pad UI from the current state."""
    state: SketchState = app.state
    current_color: list[float] = INK_COLORS.get(
        state.ink_color_name, INK_COLORS["Black"]
    )

    # ... (handlers definidos aqui — ver Passo 4)

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

!!! tip "Dica — swatch de cor como `Column` vazio"
    O pequeno círculo colorido ao lado do dropdown é um `Column` sem filhos com `width`, `height` e `radius` definidos no `Style`. É a forma mais simples de exibir um bloco de cor no tempestweb — sem widget especial.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

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
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
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

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/sketch-canvas
```

O Python roda **dentro do browser** via Pyodide. Sem servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/sketch-canvas
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Tela com um traço diagonal preto já desenhado (stroke seed do `make_state`)
    2. Toolbar com dropdowns "Ink" e "Width" e um swatch circular de cor
    3. Linha de presets: botões **Diagonal**, **Box**, **Cross**
    4. Superfície canvas de 480 × 320 px
    5. Botões **Undo** e **Clear** alinhados à direita
    6. Clique **Box** → retângulo aparece no canvas; contador muda para "2 strokes"
    7. Selecione **Red** no dropdown de cor → swatch fica vermelho
    8. Clique **Cross** → X vermelho aparece; contador "3 strokes"
    9. Clique **Undo** → último traço desaparece
    10. Clique **Clear** → canvas fica vazio; contador "0 strokes"

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes
pytest -q
```

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O pipeline de renderização do Canvas

```
app.set_state(mutador)
      │
      ▼
novo estado com lista de Stroke atualizada
      │
      ▼
view(app) chamada novamente
      │
      ▼
_build_commands(state.strokes)
   → cada Stroke.to_commands() → [MoveTo, LineTo…, StrokeCmd]
   → lista plana concatenada
      │
      ▼
Canvas(commands=[...])
      │
      ▼
reconciliador: Update em commands (um único patch)
      │
      ▼
cliente JS redesenha o <canvas> com os novos comandos
```

### Por que armazenar pontos e não comandos diretamente?

Guardamos `Stroke(points=[...], color=[...], width=...)` em vez de `list[DrawCommand]` no estado por duas razões:

1. **Manipulação** — remover o último traço (`pop()`) funciona em nível de stroke inteiro, não em nível de comando individual.
2. **Rederivação** — ao trocar cor ou espessura, você poderia re-compilar o último traço com os novos valores sem retocar os anteriores.

`to_commands()` é chamado apenas dentro de `view()`, mantendo o estado **livre de artefatos de renderização**.

### O swatch de cor — `Column` como bloco de cor

```python
color_dot_style = Style(
    background=Color(
        r=int(current_color[0] * 255),  # converte [0,1] → [0,255]
        g=int(current_color[1] * 255),
        b=int(current_color[2] * 255),
    ),
    width=16.0,
    height=16.0,
    radius=8.0,  # torna quadrado → círculo
)
Column(key="color-dot", style=color_dot_style, children=[])
```

Um `Column` sem filhos com dimensões fixas e `radius` igual à metade da largura se transforma em um círculo de cor — o widget mais simples para um swatch visual.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Usar o widget **`Canvas`** com uma lista plana de `DrawCommand`
- ✅ O padrão **`MoveTo` → `LineTo`… → `StrokeCmd`** para traçar caminhos
- ✅ Separar o **domínio** (`Stroke` com pontos) da **renderização** (`to_commands()`)
- ✅ Usar `Dropdown` + `SelectEvent` para seleção de cor e espessura
- ✅ Implementar **Undo** com `list.pop()` e **Clear** com `setattr`
- ✅ Exibir um **swatch de cor** usando um `Column` vazio com estilo de fundo

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um **seletor de opacidade** com um terceiro `Dropdown` e use o canal `a` do `StrokeCmd`
- 💡 Salve traços no `localStorage` via [capacidades nativas](../capabilities.md) do Modo A
- 💡 Explore o exemplo [Image Gallery](./image-gallery.md) para ver outro uso de superfícies gráficas
- 💡 Leia o [contrato wire](../wire-contract.md) para entender como os `DrawCommand` são serializados como JSON e enviados ao cliente
